# M5 CVRP trajectory control

Arm means weight each available seed equally. Exact-k uses the nearest-neighbor fleet target on blind instances.

| Arm | Evaluated seeds | Penalized objective | Completed | Exact-k completed | Requests | Valid candidates | USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| legacy_baseline_500ms | 5 | 24.6404 | 1.0000 | 0.5833 | 100.0000 | 34.6000 | 0.2739 |
| whitelist_latency_500ms | 5 | 24.6472 | 1.0000 | 0.6500 | 100.0000 | 29.0000 | 0.3190 |
| trajectory_ctrl_full_500ms | 5 | 24.6979 | 1.0000 | 0.5817 | 100.0000 | 20.4000 | 0.2684 |
| model2_legacy_500ms | 3 | 24.6097 | 1.0000 | 0.6389 | 100.0000 | 37.6667 | 0.6628 |
| model2_ctrl_full_500ms | 3 | 27.2350 | 0.9444 | 0.6389 | 100.0000 | 29.6667 | 0.7943 |

## Paired blind results by seed

| Contrast | Seed | Bootstrap gain (%) | Holm-adjusted p | Common completed |
| --- | ---: | ---: | ---: | ---: |
| whitelist_latency_500ms vs legacy_baseline_500ms | 20261124 | -0.3600 | 0.0003 | 120 |
| whitelist_latency_500ms vs legacy_baseline_500ms | 20261125 | 0.1292 | 0.2250 | 120 |
| whitelist_latency_500ms vs legacy_baseline_500ms | 20261126 | -0.8859 | 0.0000 | 120 |
| whitelist_latency_500ms vs legacy_baseline_500ms | 20261127 | 0.9030 | 0.0000 | 120 |
| whitelist_latency_500ms vs legacy_baseline_500ms | 20261128 | 0.0703 | 0.9878 | 120 |
| trajectory_ctrl_full_500ms vs whitelist_latency_500ms | 20261124 | -0.0255 | 0.5410 | 120 |
| trajectory_ctrl_full_500ms vs whitelist_latency_500ms | 20261125 | -0.5823 | 0.0000 | 120 |
| trajectory_ctrl_full_500ms vs whitelist_latency_500ms | 20261126 | 0.4944 | 0.0004 | 120 |
| trajectory_ctrl_full_500ms vs whitelist_latency_500ms | 20261127 | -0.6268 | 0.0000 | 120 |
| trajectory_ctrl_full_500ms vs whitelist_latency_500ms | 20261128 | -0.2972 | 0.1035 | 120 |
| trajectory_ctrl_full_500ms vs legacy_baseline_500ms | 20261124 | -0.3856 | 0.0051 | 120 |
| trajectory_ctrl_full_500ms vs legacy_baseline_500ms | 20261125 | -0.4524 | 0.0028 | 120 |
| trajectory_ctrl_full_500ms vs legacy_baseline_500ms | 20261126 | -0.3872 | 0.0019 | 120 |
| trajectory_ctrl_full_500ms vs legacy_baseline_500ms | 20261127 | 0.2818 | 0.0056 | 120 |
| trajectory_ctrl_full_500ms vs legacy_baseline_500ms | 20261128 | -0.2267 | 0.1301 | 120 |
| model2_ctrl_full_500ms vs model2_legacy_500ms | 20261124 | -1.0340 | 0.0000 | 119 |
| model2_ctrl_full_500ms vs model2_legacy_500ms | 20261125 | 0.3048 | 0.0926 | 120 |
| model2_ctrl_full_500ms vs model2_legacy_500ms | 20261126 | -31.2758 | 0.4393 | 101 |
| legacy_baseline_500ms vs l3_ctrl@500ms | 20261124 | 13.4920 | 1.0000 | 111 |
| legacy_baseline_500ms vs l3_ctrl@500ms | 20261125 | 13.5042 | 1.0000 | 111 |
| legacy_baseline_500ms vs l3_ctrl@500ms | 20261126 | 13.3764 | 1.0000 | 111 |
| legacy_baseline_500ms vs l3_ctrl@500ms | 20261127 | 12.9322 | 0.0086 | 111 |
| legacy_baseline_500ms vs l3_ctrl@500ms | 20261128 | 13.5900 | 1.0000 | 111 |
| legacy_baseline_500ms vs m32_champion_pruned@500ms | 20261124 | 24.9404 | 0.2715 | 100 |
| legacy_baseline_500ms vs m32_champion_pruned@500ms | 20261125 | 24.9510 | 0.2445 | 100 |
| legacy_baseline_500ms vs m32_champion_pruned@500ms | 20261126 | 24.8401 | 0.1404 | 100 |
| legacy_baseline_500ms vs m32_champion_pruned@500ms | 20261127 | 24.4547 | 0.0147 | 100 |
| legacy_baseline_500ms vs m32_champion_pruned@500ms | 20261128 | 25.0255 | 0.1855 | 100 |
| whitelist_latency_500ms vs l3_ctrl@500ms | 20261124 | 13.1805 | 0.2445 | 111 |
| whitelist_latency_500ms vs l3_ctrl@500ms | 20261125 | 13.6159 | 0.9317 | 111 |
| whitelist_latency_500ms vs l3_ctrl@500ms | 20261126 | 12.6090 | 0.0006 | 111 |
| whitelist_latency_500ms vs l3_ctrl@500ms | 20261127 | 13.7185 | 0.6663 | 111 |
| whitelist_latency_500ms vs l3_ctrl@500ms | 20261128 | 13.6508 | 1.0000 | 111 |
| whitelist_latency_500ms vs m32_champion_pruned@500ms | 20261124 | 24.6702 | 0.0230 | 100 |
| whitelist_latency_500ms vs m32_champion_pruned@500ms | 20261125 | 25.0479 | 0.2445 | 100 |
| whitelist_latency_500ms vs m32_champion_pruned@500ms | 20261126 | 24.1743 | 0.0147 | 100 |
| whitelist_latency_500ms vs m32_champion_pruned@500ms | 20261127 | 25.1369 | 0.3741 | 100 |
| whitelist_latency_500ms vs m32_champion_pruned@500ms | 20261128 | 25.0782 | 0.3253 | 100 |
| trajectory_ctrl_full_500ms vs l3_ctrl@500ms | 20261124 | 13.1584 | 0.3741 | 111 |
| trajectory_ctrl_full_500ms vs l3_ctrl@500ms | 20261125 | 13.1129 | 0.3253 | 111 |
| trajectory_ctrl_full_500ms vs l3_ctrl@500ms | 20261126 | 13.0410 | 0.1855 | 111 |
| trajectory_ctrl_full_500ms vs l3_ctrl@500ms | 20261127 | 13.1776 | 0.1400 | 111 |
| trajectory_ctrl_full_500ms vs l3_ctrl@500ms | 20261128 | 13.3941 | 1.0000 | 111 |
| trajectory_ctrl_full_500ms vs m32_champion_pruned@500ms | 20261124 | 24.6510 | 0.0158 | 100 |
| trajectory_ctrl_full_500ms vs m32_champion_pruned@500ms | 20261125 | 24.6115 | 0.0164 | 100 |
| trajectory_ctrl_full_500ms vs m32_champion_pruned@500ms | 20261126 | 24.5491 | 0.0230 | 100 |
| trajectory_ctrl_full_500ms vs m32_champion_pruned@500ms | 20261127 | 24.6677 | 0.0207 | 100 |
| trajectory_ctrl_full_500ms vs m32_champion_pruned@500ms | 20261128 | 24.8555 | 0.1376 | 100 |
| model2_legacy_500ms vs l3_ctrl@500ms | 20261124 | 13.6889 | 1.0000 | 111 |
| model2_legacy_500ms vs l3_ctrl@500ms | 20261125 | 13.2904 | 1.0000 | 111 |
| model2_legacy_500ms vs l3_ctrl@500ms | 20261126 | 13.4816 | 1.0000 | 111 |
| model2_legacy_500ms vs m32_champion_pruned@500ms | 20261124 | 25.1113 | 0.5232 | 100 |
| model2_legacy_500ms vs m32_champion_pruned@500ms | 20261125 | 24.7656 | 0.2445 | 100 |
| model2_legacy_500ms vs m32_champion_pruned@500ms | 20261126 | 24.9314 | 0.0810 | 100 |
| model2_ctrl_full_500ms vs l3_ctrl@500ms | 20261124 | 12.7965 | 0.0000 | 111 |
| model2_ctrl_full_500ms vs l3_ctrl@500ms | 20261125 | 13.5548 | 1.0000 | 111 |
| model2_ctrl_full_500ms vs l3_ctrl@500ms | 20261126 | -13.5777 | 0.0983 | 101 |
| model2_ctrl_full_500ms vs m32_champion_pruned@500ms | 20261124 | 24.3369 | 0.0127 | 100 |
| model2_ctrl_full_500ms vs m32_champion_pruned@500ms | 20261125 | 24.9949 | 0.1028 | 100 |
| model2_ctrl_full_500ms vs m32_champion_pruned@500ms | 20261126 | 1.4531 | 0.0000 | 95 |

The JSON report contains per-size, fleet, external-suite, and trajectory detail.
