# user_genroute_go

该示例用于在不直接修改 `Archive_extracted` 源码文件的前提下，让 EoH 的 v0/v1/v2 工作流自动生成并评估一个 Go 算子：

```go
func (assign *Assign) GenRoute()
```

评估方式为：将生成的 `GenRoute` 写入临时 Go 文件，与 `Archive_extracted/main.go + routing.go` 一起编译生成可执行文件，然后在 `Archive_extracted/solomon_benchmark` 上运行并解析 `final cost` 作为 fitness（越小越好）。

## 运行（V0 最小闭环）

在本目录下运行：

```bash
python v0_baseline/runEoH_genroute_go.py --loops 1 --gens 1 --max-instances 1
```

参数说明：
- `--max-instances`：每次评估跑多少个 `solomon_benchmark/*.json`（建议先用 1 做 smoke test）
- `--sim-time-multi`：传给 Go 程序的第二个参数（影响仿真时间缩放，默认 10）

