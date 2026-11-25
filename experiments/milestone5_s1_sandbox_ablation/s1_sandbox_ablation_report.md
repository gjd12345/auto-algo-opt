# S1 CVRP numerical sandbox ablation

Phase **full**, mode **live**. 
Each paired test uses instances from one search seed. Holm–Bonferroni families are defined by suite, model, fleet policy and denominator, across all planned arm comparisons and seeds.

## Completion and tour length by seed

| Suite | Model | Arm | Seed | Fleet | Completion rate | Completed mean length | 2×-penalized mean length |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261124 | free_fleet | 1 | 904.108 | 904.108 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261124 | exact_k | 0.675676 | 913.62 | 1171.55 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261124 | free_fleet | 1 | 910.243 | 910.243 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261124 | exact_k | 0.689189 | 923.569 | 1156.59 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261124 | free_fleet | 1 | 909.77 | 909.77 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261124 | exact_k | 0.675676 | 923.28 | 1168.73 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261125 | free_fleet | 1 | 914.676 | 914.676 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261125 | exact_k | 0.648649 | 902.062 | 1209.01 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261125 | free_fleet | 1 | 914.676 | 914.676 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261125 | exact_k | 0.648649 | 902.062 | 1209.01 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261125 | free_fleet | 1 | 909.514 | 909.514 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261125 | exact_k | 0.662162 | 926.02 | 1178.18 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261126 | free_fleet | 1 | 904.554 | 904.554 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261126 | exact_k | 0.675676 | 913.54 | 1168.88 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261126 | free_fleet | 1 | 903.405 | 903.405 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261126 | exact_k | 0.689189 | 894.902 | 1170.08 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261126 | free_fleet | 1 | 914.676 | 914.676 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261126 | exact_k | 0.648649 | 902.062 | 1209.01 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261127 | free_fleet | 1 | 910.27 | 910.27 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261127 | exact_k | 0.648649 | 934.812 | 1184.23 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261127 | free_fleet | 1 | 910.5 | 910.5 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261127 | exact_k | 0.675676 | 924.34 | 1169.45 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261127 | free_fleet | 1 | 904.554 | 904.554 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261127 | exact_k | 0.662162 | 910.143 | 1183.55 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261128 | free_fleet | 1 | 905.689 | 905.689 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261128 | exact_k | 0.675676 | 919.04 | 1165.86 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261128 | free_fleet | 1 | 909.662 | 909.662 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261128 | exact_k | 0.689189 | 917.451 | 1161.3 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261128 | free_fleet | 1 | 905.689 | 905.689 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261128 | exact_k | 0.675676 | 919.04 | 1165.86 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | 20261124 | free_fleet | 1 | 904.581 | 904.581 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | 20261124 | exact_k | 0.662162 | 911.49 | 1181.34 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | 20261124 | free_fleet | 1 | 896.595 | 896.595 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | 20261124 | exact_k | 0.797297 | 909.119 | 1060.78 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | 20261124 | free_fleet | 1 | 910.203 | 910.203 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | 20261124 | exact_k | 0.648649 | 921.875 | 1191.97 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | 20261125 | free_fleet | 0.986486 | 903.603 | 909.797 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | 20261125 | exact_k | 0.72973 | 925.685 | 1109.61 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | 20261125 | free_fleet | 1 | 905.419 | 905.419 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | 20261125 | exact_k | 0.675676 | 918.62 | 1165.58 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | 20261125 | free_fleet | 1 | 908.189 | 908.189 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | 20261125 | exact_k | 0.594595 | 909.841 | 1239.42 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | 20261126 | free_fleet | 0.986486 | 906.219 | 912.378 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | 20261126 | exact_k | 0.675676 | 891.22 | 1180.15 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | 20261126 | free_fleet | 1 | 905.419 | 905.419 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | 20261126 | exact_k | 0.662162 | 910.49 | 1181.24 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | 20261126 | free_fleet | 1 | 905.176 | 905.176 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | 20261126 | exact_k | 0.675676 | 918.16 | 1165.27 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | 20261127 | free_fleet | 0.986486 | 903.932 | 910.122 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | 20261127 | exact_k | 0.675676 | 905.08 | 1170.43 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | 20261127 | free_fleet | 1 | 904.919 | 904.919 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | 20261127 | exact_k | 0.662162 | 920.449 | 1175.38 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | 20261127 | free_fleet | 1 | 908.108 | 908.108 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | 20261127 | exact_k | 0.662162 | 924.776 | 1177.35 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | 20261128 | free_fleet | 0.986486 | 903.37 | 909.568 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | 20261128 | exact_k | 0.716216 | 901.509 | 1137.57 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | 20261128 | free_fleet | 0.986486 | 911.425 | 917.514 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | 20261128 | exact_k | 0.635135 | 899.766 | 1213.77 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | 20261128 | free_fleet | 1 | 905.365 | 905.365 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | 20261128 | exact_k | 0.662162 | 924.184 | 1172.88 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261124 | free_fleet | 0.95 | 63411.6 | 71357.9 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261124 | free_fleet | 1 | 66309.6 | 66309.6 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261124 | free_fleet | 1 | 66310.7 | 66310.7 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261125 | free_fleet | 1 | 66352.2 | 66352.2 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261125 | free_fleet | 1 | 66352.2 | 66352.2 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261125 | free_fleet | 1 | 66333.2 | 66333.2 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261126 | free_fleet | 0.95 | 63010.4 | 71555.8 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261126 | free_fleet | 0.95 | 62573 | 71943.8 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261126 | free_fleet | 1 | 66352.2 | 66352.2 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261127 | free_fleet | 1 | 66290.5 | 66290.5 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261127 | free_fleet | 1 | 66326.2 | 66326.2 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261127 | free_fleet | 0.95 | 63153.6 | 71389.5 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261128 | free_fleet | 0.96 | 62550.8 | 71101.1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261128 | free_fleet | 1 | 66348.2 | 66348.2 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261128 | free_fleet | 0.96 | 62550.8 | 71101.1 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_0_free_tool | 20261124 | free_fleet | 0.95 | 62463.5 | 71839.7 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_1_slice_only | 20261124 | free_fleet | 0.05 | 31674.6 | 124730 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_2_sandbox_only | 20261124 | free_fleet | 1 | 66315.6 | 66315.6 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_0_free_tool | 20261125 | free_fleet | 0.05 | 32146 | 124753 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_1_slice_only | 20261125 | free_fleet | 0.95 | 61926.8 | 72171.1 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_2_sandbox_only | 20261125 | free_fleet | 0.94 | 62586.4 | 72513.1 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_0_free_tool | 20261126 | free_fleet | 0.05 | 32171.2 | 124755 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_1_slice_only | 20261126 | free_fleet | 0.96 | 63445.3 | 70315.1 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_2_sandbox_only | 20261126 | free_fleet | 0.95 | 62872.3 | 71424.6 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_0_free_tool | 20261127 | free_fleet | 0.05 | 31773.8 | 124735 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_1_slice_only | 20261127 | free_fleet | 0.95 | 62509.6 | 71883.5 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_2_sandbox_only | 20261127 | free_fleet | 1 | 66343 | 66343 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_0_free_tool | 20261128 | free_fleet | 0.05 | 31850 | 124738 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_1_slice_only | 20261128 | free_fleet | 0.04 | 32882.2 | 125040 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_2_sandbox_only | 20261128 | free_fleet | 0.94 | 61772.1 | 72853.5 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261124 | free_fleet | 1 | 24.8899 | 24.8899 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261124 | exact_k | 0.65 | 24.3673 | 38.0027 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261124 | free_fleet | 1 | 24.9512 | 24.9512 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261124 | exact_k | 0.616667 | 23.6191 | 39.6875 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261124 | free_fleet | 1 | 24.9565 | 24.9565 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261124 | exact_k | 0.591667 | 21.0609 | 42.3308 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261125 | free_fleet | 1 | 24.9243 | 24.9243 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261125 | exact_k | 0.608333 | 21.3938 | 41.9663 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261125 | free_fleet | 1 | 24.9243 | 24.9243 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261125 | exact_k | 0.608333 | 21.3938 | 41.9663 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261125 | free_fleet | 1 | 24.9481 | 24.9481 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261125 | exact_k | 0.583333 | 21.5686 | 42.4192 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261126 | free_fleet | 1 | 24.7995 | 24.7995 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261126 | exact_k | 0.641667 | 24.2116 | 38.5153 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261126 | free_fleet | 1 | 24.829 | 24.829 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261126 | exact_k | 0.716667 | 23.435 | 36.3105 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261126 | free_fleet | 1 | 24.9243 | 24.9243 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261126 | exact_k | 0.608333 | 21.3938 | 41.9663 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261127 | free_fleet | 1 | 24.9398 | 24.9398 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261127 | exact_k | 0.591667 | 21.5694 | 42.067 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261127 | free_fleet | 1 | 24.9584 | 24.9584 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261127 | exact_k | 0.608333 | 20.9268 | 42.0252 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261127 | free_fleet | 1 | 24.8131 | 24.8131 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261127 | exact_k | 0.65 | 23.5701 | 38.7552 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261128 | free_fleet | 1 | 24.8199 | 24.8199 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | 20261128 | exact_k | 0.625 | 21.4153 | 40.9797 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261128 | free_fleet | 1 | 24.9586 | 24.9586 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | 20261128 | exact_k | 0.591667 | 21.1161 | 42.3604 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261128 | free_fleet | 1 | 24.8199 | 24.8199 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | 20261128 | exact_k | 0.625 | 21.4153 | 40.9797 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | 20261124 | free_fleet | 1 | 24.7962 | 24.7962 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | 20261124 | exact_k | 0.65 | 23.6205 | 38.5142 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | 20261124 | free_fleet | 0.5 | 15.6703 | 48.6173 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | 20261124 | exact_k | 0.391667 | 14.8927 | 51.5195 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | 20261124 | free_fleet | 1 | 24.938 | 24.938 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | 20261124 | exact_k | 0.608333 | 22.7131 | 40.8082 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | 20261125 | free_fleet | 0.5 | 15.7787 | 48.6715 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | 20261125 | exact_k | 0.383333 | 15.0122 | 51.7567 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | 20261125 | free_fleet | 1 | 24.8188 | 24.8188 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | 20261125 | exact_k | 0.625 | 22.1936 | 40.4917 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | 20261125 | free_fleet | 1 | 24.9218 | 24.9218 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | 20261125 | exact_k | 0.525 | 22.047 | 43.697 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | 20261126 | free_fleet | 0.5 | 15.8065 | 48.6854 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | 20261126 | exact_k | 0.4 | 15.0774 | 51.366 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | 20261126 | free_fleet | 1 | 24.8359 | 24.8359 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | 20261126 | exact_k | 0.616667 | 23.2384 | 39.9849 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | 20261126 | free_fleet | 1 | 24.8114 | 24.8114 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | 20261126 | exact_k | 0.625 | 22.6694 | 40.0158 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | 20261127 | free_fleet | 0.5 | 15.7508 | 48.6575 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | 20261127 | exact_k | 0.408333 | 15.2817 | 50.9963 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | 20261127 | free_fleet | 1 | 24.8339 | 24.8339 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | 20261127 | exact_k | 0.616667 | 23.2474 | 40.061 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | 20261127 | free_fleet | 1 | 24.9642 | 24.9642 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | 20261127 | exact_k | 0.533333 | 21.6583 | 43.6774 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | 20261128 | free_fleet | 0.5 | 15.7632 | 48.6637 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | 20261128 | exact_k | 0.4 | 15.4001 | 51.1905 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | 20261128 | free_fleet | 0.5 | 15.8923 | 48.7283 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | 20261128 | exact_k | 0.383333 | 14.8839 | 52.0264 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | 20261128 | free_fleet | 1 | 24.8144 | 24.8144 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | 20261128 | exact_k | 0.616667 | 22.1778 | 40.8342 |

## Cross-seed sample standard deviations

| Suite | Model | Arm | Fleet | Completion rate SD | Completed mean length SD | Penalized mean length SD |
| --- | --- | --- | --- | ---: | ---: | ---: |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | free_fleet | 0 (5 seeds) | 4.52717 (5 seeds) | 4.52717 (5 seeds) |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | exact_k | 0.0148033 (5 seeds) | 11.9083 (5 seeds) | 17.7092 (5 seeds) |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | free_fleet | 0 (5 seeds) | 4.04091 (5 seeds) | 4.04091 (5 seeds) |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | exact_k | 0.0176195 (5 seeds) | 13.2838 (5 seeds) | 20.7594 (5 seeds) |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | free_fleet | 0 (5 seeds) | 3.98971 (5 seeds) | 3.98971 (5 seeds) |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | exact_k | 0.0113062 (5 seeds) | 9.88874 (5 seeds) | 17.1673 (5 seeds) |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | free_fleet | 0.00604343 (5 seeds) | 1.14466 (5 seeds) | 2.86086 (5 seeds) |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_0_free_tool | exact_k | 0.0292966 (5 seeds) | 12.7685 (5 seeds) | 31.3259 (5 seeds) |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | free_fleet | 0.00604343 (5 seeds) | 5.29115 (5 seeds) | 7.4643 (5 seeds) |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_1_slice_only | exact_k | 0.0636715 (5 seeds) | 8.29126 (5 seeds) | 57.9912 (5 seeds) |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | free_fleet | 0 (5 seeds) | 2.12535 (5 seeds) | 2.12535 (5 seeds) |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | arm_s1_2_sandbox_only | exact_k | 0.031692 (5 seeds) | 6.1267 (5 seeds) | 29.6179 (5 seeds) |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | free_fleet | 0.0258844 (5 seeds) | 1849.53 (5 seeds) | 2752.68 (5 seeds) |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | free_fleet | 0.0223607 (5 seeds) | 1682.09 (5 seeds) | 2508.8 (5 seeds) |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | free_fleet | 0.0248998 (5 seeds) | 1917.93 (5 seeds) | 2693.05 (5 seeds) |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_0_free_tool | free_fleet | 0.402492 (5 seeds) | 13631.4 (5 seeds) | 23660.1 (5 seeds) |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_1_slice_only | free_fleet | 0.497544 (5 seeds) | 16637 (5 seeds) | 29272.6 (5 seeds) |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | arm_s1_2_sandbox_only | free_fleet | 0.031305 (5 seeds) | 2184.18 (5 seeds) | 3293.02 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | free_fleet | 0 (5 seeds) | 0.0624281 (5 seeds) | 0.0624281 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_0_free_tool | exact_k | 0.023863 (5 seeds) | 1.5525 (5 seeds) | 1.92504 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | free_fleet | 0 (5 seeds) | 0.0551102 (5 seeds) | 0.0551102 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_1_slice_only | exact_k | 0.0502079 (5 seeds) | 1.31653 (5 seeds) | 2.55661 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | free_fleet | 0 (5 seeds) | 0.0703208 (5 seeds) | 0.0703208 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | arm_s1_2_sandbox_only | exact_k | 0.0267447 (5 seeds) | 1.00575 (5 seeds) | 1.52784 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | free_fleet | 0.223607 (5 seeds) | 4.03454 (5 seeds) | 10.6765 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_0_free_tool | exact_k | 0.1131 (5 seeds) | 3.77217 (5 seeds) | 5.73707 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | free_fleet | 0.273861 (5 seeds) | 4.95655 (5 seeds) | 13.0595 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_1_slice_only | exact_k | 0.127121 (5 seeds) | 4.4053 (5 seeds) | 6.35564 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | free_fleet | 0 (5 seeds) | 0.0719468 (5 seeds) | 0.0719468 (5 seeds) |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | arm_s1_2_sandbox_only | exact_k | 0.0483764 (5 seeds) | 0.443521 (5 seeds) | 1.74809 (5 seeds) |

## Paired tests by seed

Positive gain means the left arm has shorter tours. Bootstrap intervals use 10,000 resamples.

| Suite | Model | Seed | Left arm | Right arm | Fleet | Denominator | Pairs | Gain (%) | 95% CI (%) | Wilcoxon p | Holm p |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | -0.6786 | -1.2362, -0.1974 | 0.00235806 | 0.0212225 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | -0.6786 | -1.2362, -0.1974 | 0.00235806 | 0.0212225 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 46 | -0.4818 | -0.8888, -0.0596 | 0.00711824 | 0.0640642 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | 1.2769 | -5.4283, 7.8371 | 0.0779686 | 0.623749 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | -0.6263 | -1.1194, -0.1589 | 0.00674309 | 0.0539447 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | -0.6263 | -1.1194, -0.1589 | 0.00674309 | 0.0539447 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 46 | -0.5651 | -1.0288, -0.0997 | 0.00786389 | 0.0640642 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | 0.2411 | -6.1349, 6.4598 | 0.0433911 | 0.39052 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 74 | 0.052 | -0.1408, 0.2565 | 0.507243 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 74 | 0.052 | -0.1408, 0.2565 | 0.507243 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 49 | -0.0176 | -0.25, 0.2158 | 0.808867 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 74 | -1.0492 | -4.3502, 1.6722 | 0.962327 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 48 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | 0.5644 | 0.1848, 0.999 | 0.00889884 | 0.0622919 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0.5644 | 0.1848, 0.999 | 0.00889884 | 0.0622919 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 45 | 0.3901 | -0.0595, 0.8998 | 0.178371 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | 2.5507 | -1.9067, 7.1714 | 0.175242 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 74 | 0.5644 | 0.1848, 0.999 | 0.00889884 | 0.0622919 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 74 | 0.5644 | 0.1848, 0.999 | 0.00889884 | 0.0622919 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 45 | 0.3901 | -0.0595, 0.8998 | 0.178371 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 74 | 2.5507 | -1.9067, 7.1714 | 0.175242 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | 0.127 | -0.3015, 0.55 | 0.166717 | 0.833586 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0.127 | -0.3015, 0.55 | 0.166717 | 0.833586 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 44 | 0.2317 | -0.3221, 0.8115 | 0.0882272 | 0.61759 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | -0.1029 | -7.664, 6.9069 | 0.222923 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | -1.119 | -1.5623, -0.7133 | 2.00317e-08 | 2.6e-07 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | -1.119 | -1.5623, -0.7133 | 2.00317e-08 | 2.6e-07 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 45 | -0.7807 | -1.2028, -0.3684 | 0.000116338 | 0.00133907 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | -3.4336 | -9.6541, 2.0392 | 0.000598576 | 0.00778149 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 74 | -1.2475 | -1.8595, -0.6801 | 3.78176e-05 | 0.00037818 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 74 | -1.2475 | -1.8595, -0.6801 | 3.78176e-05 | 0.00037818 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 43 | -1.1111 | -1.8573, -0.4291 | 0.00367723 | 0.0367723 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 74 | -3.3273 | -10.7983, 3.4727 | 0.0117658 | 0.117658 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | -0.0252 | -0.1544, 0.0885 | 0.767093 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | -0.0252 | -0.1544, 0.0885 | 0.767093 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 48 | 0.0089 | -0.1836, 0.1659 | 0.585283 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | 1.2484 | -0.031, 3.2244 | 0.221039 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | 0.628 | 0.2976, 0.9584 | 1.38449e-05 | 0.00015229 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0.628 | 0.2976, 0.9584 | 1.38449e-05 | 0.00015229 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 45 | 0.6607 | 0.254, 1.0382 | 0.000111589 | 0.00133907 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | 0.0571 | -4.8658, 4.4333 | 0.00152782 | 0.0183338 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 74 | 0.653 | 0.3304, 0.977 | 4.7241e-06 | 5.669e-05 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 74 | 0.653 | 0.3304, 0.977 | 4.7241e-06 | 5.669e-05 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 47 | 0.6932 | 0.3002, 1.0508 | 4.69606e-05 | 0.00061049 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 74 | -1.2064 | -5.8792, 2.8339 | 0.00172014 | 0.0189215 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | -0.4387 | -0.6038, -0.2777 | 3.72336e-09 | 6e-08 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | -0.4387 | -0.6038, -0.2777 | 3.72336e-09 | 6e-08 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 50 | -0.4788 | -0.7056, -0.262 | 8.9464e-07 | 1.342e-05 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | 0.3918 | -0.365, 1.8161 | 8.08955e-06 | 0.00012134 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 50 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 74 | 0.4368 | 0.277, 0.6001 | 3.72336e-09 | 6e-08 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 74 | 0.4368 | 0.277, 0.6001 | 3.72336e-09 | 6e-08 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 50 | 0.4765 | 0.2613, 0.7006 | 8.9464e-07 | 1.342e-05 |
| cvrp_ext_cvrplib_abp_74 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 74 | -0.3933 | -1.8497, 0.3637 | 8.08955e-06 | 0.00012134 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | 0.8829 | 0.4917, 1.2782 | 3.41527e-05 | 0.00044399 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0.8829 | 0.4917, 1.2782 | 3.41527e-05 | 0.00044399 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 47 | 0.6168 | 0.2035, 1.038 | 0.00360602 | 0.0324542 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | 10.2049 | 3.8032, 16.6233 | 7.56474e-05 | 0.00098342 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 74 | -0.6215 | -1.0266, -0.2576 | 8.4301e-05 | 0.00101161 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | -0.6215 | -1.0266, -0.2576 | 8.4301e-05 | 0.00101161 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 47 | -0.5908 | -0.9604, -0.1867 | 0.000355254 | 0.00390779 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | -0.9003 | -4.8057, 2.9354 | 0.000588596 | 0.00647455 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 74 | -1.5178 | -2.1033, -0.9746 | 1.21291e-07 | 1.7e-06 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 74 | -1.5178 | -2.1033, -0.9746 | 1.21291e-07 | 1.7e-06 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 46 | -1.1578 | -1.6639, -0.5995 | 2.38059e-05 | 0.00033328 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 74 | -12.3672 | -21.0203, -4.9337 | 8.24719e-07 | 1.155e-05 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 73 | -0.4912 | -0.9882, 0.053 | 0.00468573 | 0.0328001 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0.4812 | -0.8625, 2.7003 | 0.0110856 | 0.0775995 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 46 | -0.4489 | -0.894, 0.0457 | 0.0106423 | 0.0851384 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | -5.0444 | -12.9472, 2.0955 | 0.0098782 | 0.0691474 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 73 | -0.8004 | -1.4643, -0.1864 | 0.0038497 | 0.0307976 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0.1768 | -1.2666, 2.4633 | 0.00929947 | 0.0743957 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 41 | -0.3774 | -0.7557, 0.0057 | 0.0499372 | 0.34956 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | -11.6988 | -20.6438, -3.5904 | 0.00124674 | 0.0124674 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 74 | -0.306 | -0.7485, 0.0977 | 0.452341 | 0.904682 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 74 | -0.306 | -0.7485, 0.0977 | 0.452341 | 1 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 43 | -0.0469 | -0.4135, 0.2784 | 0.74644 | 1 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 74 | -6.3349 | -13.9438, 0.6907 | 0.197997 | 0.989983 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 73 | -0.201 | -0.6742, 0.2657 | 0.252616 | 0.757847 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0.7628 | -0.5479, 2.978 | 0.37089 | 1 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 46 | -0.2152 | -0.5722, 0.1416 | 0.225973 | 0.903891 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | -0.0928 | -3.8096, 3.7066 | 0.261198 | 0.989983 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 73 | -0.1738 | -0.6117, 0.2999 | 0.0583079 | 0.349847 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0.7894 | -0.5036, 2.9846 | 0.102962 | 0.51481 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 46 | -0.1501 | -0.597, 0.3343 | 0.0754228 | 0.424879 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | 1.2607 | -2.567, 5.4305 | 0.206795 | 0.989983 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 74 | 0.0269 | -0.2875, 0.3478 | 0.727156 | 0.904682 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 74 | 0.0269 | -0.2875, 0.3478 | 0.727156 | 1 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 48 | 0.0023 | -0.3291, 0.3652 | 0.327811 | 0.983433 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 74 | 1.3522 | -1.0491, 4.3479 | 0.611164 | 0.989983 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 73 | -0.3531 | -0.9761, 0.1349 | 0.135174 | 0.540696 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0.5716 | -0.7856, 2.7744 | 0.213838 | 0.855351 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 45 | -0.2084 | -0.6144, 0.2145 | 0.0708132 | 0.424879 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | -0.4226 | -6.3775, 5.0381 | 0.122222 | 0.733331 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 73 | -0.7001 | -1.1113, -0.3221 | 0.00019393 | 0.00199216 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0.2212 | -0.9953, 2.3815 | 0.000605356 | 0.00605356 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 45 | -0.6519 | -1.0056, -0.252 | 0.000152879 | 0.00183455 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | -0.5911 | -6.3446, 4.8246 | 0.00250625 | 0.0225563 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 74 | -0.3524 | -0.6223, -0.04 | 0.000181106 | 0.00199216 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 74 | -0.3524 | -0.6223, -0.04 | 0.000181106 | 0.00199216 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 47 | -0.5882 | -0.8628, -0.3414 | 2.52101e-05 | 0.00033328 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 74 | -0.1679 | -3.9846, 3.5522 | 0.000312338 | 0.00374806 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 73 | -0.8916 | -1.1586, -0.6474 | 5.07723e-11 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | -0.8736 | -1.1491, -0.6365 | 5.07723e-11 | 0 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 47 | -0.6929 | -0.9588, -0.4709 | 7.71118e-08 | 1.16e-06 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | -6.6987 | -12.7834, -2.1221 | 7.63068e-09 | 1.1e-07 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 73 | -0.511 | -0.949, -0.0221 | 0.000653356 | 0.00588021 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 74 | 0.4621 | -0.8387, 2.7082 | 0.00185526 | 0.0166973 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 45 | -0.5326 | -0.9961, 0.0028 | 0.00169411 | 0.0169411 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 74 | -3.1041 | -9.4164, 2.6616 | 0.0036712 | 0.0293696 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 73 | 0.3773 | -0.0097, 0.8095 | 0.0795917 | 0.397959 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 74 | 1.3241 | 0.0852, 3.5035 | 0.0532472 | 0.319483 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 44 | 0.177 | -0.2638, 0.6891 | 0.500348 | 1 |
| cvrp_ext_cvrplib_abp_74 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 74 | 3.369 | -1.0193, 8.1966 | 0.288009 | 0.989983 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 95 | -0.1138 | -0.3026, 0.0667 | 0.0214761 | 0.193285 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 7.0746 | 1.6535, 12.8159 | 0.197865 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 95 | -0.0815 | -0.3069, 0.1395 | 0.0757116 | 0.45427 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 7.0731 | 1.6672, 12.8109 | 0.422061 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 100 | -0.0017 | -0.1513, 0.1529 | 0.599342 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 100 | -0.0017 | -0.1513, 0.1529 | 0.599342 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 100 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 100 | 0.0287 | -0.2064, 0.2479 | 0.053742 | 0.429936 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 0.0287 | -0.2064, 0.2479 | 0.053742 | 0.483678 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 100 | 0.0287 | -0.2064, 0.2479 | 0.053742 | 0.429936 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 100 | 0.0287 | -0.2064, 0.2479 | 0.053742 | 0.483678 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 94 | -0.0122 | -0.1971, 0.1879 | 0.886056 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | -0.5422 | -6.2182, 4.1893 | 0.891001 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 95 | -0.426 | -0.6256, -0.2511 | 3.04675e-07 | 3.96e-06 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 7.2721 | 1.4112, 13.3103 | 9.58777e-05 | 0.00124641 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 95 | -0.3552 | -0.6295, -0.1086 | 0.000162424 | 0.00178666 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 100 | 7.7721 | 1.6836, 13.983 | 0.00802642 | 0.0882906 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 100 | -0.0538 | -0.1573, 0.0442 | 0.502232 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | -0.0538 | -0.1573, 0.0442 | 0.502232 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 95 | 0.2556 | 0.0505, 0.4592 | 2.4589e-05 | 0.00029507 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | -7.6918 | -14.7771, -1.6301 | 0.00217471 | 0.0260965 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 95 | 0.2843 | 0.0873, 0.4976 | 0.000445681 | 0.00445681 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 100 | -7.6339 | -14.6822, -1.5988 | 0.0159403 | 0.159403 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 96 | -0.4667 | -0.6206, -0.3347 | 2.49607e-12 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 6.6847 | 1.2623, 12.8531 | 3.37515e-09 | 5e-08 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 96 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 0 | 0, 0 | 1 | 1 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 96 | 0.4645 | 0.3336, 0.6167 | 2.49607e-12 | 0 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 100 | -7.1635 | -14.7488, -1.2785 | 3.37515e-09 | 5e-08 |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 5 | 2.0381 | 1.232, 2.6465 | 0.0590582 | 0.708699 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | -73.6222 | -85.4918, -61.1454 | 4.26022e-17 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 95 | -0.3326 | -0.4901, -0.1819 | 1.97107e-07 | 2.96e-06 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 7.6895 | 1.6162, 13.9358 | 7.23305e-05 | 0.00036165 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 5 | -1.6657 | -2.6755, -1.1023 | 0.0590582 | 0.708699 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 100 | 46.8326 | 46.0772, 47.4256 | 6.21747e-18 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 5 | 0.5214 | -0.1826, 1.1261 | 0.280713 | 1 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 42.1489 | 37.6735, 46.0771 | 2.91183e-17 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 5 | -0.3733 | -1.4462, 0.6085 | 0.589639 | 1 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 41.8748 | 37.619, 45.6124 | 5.33718e-17 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 93 | -0.2412 | -0.3973, -0.0784 | 0.0226193 | 0.294051 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 100 | -0.4739 | -5.556, 4.678 | 0.0190656 | 0.0571967 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 5 | 0.2605 | -0.473, 0.8375 | 0.589639 | 1 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 43.6373 | 39.7162, 46.7067 | 2.1179e-17 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 5 | 0.1262 | -1.3233, 1.1153 | 1 | 1 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 42.7479 | 38.5099, 46.209 | 3.30635e-17 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 95 | -0.0334 | -0.2049, 0.1277 | 0.756891 | 1 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 100 | -1.5779 | -5.1413, 0.0787 | 0.899381 | 0.899381 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 5 | -1.3325 | -1.9941, -0.1617 | 0.105645 | 0.903134 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 42.3708 | 38.0057, 46.0609 | 4.12755e-17 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 5 | -1.2281 | -1.8694, -0.7343 | 0.0590582 | 0.708699 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 46.8127 | 46.0253, 47.4172 | 6.21747e-18 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 95 | -0.2712 | -0.4727, -0.0786 | 3.09189e-05 | 0.00043286 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 100 | 7.7077 | 1.711, 13.7965 | 0.00255165 | 0.0102066 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 4 | -1.8886 | -2.7829, -0.7121 | 0.100348 | 0.903134 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | -0.2418 | -0.7857, -0.0032 | 0.0590582 | 0.118116 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 5 | -0.4031 | -0.9768, 0.5943 | 0.418492 | 1 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 100 | 41.595 | 36.9873, 45.6445 | 5.51089e-17 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 4 | 1.0674 | 0.0133, 1.7431 | 0.201243 | 1 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 100 | 41.7359 | 37.1747, 45.7517 | 3.99809e-17 | 0 |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 0 | — | — | — | — |
| cvrp_ext_cvrplib_x_100 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 0 | — | — | — | — |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 120 | -0.2462 | -0.4892, 0.0026 | 0.0846131 | 0.761517 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | -0.2462 | -0.4892, 0.0026 | 0.0846131 | 0.761517 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 66 | -0.2527 | -0.6113, 0.0793 | 0.215239 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | -4.4335 | -12.4666, 3.0009 | 0.12214 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 120 | -0.2677 | -0.6267, 0.067 | 0.45623 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | -0.2677 | -0.6267, 0.067 | 0.45623 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 60 | 0.0213 | -0.313, 0.3689 | 0.973573 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | -11.3891 | -22.529, -1.0942 | 0.201782 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 120 | -0.0215 | -0.3575, 0.264 | 0.155684 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 120 | -0.0215 | -0.3575, 0.264 | 0.155684 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 65 | 0.1188 | -0.1567, 0.4151 | 0.138292 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 120 | -6.6603 | -14.8685, 0.4083 | 0.6684 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 120 | 0 | 0, 0 | 1 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | 0 | 0, 0 | 1 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 73 | 0 | 0, 0 | 1 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 0 | 0, 0 | 1 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 120 | -0.0958 | -0.344, 0.1497 | 0.920851 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | -0.0958 | -0.344, 0.1497 | 0.920851 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 63 | 0.0811 | -0.2285, 0.4074 | 0.773874 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | -1.0792 | -8.5931, 5.7353 | 0.799481 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 120 | -0.0958 | -0.344, 0.1497 | 0.920851 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 120 | -0.0958 | -0.344, 0.1497 | 0.920851 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 63 | 0.0811 | -0.2285, 0.4074 | 0.773874 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 120 | -1.0792 | -8.5931, 5.7353 | 0.799481 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 120 | -0.1188 | -0.3266, 0.0869 | 0.164575 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | -0.1188 | -0.3266, 0.0869 | 0.164575 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 74 | -0.0467 | -0.3286, 0.2478 | 0.348847 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 5.7246 | -1.4267, 12.392 | 0.423181 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 120 | -0.5031 | -0.726, -0.2869 | 1.01506e-05 | 0.00013196 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | -0.5031 | -0.726, -0.2869 | 1.01506e-05 | 0.00013196 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 63 | -0.5245 | -0.8247, -0.2308 | 0.00156693 | 0.0203701 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | -8.96 | -18.579, -0.5333 | 0.00479596 | 0.0575516 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 120 | -0.3838 | -0.626, -0.1473 | 0.000665042 | 0.00665042 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 120 | -0.3838 | -0.626, -0.1473 | 0.000665042 | 0.00665042 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 67 | -0.3703 | -0.6533, -0.1043 | 0.00772566 | 0.0849823 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 120 | -15.5763 | -27.1017, -5.4002 | 0.000134865 | 0.00175325 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 120 | -0.0745 | -0.2419, 0.0799 | 0.53028 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | -0.0745 | -0.2419, 0.0799 | 0.53028 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 67 | -0.0425 | -0.2278, 0.1519 | 0.394493 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 0.0993 | -6.3706, 6.0508 | 0.779138 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 120 | 0.5081 | 0.2808, 0.7406 | 4.1814e-05 | 0.00050177 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | 0.5081 | 0.2808, 0.7406 | 4.1814e-05 | 0.00050177 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 62 | 0.3834 | 0.0768, 0.6793 | 0.00787935 | 0.0849823 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 7.8725 | -0.442, 15.8721 | 0.00531938 | 0.0585132 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 120 | 0.5821 | 0.3106, 0.8688 | 5.35412e-05 | 0.00058895 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 120 | 0.5821 | 0.3106, 0.8688 | 5.35412e-05 | 0.00058895 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 64 | 0.4346 | 0.1151, 0.7366 | 0.0034359 | 0.0412308 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 120 | 7.7809 | -1.3187, 16.2053 | 0.00582627 | 0.0585132 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 120 | -0.5589 | -0.6991, -0.4213 | 5.80297e-15 | 0 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | -0.5589 | -0.6991, -0.4213 | 5.80297e-15 | 0 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 69 | -0.5657 | -0.7459, -0.4047 | 7.35231e-10 | 1e-08 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | -3.3693 | -10.06, 2.4127 | 2.43105e-09 | 4e-08 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 120 | 0 | 0, 0 | 1 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | 0 | 0, 0 | 1 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 75 | 0 | 0, 0 | 1 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 0 | 0, 0 | 1 | 1 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 120 | 0.5558 | 0.4195, 0.6943 | 5.80297e-15 | 0 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 120 | 0.5558 | 0.4195, 0.6943 | 5.80297e-15 | 0 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 69 | 0.5625 | 0.4031, 0.7403 | 7.35231e-10 | 1e-08 |
| cvrp_s1_sandbox_blind_120 | DeepSeek-V4.1-Flash | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 120 | 3.2595 | -2.4723, 9.1404 | 2.43105e-09 | 4e-08 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 60 | 1.2187 | 0.9032, 1.5712 | 1.6697e-09 | 2e-08 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | -96.0675 | -107.095, -83.151 | 5.73334e-07 | 2.87e-06 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 39 | 1.1406 | 0.827, 1.4792 | 7.60361e-07 | 9.88e-06 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | -33.7675 | -47.3832, -22.0638 | 0.00131891 | 0.0118702 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 120 | -0.5719 | -0.7549, -0.3928 | 9.32907e-09 | 1.1e-07 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | -0.5719 | -0.7549, -0.3928 | 9.32907e-09 | 8e-08 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 68 | -0.5813 | -0.8286, -0.3372 | 3.40334e-05 | 0.00034033 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | -5.9562 | -12.611, -0.1878 | 5.88614e-05 | 0.0007652 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 60 | -1.9089 | -2.3596, -1.4934 | 1.1006e-10 | 0 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 120 | 48.7055 | 45.0733, 51.4521 | 1.49299e-06 | 5.97e-06 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 42 | -1.9541 | -2.4507, -1.4858 | 9.34275e-08 | 1.31e-06 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261124 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 120 | 20.7908 | 13.9222, 27.5785 | 0.038733 | 0.154932 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 60 | -0.5856 | -0.962, -0.232 | 0.00272 | 0.01088 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | 49.0074 | 45.5217, 51.7653 | 8.58133e-10 | 1e-08 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 44 | -0.5883 | -1.0358, -0.1644 | 0.0089402 | 0.044701 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 21.7652 | 15.2289, 28.4638 | 0.000383157 | 0.00417001 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 60 | -1.2023 | -1.7222, -0.726 | 6.96289e-06 | 6.267e-05 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | 48.7959 | 45.2742, 51.5769 | 3.05409e-08 | 2.4e-07 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 38 | -1.0688 | -1.5689, -0.588 | 0.000135177 | 0.00121659 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 15.5722 | 8.3485, 22.4506 | 0.105006 | 0.315018 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 120 | -0.4148 | -0.6248, -0.2092 | 2.87289e-05 | 0.00022983 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 120 | -0.4148 | -0.6248, -0.2092 | 2.87289e-05 | 8.619e-05 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 57 | -0.4934 | -0.8452, -0.146 | 0.00319867 | 0.019192 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261125 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 120 | -7.916 | -17.3101, 0.3303 | 0.000379092 | 0.00417001 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 60 | -0.7189 | -1.228, -0.2239 | 0.000672507 | 0.00336253 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | 48.9869 | 45.4767, 51.7671 | 2.33371e-09 | 3e-08 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 40 | -0.8756 | -1.4808, -0.3204 | 0.00255073 | 0.0178551 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 22.1569 | 14.7272, 29.4527 | 0.00142858 | 0.0118702 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 60 | -0.3185 | -0.6895, 0.0266 | 0.164404 | 0.379557 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | 49.0372 | 45.5426, 51.8115 | 2.72337e-11 | 0 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 44 | -0.292 | -0.6929, 0.0954 | 0.276373 | 0.552747 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 22.0968 | 15.203, 28.7924 | 8.60041e-05 | 0.00103205 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 120 | 0.0986 | -0.0981, 0.3059 | 0.126519 | 0.379557 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 120 | 0.0986 | -0.0981, 0.3059 | 0.126519 | 0.126519 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 64 | 0.2647 | -0.014, 0.5898 | 0.0668736 | 0.267495 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261126 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 120 | -0.0772 | -7.3663, 6.6374 | 0.229614 | 0.459228 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 60 | -0.8113 | -1.189, -0.4265 | 1.49551e-06 | 1.496e-05 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | 48.9619 | 45.3904, 51.7297 | 5.73312e-08 | 4e-07 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 41 | -0.7437 | -1.0605, -0.4332 | 1.64785e-05 | 0.00018126 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 21.4435 | 13.9517, 28.6454 | 0.0107141 | 0.0535704 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 60 | -1.4054 | -1.8896, -0.9918 | 1.29413e-08 | 1.4e-07 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | 48.694 | 45.0805, 51.49 | 3.68529e-07 | 2.21e-06 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 40 | -1.1399 | -1.4614, -0.8365 | 8.3829e-07 | 1.006e-05 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 14.3518 | 7.2139, 21.51 | 0.461322 | 0.461322 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 120 | -0.5248 | -0.7965, -0.2755 | 0.000159944 | 0.00095966 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 120 | -0.5248 | -0.7965, -0.2755 | 0.000159944 | 0.00031989 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 57 | -0.273 | -0.5731, 0.0047 | 0.0952178 | 0.285653 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261127 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 120 | -9.0274 | -19.2781, 0.8926 | 0.00780992 | 0.0468764 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | common_completed | 60 | -0.8193 | -1.0642, -0.5988 | 1.40318e-10 | 0 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | -0.1327 | -0.1986, -0.0834 | 1.40318e-10 | 0 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | common_completed | 44 | -0.6185 | -0.8537, -0.4276 | 5.64956e-08 | 8.5e-07 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_1_slice_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | -1.6331 | -4.4958, 0.7888 | 7.95056e-07 | 1.193e-05 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | common_completed | 60 | -0.6386 | -0.9512, -0.3361 | 0.000102243 | 0.0007157 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | free_fleet | penalized_2x | 120 | 49.0084 | 45.4578, 51.7371 | 6.36844e-09 | 6e-08 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | common_completed | 44 | -0.5704 | -0.8952, -0.2606 | 0.000467433 | 0.00373946 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_0_free_tool | exact_k | penalized_2x | 120 | 20.2309 | 13.0336, 27.1882 | 0.00669662 | 0.0468764 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | common_completed | 60 | 0.1792 | -0.1383, 0.4791 | 0.178704 | 0.379557 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | free_fleet | penalized_2x | 120 | 49.0759 | 45.5562, 51.7876 | 2.82266e-14 | 0 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | common_completed | 44 | 0.0003 | -0.391, 0.3833 | 0.817892 | 0.817892 |
| cvrp_s1_sandbox_blind_120 | Qwen4-Max | 20261128 | arm_s1_2_sandbox_only | arm_s1_1_slice_only | exact_k | penalized_2x | 120 | 21.5127 | 14.8542, 28.0235 | 2.58472e-06 | 3.619e-05 |

## Sandbox script and gate-bypass audit

| Cell | Script | Result SHA-256 | Script SHA-256 | Binding check | Numeric output | Gate bypasses |
| --- | --- | --- | --- | --- | --- | ---: |
| DeepSeek-V4.1-Flash:arm_s1_0_free_tool:20261124 | — | — | — | — | — | 0 |
| DeepSeek-V4.1-Flash:arm_s1_1_slice_only:20261124 | — | — | — | — | — | 0 |
| DeepSeek-V4.1-Flash:arm_s1_2_sandbox_only:20261124 | `agent_artifacts/sandbox/run_0001.py` | `ab95258667a6f679695c5c60759ddc031a4a9d356fef5f8a25fdfa2bf116b65b` | `e2d712d3f0d68426e30b02533ea9a5b1b2f0e4fc9383b8129eeea24f23c263bd` | True | False | 0 |
| DeepSeek-V4.1-Flash:arm_s1_2_sandbox_only:20261124 | `agent_artifacts/sandbox/run_0002.py` | `960ac297b0ec54a8af94ebf062b0256533248d1e2fe98f8f1f67220105aa0a14` | `6d37d3e4b5c7ac2cb99918b1f67aea9951f6319b06bbdbfe6d583626fff6b5e4` | True | True | 0 |
| DeepSeek-V4.1-Flash:arm_s1_0_free_tool:20261125 | — | — | — | — | — | 0 |
| DeepSeek-V4.1-Flash:arm_s1_1_slice_only:20261125 | — | — | — | — | — | 0 |
| DeepSeek-V4.1-Flash:arm_s1_2_sandbox_only:20261125 | — | — | — | — | — | 0 |
| DeepSeek-V4.1-Flash:arm_s1_0_free_tool:20261126 | — | — | — | — | — | 0 |
| DeepSeek-V4.1-Flash:arm_s1_1_slice_only:20261126 | — | — | — | — | — | 0 |
| DeepSeek-V4.1-Flash:arm_s1_2_sandbox_only:20261126 | — | — | — | — | — | 0 |
| DeepSeek-V4.1-Flash:arm_s1_0_free_tool:20261127 | — | — | — | — | — | 0 |
| DeepSeek-V4.1-Flash:arm_s1_1_slice_only:20261127 | — | — | — | — | — | 0 |
| DeepSeek-V4.1-Flash:arm_s1_2_sandbox_only:20261127 | `agent_artifacts/sandbox/run_0001.py` | `fd58ec7805c548aae46f3f6aad30dd73631c22d436aae0d84255154e1539b1f0` | `2839b683bd1f25a29f419efea71439252b3f59e2e03ef2d73bee3b52e954da05` | True | False | 1 |
| DeepSeek-V4.1-Flash:arm_s1_2_sandbox_only:20261127 | `agent_artifacts/sandbox/run_0002.py` | `5caed18ff42468d89818fb0fb811c38798ed143dbbe4f407e2dc45db091fcab6` | `32ab2526d01bd087fbe14b79c07b9c4d40d619f4342cadd66fb623dbfed65d1f` | True | False | 1 |
| DeepSeek-V4.1-Flash:arm_s1_2_sandbox_only:20261127 | Round 2 | — | — | outer_step_cap | — | 1 |
| DeepSeek-V4.1-Flash:arm_s1_0_free_tool:20261128 | — | — | — | — | — | 0 |
| DeepSeek-V4.1-Flash:arm_s1_1_slice_only:20261128 | — | — | — | — | — | 1 |
| DeepSeek-V4.1-Flash:arm_s1_1_slice_only:20261128 | Round 2 | — | — | outer_step_cap | — | 1 |
| DeepSeek-V4.1-Flash:arm_s1_2_sandbox_only:20261128 | `agent_artifacts/sandbox/run_0001.py` | `b6997cfb3e20e18096469ed2527f219c4970cea04d9068c6eef0f7105d2f20f1` | `60b26da525e39fd67b6b84a93601c370c64e3c9aeb4e7df74b5f291121eeb5f5` | True | False | 1 |
| DeepSeek-V4.1-Flash:arm_s1_2_sandbox_only:20261128 | `agent_artifacts/sandbox/run_0002.py` | `6567b17dbeb52bb133c7b42b1440ece1d4e5c85ada535650ed562e28ce927c67` | `88572983d6459654ba9e3908cbd525e8b4820128dd45e4bd37a7506bcc470539` | True | False | 1 |
| DeepSeek-V4.1-Flash:arm_s1_2_sandbox_only:20261128 | `agent_artifacts/sandbox/run_0003.py` | `01c061fb607b7ff262b9745b352dc999d5b0deea31f2d149aa522b9c20a1f4ad` | `0e19e58e5b046162fa444beb91d7809c04b8269c1724c0a2b8e6faa4284fbf25` | True | False | 1 |
| DeepSeek-V4.1-Flash:arm_s1_2_sandbox_only:20261128 | Round 2 | — | — | outer_step_cap | — | 1 |
| Qwen4-Max:arm_s1_0_free_tool:20261124 | — | — | — | — | — | 0 |
| Qwen4-Max:arm_s1_1_slice_only:20261124 | — | — | — | — | — | 0 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261124 | `agent_artifacts/sandbox/run_0001.py` | `19843887bb4badc48e2e1c4222a8b2938db72e21a5cb69b9f4c2c3f45f666cbc` | `02a2da7f76b3e05419beb4988561c287114becf632cc7e4e491520f18c0de8f5` | True | False | 1 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261124 | `agent_artifacts/sandbox/run_0002.py` | `dd2bbc4d00cbcebc4059eb00e3e668398f779ee7c35e93630c589c55fd424858` | `1a75fddcee86e2c3452e1493b784af54a6130a55fefa3640dab21c6a6352d96f` | True | False | 1 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261124 | `agent_artifacts/sandbox/run_0003.py` | `e4340913a9b60b429412738988824b148497ef486820c4bc5be666f23acb8ca8` | `65d44b2759d471222b0597a7e7ea218a58b1818ac65b428cd04e9ec92c338c47` | True | True | 1 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261124 | Round 2 | — | — | outer_step_cap | — | 1 |
| Qwen4-Max:arm_s1_0_free_tool:20261125 | — | — | — | — | — | 0 |
| Qwen4-Max:arm_s1_1_slice_only:20261125 | — | — | — | — | — | 0 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261125 | `agent_artifacts/sandbox/run_0001.py` | `32c9c7f78ebb2ba9c74c3c6b4ff514ee170049ec456c1abdaf12d406fe7e4f59` | `f83966b9641dc9653a28f42f223ace79a8f61561c52281f0a65620e00938625c` | True | False | 1 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261125 | `agent_artifacts/sandbox/run_0002.py` | `0ecd8711caac926de10796a745c2fec11bf8e9be0672d63d851d7126e28bdd86` | `29e53807d30b5e128a140d17a928ed2e3bb5a271d4c537f03301e56b8efd476b` | True | False | 1 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261125 | Round 2 | — | — | outer_step_cap | — | 1 |
| Qwen4-Max:arm_s1_0_free_tool:20261126 | — | — | — | — | — | 0 |
| Qwen4-Max:arm_s1_1_slice_only:20261126 | — | — | — | — | — | 0 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261126 | — | — | — | — | — | 0 |
| Qwen4-Max:arm_s1_0_free_tool:20261127 | — | — | — | — | — | 0 |
| Qwen4-Max:arm_s1_1_slice_only:20261127 | — | — | — | — | — | 0 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261127 | `agent_artifacts/sandbox/run_0001.py` | `257b79f306186930227db5f89c84cfc739bdc8790e8acd9c8c8793c6c7583306` | `1156e2dfa2513a71cc40e87541892870c5315e8c58dbf8a9fd41d6100ca6a021` | True | False | 2 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261127 | `agent_artifacts/sandbox/run_0002.py` | `656eeb7682e3e2116246bff13f861a43f31307b7cb15436c4dad35afcdad307e` | `417fee8d89a62e0847f440995c58fff7b84d6b9f95aabaff34271f72f4e36ce5` | True | False | 2 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261127 | Round 2 | — | — | outer_step_cap | — | 1 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261127 | Round 3 | — | — | outer_step_cap | — | 1 |
| Qwen4-Max:arm_s1_0_free_tool:20261128 | — | — | — | — | — | 0 |
| Qwen4-Max:arm_s1_1_slice_only:20261128 | — | — | — | — | — | 0 |
| Qwen4-Max:arm_s1_2_sandbox_only:20261128 | — | — | — | — | — | 0 |

[Full paired statistics, script sources and outputs](s1_sandbox_ablation_report.json)
