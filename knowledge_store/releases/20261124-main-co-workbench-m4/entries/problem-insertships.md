# Insertships: evolve InsertShips in a Go dispatcher

Pickup-delivery station batches arrive over time. The candidate is a Go function compiled into the dispatcher, not a Python select_next_node.

## 定义或方法步骤

Copy main.go/routing.go; regex-replace InsertShips; go build; run each JSON; parse 'final cost'.

## 适用条件、假设与限制

Solomon files under go_solver are this problem's instances, not CVRP construct instances.

## 来源及支持的具体结论

The harness code is the source.

## 代码和评测关联

impl-insertships-go-harness.

## 未确认项与冲突证据

The default InsertShips body is a large random-range dispatcher; no literature name is assigned to it on this card.
