# Experiment 2C · CVRP multiscale × early-stop ablation

Each model and seed has its own paired inference and Holm family.

## Realized search budget

| Cell | Stop reason | Requests | Restarts | Checkpoint winner ordinal |
|---|---|---:|---:|---:|
| DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | request_budget_exhausted | 100 | 0 | 6 |
| DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | request_budget_exhausted | 100 | 0 | 82 |
| DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | request_budget_exhausted | 100 | 1 | 51 |
| DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | request_budget_exhausted | 100 | 2 | 9 |
| DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | request_budget_exhausted | 100 | 0 | 86 |
| DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | request_budget_exhausted | 100 | 0 | 6 |
| DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | request_budget_exhausted | 100 | 1 | 26 |
| DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | request_budget_exhausted | 100 | 2 | 10 |
| DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | request_budget_exhausted | 100 | 0 | 95 |
| DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | request_budget_exhausted | 100 | 0 | 0 |
| DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | request_budget_exhausted | 100 | 3 | 39 |
| DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | request_budget_exhausted | 100 | 2 | 43 |
| Qwen4-Max:arm_s2_00_base_whitelist:20261124 | request_budget_exhausted | 100 | 0 | 57 |
| Qwen4-Max:arm_s2_10_multiscale_only:20261124 | request_budget_exhausted | 100 | 0 | 7 |
| Qwen4-Max:arm_s2_01_earlystop_only:20261124 | request_budget_exhausted | 100 | 0 | 16 |
| Qwen4-Max:arm_s2_11_combined:20261124 | request_budget_exhausted | 100 | 3 | 13 |
| Qwen4-Max:arm_s2_00_base_whitelist:20261125 | request_budget_exhausted | 100 | 0 | 95 |
| Qwen4-Max:arm_s2_10_multiscale_only:20261125 | request_budget_exhausted | 100 | 0 | 40 |
| Qwen4-Max:arm_s2_01_earlystop_only:20261125 | request_budget_exhausted | 100 | 1 | 49 |
| Qwen4-Max:arm_s2_11_combined:20261125 | request_budget_exhausted | 100 | 3 | 9 |
| Qwen4-Max:arm_s2_00_base_whitelist:20261126 | request_budget_exhausted | 100 | 0 | 21 |
| Qwen4-Max:arm_s2_10_multiscale_only:20261126 | request_budget_exhausted | 100 | 0 | 31 |
| Qwen4-Max:arm_s2_01_earlystop_only:20261126 | request_budget_exhausted | 100 | 1 | 83 |
| Qwen4-Max:arm_s2_11_combined:20261126 | request_budget_exhausted | 100 | 0 | 72 |

## Deadline outcomes

| Suite | Cell | Fleet | Timing view | Eligible | Eligible mean | 2×-penalized mean |
|---|---|---|---|---:|---:|---:|
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | free_fleet | feasible_before_deadline | 74/74 | 910.1 | 910.1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | free_fleet | returned_before_deadline | 74/74 | 910.1 | 910.1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | exact_k | feasible_before_deadline | 51/74 | 912.4 | 1165 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | exact_k | returned_before_deadline | 50/74 | 918 | 1172 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | free_fleet | feasible_before_deadline | 74/74 | 903.6 | 903.6 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | free_fleet | returned_before_deadline | 74/74 | 903.6 | 903.6 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | exact_k | feasible_before_deadline | 53/74 | 926.4 | 1124 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | exact_k | returned_before_deadline | 52/74 | 932.1 | 1132 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | free_fleet | feasible_before_deadline | 74/74 | 911.4 | 911.4 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | free_fleet | returned_before_deadline | 74/74 | 911.4 | 911.4 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | exact_k | feasible_before_deadline | 53/74 | 941.2 | 1129 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | exact_k | returned_before_deadline | 52/74 | 947.5 | 1136 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | free_fleet | feasible_before_deadline | 74/74 | 907.6 | 907.6 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | free_fleet | returned_before_deadline | 74/74 | 907.6 | 907.6 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | exact_k | feasible_before_deadline | 49/74 | 918.8 | 1182 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | exact_k | returned_before_deadline | 48/74 | 924.9 | 1189 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | free_fleet | feasible_before_deadline | 74/74 | 914.7 | 914.7 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | free_fleet | returned_before_deadline | 74/74 | 914.7 | 914.7 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | exact_k | feasible_before_deadline | 49/74 | 896.6 | 1202 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | exact_k | returned_before_deadline | 48/74 | 902.1 | 1209 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | free_fleet | feasible_before_deadline | 74/74 | 911.2 | 911.2 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | free_fleet | returned_before_deadline | 74/74 | 911.2 | 911.2 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | exact_k | feasible_before_deadline | 52/74 | 908.6 | 1160 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | exact_k | returned_before_deadline | 51/74 | 914 | 1167 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | free_fleet | feasible_before_deadline | 74/74 | 903.5 | 903.5 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | free_fleet | returned_before_deadline | 74/74 | 903.5 | 903.5 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | exact_k | feasible_before_deadline | 49/74 | 906.8 | 1181 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | exact_k | returned_before_deadline | 48/74 | 912.6 | 1189 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | free_fleet | feasible_before_deadline | 74/74 | 905.7 | 905.7 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | free_fleet | returned_before_deadline | 74/74 | 905.7 | 905.7 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | exact_k | feasible_before_deadline | 51/74 | 913.4 | 1158 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | exact_k | returned_before_deadline | 50/74 | 919 | 1166 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | free_fleet | feasible_before_deadline | 74/74 | 904.5 | 904.5 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | free_fleet | returned_before_deadline | 74/74 | 904.5 | 904.5 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | exact_k | feasible_before_deadline | 50/74 | 918.8 | 1167 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | exact_k | returned_before_deadline | 49/74 | 924.7 | 1174 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | free_fleet | feasible_before_deadline | 74/74 | 914.7 | 914.7 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | free_fleet | returned_before_deadline | 74/74 | 914.7 | 914.7 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | exact_k | feasible_before_deadline | 49/74 | 896.6 | 1202 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | exact_k | returned_before_deadline | 48/74 | 902.1 | 1209 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | free_fleet | feasible_before_deadline | 74/74 | 904.8 | 904.8 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | free_fleet | returned_before_deadline | 74/74 | 904.8 | 904.8 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | exact_k | feasible_before_deadline | 49/74 | 910.3 | 1184 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | exact_k | returned_before_deadline | 48/74 | 916 | 1191 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | free_fleet | feasible_before_deadline | 74/74 | 915.1 | 915.1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | free_fleet | returned_before_deadline | 74/74 | 915.1 | 915.1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | exact_k | feasible_before_deadline | 47/74 | 882.6 | 1231 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | exact_k | returned_before_deadline | 46/74 | 888.2 | 1239 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | free_fleet | feasible_before_deadline | 74/74 | 906.9 | 906.9 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | free_fleet | returned_before_deadline | 74/74 | 906.9 | 906.9 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | exact_k | feasible_before_deadline | 52/74 | 911.6 | 1153 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | exact_k | returned_before_deadline | 50/74 | 914.4 | 1172 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | free_fleet | feasible_before_deadline | 74/74 | 910.1 | 910.1 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | free_fleet | returned_before_deadline | 74/74 | 910.1 | 910.1 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | exact_k | feasible_before_deadline | 51/74 | 912.4 | 1165 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | exact_k | returned_before_deadline | 50/74 | 918 | 1172 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | free_fleet | feasible_before_deadline | 74/74 | 902.7 | 902.7 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | free_fleet | returned_before_deadline | 74/74 | 902.7 | 902.7 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | exact_k | feasible_before_deadline | 51/74 | 903.8 | 1163 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | exact_k | returned_before_deadline | 50/74 | 909.3 | 1170 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261124 | free_fleet | feasible_before_deadline | 74/74 | 910.7 | 910.7 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261124 | free_fleet | returned_before_deadline | 74/74 | 910.7 | 910.7 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261124 | exact_k | feasible_before_deadline | 50/74 | 909.9 | 1180 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261124 | exact_k | returned_before_deadline | 49/74 | 915.5 | 1187 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | free_fleet | feasible_before_deadline | 74/74 | 901 | 901 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | free_fleet | returned_before_deadline | 74/74 | 901 | 901 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | exact_k | feasible_before_deadline | 59/74 | 885.5 | 1084 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | exact_k | returned_before_deadline | 56/74 | 886 | 1114 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | free_fleet | feasible_before_deadline | 74/74 | 903.9 | 903.9 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | free_fleet | returned_before_deadline | 74/74 | 903.9 | 903.9 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | exact_k | feasible_before_deadline | 52/74 | 909.4 | 1152 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | exact_k | returned_before_deadline | 51/74 | 915.1 | 1159 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | free_fleet | feasible_before_deadline | 74/74 | 906.8 | 906.8 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | free_fleet | returned_before_deadline | 74/74 | 906.8 | 906.8 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | exact_k | feasible_before_deadline | 50/74 | 893.4 | 1184 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | exact_k | returned_before_deadline | 49/74 | 898.7 | 1191 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261125 | free_fleet | feasible_before_deadline | 74/74 | 903 | 903 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261125 | free_fleet | returned_before_deadline | 74/74 | 903 | 903 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261125 | exact_k | feasible_before_deadline | 47/74 | 895.4 | 1211 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261125 | exact_k | returned_before_deadline | 47/74 | 895.4 | 1211 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | free_fleet | feasible_before_deadline | 74/74 | 903.2 | 903.2 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | free_fleet | returned_before_deadline | 74/74 | 903.2 | 903.2 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | exact_k | feasible_before_deadline | 52/74 | 918.9 | 1142 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | exact_k | returned_before_deadline | 51/74 | 924.6 | 1149 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | free_fleet | feasible_before_deadline | 74/74 | 903.2 | 903.2 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | free_fleet | returned_before_deadline | 74/74 | 903.2 | 903.2 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | exact_k | feasible_before_deadline | 52/74 | 907.5 | 1147 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | exact_k | returned_before_deadline | 51/74 | 912.9 | 1154 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | free_fleet | feasible_before_deadline | 74/74 | 894.7 | 894.7 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | free_fleet | returned_before_deadline | 74/74 | 894.7 | 894.7 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | exact_k | feasible_before_deadline | 67/74 | 916.4 | 973.6 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | exact_k | returned_before_deadline | 57/74 | 898.8 | 1088 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261126 | free_fleet | feasible_before_deadline | 74/74 | 900.9 | 900.9 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261126 | free_fleet | returned_before_deadline | 74/74 | 900.9 | 900.9 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261126 | exact_k | feasible_before_deadline | 50/74 | 907.3 | 1172 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261126 | exact_k | returned_before_deadline | 49/74 | 913.2 | 1180 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | free_fleet | feasible_before_deadline | 100/100 | 6.636e+04 | 6.636e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | free_fleet | returned_before_deadline | 100/100 | 6.636e+04 | 6.636e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | free_fleet | feasible_before_deadline | 100/100 | 6.599e+04 | 6.599e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | free_fleet | returned_before_deadline | 98/100 | 6.421e+04 | 6.85e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | free_fleet | feasible_before_deadline | 100/100 | 6.655e+04 | 6.655e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | free_fleet | returned_before_deadline | 100/100 | 6.655e+04 | 6.655e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | free_fleet | feasible_before_deadline | 100/100 | 6.639e+04 | 6.639e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | free_fleet | returned_before_deadline | 100/100 | 6.639e+04 | 6.639e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | free_fleet | feasible_before_deadline | 100/100 | 6.635e+04 | 6.635e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | free_fleet | returned_before_deadline | 100/100 | 6.635e+04 | 6.635e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | free_fleet | feasible_before_deadline | 100/100 | 6.641e+04 | 6.641e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | free_fleet | returned_before_deadline | 100/100 | 6.641e+04 | 6.641e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | free_fleet | feasible_before_deadline | 100/100 | 6.604e+04 | 6.604e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | free_fleet | returned_before_deadline | 98/100 | 6.423e+04 | 6.853e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | free_fleet | feasible_before_deadline | 100/100 | 6.601e+04 | 6.601e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | free_fleet | returned_before_deadline | 98/100 | 6.42e+04 | 6.85e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | free_fleet | feasible_before_deadline | 100/100 | 6.608e+04 | 6.608e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | free_fleet | returned_before_deadline | 98/100 | 6.427e+04 | 6.857e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | free_fleet | feasible_before_deadline | 100/100 | 6.635e+04 | 6.635e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | free_fleet | returned_before_deadline | 100/100 | 6.635e+04 | 6.635e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | free_fleet | feasible_before_deadline | 100/100 | 6.611e+04 | 6.611e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | free_fleet | returned_before_deadline | 97/100 | 6.328e+04 | 7.005e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | free_fleet | feasible_before_deadline | 100/100 | 6.667e+04 | 6.667e+04 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | free_fleet | returned_before_deadline | 100/100 | 6.667e+04 | 6.667e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | free_fleet | feasible_before_deadline | 100/100 | 6.606e+04 | 6.606e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | free_fleet | returned_before_deadline | 16/100 | 3.151e+04 | 1.216e+05 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | free_fleet | feasible_before_deadline | 100/100 | 6.636e+04 | 6.636e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | free_fleet | returned_before_deadline | 100/100 | 6.636e+04 | 6.636e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | free_fleet | feasible_before_deadline | 100/100 | 6.611e+04 | 6.611e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | free_fleet | returned_before_deadline | 98/100 | 6.426e+04 | 6.855e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261124 | free_fleet | feasible_before_deadline | 100/100 | 6.643e+04 | 6.643e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261124 | free_fleet | returned_before_deadline | 100/100 | 6.643e+04 | 6.643e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | free_fleet | feasible_before_deadline | 100/100 | 6.593e+04 | 6.593e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | free_fleet | returned_before_deadline | 10/100 | 2.552e+04 | 1.238e+05 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | free_fleet | feasible_before_deadline | 100/100 | 6.621e+04 | 6.621e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | free_fleet | returned_before_deadline | 97/100 | 6.388e+04 | 6.993e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | free_fleet | feasible_before_deadline | 100/100 | 6.615e+04 | 6.615e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | free_fleet | returned_before_deadline | 14/100 | 3.169e+04 | 1.222e+05 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261125 | free_fleet | feasible_before_deadline | 100/100 | 6.598e+04 | 6.598e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261125 | free_fleet | returned_before_deadline | 98/100 | 6.423e+04 | 6.853e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | free_fleet | feasible_before_deadline | 100/100 | 6.605e+04 | 6.605e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | free_fleet | returned_before_deadline | 98/100 | 6.433e+04 | 6.862e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | free_fleet | feasible_before_deadline | 100/100 | 6.589e+04 | 6.589e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | free_fleet | returned_before_deadline | 99/100 | 6.514e+04 | 6.715e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | free_fleet | feasible_before_deadline | 100/100 | 6.6e+04 | 6.6e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | free_fleet | returned_before_deadline | 18/100 | 2.673e+04 | 1.218e+05 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261126 | free_fleet | feasible_before_deadline | 100/100 | 6.642e+04 | 6.642e+04 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261126 | free_fleet | returned_before_deadline | 98/100 | 6.457e+04 | 6.886e+04 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | free_fleet | feasible_before_deadline | 120/120 | 24.62 | 24.62 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | free_fleet | returned_before_deadline | 120/120 | 24.62 | 24.62 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | exact_k | feasible_before_deadline | 81/120 | 24.01 | 37.06 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | exact_k | returned_before_deadline | 79/120 | 24.05 | 37.63 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | free_fleet | feasible_before_deadline | 120/120 | 24.48 | 24.48 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | free_fleet | returned_before_deadline | 120/120 | 24.48 | 24.48 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | exact_k | feasible_before_deadline | 90/120 | 23.9 | 34.44 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | exact_k | returned_before_deadline | 89/120 | 24.02 | 34.6 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | free_fleet | feasible_before_deadline | 120/120 | 24.77 | 24.77 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | free_fleet | returned_before_deadline | 120/120 | 24.77 | 24.77 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | exact_k | feasible_before_deadline | 83/120 | 24.07 | 36.54 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | exact_k | returned_before_deadline | 80/120 | 23.28 | 38.09 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | free_fleet | feasible_before_deadline | 120/120 | 24.67 | 24.67 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | free_fleet | returned_before_deadline | 120/120 | 24.67 | 24.67 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | exact_k | feasible_before_deadline | 66/120 | 23.11 | 41.7 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | exact_k | returned_before_deadline | 65/120 | 22.98 | 42.11 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | free_fleet | feasible_before_deadline | 120/120 | 24.62 | 24.62 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | free_fleet | returned_before_deadline | 120/120 | 24.62 | 24.62 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | exact_k | feasible_before_deadline | 75/120 | 23.34 | 39.39 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | exact_k | returned_before_deadline | 75/120 | 23.34 | 39.39 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | free_fleet | feasible_before_deadline | 120/120 | 24.68 | 24.68 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | free_fleet | returned_before_deadline | 120/120 | 24.68 | 24.68 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | exact_k | feasible_before_deadline | 72/120 | 22.49 | 40.53 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | exact_k | returned_before_deadline | 72/120 | 22.49 | 40.53 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | free_fleet | feasible_before_deadline | 120/120 | 24.5 | 24.5 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | free_fleet | returned_before_deadline | 120/120 | 24.5 | 24.5 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | exact_k | feasible_before_deadline | 81/120 | 23.74 | 36.78 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | exact_k | returned_before_deadline | 81/120 | 23.74 | 36.78 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | free_fleet | feasible_before_deadline | 120/120 | 24.5 | 24.5 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | free_fleet | returned_before_deadline | 120/120 | 24.5 | 24.5 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | exact_k | feasible_before_deadline | 79/120 | 24.1 | 37.2 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | exact_k | returned_before_deadline | 78/120 | 24 | 37.61 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | free_fleet | feasible_before_deadline | 120/120 | 24.48 | 24.48 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | free_fleet | returned_before_deadline | 120/120 | 24.48 | 24.48 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | exact_k | feasible_before_deadline | 88/120 | 24.16 | 34.69 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | exact_k | returned_before_deadline | 88/120 | 24.16 | 34.69 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | free_fleet | feasible_before_deadline | 120/120 | 24.62 | 24.62 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | free_fleet | returned_before_deadline | 120/120 | 24.62 | 24.62 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | exact_k | feasible_before_deadline | 75/120 | 23.34 | 39.39 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | exact_k | returned_before_deadline | 75/120 | 23.34 | 39.39 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | free_fleet | feasible_before_deadline | 120/120 | 24.5 | 24.5 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | free_fleet | returned_before_deadline | 120/120 | 24.5 | 24.5 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | exact_k | feasible_before_deadline | 80/120 | 22.81 | 37.94 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | exact_k | returned_before_deadline | 80/120 | 22.81 | 37.94 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | free_fleet | feasible_before_deadline | 120/120 | 24.8 | 24.8 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | free_fleet | returned_before_deadline | 120/120 | 24.8 | 24.8 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | exact_k | feasible_before_deadline | 71/120 | 22.35 | 41.22 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | exact_k | returned_before_deadline | 71/120 | 22.35 | 41.22 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | free_fleet | feasible_before_deadline | 120/120 | 24.44 | 24.44 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | free_fleet | returned_before_deadline | 105/120 | 23.4 | 30.56 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | exact_k | feasible_before_deadline | 86/120 | 24.29 | 35.21 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | exact_k | returned_before_deadline | 75/120 | 23.26 | 39.45 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | free_fleet | feasible_before_deadline | 120/120 | 24.62 | 24.62 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | free_fleet | returned_before_deadline | 120/120 | 24.62 | 24.62 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | exact_k | feasible_before_deadline | 81/120 | 24.01 | 37.06 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | exact_k | returned_before_deadline | 79/120 | 24.05 | 37.63 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | free_fleet | feasible_before_deadline | 120/120 | 24.52 | 24.52 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | free_fleet | returned_before_deadline | 120/120 | 24.52 | 24.52 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | exact_k | feasible_before_deadline | 83/120 | 23.78 | 36.13 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | exact_k | returned_before_deadline | 82/120 | 23.68 | 36.54 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261124 | free_fleet | feasible_before_deadline | 120/120 | 24.63 | 24.63 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261124 | free_fleet | returned_before_deadline | 120/120 | 24.63 | 24.63 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261124 | exact_k | feasible_before_deadline | 83/120 | 24.01 | 36.63 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261124 | exact_k | returned_before_deadline | 81/120 | 24.05 | 37.2 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | free_fleet | feasible_before_deadline | 120/120 | 24.31 | 24.31 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | free_fleet | returned_before_deadline | 78/120 | 19.21 | 41.35 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | exact_k | feasible_before_deadline | 103/120 | 23.7 | 30.43 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | exact_k | returned_before_deadline | 69/120 | 19.11 | 43.58 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | free_fleet | feasible_before_deadline | 120/120 | 24.61 | 24.61 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | free_fleet | returned_before_deadline | 120/120 | 24.61 | 24.61 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | exact_k | feasible_before_deadline | 90/120 | 24.31 | 34.09 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | exact_k | returned_before_deadline | 89/120 | 24.22 | 34.49 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | free_fleet | feasible_before_deadline | 120/120 | 24.46 | 24.46 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | free_fleet | returned_before_deadline | 94/120 | 21.1 | 35.76 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | exact_k | feasible_before_deadline | 88/120 | 23.26 | 35.54 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | exact_k | returned_before_deadline | 71/120 | 20.57 | 42.3 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261125 | free_fleet | feasible_before_deadline | 120/120 | 24.56 | 24.56 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261125 | free_fleet | returned_before_deadline | 120/120 | 24.56 | 24.56 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261125 | exact_k | feasible_before_deadline | 79/120 | 24.72 | 36.92 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261125 | exact_k | returned_before_deadline | 77/120 | 24.55 | 37.72 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | free_fleet | feasible_before_deadline | 120/120 | 24.5 | 24.5 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | free_fleet | returned_before_deadline | 120/120 | 24.5 | 24.5 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | exact_k | feasible_before_deadline | 89/120 | 24.28 | 34.27 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | exact_k | returned_before_deadline | 88/120 | 24.19 | 34.68 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | free_fleet | feasible_before_deadline | 120/120 | 24.47 | 24.47 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | free_fleet | returned_before_deadline | 120/120 | 24.47 | 24.47 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | exact_k | feasible_before_deadline | 95/120 | 24.66 | 32 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | exact_k | returned_before_deadline | 93/120 | 24.52 | 32.81 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | free_fleet | feasible_before_deadline | 120/120 | 24.36 | 24.36 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | free_fleet | returned_before_deadline | 113/120 | 23.77 | 27.31 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | exact_k | feasible_before_deadline | 106/120 | 24.05 | 29.26 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | exact_k | returned_before_deadline | 82/120 | 22.67 | 37.59 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261126 | free_fleet | feasible_before_deadline | 120/120 | 24.52 | 24.52 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261126 | free_fleet | returned_before_deadline | 120/120 | 24.52 | 24.52 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261126 | exact_k | feasible_before_deadline | 96/120 | 23.52 | 33.01 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261126 | exact_k | returned_before_deadline | 94/120 | 23.36 | 33.82 |

## Solve latency by size

| Suite | Cell | Size range | P95 (ms) | Lower bound | Observed | Censored | Missing |
|---|---|---|---:|---|---:|---:|---:|
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 1–99 | 1.124 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 100–200 | 1.681 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 1–99 | 2.447 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 100–200 | 7.219 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 1–99 | 1.216 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 100–200 | 1.753 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 1–99 | 0.9503 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 100–200 | 1.627 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 1–99 | 1.115 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 100–200 | 1.606 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 1–99 | 1.179 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 100–200 | 1.649 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 1–99 | 2.373 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 100–200 | 6.923 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 1–99 | 2.393 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 100–200 | 9.185 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 1–99 | 2.411 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 100–200 | 7.701 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 1–99 | 0.8832 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 100–200 | 1.503 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 1–99 | 2.516 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 100–200 | 5.48 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 1–99 | 0.99 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 100–200 | 1.733 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 1–99 | 145.2 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 100–200 | 341.4 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 1–99 | 1.107 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 100–200 | 1.759 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 1–99 | 2.48 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 100–200 | 9.282 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261124 | 1–99 | 1.115 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261124 | 100–200 | 1.907 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261124 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261124 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261124 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261124 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 1–99 | 162.9 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 100–200 | 362.4 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 1–99 | 2.883 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 100–200 | 8.803 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 1–99 | 138.8 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 100–200 | 301.1 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261125 | 1–99 | 2.925 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261125 | 100–200 | 6.617 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261125 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261125 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261125 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261125 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 1–99 | 2.531 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 100–200 | 4.753 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 1–99 | 2.527 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 100–200 | 7.314 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 1–99 | 133.4 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 100–200 | 306.7 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261126 | 1–99 | 2.761 | no | 73 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261126 | 100–200 | 4.872 | no | 1 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261126 | 201–400 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261126 | 401–600 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261126 | 601–800 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261126 | 801–1000 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max:arm_s2_11_combined:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 100–200 | 6 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 201–400 | 26.22 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 401–600 | 86.16 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 601–800 | 166.6 | no | 13 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 801–1000 | 268 | no | 10 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 100–200 | 19.35 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 201–400 | 61.38 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 401–600 | 251.3 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 601–800 | 500.9 | yes | 13 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 801–1000 | 502.1 | yes | 10 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 100–200 | 5.904 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 201–400 | 26.58 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 401–600 | 79.28 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 601–800 | 161.3 | no | 13 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 801–1000 | 268.2 | no | 10 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 100–200 | 5.749 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 201–400 | 27.07 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 401–600 | 83.99 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 601–800 | 165.8 | no | 13 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 801–1000 | 263.1 | no | 10 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 100–200 | 5.792 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 201–400 | 24.38 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 401–600 | 77.59 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 601–800 | 158.5 | no | 13 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 801–1000 | 248.1 | no | 10 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 100–200 | 5.949 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 201–400 | 27.18 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 401–600 | 79.56 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 601–800 | 158.9 | no | 13 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 801–1000 | 246 | no | 10 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 100–200 | 19.76 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 201–400 | 63.07 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 401–600 | 359.7 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 601–800 | 501.5 | yes | 13 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 801–1000 | 501.4 | yes | 10 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 100–200 | 18.96 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 201–400 | 62.76 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 401–600 | 323 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 601–800 | 501 | yes | 13 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 801–1000 | 501.4 | yes | 10 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 100–200 | 19.07 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 201–400 | 51.41 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 401–600 | 271.5 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 601–800 | 500.9 | yes | 13 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 801–1000 | 501.8 | yes | 10 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 100–200 | 5.92 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 201–400 | 24.68 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 401–600 | 71.46 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 601–800 | 151.5 | no | 13 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 801–1000 | 260 | no | 10 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 100–200 | 18.9 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 201–400 | 65.99 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 401–600 | 500.7 | yes | 18 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 601–800 | 501.1 | yes | 13 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 801–1000 | 501.6 | yes | 10 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 100–200 | 6.172 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 201–400 | 27.34 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 401–600 | 77.14 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 601–800 | 169.9 | no | 13 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 801–1000 | 273.6 | no | 10 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 100–200 | 500.8 | yes | 22 | 6 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 201–400 | 502.7 | yes | 37 | 37 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 401–600 | 504 | yes | 18 | 18 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 601–800 | 508.5 | yes | 13 | 13 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 801–1000 | 510.6 | yes | 10 | 10 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 100–200 | 6.086 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 201–400 | 29.87 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 401–600 | 84.34 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 601–800 | 159 | no | 13 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 801–1000 | 279.5 | no | 10 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 100–200 | 20.74 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 201–400 | 61.73 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 401–600 | 361.3 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 601–800 | 501.1 | yes | 13 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 801–1000 | 501.3 | yes | 10 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261124 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261124 | 100–200 | 6.707 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261124 | 201–400 | 32.02 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261124 | 401–600 | 89.38 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261124 | 601–800 | 177.3 | no | 13 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261124 | 801–1000 | 303.7 | no | 10 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261124 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 100–200 | 501.9 | yes | 22 | 12 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 201–400 | 502.6 | yes | 37 | 37 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 401–600 | 507.5 | yes | 18 | 18 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 601–800 | 506.6 | yes | 13 | 13 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 801–1000 | 510 | yes | 10 | 10 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 100–200 | 24.68 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 201–400 | 58.35 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 401–600 | 376.9 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 601–800 | 500.6 | yes | 13 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 801–1000 | 501.7 | yes | 10 | 2 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 100–200 | 501.8 | yes | 22 | 8 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 201–400 | 502.9 | yes | 37 | 37 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 401–600 | 504.5 | yes | 18 | 18 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 601–800 | 506.6 | yes | 13 | 13 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 801–1000 | 510.5 | yes | 10 | 10 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261125 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261125 | 100–200 | 20.08 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261125 | 201–400 | 66.45 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261125 | 401–600 | 268.8 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261125 | 601–800 | 501 | yes | 13 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261125 | 801–1000 | 501.4 | yes | 10 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261125 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 100–200 | 23.11 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 201–400 | 81.25 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 401–600 | 398.6 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 601–800 | 501 | yes | 13 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 801–1000 | 502.5 | yes | 10 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 100–200 | 21.84 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 201–400 | 61.18 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 401–600 | 357.8 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 601–800 | 432.5 | no | 13 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 801–1000 | 501.5 | yes | 10 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 100–200 | 500.4 | yes | 22 | 5 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 201–400 | 502.5 | yes | 37 | 36 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 401–600 | 505.2 | yes | 18 | 18 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 601–800 | 507.6 | yes | 13 | 13 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 801–1000 | 511.9 | yes | 10 | 10 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261126 | 1–99 | — | no | 0 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261126 | 100–200 | 32.15 | no | 22 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261126 | 201–400 | 70.88 | no | 37 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261126 | 401–600 | 432.2 | no | 18 | 0 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261126 | 601–800 | 501 | yes | 13 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261126 | 801–1000 | 501.5 | yes | 10 | 1 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max:arm_s2_11_combined:20261126 | 1001+ | — | no | 0 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 50 | 0.8961 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 100 | 2.161 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 150 | 3.966 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261124 | 200 | 7.061 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 50 | 2.204 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 100 | 6.784 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 150 | 11.77 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261124 | 200 | 18.43 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 50 | 0.6974 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 100 | 3.03 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 150 | 5.724 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261124 | 200 | 7.753 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 50 | 0.6721 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 100 | 1.901 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 150 | 5.302 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261124 | 200 | 6.807 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 50 | 0.7868 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 100 | 2.215 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 150 | 4.725 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261125 | 200 | 7.069 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 50 | 0.848 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 100 | 1.81 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 150 | 4.324 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261125 | 200 | 7.75 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 50 | 2.278 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 100 | 5.852 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 150 | 12.64 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261125 | 200 | 18.35 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 50 | 2.244 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 100 | 6.214 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 150 | 15.51 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261125 | 200 | 17.92 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 50 | 2.176 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 100 | 6.01 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 150 | 13.69 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_00_base_whitelist:20261126 | 200 | 19.11 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 50 | 0.7253 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 100 | 2.406 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 150 | 4.247 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_10_multiscale_only:20261126 | 200 | 6.853 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 50 | 2.155 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 100 | 6.113 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 150 | 11.07 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_01_earlystop_only:20261126 | 200 | 20.61 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 50 | 0.8469 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 100 | 2.104 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 150 | 5.236 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | DeepSeek-V4.1-Flash:arm_s2_11_combined:20261126 | 200 | 7.519 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 50 | 77.75 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 100 | 238 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 150 | 439.5 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261124 | 200 | 501.3 | yes | 30 | 15 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 50 | 0.8378 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 100 | 1.888 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 150 | 5.801 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261124 | 200 | 7.55 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 50 | 2.347 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 100 | 5.989 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 150 | 11.78 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261124 | 200 | 23.76 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261124 | 50 | 0.7394 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261124 | 100 | 2.186 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261124 | 150 | 4.258 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261124 | 200 | 9.197 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 50 | 98.55 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 100 | 275.9 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 150 | 502 | yes | 30 | 12 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261125 | 200 | 501.9 | yes | 30 | 30 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 50 | 2.648 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 100 | 7.976 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 150 | 14.22 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261125 | 200 | 19.75 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 50 | 82.24 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 100 | 236.8 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 150 | 466 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261125 | 200 | 502 | yes | 30 | 26 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261125 | 50 | 2.237 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261125 | 100 | 7.295 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261125 | 150 | 13.5 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261125 | 200 | 23.26 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 50 | 2.135 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 100 | 5.59 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 150 | 12.78 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_00_base_whitelist:20261126 | 200 | 20.98 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 50 | 2.05 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 100 | 5.688 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 150 | 12.14 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_10_multiscale_only:20261126 | 200 | 17.58 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 50 | 77.72 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 100 | 218.8 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 150 | 406.2 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_01_earlystop_only:20261126 | 200 | 501.8 | yes | 30 | 7 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261126 | 50 | 2.167 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261126 | 100 | 6.274 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261126 | 150 | 12.59 | no | 30 | 0 | 0 |
| cvrp_s2_multiscale_blind_120 | Qwen4-Max:arm_s2_11_combined:20261126 | 200 | 18.94 | no | 30 | 0 | 0 |

## Paired contrasts

Contrast signs are relative to objective cost. For `B_minus_A` (or a factor main effect), a negative value favors B (the enabled factor).

| Model | Seed | Suite | Fleet | Timing view | Denominator | Contrast | Pairs | Mean | 95% CI | Wilcoxon p | Holm p |
|---|---:|---|---|---|---|---|---:|---:|---|---:|---:|
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 74 | -5.128 | -7.426 / -2.919 | 7.768e-06 | 0.0009244 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 74 | 2.601 | 0.1485 / 4.845 | 0.001667 | 0.1334 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | interaction | 74 | 2.77 | -3.081 / 8.784 | 0.5417 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -6.514 | -9.473 / -3.635 | 1.794e-05 | 0.002063 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 1.216 | -3.311 / 5.176 | 0.1123 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -2.527 | -5.324 / 0.2432 | 0.02786 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 7.73 | 3.932 / 11.3 | 2.372e-06 | 0.0002941 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 3.986 | 0.7297 / 7.176 | 0.003547 | 0.2518 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | -3.743 | -8.162 / 0.6486 | 0.02714 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 74 | -5.128 | -7.426 / -2.919 | 7.768e-06 | 0.0009244 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 74 | 2.601 | 0.1485 / 4.845 | 0.001667 | 0.1334 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 74 | 2.77 | -3.081 / 8.784 | 0.5417 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -6.514 | -9.473 / -3.635 | 1.794e-05 | 0.002063 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 1.216 | -3.311 / 5.176 | 0.1123 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -2.527 | -5.324 / 0.2432 | 0.02786 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 7.73 | 3.932 / 11.3 | 2.372e-06 | 0.0002941 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 3.986 | 0.7297 / 7.176 | 0.003547 | 0.2518 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | -3.743 | -8.162 / 0.6486 | 0.02714 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 74 | -5.128 | -7.426 / -2.919 | 7.768e-06 | 0.0009244 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 74 | 2.601 | 0.1485 / 4.845 | 0.001667 | 0.1334 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | interaction | 74 | 2.77 | -3.081 / 8.784 | 0.5417 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -6.514 | -9.473 / -3.635 | 1.794e-05 | 0.002063 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 1.216 | -3.311 / 5.176 | 0.1123 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -2.527 | -5.324 / 0.2432 | 0.02786 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 7.73 | 3.932 / 11.3 | 2.372e-06 | 0.0002941 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 3.986 | 0.7297 / 7.176 | 0.003547 | 0.2518 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | -3.743 | -8.162 / 0.6486 | 0.02714 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 74 | -5.128 | -7.426 / -2.919 | 7.768e-06 | 0.0009244 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 74 | 2.601 | 0.1485 / 4.845 | 0.001667 | 0.1334 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | interaction | 74 | 2.77 | -3.081 / 8.784 | 0.5417 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -6.514 | -9.473 / -3.635 | 1.794e-05 | 0.002063 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 1.216 | -3.311 / 5.176 | 0.1123 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -2.527 | -5.324 / 0.2432 | 0.02786 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 7.73 | 3.932 / 11.3 | 2.372e-06 | 0.0002941 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 3.986 | 0.7297 / 7.176 | 0.003547 | 0.2518 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | -3.743 | -8.162 / 0.6486 | 0.02714 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 45 | -5.722 | -8.644 / -2.878 | 0.0002341 | 0.02364 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 45 | 4.722 | 2.2 / 7.433 | 0.0007058 | 0.06494 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | interaction | 45 | 2.244 | -4.089 / 8.556 | 0.4314 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 47 | -6.894 | -10.47 / -3.426 | 5.45e-05 | 0.005941 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 48 | 3.792 | -0.3547 / 8.083 | 0.04053 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 47 | -1.106 | -3.936 / 2.192 | 0.1181 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 52 | 10.04 | 5.885 / 14.35 | 2.583e-05 | 0.002867 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 47 | 6.064 | 2.596 / 9.787 | 0.002027 | 0.15 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 47 | -4.638 | -9.319 / 0.1277 | 0.03871 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 74 | 6.493 | -30.53 / 46.57 | 0.008071 | 0.4843 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 74 | 10.66 | -19.25 / 40.68 | 0.002448 | 0.1787 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | interaction | 74 | 93.09 | -30.06 / 225.6 | 0.114 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -40.05 | -120.1 / 35 | 0.0006136 | 0.05767 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -35.89 | -110.3 / 32.76 | 0.287 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 17.15 | -44.76 / 78.67 | 0.4323 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 4.162 | -30.27 / 35.3 | 7.992e-05 | 0.008552 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 57.2 | -8.895 / 129.8 | 0.00106 | 0.09119 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 53.04 | -14.5 / 126 | 0.537 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | multiscale_main | 44 | -6.011 | -8.943 / -3.091 | 0.0001125 | 0.01148 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | early_stop_main | 44 | 5.08 | 2.614 / 7.67 | 0.0002453 | 0.02453 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | interaction | 44 | 2.023 | -4.432 / 8.455 | 0.5298 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 46 | -7.065 | -10.61 / -3.695 | 5.813e-05 | 0.006279 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 47 | 4.234 | 0.04255 / 8.553 | 0.0211 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 46 | -1.043 | -3.978 / 2.239 | 0.1458 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 51 | 10.59 | 6.529 / 14.82 | 7.185e-06 | 0.0008622 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 46 | 6.304 | 2.783 / 9.957 | 0.001536 | 0.1287 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 46 | -5.022 | -9.783 / -0.2821 | 0.02268 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 74 | 6.399 | -30.68 / 46.54 | 0.005413 | 0.3573 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 74 | 10.8 | -19.14 / 40.79 | 0.001209 | 0.1028 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | interaction | 74 | 92.93 | -30.42 / 225.4 | 0.141 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -40.07 | -120.1 / 35 | 0.0006756 | 0.06283 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -35.66 | -110.3 / 32.88 | 0.2126 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 17.2 | -44.65 / 78.81 | 0.4914 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 4.405 | -30.04 / 35.55 | 2.643e-05 | 0.002908 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 57.27 | -8.865 / 129.9 | 0.0008696 | 0.0791 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 52.86 | -14.76 / 125.9 | 0.4494 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 100 | -263.6 | -360.7 / -165.7 | 1.649e-09 | 2.6e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 100 | 295.1 | 189.2 / 424 | 8.802e-09 | 1.35e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | interaction | 100 | 209 | 80.65 / 336 | 0.001533 | 0.1287 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | -368.1 | -485.7 / -254.4 | 6.899e-10 | 1.1e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 190.6 | 59.69 / 338.5 | 0.0063 | 0.4095 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 31.51 | -117.4 / 203.5 | 0.5225 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | 558.6 | 424 / 710.9 | 3.553e-14 | 0 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 399.6 | 280.7 / 535 | 5.795e-10 | 1e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -159.1 | -276 / -43.49 | 0.0008692 | 0.0791 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 100 | -263.6 | -360.7 / -165.7 | 1.649e-09 | 2.6e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 100 | 295.1 | 189.2 / 424 | 8.802e-09 | 1.35e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 100 | 209 | 80.65 / 336 | 0.001533 | 0.1287 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | -368.1 | -485.7 / -254.4 | 6.899e-10 | 1.1e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 190.6 | 59.69 / 338.5 | 0.0063 | 0.4095 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 31.51 | -117.4 / 203.5 | 0.5225 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | 558.6 | 424 / 710.9 | 3.553e-14 | 0 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 399.6 | 280.7 / 535 | 5.795e-10 | 1e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -159.1 | -276 / -43.49 | 0.0008692 | 0.0791 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 98 | -297.4 | -383.7 / -214.8 | 6.698e-11 | 1e-08 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 98 | 242.9 | 160.7 / 335.7 | 2.463e-08 | 3.52e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | interaction | 98 | 209.3 | 79.87 / 339.2 | 0.001573 | 0.1287 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 98 | -402.1 | -512.8 / -297.8 | 2.735e-11 | 0 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 190.6 | 59.69 / 338.5 | 0.0063 | 0.4095 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 31.51 | -117.4 / 203.5 | 0.5225 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 98 | 540.3 | 411.1 / 684.2 | 2.633e-14 | 0 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 98 | 347.5 | 248 / 453 | 1.61e-09 | 2.5e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -159.1 | -276 / -43.49 | 0.0008692 | 0.0791 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 100 | 994.4 | -337.3 / 3004 | 2.082e-09 | 3.2e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 100 | -962.9 | -2828 / 279.2 | 4.018e-07 | 5.223e-05 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | interaction | 100 | -2307 | -6242 / 267.9 | 0.006433 | 0.4095 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | 2148 | -451.7 / 6112 | 9.343e-10 | 1.5e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 190.6 | 59.69 / 338.5 | 0.0063 | 0.4095 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 31.51 | -117.4 / 203.5 | 0.5225 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | -1957 | -5827 / 599.3 | 1.83e-12 | 0 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | -2116 | -5936 / 392.1 | 3.554e-08 | 5.05e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -159.1 | -276 / -43.49 | 0.0008692 | 0.0791 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 120 | -0.1207 | -0.163 / -0.07906 | 5.153e-08 | 7.27e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 120 | 0.1662 | 0.1196 / 0.214 | 6.336e-10 | 1e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | interaction | 120 | 0.03986 | -0.05688 / 0.1335 | 0.3127 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -0.1407 | -0.1914 / -0.08914 | 1.144e-08 | 1.73e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.1462 | 0.07959 / 0.2175 | 8.072e-05 | 0.008557 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.04545 | -0.01471 / 0.1075 | 0.8025 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | 0.2869 | 0.2241 / 0.3535 | 7.29e-15 | 0 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.1861 | 0.1244 / 0.2535 | 2.341e-08 | 3.44e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | -0.1008 | -0.1765 / -0.0272 | 0.0005653 | 0.05596 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 120 | -0.1207 | -0.163 / -0.07906 | 5.153e-08 | 7.27e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 120 | 0.1662 | 0.1196 / 0.214 | 6.336e-10 | 1e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 120 | 0.03986 | -0.05688 / 0.1335 | 0.3127 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -0.1407 | -0.1914 / -0.08914 | 1.144e-08 | 1.73e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.1462 | 0.07959 / 0.2175 | 8.072e-05 | 0.008557 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.04545 | -0.01471 / 0.1075 | 0.8025 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | 0.2869 | 0.2241 / 0.3535 | 7.29e-15 | 0 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.1861 | 0.1244 / 0.2535 | 2.341e-08 | 3.44e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | -0.1008 | -0.1765 / -0.0272 | 0.0005653 | 0.05596 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 120 | -0.1207 | -0.163 / -0.07906 | 5.153e-08 | 7.27e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 120 | 0.1662 | 0.1196 / 0.214 | 6.336e-10 | 1e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | interaction | 120 | 0.03986 | -0.05688 / 0.1335 | 0.3127 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -0.1407 | -0.1914 / -0.08914 | 1.144e-08 | 1.73e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.1462 | 0.07959 / 0.2175 | 8.072e-05 | 0.008557 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.04545 | -0.01471 / 0.1075 | 0.8025 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | 0.2869 | 0.2241 / 0.3535 | 7.29e-15 | 0 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.1861 | 0.1244 / 0.2535 | 2.341e-08 | 3.44e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | -0.1008 | -0.1765 / -0.0272 | 0.0005653 | 0.05596 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 120 | -0.1207 | -0.163 / -0.07906 | 5.153e-08 | 7.27e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 120 | 0.1662 | 0.1196 / 0.214 | 6.336e-10 | 1e-07 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | interaction | 120 | 0.03986 | -0.05688 / 0.1335 | 0.3127 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -0.1407 | -0.1914 / -0.08914 | 1.144e-08 | 1.73e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.1462 | 0.07959 / 0.2175 | 8.072e-05 | 0.008557 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.04545 | -0.01471 / 0.1075 | 0.8025 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | 0.2869 | 0.2241 / 0.3535 | 7.29e-15 | 0 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.1861 | 0.1244 / 0.2535 | 2.341e-08 | 3.44e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | -0.1008 | -0.1765 / -0.0272 | 0.0005653 | 0.05596 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 59 | -0.1598 | -0.2089 / -0.115 | 6.928e-08 | 9.49e-06 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 59 | 0.07679 | 0.03625 / 0.1202 | 0.002697 | 0.1942 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | interaction | 59 | -0.05114 | -0.1646 / 0.05009 | 0.3958 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 77 | -0.1487 | -0.2054 / -0.08904 | 3.626e-07 | 4.75e-05 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 75 | 0.107 | 0.03738 / 0.1848 | 0.009267 | 0.5375 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 60 | -0.07437 | -0.1297 / -0.01628 | 0.004647 | 0.3113 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 79 | 0.2537 | 0.1918 / 0.3193 | 4.847e-11 | 1e-08 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 65 | 0.05147 | 0.005975 / 0.09503 | 0.02458 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 64 | -0.1777 | -0.2488 / -0.1085 | 1.069e-06 | 0.0001347 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 120 | 1.27 | -0.6681 / 3.179 | 0.02812 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 120 | 3.368 | 1.613 / 5.178 | 1.862e-06 | 0.0002327 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | interaction | 120 | 7.791 | 4.174 / 11.92 | 0.001903 | 0.1427 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -2.626 | -5.153 / -0.2846 | 1.912e-07 | 2.563e-05 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -0.5278 | -2.796 / 1.601 | 0.09236 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 4.638 | 1.543 / 7.884 | 0.4474 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | 2.098 | 0.2675 / 4.13 | 4.677e-10 | 8e-08 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 7.264 | 4.405 / 10.39 | 3.401e-07 | 4.489e-05 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 5.166 | 2.285 / 8.207 | 0.6836 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | multiscale_main | 55 | -0.1638 | -0.2158 / -0.1159 | 9.663e-08 | 1.314e-05 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | early_stop_main | 55 | 0.08755 | 0.04669 / 0.1323 | 0.0006013 | 0.05713 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | interaction | 55 | -0.07309 | -0.1899 / 0.02984 | 0.1926 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 75 | -0.1495 | -0.2087 / -0.08855 | 4.648e-07 | 5.903e-05 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 71 | 0.1241 | 0.05256 / 0.2035 | 0.001813 | 0.1378 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 58 | -0.0702 | -0.127 / -0.009751 | 0.009076 | 0.5355 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 75 | 0.2654 | 0.2005 / 0.3324 | 2.811e-11 | 0 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 63 | 0.05559 | 0.01115 / 0.09949 | 0.01736 | 0.9547 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 61 | -0.1913 | -0.2659 / -0.1229 | 4.599e-07 | 5.887e-05 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 120 | 0.494 | -1.694 / 2.562 | 0.01229 | 0.6884 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 120 | 3.982 | 2.027 / 5.989 | 4.333e-07 | 5.59e-05 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | interaction | 120 | 7.051 | 2.884 / 11.45 | 0.01083 | 0.6172 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -3.032 | -5.719 / -0.5544 | 1.527e-07 | 2.061e-05 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.4561 | -2.244 / 3.245 | 0.03206 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 4.476 | 1.336 / 7.756 | 0.4232 | 1 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | 3.488 | 1.017 / 6.249 | 4.146e-10 | 7e-08 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 7.507 | 4.535 / 10.75 | 3.33e-07 | 4.429e-05 |
| DeepSeek-V4.1-Flash | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 4.02 | 0.6353 / 7.451 | 0.447 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 74 | -0.6149 | -2.973 / 1.601 | 0.5947 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 74 | -8.372 | -11.72 / -5.25 | 2.275e-06 | 0.0002867 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | interaction | 74 | 5.662 | 2.162 / 9.568 | 0.007363 | 0.6258 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -3.446 | -7.027 / -0.527 | 0.1172 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -11.2 | -15.73 / -7.162 | 6.111e-07 | 8.861e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -8.986 | -13.03 / -5.486 | 1.178e-06 | 0.0001532 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -7.757 | -11.89 / -3.621 | 7.98e-05 | 0.008937 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -5.541 | -8.743 / -2.473 | 3.769e-05 | 0.004372 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 2.216 | -0.2297 / 4.838 | 0.1011 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 74 | -0.6149 | -2.973 / 1.601 | 0.5947 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 74 | -8.372 | -11.72 / -5.25 | 2.275e-06 | 0.0002867 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 74 | 5.662 | 2.162 / 9.568 | 0.007363 | 0.6258 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -3.446 | -7.027 / -0.527 | 0.1172 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -11.2 | -15.73 / -7.162 | 6.111e-07 | 8.861e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -8.986 | -13.03 / -5.486 | 1.178e-06 | 0.0001532 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -7.757 | -11.89 / -3.621 | 7.98e-05 | 0.008937 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -5.541 | -8.743 / -2.473 | 3.769e-05 | 0.004372 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 2.216 | -0.2297 / 4.838 | 0.1011 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 74 | -0.6149 | -2.973 / 1.601 | 0.5947 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 74 | -8.372 | -11.72 / -5.25 | 2.275e-06 | 0.0002867 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | interaction | 74 | 5.662 | 2.162 / 9.568 | 0.007363 | 0.6258 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -3.446 | -7.027 / -0.527 | 0.1172 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -11.2 | -15.73 / -7.162 | 6.111e-07 | 8.861e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -8.986 | -13.03 / -5.486 | 1.178e-06 | 0.0001532 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -7.757 | -11.89 / -3.621 | 7.98e-05 | 0.008937 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -5.541 | -8.743 / -2.473 | 3.769e-05 | 0.004372 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 2.216 | -0.2297 / 4.838 | 0.1011 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 74 | -0.6149 | -2.973 / 1.601 | 0.5947 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 74 | -8.372 | -11.72 / -5.25 | 2.275e-06 | 0.0002867 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | interaction | 74 | 5.662 | 2.162 / 9.568 | 0.007363 | 0.6258 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -3.446 | -7.027 / -0.527 | 0.1172 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -11.2 | -15.73 / -7.162 | 6.111e-07 | 8.861e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -8.986 | -13.03 / -5.486 | 1.178e-06 | 0.0001532 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -7.757 | -11.89 / -3.621 | 7.98e-05 | 0.008937 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -5.541 | -8.743 / -2.473 | 3.769e-05 | 0.004372 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 2.216 | -0.2297 / 4.838 | 0.1011 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 43 | 1.174 | -1.198 / 3.488 | 0.2172 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 43 | -9.407 | -14.06 / -5.081 | 0.0001857 | 0.01876 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | interaction | 43 | 3.558 | -0.6279 / 8.093 | 0.2155 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 47 | -0.8298 | -3.319 / 1.149 | 0.8842 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 44 | -10.95 | -16.39 / -5.909 | 0.0001936 | 0.01916 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 47 | -7.766 | -12.15 / -3.872 | 0.0001451 | 0.0148 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 47 | -11.4 | -16.89 / -6.277 | 8.868e-05 | 0.009577 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 49 | -7.02 | -11.31 / -3.265 | 0.0003337 | 0.03104 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 48 | 3.396 | -0.08333 / 7.271 | 0.05326 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 74 | -32.25 | -69.41 / 2.007 | 0.9305 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 74 | -10.94 | -56.41 / 32.21 | 0.01076 | 0.8612 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | interaction | 74 | 19.23 | -69.77 / 116.8 | 0.3766 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -41.86 | -106.5 / 16.65 | 0.3812 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -20.55 | -97.94 / 55.23 | 0.007119 | 0.6123 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -43.19 | -100.1 / 4.568 | 0.0002999 | 0.02819 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 21.31 | -37.41 / 84.79 | 0.01651 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -1.324 | -50.65 / 48.12 | 0.005206 | 0.4581 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | -22.64 | -79.95 / 31.45 | 0.3548 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | multiscale_main | 42 | 1.155 | -1.25 / 3.583 | 0.2637 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | early_stop_main | 42 | -9.512 | -14.24 / -5.155 | 0.0002621 | 0.02516 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | interaction | 42 | 3.548 | -0.7143 / 8.167 | 0.2607 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 46 | -0.8478 | -3.37 / 1.239 | 0.8842 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 43 | -11.05 | -16.65 / -5.977 | 0.0002638 | 0.02516 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 46 | -7.87 | -12.24 / -3.913 | 0.0001898 | 0.01898 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 46 | -11.5 | -17.22 / -6.217 | 0.00012 | 0.01248 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 48 | -7.104 | -11.54 / -3.208 | 0.0004212 | 0.03833 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 47 | 3.383 | -0.2553 / 7.426 | 0.06881 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 74 | -32.28 | -69.41 / 1.98 | 0.853 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 74 | -10.87 | -56.35 / 32.24 | 0.0135 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | interaction | 74 | 19.18 | -69.87 / 116.8 | 0.4249 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -41.86 | -106.5 / 16.65 | 0.3812 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -20.46 | -97.84 / 55.41 | 0.008901 | 0.7209 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -43.15 | -99.99 / 4.635 | 0.000382 | 0.03515 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 21.41 | -37.31 / 84.87 | 0.02052 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -1.284 | -50.64 / 48.16 | 0.006361 | 0.5534 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | -22.69 | -80 / 31.39 | 0.4161 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 100 | 18.47 | -65.96 / 110.3 | 0.6388 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 100 | -359.3 | -441.1 / -276.7 | 5.3e-12 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | interaction | 100 | -85.56 | -246.9 / 51.72 | 0.7547 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | 61.25 | -61.51 / 216.8 | 0.8533 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | -316.6 | -438.2 / -182.3 | 6.975e-10 | 1.1e-07 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | -340.9 | -468.5 / -198.9 | 8.89e-11 | 1e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | -377.8 | -478.6 / -271.7 | 3.166e-10 | 5e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | -402.1 | -493 / -308.9 | 8.568e-13 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -24.31 | -111.2 / 56.98 | 0.7353 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 100 | 18.47 | -65.96 / 110.3 | 0.6388 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 100 | -359.3 | -441.1 / -276.7 | 5.3e-12 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 100 | -85.56 | -246.9 / 51.72 | 0.7547 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | 61.25 | -61.51 / 216.8 | 0.8533 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | -316.6 | -438.2 / -182.3 | 6.975e-10 | 1.1e-07 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | -340.9 | -468.5 / -198.9 | 8.89e-11 | 1e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | -377.8 | -478.6 / -271.7 | 3.166e-10 | 5e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | -402.1 | -493 / -308.9 | 8.568e-13 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -24.31 | -111.2 / 56.98 | 0.7353 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 98 | -26.98 | -93.81 / 31.44 | 0.8969 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 98 | -378.5 | -457 / -300.7 | 5.197e-13 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | interaction | 98 | -5.255 | -104.2 / 92.32 | 0.4987 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | 61.25 | -61.51 / 216.8 | 0.8533 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 98 | -375.9 | -474.9 / -276.7 | 1.973e-11 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 98 | -405.5 | -510.8 / -308.6 | 2.032e-12 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 98 | -351.6 | -452.7 / -247.9 | 8.573e-10 | 1.3e-07 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 98 | -381.2 | -468.5 / -291.7 | 2.249e-12 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 98 | -29.61 | -119.6 / 54.26 | 0.8697 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 100 | 16.11 | -66.67 / 104.1 | 0.6388 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 100 | 2132 | -414.1 / 6004 | 2.674e-11 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | interaction | 100 | -90.27 | -257.9 / 51.05 | 0.7547 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | 61.25 | -61.51 / 216.8 | 0.8533 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 2177 | -420.7 / 6105 | 6.975e-10 | 1.1e-07 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 2148 | -449.5 / 6082 | 9.095e-11 | 1e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | 2116 | -398.1 / 5930 | 2.027e-08 | 3.02e-06 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 2087 | -421 / 5893 | 9.962e-11 | 2e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -29.02 | -115.8 / 51.91 | 0.8697 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 120 | 0.02981 | -0.01233 / 0.07399 | 0.2999 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 120 | -0.1444 | -0.1873 / -0.1038 | 6.686e-11 | 1e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | interaction | 120 | -0.05707 | -0.1238 / 0.007036 | 0.1089 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.05834 | -0.006099 / 0.1254 | 0.08079 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -0.1159 | -0.1719 / -0.06195 | 6.852e-07 | 9.661e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -0.1146 | -0.1758 / -0.05188 | 1.005e-06 | 0.0001356 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1743 | -0.2364 / -0.1168 | 4.465e-10 | 7e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -0.173 | -0.2266 / -0.1254 | 9.134e-13 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.001275 | -0.03991 / 0.04181 | 0.6722 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 120 | 0.02981 | -0.01233 / 0.07399 | 0.2999 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 120 | -0.1444 | -0.1873 / -0.1038 | 6.686e-11 | 1e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 120 | -0.05707 | -0.1238 / 0.007036 | 0.1089 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.05834 | -0.006099 / 0.1254 | 0.08079 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -0.1159 | -0.1719 / -0.06195 | 6.852e-07 | 9.661e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -0.1146 | -0.1758 / -0.05188 | 1.005e-06 | 0.0001356 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1743 | -0.2364 / -0.1168 | 4.465e-10 | 7e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -0.173 | -0.2266 / -0.1254 | 9.134e-13 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.001275 | -0.03991 / 0.04181 | 0.6722 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 120 | 0.02981 | -0.01233 / 0.07399 | 0.2999 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 120 | -0.1444 | -0.1873 / -0.1038 | 6.686e-11 | 1e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | interaction | 120 | -0.05707 | -0.1238 / 0.007036 | 0.1089 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.05834 | -0.006099 / 0.1254 | 0.08079 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -0.1159 | -0.1719 / -0.06195 | 6.852e-07 | 9.661e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -0.1146 | -0.1758 / -0.05188 | 1.005e-06 | 0.0001356 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1743 | -0.2364 / -0.1168 | 4.465e-10 | 7e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -0.173 | -0.2266 / -0.1254 | 9.134e-13 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.001275 | -0.03991 / 0.04181 | 0.6722 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 120 | 0.02981 | -0.01233 / 0.07399 | 0.2999 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 120 | -0.1444 | -0.1873 / -0.1038 | 6.686e-11 | 1e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | interaction | 120 | -0.05707 | -0.1238 / 0.007036 | 0.1089 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.05834 | -0.006099 / 0.1254 | 0.08079 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -0.1159 | -0.1719 / -0.06195 | 6.852e-07 | 9.661e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -0.1146 | -0.1758 / -0.05188 | 1.005e-06 | 0.0001356 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1743 | -0.2364 / -0.1168 | 4.465e-10 | 7e-08 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -0.173 | -0.2266 / -0.1254 | 9.134e-13 | 0 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.001275 | -0.03991 / 0.04181 | 0.6722 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 60 | -0.002628 | -0.03704 / 0.03133 | 0.9009 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 60 | -0.1184 | -0.1619 / -0.07397 | 4.757e-06 | 0.0005756 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | interaction | 60 | 0.003149 | -0.06063 / 0.06608 | 0.877 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 63 | -0.003238 | -0.05876 / 0.05014 | 0.6822 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 68 | -0.1174 | -0.1804 / -0.05265 | 0.0001009 | 0.01079 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 65 | -0.1147 | -0.1779 / -0.05087 | 0.0001094 | 0.01149 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 69 | -0.1016 | -0.1415 / -0.05956 | 5.365e-06 | 0.0006438 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 68 | -0.117 | -0.1544 / -0.07973 | 9.429e-08 | 1.396e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | -0.002798 | -0.03677 / 0.03353 | 0.3511 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 120 | 0.7823 | -1.202 / 2.759 | 0.3372 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 120 | -2.969 | -5.3 / -0.9125 | 4.347e-06 | 0.0005303 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | interaction | 120 | -0.7209 | -4.556 / 3.06 | 0.6 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 1.143 | -2.007 / 4.367 | 0.4595 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -2.608 | -5.5 / 0.04928 | 0.0002182 | 0.02138 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -2.186 | -5.294 / 0.7083 | 0.001654 | 0.1489 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -3.751 | -6.791 / -1.037 | 7.157e-07 | 9.806e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -3.329 | -6.515 / -0.514 | 1.985e-07 | 2.898e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.4219 | -1.848 / 2.635 | 0.7343 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | multiscale_main | 59 | -0.004241 | -0.03917 / 0.02949 | 0.7686 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | early_stop_main | 59 | -0.1184 | -0.1638 / -0.07315 | 6.72e-06 | 0.000793 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | interaction | 59 | 0.00345 | -0.06018 / 0.06783 | 0.9198 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 63 | -0.003238 | -0.05876 / 0.05014 | 0.6822 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 68 | -0.1174 | -0.1804 / -0.05265 | 0.0001009 | 0.01079 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 64 | -0.1161 | -0.1795 / -0.0519 | 0.0001254 | 0.01292 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 69 | -0.1016 | -0.1415 / -0.05956 | 5.365e-06 | 0.0006438 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 67 | -0.1169 | -0.1541 / -0.07918 | 1.371e-07 | 2.016e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 73 | -0.004004 | -0.03874 / 0.0322 | 0.2781 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 120 | 0.9856 | -1.025 / 2.999 | 0.3119 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 120 | -2.766 | -5.15 / -0.6227 | 1.546e-05 | 0.001809 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | interaction | 120 | -0.3145 | -4.175 / 3.565 | 0.75 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 1.143 | -2.007 / 4.367 | 0.4595 | 1 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -2.608 | -5.5 / 0.04928 | 0.0002182 | 0.02138 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -1.78 | -4.977 / 1.239 | 0.003723 | 0.3313 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -3.751 | -6.791 / -1.037 | 7.157e-07 | 9.806e-05 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -2.923 | -6.219 / 0.01469 | 1.07e-06 | 0.0001401 |
| DeepSeek-V4.1-Flash | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.8283 | -1.541 / 3.187 | 0.8043 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 74 | 10.19 | 6.918 / 14.01 | 1.569e-09 | 2.2e-07 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 74 | 0.3514 | -3.014 / 4.142 | 0.6627 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | interaction | 74 | 0.1081 | -5.446 / 6.716 | 0.628 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 10.14 | 6.486 / 14.04 | 9.131e-07 | 0.0001105 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 0.2973 | -4.014 / 4.459 | 0.3768 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 10.54 | 5.824 / 15.68 | 3.545e-06 | 0.0004148 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -9.838 | -15.08 / -4.919 | 3.279e-07 | 4.164e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 0.4054 | -4.432 / 5.486 | 0.9881 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 10.24 | 5.622 / 16.53 | 2.166e-07 | 2.924e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 74 | 10.19 | 6.918 / 14.01 | 1.569e-09 | 2.2e-07 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 74 | 0.3514 | -3.014 / 4.142 | 0.6627 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 74 | 0.1081 | -5.446 / 6.716 | 0.628 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 10.14 | 6.486 / 14.04 | 9.131e-07 | 0.0001105 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 0.2973 | -4.014 / 4.459 | 0.3768 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 10.54 | 5.824 / 15.68 | 3.545e-06 | 0.0004148 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -9.838 | -15.08 / -4.919 | 3.279e-07 | 4.164e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 0.4054 | -4.432 / 5.486 | 0.9881 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 10.24 | 5.622 / 16.53 | 2.166e-07 | 2.924e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 74 | 10.19 | 6.918 / 14.01 | 1.569e-09 | 2.2e-07 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 74 | 0.3514 | -3.014 / 4.142 | 0.6627 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | interaction | 74 | 0.1081 | -5.446 / 6.716 | 0.628 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 10.14 | 6.486 / 14.04 | 9.131e-07 | 0.0001105 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 0.2973 | -4.014 / 4.459 | 0.3768 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 10.54 | 5.824 / 15.68 | 3.545e-06 | 0.0004148 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -9.838 | -15.08 / -4.919 | 3.279e-07 | 4.164e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 0.4054 | -4.432 / 5.486 | 0.9881 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 10.24 | 5.622 / 16.53 | 2.166e-07 | 2.924e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 74 | 10.19 | 6.918 / 14.01 | 1.569e-09 | 2.2e-07 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 74 | 0.3514 | -3.014 / 4.142 | 0.6627 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | interaction | 74 | 0.1081 | -5.446 / 6.716 | 0.628 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 10.14 | 6.486 / 14.04 | 9.131e-07 | 0.0001105 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 0.2973 | -4.014 / 4.459 | 0.3768 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 10.54 | 5.824 / 15.68 | 3.545e-06 | 0.0004148 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -9.838 | -15.08 / -4.919 | 3.279e-07 | 4.164e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 0.4054 | -4.432 / 5.486 | 0.9881 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 10.24 | 5.622 / 16.53 | 2.166e-07 | 2.924e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 38 | 7.934 | 4.5 / 11.82 | 4.536e-05 | 0.004536 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 38 | -0.09211 | -2.789 / 2.487 | 0.5175 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | interaction | 38 | -2.026 | -6.974 / 2.947 | 0.6057 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 44 | 8.773 | 4.613 / 13.32 | 0.0003647 | 0.03137 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 45 | 1.733 | -1.4 / 5.023 | 0.2489 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 42 | 7.857 | 3.5 / 12.24 | 0.0003285 | 0.0289 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 44 | -7.295 | -11.55 / -3.909 | 3.985e-05 | 0.004064 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 44 | 0 | -3.546 / 3.341 | 0.5908 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 43 | 6.698 | 3.116 / 10.74 | 0.0001929 | 0.01794 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 74 | 41.15 | -18.06 / 101.4 | 0.0005733 | 0.04701 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 74 | 23.18 | -36.56 / 91.29 | 0.3525 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | interaction | 74 | 12.62 | -81.7 / 111.4 | 0.9224 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 34.84 | -40.57 / 115.3 | 0.006008 | 0.3184 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 16.86 | -68.8 / 102 | 0.3114 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 64.32 | -18.07 / 156.3 | 0.002572 | 0.1749 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -17.97 | -107.2 / 68.14 | 0.002694 | 0.1805 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 29.49 | -43.3 / 110.3 | 0.3767 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 47.46 | -24.64 / 128 | 0.001529 | 0.1055 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | multiscale_main | 37 | 8.176 | 4.595 / 12.2 | 4.433e-05 | 0.004477 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | early_stop_main | 37 | -0.04054 | -2.757 / 2.608 | 0.4993 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | interaction | 37 | -1.865 | -7 / 3.081 | 0.6815 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 43 | 8.907 | 4.698 / 13.44 | 0.0004335 | 0.03598 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 44 | 1.727 | -1.5 / 5.114 | 0.2744 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 41 | 8.122 | 3.585 / 12.54 | 0.0003321 | 0.0289 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 43 | -7.442 | -11.67 / -4 | 4.741e-05 | 0.004694 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 43 | 0.1395 | -3.651 / 3.535 | 0.5137 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 42 | 6.976 | 3.357 / 11 | 0.0001354 | 0.01273 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 74 | 41.16 | -18.05 / 101.4 | 0.0006162 | 0.04991 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 74 | 23.2 | -36.56 / 91.29 | 0.3482 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | interaction | 74 | 12.73 | -81.62 / 111.5 | 0.8662 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 34.8 | -40.64 / 115.3 | 0.006957 | 0.3479 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 16.84 | -68.8 / 102 | 0.3346 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 64.36 | -18.07 / 156.3 | 0.00274 | 0.1805 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -17.96 | -107.2 / 68.15 | 0.003157 | 0.1864 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 29.57 | -43.22 / 110.3 | 0.3307 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 47.53 | -24.52 / 128 | 0.001298 | 0.09086 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 100 | 417.1 | 282.9 / 533.5 | 2.576e-15 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 100 | 175 | 78.81 / 275.1 | 0.004343 | 0.2432 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | interaction | 100 | 292.7 | 114.4 / 475.4 | 0.006234 | 0.3242 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | 270.7 | 125 / 397.7 | 6.943e-10 | 1e-07 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 28.6 | -71.74 / 131.9 | 0.9972 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 592.1 | 403.3 / 769.4 | 6.276e-12 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | -242.1 | -366.9 / -105.1 | 7.506e-07 | 9.232e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 321.3 | 163.2 / 481.3 | 0.0007297 | 0.05692 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | 563.5 | 386.5 / 723.2 | 9.087e-14 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 100 | 417.1 | 282.9 / 533.5 | 2.576e-15 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 100 | 175 | 78.81 / 275.1 | 0.004343 | 0.2432 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 100 | 292.7 | 114.4 / 475.4 | 0.006234 | 0.3242 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | 270.7 | 125 / 397.7 | 6.943e-10 | 1e-07 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 28.6 | -71.74 / 131.9 | 0.9972 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 592.1 | 403.3 / 769.4 | 6.276e-12 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | -242.1 | -366.9 / -105.1 | 7.506e-07 | 9.232e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 321.3 | 163.2 / 481.3 | 0.0007297 | 0.05692 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | 563.5 | 386.5 / 723.2 | 9.087e-14 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 97 | 468.5 | 395.7 / 546.7 | 2.686e-17 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 97 | 178.2 | 78.1 / 285.5 | 0.005119 | 0.2764 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | interaction | 97 | 303.8 | 142.7 / 473.5 | 0.003904 | 0.2264 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 98 | 335.2 | 234.2 / 434.2 | 2.111e-11 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 97 | 26.32 | -69.63 / 128 | 0.901 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 98 | 664.6 | 515.2 / 820.1 | 1.184e-13 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 97 | -290.3 | -391.3 / -191.9 | 8.34e-08 | 1.134e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 321.3 | 163.2 / 481.3 | 0.0007297 | 0.05692 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 97 | 620.4 | 497.1 / 750.6 | 2.578e-15 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 100 | -2798 | -7210 / 457.1 | 3.649e-14 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 100 | 902.4 | 95.34 / 2438 | 0.004069 | 0.232 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | interaction | 100 | -1162 | -4196 / 427.6 | 0.009293 | 0.4553 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | -2217 | -6205 / 377.9 | 7.583e-10 | 1.1e-07 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 1483 | -47.82 / 4476 | 0.9607 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | -1896 | -5928 / 730.8 | 7.079e-12 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | 3701 | -280.4 / 8963 | 4.011e-06 | 0.0004532 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 321.3 | 163.2 / 481.3 | 0.0007297 | 0.05692 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -3379 | -8665 / 602.5 | 1.899e-12 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 120 | 0.2232 | 0.1811 / 0.2676 | 2.02e-18 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 120 | 0.09885 | 0.05226 / 0.1472 | 5.295e-05 | 0.005189 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | interaction | 120 | 0.1604 | 0.08175 / 0.2451 | 0.0002447 | 0.02251 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.143 | 0.08893 / 0.1979 | 2.345e-07 | 3.071e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.01866 | -0.02834 / 0.06693 | 0.5228 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.322 | 0.2507 / 0.3976 | 3.378e-14 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1243 | -0.1775 / -0.07161 | 7.571e-06 | 0.000848 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.179 | 0.1062 / 0.2562 | 1.471e-05 | 0.00156 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.3034 | 0.2416 / 0.3692 | 2.437e-16 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 120 | 0.2232 | 0.1811 / 0.2676 | 2.02e-18 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 120 | 0.09885 | 0.05226 / 0.1472 | 5.295e-05 | 0.005189 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 120 | 0.1604 | 0.08175 / 0.2451 | 0.0002447 | 0.02251 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.143 | 0.08893 / 0.1979 | 2.345e-07 | 3.071e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.01866 | -0.02834 / 0.06693 | 0.5228 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.322 | 0.2507 / 0.3976 | 3.378e-14 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1243 | -0.1775 / -0.07161 | 7.571e-06 | 0.000848 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.179 | 0.1062 / 0.2562 | 1.471e-05 | 0.00156 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.3034 | 0.2416 / 0.3692 | 2.437e-16 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 120 | 0.2232 | 0.1811 / 0.2676 | 2.02e-18 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 120 | 0.09885 | 0.05226 / 0.1472 | 5.295e-05 | 0.005189 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | interaction | 120 | 0.1604 | 0.08175 / 0.2451 | 0.0002447 | 0.02251 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.143 | 0.08893 / 0.1979 | 2.345e-07 | 3.071e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.01866 | -0.02834 / 0.06693 | 0.5228 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.322 | 0.2507 / 0.3976 | 3.378e-14 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1243 | -0.1775 / -0.07161 | 7.571e-06 | 0.000848 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.179 | 0.1062 / 0.2562 | 1.471e-05 | 0.00156 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.3034 | 0.2416 / 0.3692 | 2.437e-16 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 120 | 0.2232 | 0.1811 / 0.2676 | 2.02e-18 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 120 | 0.09885 | 0.05226 / 0.1472 | 5.295e-05 | 0.005189 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | interaction | 120 | 0.1604 | 0.08175 / 0.2451 | 0.0002447 | 0.02251 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.143 | 0.08893 / 0.1979 | 2.345e-07 | 3.071e-05 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.01866 | -0.02834 / 0.06693 | 0.5228 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.322 | 0.2507 / 0.3976 | 3.378e-14 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1243 | -0.1775 / -0.07161 | 7.571e-06 | 0.000848 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.179 | 0.1062 / 0.2562 | 1.471e-05 | 0.00156 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.3034 | 0.2416 / 0.3692 | 2.437e-16 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 59 | 0.1741 | 0.1362 / 0.2146 | 3.306e-10 | 5e-08 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 59 | 0.06359 | 0.007384 / 0.1204 | 0.02378 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | interaction | 59 | 0.1568 | 0.07891 / 0.2415 | 0.001012 | 0.07489 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 72 | 0.09129 | 0.03618 / 0.1461 | 0.001147 | 0.0826 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 76 | -0.001044 | -0.05555 / 0.05311 | 0.8838 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 67 | 0.2513 | 0.1756 / 0.3298 | 1.546e-08 | 2.13e-06 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 66 | -0.1087 | -0.172 / -0.04535 | 0.00071 | 0.0568 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 62 | 0.1481 | 0.07375 / 0.2238 | 0.00041 | 0.03485 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 66 | 0.2537 | 0.2001 / 0.3085 | 2.257e-11 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 120 | 3.989 | 1.935 / 6.202 | 7.138e-10 | 1e-07 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 120 | 2.538 | 0.2433 / 5.059 | 0.002714 | 0.1805 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | interaction | 120 | -1.416 | -4.81 / 1.735 | 0.09747 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 4.697 | 2.049 / 7.647 | 8.741e-06 | 0.000944 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 3.246 | 0.5806 / 6.202 | 0.2065 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 6.527 | 3.464 / 9.862 | 2.933e-10 | 4e-08 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -1.451 | -4.627 / 1.808 | 0.003055 | 0.1864 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 1.83 | -1.105 / 4.89 | 0.002747 | 0.1805 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 3.281 | 0.8174 / 5.942 | 7.24e-10 | 1e-07 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | multiscale_main | 59 | 0.1741 | 0.1362 / 0.2146 | 3.306e-10 | 5e-08 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | early_stop_main | 59 | 0.06359 | 0.007384 / 0.1204 | 0.02378 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | interaction | 59 | 0.1568 | 0.07891 / 0.2415 | 0.001012 | 0.07489 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 72 | 0.09129 | 0.03618 / 0.1461 | 0.001147 | 0.0826 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 76 | -0.001044 | -0.05555 / 0.05311 | 0.8838 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 67 | 0.2513 | 0.1756 / 0.3298 | 1.546e-08 | 2.13e-06 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 66 | -0.1087 | -0.172 / -0.04535 | 0.00071 | 0.0568 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 62 | 0.1481 | 0.07375 / 0.2238 | 0.00041 | 0.03485 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 66 | 0.2537 | 0.2001 / 0.3085 | 2.257e-11 | 0 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 120 | 3.989 | 1.935 / 6.202 | 7.138e-10 | 1e-07 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 120 | 2.538 | 0.2433 / 5.059 | 0.002714 | 0.1805 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | interaction | 120 | -1.416 | -4.81 / 1.735 | 0.09747 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 4.697 | 2.049 / 7.647 | 8.741e-06 | 0.000944 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 3.246 | 0.5806 / 6.202 | 0.2065 | 1 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 6.527 | 3.464 / 9.862 | 2.933e-10 | 4e-08 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -1.451 | -4.627 / 1.808 | 0.003055 | 0.1864 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 1.83 | -1.105 / 4.89 | 0.002747 | 0.1805 |
| DeepSeek-V4.1-Flash | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 3.281 | 0.8174 / 5.942 | 7.24e-10 | 1e-07 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 74 | 5.588 | 2.155 / 9.824 | 0.000522 | 0.05951 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 74 | -1.818 | -3.635 / -0.1419 | 0.05548 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | interaction | 74 | 4.743 | 0.4324 / 9.324 | 0.01288 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 3.216 | -1.486 / 8.162 | 0.01955 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -4.189 | -8.041 / -0.6757 | 0.0396 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 3.77 | -0.5135 / 8.446 | 0.01727 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -7.405 | -11.72 / -3.838 | 8.719e-06 | 0.001081 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 0.5541 | -0.8787 / 2.189 | 0.4259 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 7.959 | 4.473 / 12.3 | 3.771e-06 | 0.0004902 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 74 | 5.588 | 2.155 / 9.824 | 0.000522 | 0.05951 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 74 | -1.818 | -3.635 / -0.1419 | 0.05548 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 74 | 4.743 | 0.4324 / 9.324 | 0.01288 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 3.216 | -1.486 / 8.162 | 0.01955 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -4.189 | -8.041 / -0.6757 | 0.0396 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 3.77 | -0.5135 / 8.446 | 0.01727 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -7.405 | -11.72 / -3.838 | 8.719e-06 | 0.001081 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 0.5541 | -0.8787 / 2.189 | 0.4259 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 7.959 | 4.473 / 12.3 | 3.771e-06 | 0.0004902 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 74 | 5.588 | 2.155 / 9.824 | 0.000522 | 0.05951 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 74 | -1.818 | -3.635 / -0.1419 | 0.05548 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | interaction | 74 | 4.743 | 0.4324 / 9.324 | 0.01288 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 3.216 | -1.486 / 8.162 | 0.01955 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -4.189 | -8.041 / -0.6757 | 0.0396 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 3.77 | -0.5135 / 8.446 | 0.01727 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -7.405 | -11.72 / -3.838 | 8.719e-06 | 0.001081 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 0.5541 | -0.8787 / 2.189 | 0.4259 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 7.959 | 4.473 / 12.3 | 3.771e-06 | 0.0004902 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 74 | 5.588 | 2.155 / 9.824 | 0.000522 | 0.05951 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 74 | -1.818 | -3.635 / -0.1419 | 0.05548 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | interaction | 74 | 4.743 | 0.4324 / 9.324 | 0.01288 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 3.216 | -1.486 / 8.162 | 0.01955 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -4.189 | -8.041 / -0.6757 | 0.0396 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 3.77 | -0.5135 / 8.446 | 0.01727 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -7.405 | -11.72 / -3.838 | 8.719e-06 | 0.001081 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 0.5541 | -0.8787 / 2.189 | 0.4259 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 7.959 | 4.473 / 12.3 | 3.771e-06 | 0.0004902 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 43 | 5.209 | 2.023 / 8.674 | 0.002087 | 0.2212 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 43 | -1.186 | -3.395 / 0.8953 | 0.3599 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | interaction | 43 | 5.953 | 1.116 / 11.95 | 0.04042 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 48 | 2.062 | -2.73 / 6.042 | 0.04647 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 47 | -4.234 | -8.362 / -0.2766 | 0.09296 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 47 | 3.596 | -0.2984 / 7.17 | 0.03295 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 46 | -6.565 | -10.85 / -3.087 | 9.193e-05 | 0.01094 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 50 | 1.58 | 0.1 / 3.78 | 0.07479 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 45 | 8.222 | 4.822 / 12.33 | 3.062e-06 | 0.0004134 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 74 | 14.28 | -43.58 / 75.76 | 0.04172 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 74 | 12.36 | -26.61 / 51.7 | 0.7519 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | interaction | 74 | 5.189 | -72.8 / 82.91 | 0.118 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 11.69 | -44.96 / 72.84 | 0.06817 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 9.77 | -62.2 / 82.81 | 0.3355 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 26.65 | -34.69 / 92.41 | 0.03447 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -1.919 | -81.07 / 75.72 | 0.005087 | 0.4782 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 14.96 | 0.2162 / 43.49 | 0.04109 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 16.88 | -64.54 / 99.87 | 0.0005644 | 0.06208 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | multiscale_main | 42 | 5.357 | 2.071 / 8.798 | 0.002157 | 0.2265 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | early_stop_main | 42 | -1.214 | -3.5 / 0.9167 | 0.3599 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | interaction | 42 | 5.952 | 1 / 12.02 | 0.05526 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 46 | 2.913 | -1.696 / 6.826 | 0.02028 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 46 | -4.261 | -8.522 / -0.3473 | 0.1059 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 45 | 4.467 | 0.8222 / 7.978 | 0.01586 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 45 | -6.733 | -11.02 / -3.133 | 0.0001001 | 0.01171 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 49 | 1.551 | 0.04082 / 3.837 | 0.1065 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 44 | 8.364 | 4.886 / 12.68 | 3.968e-06 | 0.0004999 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 74 | 8.311 | -53.72 / 72.86 | 0.04916 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 74 | 6.378 | -30.68 / 44.46 | 0.5712 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | interaction | 74 | 17.08 | -57.51 / 92.92 | 0.08191 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -0.2297 | -63.57 / 65.53 | 0.07322 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -2.162 | -71.37 / 68.58 | 0.2372 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 14.69 | -52.16 / 85.8 | 0.04158 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -1.932 | -81.07 / 75.69 | 0.005684 | 0.5116 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 14.92 | 0.1757 / 43.47 | 0.05758 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 16.85 | -64.54 / 99.86 | 0.000709 | 0.07728 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 100 | 310.5 | 193.9 / 424.2 | 1.236e-09 | 2e-07 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 100 | 59.95 | -35.09 / 180.2 | 0.8433 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | interaction | 100 | 27.84 | -116.8 / 167.1 | 0.6133 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | 296.6 | 180.5 / 411.3 | 4.091e-07 | 5.85e-05 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 46.03 | -96.44 / 220.1 | 0.4463 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 370.5 | 248.5 / 497.7 | 7.4e-09 | 1.15e-06 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | -250.6 | -418.3 / -48.48 | 9.487e-08 | 1.414e-05 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 73.87 | -6.185 / 167.1 | 0.8114 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | 324.5 | 165.6 / 470.3 | 1.678e-08 | 2.57e-06 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 100 | 310.5 | 193.9 / 424.2 | 1.236e-09 | 2e-07 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 100 | 59.95 | -35.09 / 180.2 | 0.8433 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 100 | 27.84 | -116.8 / 167.1 | 0.6133 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | 296.6 | 180.5 / 411.3 | 4.091e-07 | 5.85e-05 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 46.03 | -96.44 / 220.1 | 0.4463 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 370.5 | 248.5 / 497.7 | 7.4e-09 | 1.15e-06 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | -250.6 | -418.3 / -48.48 | 9.487e-08 | 1.414e-05 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 73.87 | -6.185 / 167.1 | 0.8114 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | 324.5 | 165.6 / 470.3 | 1.678e-08 | 2.57e-06 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 16 | 386.1 | 168.5 / 638.2 | 0.004107 | 0.4126 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 16 | -5.406 | -100.4 / 78.72 | 0.816 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | interaction | 16 | 9.188 | -138.4 / 169.4 | 0.9382 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 16 | 381.5 | 156.6 / 630.8 | 0.01048 | 0.9117 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 16 | -10 | -143.8 / 124.1 | 0.8971 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 16 | 380.7 | 202.2 / 580.1 | 0.002703 | 0.2811 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 98 | -351.4 | -472.4 / -231.3 | 4.85e-09 | 7.6e-07 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 73.87 | -6.185 / 167.1 | 0.8114 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 98 | 388.7 | 272.5 / 511.4 | 8.668e-10 | 1.4e-07 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 100 | -2.869e+04 | -3.488e+04 / -2.305e+04 | 1.536e-16 | 0 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 100 | -2.65e+04 | -3.186e+04 / -2.15e+04 | 9.675e-17 | 0 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | interaction | 100 | 5.314e+04 | 4.314e+04 / 6.385e+04 | 3.191e-17 | 0 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | -5.526e+04 | -6.624e+04 / -4.502e+04 | 1.292e-16 | 0 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | -5.307e+04 | -6.38e+04 / -4.306e+04 | 6.123e-17 | 0 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | -5.519e+04 | -6.616e+04 / -4.495e+04 | 1.65e-16 | 0 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | 2198 | -403 / 6162 | 9.487e-08 | 1.414e-05 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 73.87 | -6.185 / 167.1 | 0.8114 | 1 |
| Qwen4-Max | 20261124 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -2124 | -6026 / 440.3 | 2.048e-08 | 3.09e-06 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 120 | 0.1451 | 0.09939 / 0.191 | 1.537e-09 | 2.5e-07 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 120 | 0.04361 | 0.01164 / 0.07691 | 0.004399 | 0.423 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | interaction | 120 | -0.07852 | -0.1361 / -0.02221 | 0.005393 | 0.4962 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.1843 | 0.1323 / 0.2373 | 2.353e-10 | 4e-08 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.08286 | 0.02482 / 0.1429 | 0.004272 | 0.423 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.1887 | 0.1333 / 0.2451 | 4.695e-10 | 8e-08 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1015 | -0.1567 / -0.04455 | 3.113e-06 | 0.0004172 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.004349 | -0.01116 / 0.02387 | 0.1092 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.1058 | 0.05012 / 0.1606 | 1.259e-06 | 0.0001775 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 120 | 0.1451 | 0.09939 / 0.191 | 1.537e-09 | 2.5e-07 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 120 | 0.04361 | 0.01164 / 0.07691 | 0.004399 | 0.423 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 120 | -0.07852 | -0.1361 / -0.02221 | 0.005393 | 0.4962 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.1843 | 0.1323 / 0.2373 | 2.353e-10 | 4e-08 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.08286 | 0.02482 / 0.1429 | 0.004272 | 0.423 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.1887 | 0.1333 / 0.2451 | 4.695e-10 | 8e-08 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1015 | -0.1567 / -0.04455 | 3.113e-06 | 0.0004172 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.004349 | -0.01116 / 0.02387 | 0.1092 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.1058 | 0.05012 / 0.1606 | 1.259e-06 | 0.0001775 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 105 | 0.1432 | 0.09511 / 0.19 | 3.973e-09 | 6.3e-07 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 105 | 0.04973 | 0.01551 / 0.08732 | 0.003625 | 0.3697 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | interaction | 105 | -0.08784 | -0.1499 / -0.02873 | 0.006582 | 0.5858 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 105 | 0.1871 | 0.1337 / 0.2424 | 3.635e-10 | 6e-08 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 105 | 0.09365 | 0.03234 / 0.1587 | 0.004085 | 0.4126 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 105 | 0.1929 | 0.1356 / 0.2524 | 5.813e-10 | 1e-07 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1015 | -0.1567 / -0.04455 | 3.113e-06 | 0.0004172 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.004349 | -0.01116 / 0.02387 | 0.1092 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.1058 | 0.05012 / 0.1606 | 1.259e-06 | 0.0001775 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 120 | -2.916 | -4.529 / -1.523 | 0.009272 | 0.816 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 120 | -3.018 | -4.625 / -1.623 | 0.87 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | interaction | 120 | 6.044 | 3.255 / 9.263 | 0.9948 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -5.938 | -9.168 / -3.149 | 0.003544 | 0.3651 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -6.04 | -9.261 / -3.253 | 0.904 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -5.934 | -9.165 / -3.144 | 0.004292 | 0.423 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1015 | -0.1567 / -0.04455 | 3.113e-06 | 0.0004172 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.004349 | -0.01116 / 0.02387 | 0.1092 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.1058 | 0.05012 / 0.1606 | 1.259e-06 | 0.0001775 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 69 | 0.1904 | 0.1416 / 0.2422 | 9.568e-10 | 1.6e-07 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 69 | 0.0459 | 0.007248 / 0.08934 | 0.01819 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | interaction | 69 | -0.062 | -0.1217 / -0.0009693 | 0.02457 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 75 | 0.2051 | 0.14 / 0.2683 | 3.388e-09 | 5.4e-07 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 75 | 0.0393 | -0.04108 / 0.1184 | 0.08869 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 77 | 0.2376 | 0.1726 / 0.3033 | 1.209e-10 | 2e-08 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 73 | -0.1461 | -0.2058 / -0.08724 | 2.987e-06 | 0.0004062 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 80 | 0.01192 | -0.006169 / 0.03886 | 0.3919 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 75 | 0.1648 | 0.1128 / 0.2192 | 2.319e-07 | 3.34e-05 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 120 | 1.171 | -0.7029 / 3.063 | 4.8e-06 | 0.0006 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 120 | 0.2413 | -1.248 / 1.769 | 0.1519 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | interaction | 120 | -1.358 | -4.42 / 1.621 | 0.05033 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 1.85 | -0.7306 / 4.543 | 2.163e-07 | 3.159e-05 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.9201 | -1.742 / 3.656 | 0.0933 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 1.412 | -1.152 / 4.048 | 4.942e-08 | 7.41e-06 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.9296 | -3.252 / 1.31 | 0.0002074 | 0.02385 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -0.4375 | -1.871 / 0.8269 | 0.2137 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.4921 | -1.65 / 2.688 | 9.502e-05 | 0.01121 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | multiscale_main | 61 | 0.1859 | 0.1352 / 0.2363 | 7.067e-09 | 1.1e-06 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | early_stop_main | 61 | 0.04145 | 0.0008917 / 0.08964 | 0.03062 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | interaction | 61 | -0.05073 | -0.1161 / 0.01205 | 0.04743 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 66 | 0.2076 | 0.1489 / 0.2642 | 3.185e-09 | 5.1e-07 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 65 | 0.07006 | 0.003803 / 0.1398 | 0.02803 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 68 | 0.2331 | 0.1694 / 0.2995 | 8.692e-10 | 1.4e-07 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 71 | -0.1498 | -0.2105 / -0.0898 | 2.927e-06 | 0.000401 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 78 | 0.01222 | -0.006346 / 0.04068 | 0.3919 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 73 | 0.1688 | 0.1155 / 0.2246 | 2.257e-07 | 3.273e-05 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 120 | -0.581 | -2.508 / 1.288 | 0.005219 | 0.4854 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 120 | -1.675 | -3.564 / 0.06382 | 0.7987 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | interaction | 120 | 2.475 | -0.9994 / 6.174 | 0.8931 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -1.818 | -4.857 / 1.139 | 0.001923 | 0.2057 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -2.912 | -6.306 / 0.4002 | 0.9353 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -2.256 | -5.28 / 0.6472 | 0.001767 | 0.1908 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -1.094 | -3.458 / 1.166 | 0.000154 | 0.01787 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -0.4375 | -1.871 / 0.8269 | 0.2137 | 1 |
| Qwen4-Max | 20261124 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.6564 | -1.501 / 2.872 | 7.107e-05 | 0.008529 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 74 | -0.3851 | -4.764 / 3.845 | 0.9017 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 74 | 2.466 | -0.1216 / 5.291 | 0.217 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | interaction | 74 | -6.743 | -12.3 / -1.108 | 0.001045 | 0.1213 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 2.986 | -1.122 / 6.865 | 0.04441 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 5.838 | 2.946 / 8.987 | 1.144e-06 | 0.0001681 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 2.081 | -3.757 / 7.838 | 0.572 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 2.851 | -1.284 / 7.23 | 0.3142 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -0.9054 | -5.378 / 3.879 | 0.2327 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | -3.757 | -9.892 / 2.244 | 0.1359 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 74 | -0.3851 | -4.764 / 3.845 | 0.9017 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 74 | 2.466 | -0.1216 / 5.291 | 0.217 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 74 | -6.743 | -12.3 / -1.108 | 0.001045 | 0.1213 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 2.986 | -1.122 / 6.865 | 0.04441 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 5.838 | 2.946 / 8.987 | 1.144e-06 | 0.0001681 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 2.081 | -3.757 / 7.838 | 0.572 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 2.851 | -1.284 / 7.23 | 0.3142 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -0.9054 | -5.378 / 3.879 | 0.2327 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | -3.757 | -9.892 / 2.244 | 0.1359 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 74 | -0.3851 | -4.764 / 3.845 | 0.9017 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 74 | 2.466 | -0.1216 / 5.291 | 0.217 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | interaction | 74 | -6.743 | -12.3 / -1.108 | 0.001045 | 0.1213 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 2.986 | -1.122 / 6.865 | 0.04441 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 5.838 | 2.946 / 8.987 | 1.144e-06 | 0.0001681 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 2.081 | -3.757 / 7.838 | 0.572 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 2.851 | -1.284 / 7.23 | 0.3142 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -0.9054 | -5.378 / 3.879 | 0.2327 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | -3.757 | -9.892 / 2.244 | 0.1359 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 74 | -0.3851 | -4.764 / 3.845 | 0.9017 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 74 | 2.466 | -0.1216 / 5.291 | 0.217 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | interaction | 74 | -6.743 | -12.3 / -1.108 | 0.001045 | 0.1213 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 2.986 | -1.122 / 6.865 | 0.04441 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 5.838 | 2.946 / 8.987 | 1.144e-06 | 0.0001681 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 2.081 | -3.757 / 7.838 | 0.572 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 2.851 | -1.284 / 7.23 | 0.3142 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -0.9054 | -5.378 / 3.879 | 0.2327 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | -3.757 | -9.892 / 2.244 | 0.1359 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 41 | -0.1098 | -5.061 / 5.012 | 0.7066 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 41 | 0.2805 | -2.244 / 2.756 | 0.5714 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | interaction | 41 | -8.317 | -14.15 / -2.927 | 0.008645 | 0.8645 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 49 | 5.204 | 0.9388 / 9.571 | 0.04209 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 50 | 3.82 | 2.1 / 5.56 | 0.0001432 | 0.01819 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 46 | 1.109 | -5.065 / 7.674 | 0.8566 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 46 | 0.6087 | -3.305 / 4.501 | 0.7015 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 44 | -3.864 | -8.682 / 0.7273 | 0.1942 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 43 | -3.977 | -10.58 / 2.628 | 0.2237 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 74 | 47.61 | -12.14 / 108.3 | 0.1549 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 74 | 79.84 | 31.29 / 134.4 | 0.005061 | 0.5466 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | interaction | 74 | -40.76 | -136.4 / 55.47 | 0.03296 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 67.99 | -9.177 / 145.6 | 0.006139 | 0.6323 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 100.2 | 41.85 / 168.4 | 1.553e-06 | 0.000219 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 127.4 | 53.98 / 205.9 | 0.0126 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 32.23 | -46.85 / 117.1 | 0.4572 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 59.46 | -13.28 / 140.4 | 0.8476 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 27.23 | -47.2 / 103.3 | 0.8256 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | multiscale_main | 40 | 0.275 | -4.7 / 5.513 | 0.856 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | early_stop_main | 40 | 0.325 | -2.263 / 2.875 | 0.5503 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | interaction | 40 | -8.45 | -14.45 / -3.075 | 0.01008 | 0.9878 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 48 | 5.604 | 1.312 / 10 | 0.02492 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 48 | 4.146 | 2.438 / 5.938 | 5.205e-05 | 0.006871 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 44 | 1.614 | -4.841 / 8.114 | 0.7216 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 45 | 0.3111 | -3.711 / 4.2 | 0.856 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 43 | -3.884 | -8.791 / 0.8372 | 0.2139 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 42 | -3.667 | -10.4 / 3.238 | 0.2919 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 74 | 32.36 | -25.97 / 91.19 | 0.2907 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 74 | 64.41 | 8.412 / 122.8 | 0.01407 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | interaction | 74 | -24.92 | -115.3 / 66.61 | 0.05885 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 44.82 | -27.53 / 115.1 | 0.009815 | 0.9717 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | 76.86 | 12.85 / 148.2 | 7.889e-06 | 0.001073 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 96.77 | 18.13 / 179 | 0.04574 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | 32.04 | -47.14 / 116.9 | 0.5472 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 51.95 | -22.27 / 134 | 0.9551 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 19.91 | -55.08 / 97.78 | 0.7749 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 100 | 55.05 | -87.25 / 192.9 | 0.2101 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 100 | -7.635 | -95.56 / 81.06 | 0.8581 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | interaction | 100 | -454.5 | -616.3 / -295.3 | 6.155e-09 | 9.7e-07 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | 282.3 | 104.4 / 461 | 5.995e-06 | 0.0008273 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 219.6 | 162.7 / 287.9 | 3.582e-16 | 0 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 47.42 | -102 / 202.1 | 0.6699 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | -62.69 | -241.5 / 116.5 | 0.5881 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | -234.9 | -391.8 / -80.98 | 0.0004501 | 0.05491 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -172.2 | -319 / -25.96 | 0.01255 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 100 | 55.05 | -87.25 / 192.9 | 0.2101 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 100 | -7.635 | -95.56 / 81.06 | 0.8581 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 100 | -454.5 | -616.3 / -295.3 | 6.155e-09 | 9.7e-07 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | 282.3 | 104.4 / 461 | 5.995e-06 | 0.0008273 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 219.6 | 162.7 / 287.9 | 3.582e-16 | 0 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 47.42 | -102 / 202.1 | 0.6699 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | -62.69 | -241.5 / 116.5 | 0.5881 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | -234.9 | -391.8 / -80.98 | 0.0004501 | 0.05491 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -172.2 | -319 / -25.96 | 0.01255 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 10 | 265.1 | 82.75 / 467 | 0.02493 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 10 | 276.4 | 16.29 / 639.5 | 0.1029 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | interaction | 10 | -309.9 | -579.3 / -66.59 | 0.06655 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 10 | 420 | 171.8 / 719.2 | 0.008045 | 0.8126 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 10 | 431.3 | 137.9 / 874.7 | 0.005922 | 0.6158 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 10 | 541.4 | 149.3 / 1080 | 0.03231 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 14 | 158.9 | -90.57 / 424 | 0.2859 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 97 | -254 | -404.2 / -113.7 | 0.0001367 | 0.01749 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 14 | -50.86 | -473.2 / 296.2 | 0.4899 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 100 | -5.38e+04 | -6.454e+04 / -4.432e+04 | 3.896e-17 | 0 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 100 | -1487 | -3032 / -324.2 | 4.165e-05 | 0.005622 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | interaction | 100 | 184.7 | -2873 / 2773 | 0.0001155 | 0.0149 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | -5.389e+04 | -6.462e+04 / -4.433e+04 | 6.538e-17 | 0 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | -1580 | -3391 / -143.5 | 0.9001 | 1 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | -5.529e+04 | -6.59e+04 / -4.58e+04 | 3.78e-17 | 0 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | 5.231e+04 | 4.258e+04 / 6.329e+04 | 3.655e-17 | 0 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | -1395 | -3760 / -139.9 | 8.5e-05 | 0.01105 |
| Qwen4-Max | 20261125 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -5.371e+04 | -6.458e+04 / -4.405e+04 | 5.941e-17 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 120 | 0.2025 | 0.1518 / 0.2538 | 6.277e-12 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 120 | 0.04744 | 0.01454 / 0.0802 | 0.005525 | 0.5857 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | interaction | 120 | -0.2084 | -0.2735 / -0.1448 | 1.81e-08 | 2.82e-06 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.3068 | 0.2479 / 0.3648 | 6.878e-16 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.1517 | 0.1172 / 0.19 | 4.583e-18 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.25 | 0.1934 / 0.3089 | 5.318e-13 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1551 | -0.2168 / -0.09291 | 1.454e-06 | 0.000208 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -0.05678 | -0.112 / -0.003611 | 0.03841 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.09832 | 0.03833 / 0.1594 | 0.001013 | 0.1195 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 120 | 0.2025 | 0.1518 / 0.2538 | 6.277e-12 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 120 | 0.04744 | 0.01454 / 0.0802 | 0.005525 | 0.5857 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 120 | -0.2084 | -0.2735 / -0.1448 | 1.81e-08 | 2.82e-06 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 0.3068 | 0.2479 / 0.3648 | 6.878e-16 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 0.1517 | 0.1172 / 0.19 | 4.583e-18 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.25 | 0.1934 / 0.3089 | 5.318e-13 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.1551 | -0.2168 / -0.09291 | 1.454e-06 | 0.000208 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -0.05678 | -0.112 / -0.003611 | 0.03841 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.09832 | 0.03833 / 0.1594 | 0.001013 | 0.1195 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 78 | 0.1548 | 0.09455 / 0.2162 | 2.12e-06 | 0.0002967 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 78 | 0.03565 | 0.001238 / 0.07064 | 0.07457 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | interaction | 78 | -0.1601 | -0.2343 / -0.08636 | 0.0001873 | 0.0236 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 78 | 0.2348 | 0.1728 / 0.2965 | 2.274e-09 | 3.6e-07 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 78 | 0.1157 | 0.08308 / 0.1508 | 4.334e-11 | 1e-08 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 78 | 0.1904 | 0.1236 / 0.2613 | 8.652e-07 | 0.000128 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 94 | -0.1204 | -0.1809 / -0.05921 | 6.617e-05 | 0.008668 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -0.05678 | -0.112 / -0.003611 | 0.03841 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 94 | 0.06751 | -0.001688 / 0.1365 | 0.02907 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 120 | -13.97 | -18 / -10.09 | 0.002917 | 0.3209 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 120 | -2.825 | -4.27 / -1.533 | 0.1457 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | interaction | 120 | 5.536 | 2.965 / 8.449 | 0.522 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -16.74 | -21.12 / -12.35 | 0.01997 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -5.593 | -8.485 / -3.018 | 0.02944 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -16.8 | -21.18 / -12.4 | 0.00358 | 0.3902 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | 11.15 | 7.361 / 15.19 | 0.3754 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | -0.05678 | -0.112 / -0.003611 | 0.03841 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | -11.2 | -15.24 / -7.411 | 0.02961 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 70 | 0.1902 | 0.1178 / 0.2621 | 5.458e-07 | 8.133e-05 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 70 | -0.004538 | -0.04775 / 0.03918 | 0.5428 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | interaction | 70 | -0.2334 | -0.3144 / -0.157 | 3.554e-07 | 5.331e-05 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 85 | 0.3043 | 0.2345 / 0.378 | 3.666e-12 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 88 | 0.1282 | 0.09095 / 0.1725 | 3.69e-13 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 78 | 0.1937 | 0.1304 / 0.2617 | 2.697e-07 | 4.099e-05 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 78 | -0.1788 | -0.2671 / -0.087 | 5.829e-06 | 0.0008103 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 75 | -0.109 | -0.1797 / -0.04058 | 0.0009225 | 0.1098 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 71 | 0.07596 | -0.0076 / 0.1561 | 0.01571 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 120 | 2.516 | 0.487 / 4.585 | 3.001e-07 | 4.531e-05 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 120 | 3.968 | 2.343 / 5.845 | 0.0003974 | 0.04889 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | interaction | 120 | -2.281 | -6.46 / 1.567 | 4.193e-05 | 0.005622 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | 3.656 | 0.7523 / 6.597 | 1.321e-11 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 5.109 | 2.74 / 7.772 | 5.967e-16 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 6.484 | 4.095 / 9.089 | 4.505e-12 | 0 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | 1.453 | -1.264 / 4.434 | 0.006433 | 0.6561 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 2.828 | 0.08694 / 5.654 | 0.5398 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 1.375 | -1.468 / 4.17 | 0.005387 | 0.5764 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | multiscale_main | 47 | 0.1243 | 0.05476 / 0.189 | 0.0003848 | 0.04771 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | early_stop_main | 47 | -0.007172 | -0.04735 / 0.03477 | 0.5359 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | interaction | 47 | -0.1835 | -0.2652 / -0.09716 | 0.0003017 | 0.03772 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 56 | 0.2175 | 0.1484 / 0.2866 | 2.478e-07 | 3.791e-05 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 60 | 0.085 | 0.05714 / 0.1143 | 2.03e-08 | 3.13e-06 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 52 | 0.116 | 0.05004 / 0.1816 | 0.001242 | 0.1391 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 61 | -0.141 | -0.2079 / -0.06981 | 4.794e-05 | 0.006376 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 73 | -0.1161 | -0.1865 / -0.04739 | 0.0005081 | 0.06097 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 56 | 0.04905 | -0.02581 / 0.1182 | 0.09656 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 120 | -6.835 | -10.62 / -3.103 | 0.1804 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 120 | 0.9731 | -1.035 / 3.009 | 0.742 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | interaction | 120 | 4.519 | 0.2658 / 8.877 | 0.6591 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -9.095 | -13.73 / -4.593 | 0.338 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -1.286 | -4.325 / 1.687 | 0.001787 | 0.1984 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -5.862 | -10.37 / -1.509 | 0.7245 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | 7.809 | 3.768 / 12.01 | 0.3915 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 3.233 | 0.4354 / 6.231 | 0.6113 | 1 |
| Qwen4-Max | 20261125 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | -4.576 | -8.705 / -0.5552 | 0.587 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 74 | 3.081 | 0.5742 / 5.703 | 0.03525 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 74 | -5.405 | -8.216 / -2.899 | 0.0001122 | 0.01582 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | interaction | 74 | 6.27 | -0.122 / 11.96 | 0.001805 | 0.1949 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -0.05405 | -4.081 / 4.392 | 0.2154 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -8.541 | -12.65 / -4.446 | 7.187e-05 | 0.01071 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -2.324 | -5.217 / 0.4865 | 0.143 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -8.486 | -13.03 / -4.283 | 0.0002235 | 0.02906 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -2.27 | -6.365 / 1.446 | 0.832 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 6.216 | 2.554 / 9.838 | 0.0002947 | 0.03684 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 74 | 3.081 | 0.5742 / 5.703 | 0.03525 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 74 | -5.405 | -8.216 / -2.899 | 0.0001122 | 0.01582 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 74 | 6.27 | -0.122 / 11.96 | 0.001805 | 0.1949 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -0.05405 | -4.081 / 4.392 | 0.2154 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -8.541 | -12.65 / -4.446 | 7.187e-05 | 0.01071 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -2.324 | -5.217 / 0.4865 | 0.143 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -8.486 | -13.03 / -4.283 | 0.0002235 | 0.02906 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -2.27 | -6.365 / 1.446 | 0.832 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 6.216 | 2.554 / 9.838 | 0.0002947 | 0.03684 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 74 | 3.081 | 0.5742 / 5.703 | 0.03525 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 74 | -5.405 | -8.216 / -2.899 | 0.0001122 | 0.01582 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | interaction | 74 | 6.27 | -0.122 / 11.96 | 0.001805 | 0.1949 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -0.05405 | -4.081 / 4.392 | 0.2154 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -8.541 | -12.65 / -4.446 | 7.187e-05 | 0.01071 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -2.324 | -5.217 / 0.4865 | 0.143 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -8.486 | -13.03 / -4.283 | 0.0002235 | 0.02906 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -2.27 | -6.365 / 1.446 | 0.832 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 6.216 | 2.554 / 9.838 | 0.0002947 | 0.03684 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 74 | 3.081 | 0.5742 / 5.703 | 0.03525 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 74 | -5.405 | -8.216 / -2.899 | 0.0001122 | 0.01582 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | interaction | 74 | 6.27 | -0.122 / 11.96 | 0.001805 | 0.1949 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | -0.05405 | -4.081 / 4.392 | 0.2154 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -8.541 | -12.65 / -4.446 | 7.187e-05 | 0.01071 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | -2.324 | -5.217 / 0.4865 | 0.143 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -8.486 | -13.03 / -4.283 | 0.0002235 | 0.02906 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | -2.27 | -6.365 / 1.446 | 0.832 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 6.216 | 2.554 / 9.838 | 0.0002947 | 0.03684 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 44 | 0.9773 | -3.011 / 4.693 | 0.6188 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 44 | -2.841 | -5.648 / 0.2389 | 0.0124 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | interaction | 44 | 4.227 | -5.136 / 12.32 | 0.03633 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 47 | -1.426 | -6.34 / 4.128 | 0.1294 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 51 | -4.216 | -9.02 / 0.902 | 0.02882 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 47 | -1.894 | -5.043 / 1.234 | 0.2489 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 50 | -1.48 | -8.82 / 7.58 | 0.04606 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 47 | -0.4681 | -5.362 / 3.787 | 0.5379 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 49 | 4.898 | -1.041 / 10.49 | 0.01341 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 74 | 101.6 | 39.38 / 168.6 | 0.005934 | 0.5696 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 74 | -71.34 | -126.2 / -17.27 | 0.0008491 | 0.09679 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | interaction | 74 | 194.2 | 92.81 / 299.3 | 9.61e-05 | 0.01365 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 4.459 | -68.95 / 79.61 | 0.2906 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -168.4 | -256.5 / -85.88 | 2.581e-05 | 0.003898 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 30.22 | -36.41 / 101.9 | 0.794 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -172.9 | -271.2 / -75.94 | 8.677e-05 | 0.01241 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 25.76 | -35.54 / 92.62 | 0.3418 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 198.6 | 110.2 / 292.5 | 3.999e-06 | 0.0006358 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | multiscale_main | 41 | 2.793 | -0.4027 / 6.098 | 0.2273 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | early_stop_main | 41 | -4.183 | -6.524 / -1.768 | 0.00203 | 0.2091 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | interaction | 41 | 6.902 | -2.488 / 14.98 | 0.003011 | 0.3011 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 46 | -1.522 | -6.587 / 4.152 | 0.1112 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 47 | -6.638 | -10.87 / -2.234 | 0.003284 | 0.3251 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 46 | -1.739 | -4.978 / 1.478 | 0.309 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 45 | -7.8 | -12.27 / -3.311 | 0.002264 | 0.2309 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 46 | -0.2174 | -5.239 / 4.065 | 0.4107 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 46 | 7.826 | 2.913 / 12.7 | 0.0007004 | 0.08055 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 74 | 48.19 | -13.53 / 114.4 | 0.07859 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 74 | -17.85 | -72.22 / 38.2 | 0.01638 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | interaction | 74 | 87.54 | -5.14 / 183.4 | 0.001689 | 0.1875 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 74 | 4.419 | -68.96 / 79.56 | 0.2709 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 74 | -61.62 | -143.4 / 17.88 | 0.001906 | 0.1983 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 74 | 30.34 | -36.34 / 101.9 | 0.88 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 74 | -66.04 | -161.6 / 31.88 | 0.003745 | 0.367 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 74 | 25.92 | -35.53 / 92.8 | 0.2705 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_abp_74 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 91.96 | 8.025 / 177.4 | 0.000128 | 0.01729 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 100 | 131.3 | 48.05 / 218.6 | 0.0003312 | 0.04007 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 100 | 237.4 | 22.16 / 504.8 | 0.846 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | interaction | 100 | 589.4 | 270.9 / 980.6 | 0.001724 | 0.1897 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | -163.4 | -354.4 / -8.038 | 0.4884 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | -57.28 | -204.8 / 87.71 | 0.1914 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 368.7 | 128.4 / 660.4 | 0.05468 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | 106.1 | -118.4 / 380.9 | 0.1967 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 532.1 | 183.8 / 972.2 | 0.04215 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | 426 | 226.6 / 663.2 | 0.0001382 | 0.01852 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 100 | 131.3 | 48.05 / 218.6 | 0.0003312 | 0.04007 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 100 | 237.4 | 22.16 / 504.8 | 0.846 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 100 | 589.4 | 270.9 / 980.6 | 0.001724 | 0.1897 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | -163.4 | -354.4 / -8.038 | 0.4884 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | -57.28 | -204.8 / 87.71 | 0.1914 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 368.7 | 128.4 / 660.4 | 0.05468 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | 106.1 | -118.4 / 380.9 | 0.1967 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 532.1 | 183.8 / 972.2 | 0.04215 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | 426 | 226.6 / 663.2 | 0.0001382 | 0.01852 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 18 | 201.1 | 74.83 / 323.1 | 0.01154 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 18 | 22.78 | -176.2 / 286.2 | 0.3165 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | interaction | 18 | 304.4 | -15.95 / 682.7 | 0.1507 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 98 | -67.03 | -189.6 / 40.54 | 0.7178 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 18 | -129.4 | -278.1 / 26.95 | 0.1387 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 98 | 240.8 | 57.96 / 471.9 | 0.1039 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 18 | -178.3 | -390.7 / 77.51 | 0.04514 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 98 | 307.8 | 77.21 / 608 | 0.08156 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 18 | 353.3 | 138.4 / 600.8 | 0.008975 | 0.8526 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 100 | -2.72e+04 | -3.264e+04 / -2.221e+04 | 4.149e-16 | 0 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 100 | 2.744e+04 | 2.24e+04 / 3.291e+04 | 1.503e-16 | 0 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | interaction | 100 | -5.145e+04 | -6.265e+04 / -4.083e+04 | 2.862e-15 | 0 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 100 | -1479 | -4382 / 15.13 | 0.597 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 100 | 5.316e+04 | 4.328e+04 / 6.377e+04 | 3.137e-16 | 0 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 100 | 235.9 | 54.57 / 463.9 | 0.1039 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 100 | 5.464e+04 | 4.463e+04 / 6.554e+04 | 2.934e-16 | 0 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 100 | 1715 | 127.4 / 4701 | 0.05899 | 1 |
| Qwen4-Max | 20261126 | cvrp_ext_cvrplib_x_100 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 100 | -5.293e+04 | -6.351e+04 / -4.309e+04 | 6.703e-16 | 0 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | multiscale_main | 120 | 0.06341 | 0.02401 / 0.1038 | 0.0001761 | 0.02325 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | early_stop_main | 120 | -0.04761 | -0.08231 / -0.01247 | 0.0005874 | 0.06931 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | interaction | 120 | 0.1958 | 0.1225 / 0.2705 | 3.387e-06 | 0.0005453 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -0.03449 | -0.08623 / 0.01717 | 0.3666 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -0.1455 | -0.1973 / -0.09403 | 1.023e-07 | 1.719e-05 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.0158 | -0.03127 / 0.0634 | 0.6248 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.111 | -0.1693 / -0.05446 | 1.552e-05 | 0.002406 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.05029 | 0.001542 / 0.1004 | 0.03796 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.1613 | 0.1056 / 0.2194 | 4.795e-08 | 8.2e-06 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | multiscale_main | 120 | 0.06341 | 0.02401 / 0.1038 | 0.0001761 | 0.02325 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | early_stop_main | 120 | -0.04761 | -0.08231 / -0.01247 | 0.0005874 | 0.06931 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | interaction | 120 | 0.1958 | 0.1225 / 0.2705 | 3.387e-06 | 0.0005453 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -0.03449 | -0.08623 / 0.01717 | 0.3666 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -0.1455 | -0.1973 / -0.09403 | 1.023e-07 | 1.719e-05 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.0158 | -0.03127 / 0.0634 | 0.6248 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -0.111 | -0.1693 / -0.05446 | 1.552e-05 | 0.002406 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.05029 | 0.001542 / 0.1004 | 0.03796 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 0.1613 | 0.1056 / 0.2194 | 4.795e-08 | 8.2e-06 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | multiscale_main | 113 | 0.07091 | 0.03107 / 0.1097 | 8.313e-05 | 0.01197 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | early_stop_main | 113 | -0.05702 | -0.09163 / -0.02136 | 0.0001239 | 0.01698 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | interaction | 113 | 0.2165 | 0.1415 / 0.2894 | 7.296e-07 | 0.0001204 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -0.03449 | -0.08623 / 0.01717 | 0.3666 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 113 | -0.1653 | -0.2153 / -0.1141 | 4.982e-09 | 8.7e-07 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.0158 | -0.03127 / 0.0634 | 0.6248 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 113 | -0.1279 | -0.1849 / -0.06882 | 1.911e-06 | 0.0003096 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.05029 | 0.001542 / 0.1004 | 0.03796 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 113 | 0.1792 | 0.1225 / 0.2343 | 8.943e-09 | 1.55e-06 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | multiscale_main | 120 | -1.415 | -2.604 / -0.3916 | 0.01181 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | early_stop_main | 120 | 1.43 | 0.4121 / 2.616 | 0.01542 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | interaction | 120 | -2.76 | -5.136 / -0.7319 | 0.0005816 | 0.06921 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -0.03449 | -0.08623 / 0.01717 | 0.3666 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 2.81 | 0.7754 / 5.188 | 2.077e-05 | 0.003178 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | 0.0158 | -0.03127 / 0.0634 | 0.6248 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | 2.845 | 0.8026 / 5.216 | 0.001062 | 0.12 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 0.05029 | 0.001542 / 0.1004 | 0.03796 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | free_fleet | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | -2.795 | -5.163 / -0.7492 | 2.976e-05 | 0.004464 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | multiscale_main | 78 | 0.06967 | 0.02072 / 0.1162 | 0.0006096 | 0.07072 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | early_stop_main | 78 | -0.02967 | -0.07325 / 0.01536 | 0.06271 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | interaction | 78 | 0.2012 | 0.1151 / 0.2905 | 7.989e-06 | 0.001254 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 82 | -0.03404 | -0.09866 / 0.02849 | 0.3488 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 86 | -0.07005 | -0.169 / 0.07428 | 7.991e-05 | 0.01159 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 83 | 0.03584 | -0.02063 / 0.09266 | 0.2012 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 90 | -0.06356 | -0.1423 / 0.02051 | 0.005006 | 0.4856 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 88 | 0.06593 | 0.009283 / 0.1231 | 0.01356 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 90 | 0.1285 | 0.04064 / 0.2071 | 2.463e-05 | 0.003744 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | multiscale_main | 120 | 0.7359 | -1.358 / 2.866 | 0.01465 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | early_stop_main | 120 | -1.999 | -3.748 / -0.2088 | 0.002882 | 0.2911 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | interaction | 120 | 6.021 | 2.346 / 9.857 | 1.084e-06 | 0.0001777 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -2.274 | -5.127 / 0.44 | 0.1025 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | -5.009 | -7.667 / -2.613 | 9.56e-08 | 1.616e-05 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -1.263 | -3.728 / 1.287 | 0.8793 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | -2.735 | -5.725 / 0.2716 | 0.0002619 | 0.033 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 1.011 | -1.478 / 3.801 | 0.072 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | feasible_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | 3.746 | 0.9576 / 6.687 | 5.284e-06 | 0.0008349 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | multiscale_main | 66 | 0.08699 | 0.03366 / 0.1369 | 0.0001251 | 0.01701 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | early_stop_main | 66 | -0.05919 | -0.1045 / -0.01244 | 0.001312 | 0.1469 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | interaction | 66 | 0.2207 | 0.1309 / 0.3137 | 1.445e-05 | 0.002255 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 80 | -0.03229 | -0.0947 / 0.03001 | 0.3672 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 72 | -0.1732 | -0.2302 / -0.1197 | 1.788e-07 | 2.968e-05 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 81 | 0.03176 | -0.02484 / 0.08748 | 0.2186 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 73 | -0.1599 | -0.2287 / -0.08999 | 1.869e-06 | 0.0003046 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 86 | 0.06036 | 0.005095 / 0.1169 | 0.02494 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | common_completed | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 74 | 0.2125 | 0.1491 / 0.2732 | 1.399e-08 | 2.41e-06 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | multiscale_main | 120 | -2.82 | -5.063 / -0.6147 | 0.8998 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | early_stop_main | 120 | 1.962 | -0.1115 / 4.298 | 0.3792 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | interaction | 120 | -1.912 | -5.572 / 1.734 | 0.0729 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_10_multiscale_only_minus_arm_s2_00_base_whitelist | 120 | -1.864 | -4.796 / 0.9808 | 0.1541 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_00_base_whitelist | 120 | 2.918 | 0.02467 / 6.104 | 0.02768 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_00_base_whitelist | 120 | -0.8582 | -3.426 / 1.784 | 0.9802 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_01_earlystop_only_minus_arm_s2_10_multiscale_only | 120 | 4.783 | 1.351 / 8.477 | 0.2665 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_10_multiscale_only | 120 | 1.006 | -1.482 / 3.799 | 0.1068 | 1 |
| Qwen4-Max | 20261126 | cvrp_s2_multiscale_blind_120 | exact_k | returned_before_deadline | penalized_2x | arm_s2_11_combined_minus_arm_s2_01_earlystop_only | 120 | -3.776 | -6.673 / -1.003 | 0.1076 | 1 |
