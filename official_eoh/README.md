# official_eoh — vendored EoH evaluation engine

主线三个问题（`bp_online` / `tsp_construct` / `cvrp_construct`）的进化与评测引擎，
内置自上游 **Evolution of Heuristics (EoH)**，让本仓可以**自包含复现**主线实验，
无需再依赖任何外部 EoH 安装。

- **上游**：https://github.com/FeiLiu36/EoH （MIT License，见 `LICENSE`）
- **引用**：Fei Liu, Xialiang Tong, Mingxuan Yuan, Xi Lin, Fu Luo, Zhenkun Wang,
  Zhichao Lu, Qingfu Zhang. *Evolution of Heuristics: Towards Efficient Automatic
  Algorithm Design Using Large Language Model.* ICML 2024.

## 内容（精简）
- `eoh/` —— EoH 引擎（`eoh/src/eoh`）。
- `examples/{bp_online,tsp_construct,cvrp_construct}/` —— 每个问题的评测器
  `prob.py`（`BPONLINE`/`TSPCONST`/`CVRPCONST`，暴露 `evaluate_program`）与实例
  生成器 `get_instance.py`。
- 未收录上游的其余示例、训练/测试数据集、结果目录：三题的评测实例都由
  `get_instance.py` 用固定随机种子（`np.random.seed(2024)`）在运行时生成，或直接内嵌，
  **无需任何数据文件**。

## 依赖 & 运行
- Python **3.10+**（引擎使用 `X | None` 类型标注）；`numpy`、`joblib`、`requests`。
- 主线运行器默认已把 `official_root` 指向本目录；也可用 `EOH_OFFICIAL_ROOT` 覆盖。

## 复现基线（已验证，与 `evidence/` 一致）
| 问题 | 最优目标 |
| --- | --- |
| `bp_online` | 0.006741 |
| `tsp_construct` | 6.003926 |
| `cvrp_construct` | 12.356387 |
