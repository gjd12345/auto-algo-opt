"""SFT fine-tune a small reranker model (Qwen2-0.5B / 1.5B) on extracted
LLM rerank traces, adapted from castorini/rank_llm training pipeline.

Why a separate trainer instead of using rank_llm directly:

- rank_llm's `train_rankllm.py` expects HuggingFace listwise datasets with
  passage shuffling and label-letter encoding. Our data is JSON-style
  card selection — closer to `objective="generation"` SFT.
- We want LoRA by default (0.5B fits on one consumer GPU).
- We want to drop in the same `_RERANK_PROMPT_V1` we used at inference,
  guaranteeing train/serve distribution match.

Usage (single GPU):
    pip install transformers accelerate peft bitsandbytes datasets ftfy

    python -m eoh_rag.experiments.training.train_rerank_sft \\
        --base-model Qwen/Qwen2.5-0.5B-Instruct \\
        --train-data eoh_rag_workspace/training/rerank_sft_data.jsonl \\
        --output-dir eoh_rag_workspace/training/checkpoints/qwen2_0_5b_lora \\
        --num-epochs 3 --per-device-batch 2 --grad-accum 4

Output:
    LoRA adapter dir loadable with PeftModel.from_pretrained(...).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _import_training_libs():
    """Lazy import so the file is importable on machines without these deps."""
    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    return {
        "torch": torch,
        "Dataset": Dataset,
        "LoraConfig": LoraConfig,
        "TaskType": TaskType,
        "get_peft_model": get_peft_model,
        "AutoModelForCausalLM": AutoModelForCausalLM,
        "AutoTokenizer": AutoTokenizer,
        "DataCollatorForLanguageModeling": DataCollatorForLanguageModeling,
        "Trainer": Trainer,
        "TrainingArguments": TrainingArguments,
    }


def load_examples(path: Path) -> list[dict]:
    examples = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ex = json.loads(line)
            # Defensive: drop examples without an assistant response
            conv = ex.get("conversations", [])
            if len(conv) >= 3 and conv[-1].get("value"):
                examples.append(ex)
    return examples


def format_chat(example: dict, tokenizer) -> dict:
    """Build prompt/response strings; mask prompt tokens during loss."""
    conv = example["conversations"]
    sys_msg = conv[0]["value"]
    user_msg = conv[1]["value"]
    assistant_msg = conv[2]["value"]

    if "system" in (tokenizer.chat_template or ""):
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ]
    else:
        messages = [{"role": "user", "content": sys_msg + "\n" + user_msg}]

    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    full = prompt + assistant_msg + (tokenizer.eos_token or "")
    return {"prompt": prompt, "full": full}


def make_tokenized_dataset(examples, tokenizer, max_length: int, libs):
    Dataset = libs["Dataset"]

    formatted = [format_chat(ex, tokenizer) for ex in examples]

    def gen():
        for f in formatted:
            full_ids = tokenizer(
                f["full"],
                truncation=True,
                max_length=max_length,
                add_special_tokens=False,
            )["input_ids"]
            prompt_ids = tokenizer(
                f["prompt"],
                truncation=True,
                max_length=max_length,
                add_special_tokens=False,
            )["input_ids"]
            labels = list(full_ids)
            for i in range(min(len(prompt_ids), len(labels))):
                labels[i] = -100  # mask prompt
            yield {
                "input_ids": full_ids,
                "attention_mask": [1] * len(full_ids),
                "labels": labels,
            }

    return Dataset.from_generator(gen)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument(
        "--train-data",
        default="eoh_rag_workspace/training/rerank_sft_data.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        default="eoh_rag_workspace/training/checkpoints/qwen2_0_5b_lora",
    )
    parser.add_argument("--num-epochs", type=int, default=3)
    parser.add_argument("--per-device-batch", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--bf16", action="store_true", default=True)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument(
        "--target-modules",
        default="q_proj,k_proj,v_proj,o_proj",
        help="Comma-separated LoRA target modules (Qwen2 attention projections)",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    libs = _import_training_libs()
    torch = libs["torch"]

    train_path = Path(args.train_data)
    if not train_path.exists():
        raise FileNotFoundError(f"Training data not found: {train_path}")
    examples = load_examples(train_path)
    if not examples:
        raise ValueError(f"No training examples found in {train_path}")
    print(f"Loaded {len(examples)} training examples from {train_path}")

    tokenizer = libs["AutoTokenizer"].from_pretrained(
        args.base_model, trust_remote_code=True, use_fast=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = torch.bfloat16 if args.bf16 and not args.fp16 else torch.float16
    model = libs["AutoModelForCausalLM"].from_pretrained(
        args.base_model,
        torch_dtype=dtype,
        trust_remote_code=True,
        device_map="auto",
    )
    model.gradient_checkpointing_enable()

    lora_config = libs["LoraConfig"](
        task_type=libs["TaskType"].CAUSAL_LM,
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        target_modules=args.target_modules.split(","),
    )
    model = libs["get_peft_model"](model, lora_config)
    model.print_trainable_parameters()

    dataset = make_tokenized_dataset(examples, tokenizer, args.max_length, libs)

    def collate_fn(batch):
        max_len = max(len(b["input_ids"]) for b in batch)
        pad_id = tokenizer.pad_token_id
        input_ids, attention_mask, labels = [], [], []
        for b in batch:
            ids = b["input_ids"] + [pad_id] * (max_len - len(b["input_ids"]))
            mask = b["attention_mask"] + [0] * (max_len - len(b["attention_mask"]))
            lab = b["labels"] + [-100] * (max_len - len(b["labels"]))
            input_ids.append(ids)
            attention_mask.append(mask)
            labels.append(lab)
        return {
            "input_ids": torch.tensor(input_ids),
            "attention_mask": torch.tensor(attention_mask),
            "labels": torch.tensor(labels),
        }

    training_args = libs["TrainingArguments"](
        output_dir=args.output_dir,
        num_train_epochs=args.num_epochs,
        per_device_train_batch_size=args.per_device_batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.learning_rate,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        bf16=args.bf16 and not args.fp16,
        fp16=args.fp16,
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=2,
        report_to=[],  # disable wandb by default
        seed=args.seed,
        gradient_checkpointing=True,
    )

    trainer = libs["Trainer"](
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collate_fn,
    )

    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    # Write training manifest for reproducibility
    manifest = {
        "base_model": args.base_model,
        "train_data": str(train_path.resolve()),
        "num_examples": len(examples),
        "epochs": args.num_epochs,
        "effective_batch_size": args.per_device_batch * args.grad_accum,
        "lora_rank": args.lora_rank,
        "lora_alpha": args.lora_alpha,
        "target_modules": args.target_modules.split(","),
        "max_length": args.max_length,
    }
    (Path(args.output_dir) / "training_manifest.json").write_text(
        json.dumps(manifest, indent=2)
    )
    print(f"Saved LoRA adapter to {args.output_dir}")


if __name__ == "__main__":
    main()
