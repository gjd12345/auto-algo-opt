# 网络搜集操作说明

默认走 `knowledge_workspace/literature_harvest_scheme.md`：OpenAlex 脚本检索，grok-4.5 筛读，宿主终审。不要用 grok-4.6 逐篇检索。

1. 宿主 Agent 记录查询词、日期和候选来源。目录已冻结在 `catalogs/subproblems.json`；单个问题族试点最多 5 个子问题，铺满前不要一次筛 30。
2. 优先 OpenAlex 摘要、作者/出版社页面、原论文。综述只用于定位，具体算法结论追到原始来源。
3. 登记题名、作者、年份、DOI/URL、页码或章节、获取日期、可用性和许可。公开全文若保存，先计算 SHA256；无权分发的全文留在本地，发布包只含书目信息、链接和自主摘要。
4. 不执行任意下载脚本，不加载 pickle，不绕过认证，不关闭 TLS 校验。OpenAlex harvest 是白名单 HTTPS GET，不存 PDF。
5. 历史成绩绑定原 suite、指标、预算和代码 hash；代码匹配仅是推断时标明推断依据，缺失证据保持缺口。
6. 筛读 JSON 无 DOI 不得入库。`eoh_map=possible` 才写 EoH 适配签名；否则只作文献卡。

登记模板：

~~~json
{
  "id": "src-example",
  "title": "",
  "authors": [],
  "year": 0,
  "doi": "",
  "url": "https://",
  "locator": "page or section",
  "accessed_on": "YYYY-MM-DD",
  "availability": "",
  "license": "",
  "selected": false,
  "selection_reason": ""
}
~~~
