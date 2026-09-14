"""Method-first dashboard for the offline knowledge base.

Layout: search + type filter on top; family tree on the left; method list in
the middle; fixed reading pane on the right. Coverage matrix, sources and
change lists are separate views. Generated HTML is self-contained and works
from file://. Dashboard must not import core.py (circular).
"""

from __future__ import annotations

import html
import json
import re
from typing import Any, Mapping, Sequence

FAMILY_UI_LABELS = {
    "online_bin_packing": "在线装箱",
    "offline_bin_packing": "离线装箱",
    "tsp": "旅行商问题",
    "cvrp": "带容量车辆路径",
    "knapsack": "背包",
    "mixer_split": "Mixer split",
    "insertships_routing": "Insertships 路径",
    "optimization_frameworks_experiments": "优化框架与实验",
    "unknown": "未标注",
}
KIND_LABELS = {
    "problem": "问题",
    "method": "方法",
    "implementation": "实现",
    "framework": "框架",
    "other": "其他",
}
ONLINE_LABELS = {"online": "在线", "offline": "离线", "unknown": "在线/离线未定"}
READ_DEPTH_LABELS = {
    "full_text_local": "全文核对",
    "abstract": "摘要整理",
    "metadata": "仅书目",
    "metadata_only": "仅书目",
}
QUERY_ALIASES = {
    "构造": ["construct", "construction"],
    "装箱": ["binpacking", "obp", "onlinebinpacking"],
    "旅行商": ["tsp"],
    "背包": ["knapsack"],
    "车辆路径": ["cvrp", "vehiclerouting"],
}

# Display translations only; source titles and Markdown remain unchanged.
METHOD_TITLES = {
    "method-obp-best-fit": "最佳适应装箱（Best Fit）",
    "method-obp-first-fit": "首次适应装箱（First Fit）",
    "method-obp-worst-fit-template": "最差适应装箱（Worst Fit）",
    "method-obp-residual-utilization": "基于剩余容量利用率的装箱评分",
    "method-tsp-double-bridge-ils": "双桥扰动与 2-opt 迭代局部搜索",
    "method-tsp-nearest-neighbor-construct": "候选邻域内的最近邻构造",
    "method-tsp-two-opt": "邻域受限的 2-opt 路径改进",
    "method-tsp-restricted-3opt": "邻域受限的 3-opt 路径重连",
    "method-tsp-relocation": "邻域受限的单节点迁移",
    "method-tsp-or-opt-2": "双节点片段迁移（Or-opt-2）",
    "method-cvrp-far-regret-seed": "远端种子与插入绕行后悔值构造",
    "method-cvrp-nearest-feasible-construct": "最近可行客户构造",
    "method-cvrp-savings-next-node": "以节约值选择下一个客户",
    "method-knapsack-order-greedy": "按输入顺序的背包贪心选择",
    "method-mixer-greedy-capacity-split": "按最小可容纳容量切分体积",
}


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _entry_kind(entry: Mapping[str, Any]) -> str:
    kind = str(entry.get("type") or entry.get("category") or "")
    if kind in KIND_LABELS:
        return kind
    if kind in {"optimization_frameworks_experiments"}:
        return "framework"
    return "other"


def tokenize_query(query: str) -> list[str]:
    raw = re.findall(r"\w+(?:[-_]\w+)*", str(query).casefold())
    terms: list[str] = []
    for item in raw:
        term = re.sub(r"[-_]", "", item)
        if len(term) == 1 and term.isascii():
            continue
        if term not in terms:
            terms.append(term)
        for extra in QUERY_ALIASES.get(item, []) + QUERY_ALIASES.get(term, []):
            extra_n = re.sub(r"[-_]", "", extra.casefold())
            if extra_n and extra_n not in terms:
                terms.append(extra_n)
    return terms


def _sections(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"_lead": []}
    current = "_lead"
    for line in str(markdown or "").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def _first_paragraph(text: str) -> str:
    for block in str(text or "").split("\n\n"):
        clean = " ".join(block.split())
        if clean and not clean.startswith("#"):
            return clean[:180]
    return ""


def _family_label(family: str) -> str:
    return FAMILY_UI_LABELS.get(family, family)


def _read_depth_for_entry(entry: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]) -> str:
    attrs = _as_mapping(entry.get("attributes"))
    if attrs.get("source_trust") == "unverified":
        return "unverified"
    depths = []
    for sid in entry.get("source_refs") or []:
        rec = sources.get(str(sid)) or {}
        depths.append(str(rec.get("read_depth") or "metadata"))
    if "full_text_local" in depths:
        return "full_text_local"
    if "abstract" in depths:
        return "abstract"
    return "metadata_only"


def _code_paths(entry: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    for ref in entry.get("code_refs") or []:
        if isinstance(ref, Mapping) and ref.get("path"):
            paths.append(str(ref["path"]))
        elif isinstance(ref, str) and ref.strip():
            paths.append(ref.strip())
    for item in entry.get("evidence_refs") or []:
        text = str(item)
        if text.startswith("code:"):
            path = text.split(":", 1)[1].strip()
            if path and path not in paths:
                paths.append(path)
    return paths


def _evidence_flags(entry: Mapping[str, Any]) -> dict[str, bool]:
    refs = [str(item) for item in entry.get("evidence_refs") or []]
    return {
        "code": bool(_code_paths(entry)),
        "eval": any(ref.startswith(("evaluation:", "metric:")) for ref in refs),
        "gap": any(ref.startswith("gap:") for ref in refs),
        "unverified": _as_mapping(entry.get("attributes")).get("source_trust") == "unverified",
        "interface": bool(_as_mapping(entry.get("attributes")).get("interface")),
    }


def _status_chips(entry: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]) -> list[str]:
    depth = _read_depth_for_entry(entry, sources)
    flags = _evidence_flags(entry)
    chips = []
    if flags["unverified"]:
        chips.append("来源待核对")
    else:
        chips.append(READ_DEPTH_LABELS.get(depth, "仅书目") if entry.get("source_refs") else "无文献来源")
    if flags["code"]:
        chips.append("代码已定位")
    else:
        chips.append("无本地代码")
    if not flags["interface"]:
        chips.append("接口未验证")
    if not flags["eval"]:
        chips.append("无评测证据")
    return chips


def _source_map(sources_doc: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in sources_doc.get("sources") or []:
        if not isinstance(row, Mapping) or not row.get("id"):
            continue
        out[str(row["id"])] = {
            "title": str(row.get("title") or ""),
            "year": str(row.get("year") or ""),
            "venue": str(row.get("venue") or ""),
            "doi": str(row.get("doi") or ""),
            "url": str(row.get("url") or ""),
            "read_depth": str(row.get("read_depth") or "metadata"),
            "locator": str(row.get("locator") or ""),
        }
    return out


def _payload(
    entry: Mapping[str, Any],
    *,
    body: str,
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    kind = _entry_kind(entry)
    family = str(entry.get("problem_family") or "unknown")
    attrs = _as_mapping(entry.get("attributes"))
    eoh = _as_mapping(attrs.get("eoh_map"))
    sections = _sections(body)
    flags = _evidence_flags(entry)
    online = attrs.get("online_offline") or ""
    relations = _as_mapping(entry.get("relations"))
    search_blob = " ".join([
        str(entry.get("title") or ""),
        str(entry.get("summary") or ""),
        family,
        METHOD_TITLES.get(str(entry.get("id")), ""),
        _family_label(family),
        str(entry.get("id") or ""),
        str(attrs.get("interface") or ""),
        body,
        " ".join(str(t) for t in (entry.get("tags") or [])),
    ])
    return {
        "id": str(entry.get("id") or ""),
        "title": METHOD_TITLES.get(str(entry.get("id")), str(entry.get("title") or entry.get("id") or "")),
        "originalTitle": str(entry.get("title") or ""),
        "kind": kind,
        "kindLabel": KIND_LABELS.get(kind, kind),
        "family": family,
        "familyLabel": _family_label(family),
        "summary": str(entry.get("summary") or "").strip(),
        "applicable": _first_paragraph(sections.get("适用条件、假设与限制", "")),
        "steps": sections.get("定义或方法步骤", ""),
        "limits": sections.get("适用条件、假设与限制", ""),
        "sourceSection": sections.get("来源及支持的具体结论", ""),
        "eohSection": sections.get("EoH 适配", ""),
        "body": body,
        "interface": str(attrs.get("interface") or ""),
        "objective": str(attrs.get("objective") or ""),
        "eohStatus": str(eoh.get("status") or ""),
        "eohKind": str(eoh.get("adapter_kind") or ""),
        "notOriginal": str(attrs.get("not_the_original") or ""),
        "online": ONLINE_LABELS.get(str(online), str(online)) if online else "",
        "statusChips": _status_chips(entry, sources),
        "unverified": flags["unverified"],
        "hasCode": flags["code"],
        "path": str(entry.get("path") or ""),
        "sourceRefs": [str(x) for x in (entry.get("source_refs") or [])],
        "codePaths": _code_paths(entry),
        "evidenceRefs": [str(x) for x in (entry.get("evidence_refs") or [])],
        "relations": {
            "problems": [str(x) for x in (relations.get("problems") or [])],
            "methods": [str(x) for x in (relations.get("methods") or [])],
            "implementations": [str(x) for x in (relations.get("implementations") or [])],
            "sources": [str(x) for x in (relations.get("sources") or [])],
        },
        "search": search_blob.casefold(),
        "parentProblem": next((str(x) for x in (relations.get("problems") or []) if str(x).startswith("problem-")), ""),
    }


_STYLE = """
:root{--bg:#f5f6f8;--panel:#fff;--ink:#202b3c;--muted:#66758a;--line:#e1e6ee;--accent:#255ad5;--soft:#edf3ff;--warn:#9b4c16;--mono:Consolas,monospace}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--bg);font:15px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}
button,input,select{font:inherit}button{cursor:pointer;color:inherit}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #88acff;outline-offset:2px}
button{border:0;background:none}a{color:var(--accent);text-underline-offset:3px}[hidden]{display:none!important}
.topbar{height:72px;display:flex;align-items:center;gap:32px;padding:0 28px;border-bottom:1px solid var(--line);background:white}
.brand{font-size:19px;font-weight:700;letter-spacing:.03em}.brand small{display:block;font-size:11px;color:var(--muted);font-weight:400;letter-spacing:.06em}
.views{display:flex;height:100%;gap:26px}.view{border-bottom:3px solid transparent;color:var(--muted);padding:0 2px}.view.active{border-color:var(--accent);color:var(--accent);font-weight:600}
.ver{margin-left:auto;color:var(--muted);font-size:12px;position:relative}.ver summary{cursor:pointer}.ver p{position:absolute;z-index:5;right:0;min-width:290px;background:white;padding:18px;box-shadow:0 5px 24px #23334820;border:1px solid var(--line);overflow-wrap:anywhere}
.toolbar{height:72px;padding:14px 24px;display:flex;align-items:center;gap:14px;border-bottom:1px solid var(--line);background:white}
.search{flex:1;max-width:660px;position:relative}.search input{width:100%;padding:10px 46px 10px 15px;border:1px solid #cad3e1;border-radius:8px;background:#fafbfd;color:var(--ink)}.search button{position:absolute;right:8px;top:7px;padding:3px 9px;color:var(--muted)}
.filter{display:flex;gap:7px;align-items:center;font-size:13px;color:var(--muted)}select{max-width:220px;padding:8px;border:1px solid #cad3e1;border-radius:7px;background:white;color:var(--ink)}
.app{height:calc(100dvh - 144px);min-height:360px;display:grid;grid-template-columns:224px 350px minmax(0,1fr)}
.tree,.list,.reader{min-width:0;overflow-y:auto}.tree{padding:20px 12px;border-right:1px solid var(--line);background:#f8f9fb}
.tree h3{margin:0 10px 12px;font-size:12px;color:var(--muted);font-weight:500}.tbtn{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;text-align:left;padding:10px;border-radius:7px;font-size:14px}.tbtn .n{font-size:11px;color:var(--muted);white-space:nowrap}.tbtn.active{background:var(--soft);color:var(--accent);font-weight:600}
.family-group{margin-top:5px}.family-group summary{font-size:12px;padding:3px 10px 8px;color:var(--muted);cursor:pointer}.child{display:block;width:100%;text-align:left;font-size:12px;line-height:1.5;color:var(--muted);padding:7px 10px 7px 22px;overflow-wrap:anywhere}.child.active{color:var(--accent);background:var(--soft)}
.list{padding:18px 12px;background:white;border-right:1px solid var(--line)}.list-head{display:flex;justify-content:space-between;align-items:baseline;padding:0 8px 14px}.list-head h2{margin:0;font-size:16px}.list-head span{font-size:12px;color:var(--muted)}
.card{width:100%;display:block;text-align:left;padding:16px;margin-bottom:8px;border:1px solid var(--line);border-radius:10px;background:white;transition:background .15s}
.card:hover{background:#fafcff;border-color:#b0c5ee}.card.active{background:var(--soft);border-color:#9bb9f5;box-shadow:inset 3px 0 var(--accent)}
.card .title{font-size:15px;font-weight:600;line-height:1.5;overflow-wrap:anywhere}.card .sub{font-size:12px;color:var(--muted);margin-top:5px}
.card .why{font-size:13px;color:#546276;margin:8px 0 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.chip{display:inline-block;font-size:11px;line-height:1.5;padding:3px 7px;border-radius:5px;background:#eef1f6;color:#536379}.chip.bad{background:#fff0e6;color:var(--warn)}
.reader{background:white}.rh{padding:28px 36px 20px;border-bottom:1px solid var(--line)}.rh h1{margin:8px 0;font-size:26px;font-weight:650;line-height:1.4;letter-spacing:-.02em;overflow-wrap:anywhere}.meta{font-size:12px;color:var(--muted)}
.rh-actions{display:flex;gap:16px;align-items:center;font-size:12px}.reader-close{margin-left:auto;color:var(--muted)}.reader-fab{display:none}.rb{max-width:960px;margin:auto;padding:8px 36px 48px}
.rb h2{font-size:18px;margin:30px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line);color:#21324d}.rb h3{font-size:16px;margin-top:24px}
.rb p{margin:10px 0;overflow-wrap:anywhere}.rb li{margin:6px 0;overflow-wrap:anywhere}.rb ul,.rb ol{padding-left:24px}
.rb pre{padding:18px;background:#f4f6fa;border:1px solid var(--line);border-radius:8px;overflow:auto;font:13px/1.7 var(--mono);tab-size:4;white-space:pre}
.rb code{font-family:var(--mono);font-size:.88em;background:#f0f3f7;border-radius:3px;padding:2px 4px}.rb pre code{background:none;padding:0;font-size:inherit}
.rb blockquote{margin:18px 0;padding:8px 16px;border-left:3px solid #c6d5ef;color:var(--muted);background:#f8faff}
.table-wrap{overflow:auto}.rb table{border-collapse:collapse;font-size:13px;min-width:100%}.rb th,.rb td{border:1px solid var(--line);padding:9px 12px;text-align:left;white-space:normal}.rb th{background:#f6f8fb}
.notice{background:#fff6eb;border:1px solid #f0d5b5;color:#86511f;padding:13px 16px;border-radius:8px;font-size:13px;margin-top:18px}
.note{color:var(--muted);font-size:13px}.empty{padding:60px 32px;color:var(--muted);text-align:center}.empty h2{font-size:20px;color:var(--ink)}.empty p{max-width:400px;margin:12px auto}.empty button{padding:8px 14px;border:1px solid var(--line);border-radius:7px;background:white}
.source-card{border:1px solid var(--line);border-radius:8px;padding:16px;margin:12px 0;font-size:14px;overflow-wrap:anywhere}.source-card .note{margin-top:6px}
.technical{margin-top:28px;border-top:1px solid var(--line);padding-top:16px;color:var(--muted);font-size:13px}.technical summary{cursor:pointer}.technical pre{white-space:pre-wrap;overflow-wrap:anywhere}
.page{height:calc(100dvh - 72px);overflow:auto;padding:40px max(28px,calc((100vw - 1080px)/2));background:var(--bg)}.page h1{font-size:28px;margin:0 0 12px}.page h2{margin-top:28px;font-size:18px}
.matrix{border-collapse:collapse;width:100%;margin-top:24px;background:white;border:1px solid var(--line)}.matrix th,.matrix td{text-align:left;padding:16px;border-bottom:1px solid var(--line)}.mcell b{font-size:19px;font-weight:600;color:var(--accent)}.page .chip{margin:3px}
.mobile-family{display:none}
@media(min-width:1600px){.app{grid-template-columns:248px 400px minmax(0,1fr)}.rb{font-size:16px}}
@media(max-width:1180px){.app{grid-template-columns:310px minmax(0,1fr)}.tree{display:none}.mobile-family{display:flex}.rh{padding:24px}.rb{padding:8px 24px 40px}.toolbar{gap:10px}.filter label{display:none}.topbar{gap:22px}}
@media(max-width:760px){.topbar{height:auto;min-height:100px;padding:14px 16px;gap:12px;flex-wrap:wrap}.brand{font-size:17px}.views{order:3;width:100%;height:35px;gap:24px}.view{font-size:13px}.ver{font-size:11px}.toolbar{height:auto;flex-wrap:wrap;padding:12px 16px;gap:8px}.search{flex-basis:100%;max-width:none}.filter{flex:1}.filter select{width:100%;max-width:none;font-size:13px}.app{height:auto;display:block;min-height:0}.list{overflow:visible;border:0}.reader{display:none}.reader.open{display:block;position:fixed;inset:0;z-index:20;overflow:auto}.rh{position:sticky;top:0;z-index:3;padding:12px 20px 10px;background:white;box-shadow:0 1px 0 var(--line)}.rh h1{font-size:23px}.rh-actions{position:static}.reader-close{padding:7px 10px;border:1px solid var(--line);border-radius:6px}.reader.open .reader-fab{display:block;position:fixed;right:16px;bottom:16px;z-index:21;padding:10px 14px;border-radius:8px;background:var(--accent);color:#fff;border:0;box-shadow:0 4px 16px #255ad544}.rb{padding:0 20px 72px}.page{height:auto;padding:24px 16px}.matrix th,.matrix td{padding:10px;font-size:12px}.rh-actions a{font-size:12px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
"""

_SCRIPT = r"""
"use strict";
const DATA=__DATA__, SOURCES=__SOURCES__, ALIASES=__ALIASES__, FAMILY_LABELS=__FAMILIES__, RELEASE=__RELEASE__;
let view="methods",kind="method",family="all",problem="all",query="",openId=null;
const byId=id=>document.getElementById(id);
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function norm(s){return String(s||"").toLowerCase().replace(/[-_]/g,"");}
function groups(q){return (String(q||"").toLowerCase().match(/[\p{L}\p{N}_]+(?:[-_][\p{L}\p{N}_]+)*/gu)||[]).filter(t=>!(t.length===1&&/^[a-z0-9]$/.test(t))).map(t=>[t,...(ALIASES[t]||ALIASES[norm(t)]||[])].map(norm));}
function matches(d){return (kind==="all"||d.kind===kind)&&(family==="all"||family===d.family)&&(problem==="all"||d.id===problem||(d.relations.problems||[]).includes(problem))&&groups(query).every(g=>g.some(t=>norm(d.search).includes(t)));}
function safeURL(s){return /^https?:\/\//i.test(s||"")?s:"";}
function inline(s){return esc(s).replace(/&#96;([^&#]*?)&#96;/g,"<code>$1</code>").replace(/\x60([^\x60]+)\x60/g,"<code>$1</code>").replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>");}
function md(src){
 const lines=String(src||"").split(/\r?\n/);let out="",list="",code=null,para=[];
 const flush=()=>{if(para.length){out+="<p>"+inline(para.join(" "))+"</p>";para=[];}};
 const close=()=>{flush();if(list){out+="</"+list+">";list="";}};
 for(let i=0;i<lines.length;i++){
  const line=lines[i];
  if(/^\s*(```|~~~)/.test(line)){close();if(code!==null){out+="<pre><code>"+esc(code.join("\n"))+"</code></pre>";code=null;}else code=[];continue;}
  if(code!==null){code.push(line);continue;}
  if(!line.trim()){close();continue;}
  const h=/^(#{1,6})\s+(.*)$/.exec(line);
  if(h){close();const level=Math.max(2,Math.min(3,h[1].length));out+="<h"+level+">"+inline(h[2])+"</h"+level+">";continue;}
  if(line.includes("|")&&i+1<lines.length&&/^\s*\|?\s*:?-{3,}/.test(lines[i+1])){
   close();const cells=l=>l.trim().replace(/^\||\|$/g,"").split("|").map(x=>x.trim());
   out+="<div class='table-wrap'><table><thead><tr>"+cells(line).map(x=>"<th>"+inline(x)+"</th>").join("")+"</tr></thead><tbody>";i++;
   while(i+1<lines.length&&lines[i+1].includes("|"))out+="<tr>"+cells(lines[++i]).map(x=>"<td>"+inline(x)+"</td>").join("")+"</tr>";
   out+="</tbody></table></div>";continue;
  }
  const li=/^\s*(?:([-*])|(\d+)[.)])\s+(.*)$/.exec(line);
  if(li){flush();const type=li[2]?"ol":"ul";if(list!==type){if(list)out+="</"+list+">";list=type;out+="<"+list+">";}out+="<li>"+inline(li[3])+"</li>";continue;}
  if(list){out+="</"+list+">";list="";}
  if(/^>\s?/.test(line)){flush();out+="<blockquote>"+inline(line.replace(/^>\s?/,""))+"</blockquote>";continue;}
  para.push(line);
 }
 close();if(code!==null)out+="<pre><code>"+esc(code.join("\n"))+"</code></pre>";return out;
}
function chips(d,compact=false){const labels=compact?d.statusChips.filter(c=>["来源待核对","摘要整理","全文核对","仅书目","无文献来源","代码已定位"].includes(c)):d.statusChips;return labels.map(c=>"<span class='chip"+(c==="来源待核对"?" bad":"")+"'>"+esc(c)+"</span>").join("");}
function snippet(d){
 if(!query.trim())return d.summary||d.applicable||"";
 const words=groups(query).flat();const lines=(d.body||"").split("\n").filter(l=>l.trim()&&!l.startsWith("#"));
 return (lines.find(l=>words.some(t=>norm(l).includes(t)))||d.summary||"").slice(0,190);
}
function filtered(){return Object.values(DATA).filter(matches).sort((a,b)=>Number(a.unverified)-Number(b.unverified)||Number(b.hasCode)-Number(a.hasCode)||a.title.localeCompare(b.title));}
function renderList(){
 const rows=filtered();byId("listDesc").textContent=rows.length+" 条";
 byId("listTitle").textContent=problem!=="all"?"相关条目":family==="all"?"浏览知识":FAMILY_LABELS[family]||family;
 byId("cards").innerHTML=rows.map(d=>"<button class='card"+(d.id===openId?" active":"")+"' data-open='"+esc(d.id)+"' aria-pressed='"+(d.id===openId)+"'><div class='title'>"+esc(d.title)+"</div><div class='sub'>"+esc(d.familyLabel)+" · "+esc(d.kindLabel)+"</div><div class='why'>"+esc(snippet(d))+"</div><div class='chips'>"+chips(d,true)+"</div></button>").join("")||"<div class='empty'><h2>没有匹配条目</h2><p>尝试缩短关键词，或清除问题与类型筛选。</p><button data-reset>清除筛选</button></div>";
}
function sourceHTML(sid){
 const s=SOURCES[sid]||{},doi=String(s.doi||"").replace(/^https?:\/\/doi\.org\//i,"");
 const doiURL=doi?"https://doi.org/"+doi:"";
 const url=safeURL(s.url)||doiURL,title=[s.year,s.title].filter(Boolean).join(" · ")||sid;
 const depth=({abstract:"摘要整理",full_text_local:"全文核对",metadata:"仅书目",metadata_only:"仅书目"})[s.read_depth]||"阅读深度未登记";
 return "<div class='source-card'>"+(url?"<a href='"+esc(url)+"' target='_blank' rel='noopener noreferrer'>"+esc(title)+" ↗</a>":esc(title))+"<div class='note'>"+esc(depth)+(s.locator?" · "+esc(s.locator):"")+"</div>"+(doi?"<div class='note'>DOI：<a href='"+esc(doiURL)+"' target='_blank' rel='noopener noreferrer'>"+esc(doi)+" ↗</a></div>":"")+"</div>";
}
function renderReader(id){
 const d=DATA[id],pane=byId("reader");if(!d){pane.innerHTML="<div class='empty'><h2>从左侧选择一条知识</h2><p>这里显示完整步骤、适用条件与原始来源。</p></div>";pane.classList.remove("open");return;}
 pane.classList.add("open");
 const rel=[["相关问题",d.relations.problems],["相关方法",d.relations.methods],["关联实现",d.relations.implementations]].map(([label,ids])=>{const found=(ids||[]).filter(x=>DATA[x]);return found.length?"<h2>"+label+"</h2><div class='chips'>"+found.map(x=>"<button class='chip' data-open='"+esc(x)+"'>"+esc(DATA[x].title)+"</button>").join("")+"</div>":"";}).join("");
 const body=(d.body||"").replace(/^# [^\n]+\n?/,"");
 const warning=d.unverified?"<div class='notice'>来源待核对：以下内容保留用于追溯，不能据此确认论文支持该方法。</div>":"";
 const local=/^entries\/[a-z0-9._-]+\.md$/.test(d.path)?d.path:"";
 pane.innerHTML="<div class='rh'><div class='rh-actions'><span class='meta'>"+esc(d.familyLabel)+" / "+esc(d.kindLabel)+"</span><button class='reader-close' data-close>返回列表 ×</button></div><h1 id='readerTitle' tabindex='-1'>"+esc(d.title)+"</h1>"+(d.originalTitle!==d.title?"<p class='meta'>"+esc(d.originalTitle)+"</p>":"")+"<div class='chips'>"+chips(d)+"</div>"+warning+"</div><article class='rb'>"+(md(body)||"<p>暂无正文</p>")+"<h2>查阅原始来源</h2>"+((d.sourceRefs||[]).map(sourceHTML).join("")||"<p class='note'>该条目没有登记外部来源。</p>")+rel+"<details class='technical'><summary>文件、引用与命令行读取</summary>"+(local?"<p><a href='"+esc(local)+"' target='_blank' rel='noopener'>打开 Markdown 原文 ↗</a></p>":"")+"<p>固定版本："+esc(RELEASE)+"</p><pre>"+esc("python -m knowledge_tools read --release knowledge_store/releases/"+RELEASE+" --id "+d.id)+"</pre><p>"+esc((d.codePaths||[]).join("\n"))+"</p><p>"+esc((d.evidenceRefs||[]).join("\n"))+"</p></details></article><button class='reader-fab' data-close>返回列表</button>";
}
function fillProblemFilter(){
 const sel=byId("problemFilter");if(!sel)return;
 const probs=Object.values(DATA).filter(d=>d.kind==="problem"&&(family==="all"||d.family===family))
  .sort((a,b)=>a.title.localeCompare(b.title));
 const label=p=>p.title.replace(" (literature secondary)","");
 sel.innerHTML="<option value='all'>全部问题形式</option>"+probs.map(p=>"<option value='"+esc(p.id)+"'>"+esc(label(p))+"</option>").join("");
 sel.value=probs.some(p=>p.id===problem)?problem:"all";
 if(sel.value==="all")problem="all";
}
function syncReaderToFilter(){
 const rows=filtered();
 if(!openId){if(window.innerWidth>760&&rows[0]){openId=rows[0].id;renderReader(openId);}else renderReader("");return;}
 if(rows.some(d=>d.id===openId)){renderReader(openId);return;}
 const next=rows[0];
 if(next){openId=next.id;renderReader(openId);if(location.hash)location.hash="#detail-"+openId;}
 else{openId=null;renderReader("");if(location.hash)location.hash="";}
}
function apply(){
 fillProblemFilter();
 byId("kindFilter").value=kind;byId("familyFilter").value=family;byId("clearSearch").hidden=!query;
 document.querySelectorAll("[data-family]").forEach(b=>{const active=b.dataset.family===family&&problem==="all";b.classList.toggle("active",active);b.setAttribute("aria-pressed",active);});
 document.querySelectorAll("[data-problem]").forEach(b=>b.classList.toggle("active",b.dataset.problem===problem));
 renderList();
 syncReaderToFilter();
}
function setView(v){
 view=v;document.querySelectorAll(".view").forEach(b=>{b.classList.toggle("active",b.dataset.view===v);b.setAttribute("aria-pressed",b.dataset.view===v);});
 for(const [id,val]of [["methodsView","methods"],["coverageView","coverage"],["sourceView","sources"],["changeView","changes"]])byId(id).hidden=v!==val;
 byId("toolbar").hidden=v!=="methods";
 if(v==="sources")byId("sourceView").innerHTML="<h1>文献来源</h1><p class='note'>"+Object.keys(SOURCES).length+" 条登记来源 · 书目、阅读深度和链接</p>"+Object.keys(SOURCES).map(sourceHTML).join("");
}
function openEntry(id,focus=true){
 if(!DATA[id])return;
 const d=DATA[id];
 family=d.family;kind="all";problem="all";
 setView("methods");openId=id;apply();renderReader(id);
 if(location.hash!=="#detail-"+id)location.hash="#detail-"+id;
 byId("reader").scrollTop=0;if(focus){const t=byId("readerTitle");if(t)t.focus({preventScroll:true});}
}
function closeReader(){openId=null;renderReader("");renderList();if(location.hash)location.hash="";}
document.body.addEventListener("click",e=>{
 const t=e.target.closest("button");if(!t)return;
 if(t.hasAttribute("data-open")){openEntry(t.dataset.open);return;}
 if(t.hasAttribute("data-close")){closeReader();return;}
 if(t.hasAttribute("data-view")){setView(t.dataset.view);return;}
 if(t.hasAttribute("data-family")){family=t.dataset.family;problem="all";apply();return;}
 if(t.hasAttribute("data-problem")){problem=t.dataset.problem;family=DATA[problem].family;apply();return;}
 if(t.hasAttribute("data-reset")){query="";family="all";problem="all";kind="method";byId("q").value="";apply();}
});
byId("kindFilter").addEventListener("change",e=>{kind=e.target.value;apply();});
byId("familyFilter").addEventListener("change",e=>{family=e.target.value;problem="all";apply();});
byId("problemFilter").addEventListener("change",e=>{
 problem=e.target.value;
 if(problem!=="all"&&DATA[problem])family=DATA[problem].family;
 apply();
});
byId("q").addEventListener("input",e=>{query=e.target.value;apply();});
byId("clearSearch").addEventListener("click",()=>{query="";byId("q").value="";apply();byId("q").focus();});
document.addEventListener("keydown",e=>{if(e.key==="Escape")closeReader();});
window.addEventListener("hashchange",()=>{const m=/^#detail-(.+)$/.exec(location.hash);if(m&&DATA[m[1]]){if(openId!==m[1])openEntry(m[1],false);}else{openId=null;renderReader("");renderList();}});
apply();const boot=/^#detail-(.+)$/.exec(location.hash);
if(boot&&DATA[boot[1]])openEntry(boot[1],false);else{const first=filtered()[0];openId=first?first.id:null;renderReader(openId);renderList();if(window.innerWidth<=760){openId=null;renderReader("");renderList();}}
"""

def dashboard_html(release_id, index, taxonomy, sources, pending, diff, inventory=None, bodies=None) -> str:
    source_map = _source_map(sources or {})
    bodies = bodies or {}
    entries = [e for e in (index or {}).get("entries", []) if isinstance(e, Mapping)]
    payloads = [_payload(e, body=bodies.get(str(e.get("id")), ""), sources=source_map) for e in entries]
    data = {p["id"]: p for p in payloads}
    grouped = {}
    for p in payloads:
        grouped.setdefault(p["family"], []).append(p)
    ordered = [str(p.get("id")) for p in (taxonomy or {}).get("pages", []) if p.get("id") in grouped]
    families = list(dict.fromkeys(ordered + sorted(grouped)))
    family_map = {fid: _family_label(fid) for fid in families}
    tree = ['<h3>按问题浏览</h3><button class="tbtn active" data-family="all"><span>全部问题</span><span class="n">'+str(len(data))+'</span></button>']
    for fid in families:
        group = grouped[fid]
        tree.append('<button class="tbtn" data-family="'+_esc(fid)+'"><span>'+_esc(family_map[fid])+'</span><span class="n">'+str(len(group))+'</span></button>')
        probs = [p for p in group if p["kind"] == "problem"]
        if probs:
            tree.append('<details class="family-group"><summary>'+str(len(probs))+' 种问题形式</summary>')
            for p in probs:
                label = p["title"].replace(" (literature secondary)", "")
                tree.append('<button class="child" data-problem="'+_esc(p["id"])+'">'+_esc(label)+'</button>')
            tree.append('</details>')
    options = '<option value="all">全部问题</option>'+''.join('<option value="'+_esc(fid)+'">'+_esc(family_map[fid])+'</option>' for fid in families)
    kinds = '<option value="method">方法</option><option value="all">全部类型</option>'+''.join('<option value="'+k+'">'+v+'</option>' for k,v in KIND_LABELS.items() if k != "method")
    header = '<header class="topbar"><div class="brand">优化知识库<small>OPTIMIZATION LIBRARY</small></div><nav class="views" aria-label="主导航">'+''.join('<button class="view'+(' active' if v=='methods' else '')+'" data-view="'+v+'">'+label+'</button>' for v,label in [('methods','浏览'),('sources','文献'),('coverage','覆盖'),('changes','版本变更')])+'</nav><details class="ver"><summary>版本信息</summary><p>'+_esc(release_id)+'<br>main '+_esc((index or {}).get('source_main_sha',''))+'</p></details></header>'
    toolbar = '<div class="toolbar" id="toolbar"><div class="search"><input id="q" type="search" placeholder="搜索算法、问题或正文，例如 2-opt、装箱" aria-label="搜索知识"><button id="clearSearch" aria-label="清空搜索" hidden>×</button></div><div class="filter mobile-family"><label for="familyFilter">问题</label><select id="familyFilter" aria-label="问题族">'+options+'</select></div><div class="filter mobile-family"><label for="problemFilter">问题形式</label><select id="problemFilter" aria-label="问题形式"><option value="all">全部问题形式</option></select></div><div class="filter"><label for="kindFilter">查看</label><select id="kindFilter" aria-label="条目类型">'+kinds+'</select></div></div>'
    main = '<main class="app" id="methodsView"><nav class="tree" aria-label="问题分类">'+''.join(tree)+'</nav><section class="list" aria-label="知识列表"><div class="list-head"><h2 id="listTitle">浏览知识</h2><span id="listDesc" aria-live="polite"></span></div><div id="cards"></div></section><aside class="reader" id="reader" aria-label="知识正文"></aside></main>'
    rows = ''.join('<tr><th>'+_esc(family_map[fid])+'</th>'+''.join('<td><div class="mcell"><b>'+str(sum(p['kind']==k for p in grouped[fid]))+'</b></div></td>' for k in ('problem','method','implementation'))+'</tr>' for fid in families)
    coverage = '<section class="page" id="coverageView" hidden><h1>知识覆盖</h1><p class="note">统计登记条目数量，不代表算法效果或证据已验证。</p><table class="matrix"><thead><tr><th>问题族</th><th>问题形式</th><th>方法</th><th>实现</th></tr></thead><tbody>'+rows+'</tbody></table></section>'
    prev = (diff or {}).get("previous_release_id")
    baseline = _esc(release_id) + " 为当前展示基线" if not prev else _esc(prev) + " → " + _esc(release_id)
    changes = '<section class="page" id="changeView" hidden><h1>版本变更</h1><p class="note">'+baseline+'。对照目录必须实际存在于 knowledge_store/releases/。</p>'
    for key,label in [('added','新增'),('changed','更新'),('removed','移除')]:
        ids = (diff or {}).get(key) or []
        changes += '<h2>'+label+' · '+str(len(ids))+'</h2>'
        changes += ''.join('<button class="chip" data-open="'+_esc(eid)+'">'+_esc(data[eid]['title'])+'</button>' if eid in data else '<span class="chip">'+_esc(eid)+'</span>' for eid in ids)
    changes += '<p class="note">正文变更 '+str(len((diff or {}).get('changed_body') or []))+' · 元数据变更 '+str(len((diff or {}).get('changed_metadata') or []))+'</p></section>'
    values = {'__DATA__':data,'__SOURCES__':source_map,'__ALIASES__':QUERY_ALIASES,'__FAMILIES__':family_map,'__RELEASE__':release_id}
    script = re.sub(r'__(?:DATA|SOURCES|ALIASES|FAMILIES|RELEASE)__', lambda m: json.dumps(values[m[0]],ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'), _SCRIPT)
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>优化知识库 · '+_esc(release_id)+'</title><style>'+_STYLE+'</style></head><body>'+header+toolbar+main+coverage+'<section class="page" id="sourceView" hidden></section>'+changes+'<script>'+script+'</script></body></html>'

__all__ = ["dashboard_html", "tokenize_query"]
