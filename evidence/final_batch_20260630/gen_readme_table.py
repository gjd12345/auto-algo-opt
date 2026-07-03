"""从 batch_status.json 生成 README 结果表。

batch_status.json 是本批次实验数值的唯一权威来源;README 表格里的
`Improvement (best)`、`>5% Rate` 等列都应由本脚本生成,而不是手工维护,
以免数值随手改而与权威数据漂移。

用法(在本目录下运行):
    python gen_readme_table.py
把输出的 Markdown 表粘贴回 README.md 的结果表即可。
"""

import json
from pathlib import Path

# 表格按问题展示的固定顺序(与 README 一致)
PROBLEM_ORDER = ["bp_online", "tsp_construct", "cvrp_construct"]

# 各问题最优目标值的展示精度(仅影响表格显示,不改动权威数据)
BEST_DECIMALS = {"bp_online": 5, "tsp_construct": 3, "cvrp_construct": 3}


def render_table(status: dict) -> str:
    """把 batch_status.json 的内容渲染成 Markdown 结果表。"""
    problems = status["problems"]
    lines = [
        "| Problem | Runs | Best | Improvement (best) | >5% Rate |",
        "|---------|------|------|--------------------|----------|",
    ]
    for name in PROBLEM_ORDER:
        info = problems[name]
        best = round(info["best"], BEST_DECIMALS.get(name, 5))
        improvement = info["improvement_best"] * 100
        rate = info["above_5pct_rate"] * 100
        lines.append(
            f"| {name} | {info['runs']} | {best} | +{improvement:.1f}% | {rate:.1f}% |"
        )
    return "\n".join(lines)


def main() -> None:
    status_path = Path(__file__).resolve().parent / "batch_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    print(f"总运行数:{status['total_runs']}")
    print(render_table(status))


if __name__ == "__main__":
    main()
