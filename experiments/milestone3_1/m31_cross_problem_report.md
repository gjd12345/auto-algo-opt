# Milestone 3.1 Cross-Problem Generalization Report

## 1. Main Track: TSP (`tsp/v1`) & Online OBP (`obp_online/v1`) on Blind-72

| Family | Protocol | Track / Baseline | Mean Obj | Completion |
|---|---|---|---:|---:|
| tsp | tsp/v1 | tsp_l2 | 83833.4340 | 1.000 |
| tsp | tsp/v1 | tsp_l1 | 92970.5539 | 1.000 |
| tsp | tsp/v1 | tsp_nn_2opt | 84610.3681 | 1.000 |
| tsp | tsp/v1 | tsp_nn | 98818.4295 | 1.000 |
| tsp | tsp/v1 | tsp_farthest_insertion | 85588.1502 | 1.000 |
| obp | obp_online/v1 | obp_online | 28.2222 | 1.000 |
| obp | obp_online/v1 | obp_best_fit | 28.2222 | 1.000 |
| obp | obp_online/v1 | obp_first_fit | 28.3333 | 1.000 |

## 2. Independent Extension (Strictly Separate): Offline BPP (`bpp_offline/v1`)

| Track / Baseline | Protocol | Mean Bins | Completion |
|---|---|---:|---:|
| bpp_offline | bpp_offline/v1 | 27.7500 | 1.000 |
| bpp_ffd | bpp_offline/v1 | 27.7500 | 1.000 |
| bpp_bfd | bpp_offline/v1 | 27.7639 | 1.000 |

## 3. External Benchmarks & Adapter Code Footprint

- **tsp_ext_tsplib_euc2d** (`tsp/v1`, N=18): tsp_nn_2opt=54830.7222, tsp_nn=64150.6667, tsp_farthest_insertion=56434.3333, tsp_l1=58916.1667, tsp_l2=67421.0556
- **obp_ext_bpplib** (`obp_online/v1`, N=70): obp_best_fit=72.9143, obp_first_fit=73.6429, obp_online=72.9143
- **tsp** added adapter+template+probe LOC = 468
- **obp** added adapter+template+probe LOC = 387
- **bpp** added adapter+template+probe LOC = 573

## 4. Excluded Selection Runs (`no_champion` / Missing)

- `m31_tsp_l1_s20261124` (lane=`tsp_l1`, final_phase=`no_champion`, reason=`no_champion`)
- `m31_tsp_l1_s20261126` (lane=`tsp_l1`, final_phase=`no_champion`, reason=`no_champion`)
