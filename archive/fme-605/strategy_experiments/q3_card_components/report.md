# Q3 胜出卡组件归因实验

结论：`supports_pair_complementarity`。双卡 answer 的优势不能由任一单卡单独解释。

| arm | valid | valid rate | first-attempt success | median valid 5k gap |
|---|---:|---:|---:|---:|
| harmonic_only | 9/10 | 90.0% | 7 | 4.0770 |
| residual_poly_only | 3/10 | 30.0% | 3 | 4.0770 |

| comparison | paired valid | win | tie | loss |
|---|---:|---:|---:|---:|
| answer vs harmonic_only | 9 | 7 | 1 | 1 |
| harmonic_only vs pure | 9 | 2 | 2 | 5 |
| answer vs residual_poly_only | 3 | 3 | 0 | 0 |
| residual_poly_only vs pure | 3 | 0 | 1 | 2 |

失败坐标均保留为 `failed_after_retries`，不通过额外补抽把失败洗成成功。
双卡组合优于任一单卡，但单卡实验同时改变了上下文长度和选择空间；因此结论是互补或上下文交互得到支持，而不是已证明严格加性协同。
已导出 2 份单卡臂最佳有效代码。
