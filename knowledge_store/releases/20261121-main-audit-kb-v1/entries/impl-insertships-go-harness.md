# Insertships evaluator: replace InsertShips in a Go dispatcher and run Solomon-like JSON

The Python Evaluation class copies go_solver sources, regex-replaces InsertShips (or Optimization), go build, then runs the binary on Solomon-format JSON batches. Objective is mean parsed 'final cost' (optional composite with RES time). This is an online insertion/dispatch problem on pickup-delivery stations, not CVRP construct.

## 定义或方法步骤

Missing function or build failure yields a penalty. Density/time filters may rewrite JSON.

## 适用条件、假设与限制

The heuristic is whatever Go function EoH writes; this file is the harness.

## 来源及支持的具体结论

No literature identity is inferred from the filename. The conclusions below are from reading this blob on main.

## 代码和评测关联

SHA256 02bc4199aa17998531a4df1239fe82a887c0a7b226d42577537635b24643a9bb.

## 未确认项与冲突证据

Default InsertShips in go_solver/main.go is a large dispatcher with random assignment ranges; it is not Clarke–Wright.
