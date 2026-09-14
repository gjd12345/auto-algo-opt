# Plan 启动读取示例

启动时先解析 knowledge_store/current；若 Windows 没有创建目录软链接的权限，读取 knowledge_store/current.path，并记录它解析出的真实 release 路径。随后读取该 release 的 manifest.json（记录 manifest hash）和 index.json，再按当前问题选择最多三条方法正文。

示例（PowerShell）：

~~~powershell
$store = (Resolve-Path .\knowledge_store).Path
$pointer = Join-Path $store "current"
if (Test-Path $pointer) {
  $release = (Resolve-Path $pointer).Path
} else {
  $release = Join-Path $store ((Get-Content (Join-Path $store "current.path") -Raw).Trim())
}
$manifest = Get-Content (Join-Path $release "manifest.json") -Raw | ConvertFrom-Json
$manifestHash = (Get-FileHash (Join-Path $release "manifest.json") -Algorithm SHA256).Hash
python -m knowledge_tools search --release $release --query "当前问题关键词" --limit 3
python -m knowledge_tools read --release $release --id method-tsp-two-opt
~~~

把真实路径、manifest hash、选读条目 ID、正文 hash 和采用摘要保存到独立的 knowledge_context.json。之后补读继续使用这一路径，即使 current 已切换；这只是宿主 Agent 操作记录，不宣称取得了 Session 级引用校验。当前问题合同、工具权限和预算规则优先，Memory 仍由原系统单独管理。

若读到带 `## EoH 适配` 的方法卡：只把适配节的机制写入 `plan.operations[].mechanism`。plan.json 不能有 `code` 字段。签名模板在发布包的 `eoh_adapters/`（TSP `select_next_node(..., start_node, ...)`，CVRP 含 `depot/rest_capacity/demands`，OBP 同时给出 `score` 与 `priority`，2-opt 为 `select_2opt_move`）。文献适配不是原文算法；需要种子代码时走 `explicit_seeds` 并标明 adapter。二级子问题目录在 `catalogs/subproblems.json`，不是新的 `problem_id`。
