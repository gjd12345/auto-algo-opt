"""
模块：train_rerank_sft（小型重排模型 SFT 微调器）
功能：用一批「LLM 重排轨迹」样本，对小型语言模型（如 Qwen2-0.5B / 1.5B）做监督微调（SFT），
      训练出一个能给候选卡片打分排序（rerank）的小模型。
职责：
  - 读取并清洗 JSONL 训练样本（每条含 system / user / assistant 三段对话）；
  - 把对话拼成聊天模板文本，并对提示部分做 loss 掩码（只在助手回复上算损失）；
  - 加载基座模型、挂上 LoRA 适配器，用 HuggingFace Trainer 跑训练；
  - 保存 LoRA 适配器、分词器以及一份可复现的训练清单（manifest）。
接口：
  - load_examples(path) -> list[dict]：从 JSONL 读取并过滤训练样本。
  - format_chat(example, tokenizer) -> dict：构造 prompt/full 两段文本。
  - make_tokenized_dataset(examples, tokenizer, max_length, libs)：生成已分词、已掩码的数据集。
  - main()：命令行入口，串起加载数据、建模、训练、保存的完整流程。
输入：
  - --train-data 指向的 JSONL 训练文件（默认 eoh_rag_workspace/training/rerank_sft_data.jsonl）；
  - --base-model 指定的 HuggingFace 基座模型；
  - 其余训练超参数（轮数、批大小、学习率、LoRA 秩等）均来自命令行参数。
输出：
  - 一个 LoRA 适配器目录，可用 PeftModel.from_pretrained(...) 加载；
  - 同目录下的分词器文件与 training_manifest.json。
示例（单卡）：
    pip install transformers accelerate peft bitsandbytes datasets ftfy

    python -m eoh_rag.experiments.training.train_rerank_sft \\
        --base-model Qwen/Qwen2.5-0.5B-Instruct \\
        --train-data eoh_rag_workspace/training/rerank_sft_data.jsonl \\
        --output-dir eoh_rag_workspace/training/checkpoints/qwen2_0_5b_lora \\
        --num-epochs 3 --per-device-batch 2 --grad-accum 4

说明：
  - 采用「生成式 SFT」的思路来训练重排：数据是 JSON 风格的候选卡片选择，
    因此目标更接近文本生成，而不是 listwise 打乱式排序。
  - 默认启用 LoRA，使 0.5B 规模的模型能在单张消费级 GPU 上完成训练。
  - 训练时复用推理阶段所用的重排提示模板，尽量保证「训练分布」与「服务分布」一致。
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _import_training_libs():
    """延迟导入重型训练依赖（torch/datasets/peft/transformers）。

    这样即使在没有安装这些库的机器上，本文件也能被正常 import（例如只用到常量或做静态检查）。
    真正需要训练时才在此处集中导入，并以字典形式返回所需的类与模块。
    """
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
    """从 JSONL 文件逐行读取训练样本，并做基本清洗。

    每行是一个 JSON 对象，核心字段为 conversations（一个对话列表，依次是 system / user / assistant）。
    仅保留「至少含三段对话、且助手回复非空」的样本，缺少助手答案的样本会被丢弃。
    返回：合格样本组成的列表。
    """
    examples = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:  # 跳过空行
                continue
            ex = json.loads(line)
            # 防御性过滤：丢弃缺少助手回复的样本
            conv = ex.get("conversations", [])
            if len(conv) >= 3 and conv[-1].get("value"):
                examples.append(ex)
    return examples


def format_chat(example: dict, tokenizer) -> dict:
    """把一条样本拼成聊天模板文本，供后续分词与 loss 掩码使用。

    从样本中取出 system / user / assistant 三段内容，按分词器的聊天模板拼接：
      - prompt：仅含系统提示与用户输入，并追加「生成起始标记」，作为需要掩码的提示部分；
      - full：在 prompt 之后接上助手回复与结束符（eos），作为完整的训练目标序列。
    若分词器模板不支持独立的 system 角色，则把系统提示并入用户消息一起发送。
    返回：{"prompt": <提示文本>, "full": <完整文本>}。
    """
    conv = example["conversations"]
    sys_msg = conv[0]["value"]
    user_msg = conv[1]["value"]
    assistant_msg = conv[2]["value"]

    # 依据聊天模板是否支持 system 角色，决定系统提示的放置方式
    if "system" in (tokenizer.chat_template or ""):
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ]
    else:
        # 模板不含 system 角色时，把系统提示拼进用户消息
        messages = [{"role": "user", "content": sys_msg + "\n" + user_msg}]

    # 生成到「助手该开口」为止的提示文本（不含助手回复）
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    # 完整序列 = 提示 + 助手回复 + 结束符，供模型学习「在提示之后生成该回复」
    full = prompt + assistant_msg + (tokenizer.eos_token or "")
    return {"prompt": prompt, "full": full}


def make_tokenized_dataset(examples, tokenizer, max_length: int, libs):
    """把样本列表转成已分词、已做 loss 掩码的 HuggingFace Dataset。

    对每条样本：分别对 full 与 prompt 分词，labels 复制自 full 的 token；
    再把 labels 中「属于提示部分」的位置置为 -100，使损失只在助手回复上计算。
    max_length 用于截断过长序列。返回：一个可直接喂给 Trainer 的 Dataset。
    """
    Dataset = libs["Dataset"]

    # 先把每条样本转为 {"prompt", "full"} 文本
    formatted = [format_chat(ex, tokenizer) for ex in examples]

    def gen():
        # 惰性生成每条已分词样本，避免一次性占用过多内存
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
            # 将提示部分的 token 标为 -100，交叉熵会忽略这些位置，只学习助手回复
            for i in range(min(len(prompt_ids), len(labels))):
                labels[i] = -100  # mask prompt（掩码提示词）
            yield {
                "input_ids": full_ids,
                "attention_mask": [1] * len(full_ids),
                "labels": labels,
            }

    return Dataset.from_generator(gen)


def main():
    """命令行入口：解析参数并执行完整的 LoRA 微调流程。

    步骤概览：解析超参 → 校验并加载训练数据 → 载入基座模型与分词器 → 挂载 LoRA 适配器
    → 构造已掩码的数据集 → 用 Trainer 训练 → 保存适配器、分词器与训练清单。
    """
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

    # 延迟导入重型训练依赖，拿到 torch 等对象
    libs = _import_training_libs()
    torch = libs["torch"]

    # 校验训练数据路径并加载样本，缺失或为空则直接报错
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
    # 部分模型没有 pad token，用 eos 兜底以支持批内填充
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 根据 bf16/fp16 开关选择计算精度
    dtype = torch.bfloat16 if args.bf16 and not args.fp16 else torch.float16
    model = libs["AutoModelForCausalLM"].from_pretrained(
        args.base_model,
        torch_dtype=dtype,
        trust_remote_code=True,
        device_map="auto",
    )
    # 开启梯度检查点，用少量额外计算换取更低的显存占用
    model.gradient_checkpointing_enable()

    # 配置 LoRA：只在指定的注意力投影层上插入低秩适配器
    lora_config = libs["LoraConfig"](
        task_type=libs["TaskType"].CAUSAL_LM,
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        target_modules=args.target_modules.split(","),
    )
    model = libs["get_peft_model"](model, lora_config)
    model.print_trainable_parameters()  # 打印可训练参数量，确认 LoRA 生效

    dataset = make_tokenized_dataset(examples, tokenizer, args.max_length, libs)

    def collate_fn(batch):
        """把一个批次的变长样本右侧填充到统一长度，并转成张量。

        input_ids 用 pad_token 填充、attention_mask 用 0 填充、labels 用 -100 填充
        （填充位置不参与损失计算）。返回：含 input_ids/attention_mask/labels 的张量字典。
        """
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
    trainer.save_model(args.output_dir)  # 保存 LoRA 适配器权重
    tokenizer.save_pretrained(args.output_dir)  # 一并保存分词器，便于推理时直接加载

    # 写出训练清单，记录关键配置以便复现
    manifest = {
        "base_model": args.base_model,
        "train_data": str(train_path.resolve()),
        "num_examples": len(examples),
        "epochs": args.num_epochs,
        # 有效批大小 = 单卡批大小 × 梯度累积步数
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
