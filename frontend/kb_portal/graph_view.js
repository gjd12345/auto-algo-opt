/* Visual 3-Column Knowledge Constellation Graph + Encyclopedia + Slide-Over Editorial Reader. */
(function () {
  "use strict";

  const FAMILY_ORDER = ["cvrp", "tsp", "online_bin_packing", "knapsack", "mixer_split", "insertships_routing"];
  const FAMILY_NAMES = {
    cvrp: "带容量车辆路径 (CVRP)",
    tsp: "旅行商问题 (TSP)",
    online_bin_packing: "在线装箱 (OBP)",
    knapsack: "背包问题",
    mixer_split: "混料分批优化",
    insertships_routing: "船舶插入路径",
    unknown: "通用算法框架"
  };

  const TYPE_NAMES = {
    evidence: "实证发现",
    framework: "统一理论框架",
    method: "算法机理与规则",
    implementation: "工程实现",
    problem: "问题定义与基准"
  };

  function renderConstellation(data, st, R) {
    const entries = data.entries || [];
    const activeFam = st.kbFam || "";
    const activeType = st.kbType || "";

    // Count by family and type
    const famCounts = {};
    const typeCounts = {};
    const linkPairs = {};
    entries.forEach(function (e) {
      const f = e.problem_family || "unknown";
      const t = e.type || "method";
      famCounts[f] = (famCounts[f] || 0) + 1;
      typeCounts[t] = (typeCounts[t] || 0) + 1;
      const pk = f + "|" + t;
      linkPairs[pk] = (linkPairs[pk] || 0) + 1;
    });

    const fams = FAMILY_ORDER.filter(function (f) { return famCounts[f] > 0; });
    if (famCounts.unknown) fams.push("unknown");
    const types = ["framework", "evidence", "method", "implementation", "problem"].filter(function (t) { return typeCounts[t] > 0; });

    // Featured spotlight entries (8 high-value cards)
    const spotlights = entries.filter(function (e) {
      if (activeFam && e.problem_family !== activeFam) return false;
      if (activeType && e.type !== activeType) return false;
      return e.featured || e.type === "framework" || e.type === "evidence";
    }).slice(0, 7);

    const W = 960, H = 310;
    const xFam = 24, wFam = 220;
    const xType = 340, wType = 210;
    const xSpot = 640, wSpot = 296;

    const famCoords = {};
    fams.forEach(function (f, i) {
      famCoords[f] = 22 + i * ((H - 36) / Math.max(1, fams.length));
    });
    const typeCoords = {};
    types.forEach(function (t, i) {
      typeCoords[t] = 30 + i * ((H - 46) / Math.max(1, types.length));
    });
    const spotCoords = {};
    spotlights.forEach(function (s, i) {
      spotCoords[s.id] = 22 + i * ((H - 36) / Math.max(1, spotlights.length));
    });

    // Bezier edges fam -> type
    let edgesSvg = "";
    Object.keys(linkPairs).forEach(function (pk) {
      const parts = pk.split("|");
      const f = parts[0], t = parts[1];
      if (famCoords[f] === undefined || typeCoords[t] === undefined) return;
      const hi = (!activeFam && !activeType) || (activeFam === f && (!activeType || activeType === t)) || (activeType === t && (!activeFam || activeFam === f));
      const x1 = xFam + wFam, y1 = famCoords[f] + 16;
      const x2 = xType, y2 = typeCoords[t] + 18;
      const cx = (x1 + x2) / 2;
      const sw = Math.max(1, Math.min(5, Math.sqrt(linkPairs[pk]) * 0.65));
      edgesSvg += '<path d="M ' + x1 + " " + y1 + " C " + cx + " " + y1 + ", " + cx + " " + y2 + ", " + x2 + " " + y2 + '" fill="none" stroke="' + (hi ? "#2b4c7e" : "#d4cdbd") + '" stroke-width="' + sw.toFixed(1) + '" opacity="' + (hi ? "0.42" : "0.18") + '"/>';
    });

    // Bezier edges type -> spotlight
    spotlights.forEach(function (s) {
      const t = s.type || "method";
      if (typeCoords[t] === undefined || spotCoords[s.id] === undefined) return;
      const x1 = xType + wType, y1 = typeCoords[t] + 18;
      const x2 = xSpot, y2 = spotCoords[s.id] + 15;
      const cx = (x1 + x2) / 2;
      edgesSvg += '<path d="M ' + x1 + " " + y1 + " C " + cx + " " + y1 + ", " + cx + " " + y2 + ", " + x2 + " " + y2 + '" fill="none" stroke="#0f766e" stroke-width="1.5" opacity="0.38"/>';
    });

    const famNodes = fams.map(function (f) {
      const y = famCoords[f];
      const on = activeFam === f;
      return '<g class="graph-node" data-g-fam="' + f + '">' +
        '<rect x="' + xFam + '" y="' + y.toFixed(1) + '" width="' + wFam + '" height="32" rx="8" fill="' + (on ? "#2b4c7e" : "#ffffff") + '" stroke="' + (on ? "#2b4c7e" : "#d4cdbd") + '" stroke-width="1.2"/>' +
        '<text x="' + (xFam + 12) + '" y="' + (y + 20).toFixed(1) + '" font-size="12.5" font-weight="600" fill="' + (on ? "#ffffff" : "#1c1917") + '">' + R.esc(FAMILY_NAMES[f] || f) + "</text>" +
        '<text x="' + (xFam + wFam - 10) + '" y="' + (y + 20).toFixed(1) + '" text-anchor="end" font-size="11.5" fill="' + (on ? "#eef2f8" : "#78716c") + '">' + famCounts[f] + "</text>" +
        "</g>";
    }).join("");

    const typeNodes = types.map(function (t) {
      const y = typeCoords[t];
      const on = activeType === t;
      return '<g class="graph-node" data-g-type="' + t + '">' +
        '<rect x="' + xType + '" y="' + y.toFixed(1) + '" width="' + wType + '" height="36" rx="8" fill="' + (on ? "#0f766e" : "#ffffff") + '" stroke="' + (on ? "#0f766e" : "#d4cdbd") + '" stroke-width="1.2"/>' +
        '<text x="' + (xType + 12) + '" y="' + (y + 22).toFixed(1) + '" font-size="12.5" font-weight="600" fill="' + (on ? "#ffffff" : "#1c1917") + '">' + R.esc(TYPE_NAMES[t] || t) + "</text>" +
        '<text x="' + (xType + wType - 10) + '" y="' + (y + 22).toFixed(1) + '" text-anchor="end" font-size="11.5" fill="' + (on ? "#ecf7f5" : "#78716c") + '">' + typeCounts[t] + "</text>" +
        "</g>";
    }).join("");

    const spotNodes = spotlights.map(function (s) {
      const y = spotCoords[s.id];
      const title = s.display_title.length > 22 ? s.display_title.slice(0, 21) + "…" : s.display_title;
      return '<g class="graph-node" data-open-entry="' + R.esc(s.id) + '">' +
        '<rect x="' + xSpot + '" y="' + y.toFixed(1) + '" width="' + wSpot + '" height="30" rx="8" fill="#fcfbf8" stroke="#0f766e" stroke-width="1.2"/>' +
        '<text x="' + (xSpot + 12) + '" y="' + (y + 19).toFixed(1) + '" font-size="12" font-weight="500" fill="#1c1917">' + R.esc(title) + "</text>" +
        "</g>";
    }).join("");

    return '<div class="graph-panel">' +
      '  <div class="graph-header">' +
      '    <div><h2 class="serif" style="margin:0;font-size:19px;">知识脉络图谱：问题域 → 知识层级 → 代表成果</h2><div class="muted" style="font-size:13px;">点击左/中列节点即可高亮脉络并同步筛选下方百科卡片；点击右侧节点直接阅读全文。</div></div>' +
           ((activeFam || activeType) ? '<button type="button" class="btn sm" id="graph-reset-btn">重置图谱选中状态</button>' : "") +
      "  </div>" +
      '  <div class="graph-svg-wrap">' +
      '    <svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="305">' +
             edgesSvg + famNodes + typeNodes + spotNodes +
      "    </svg>" +
      "  </div>" +
      "</div>";
  }

  function renderEncyclopedia(data, st, R) {
    const entries = data.entries || [];
    const sources = data.sources || [];
    const subTab = st.kbSubTab || "cards";
    const q = (st.kbQuery || "").trim().toLowerCase();
    const fFam = st.kbFam || "";
    const fType = st.kbType || "";

    const matched = entries.filter(function (e) {
      if (fFam && e.problem_family !== fFam) return false;
      if (fType && e.type !== fType) return false;
      if (q && !(e.search_text || "").includes(q)) return false;
      return true;
    });

    const famPills = ['<button type="button" class="chip ' + (!fFam ? "active" : "") + '" data-f-fam="">全部问题域</button>']
      .concat(FAMILY_ORDER.map(function (f) {
        return '<button type="button" class="chip ' + (fFam === f ? "active" : "") + '" data-f-fam="' + f + '">' + R.esc(FAMILY_NAMES[f]) + "</button>";
      })).join("");

    const typePills = ['<button type="button" class="chip ' + (!fType ? "active" : "") + '" data-f-type="">全部类别</button>']
      .concat(["framework", "evidence", "method", "implementation", "problem"].map(function (t) {
        return '<button type="button" class="chip ' + (fType === t ? "active" : "") + '" data-f-type="' + t + '">' + R.esc(TYPE_NAMES[t]) + "</button>";
      })).join("");

    let contentHtml = "";
    if (subTab === "sources") {
      const matchedSources = sources.filter(function (s) {
        if (!q) return true;
        return [s.display_title, s.venue, (s.authors || []).join(" "), s.year].join(" ").toLowerCase().includes(q);
      });
      contentHtml = '<div class="muted" style="margin-bottom:12px;font-size:13px;">共检索到 <b>' + matchedSources.length + "</b> 篇学术文献与研究报告</div>" +
        '<div class="source-grid">' +
        matchedSources.map(function (s) {
          const auth = (s.authors || []).slice(0, 3).join(", ") + ((s.authors || []).length > 3 ? " 等" : "");
          return '<div class="source-card">' +
            '<div style="font-size:12px;color:var(--teal);font-weight:600;margin-bottom:4px;">' + R.esc(s.year || "") + (s.venue ? " · " + R.esc(s.venue) : "") + "</div>" +
            '<div class="serif" style="font-size:15.5px;font-weight:700;line-height:1.4;margin-bottom:6px;">' + R.esc(s.display_title) + "</div>" +
            '<div class="muted" style="font-size:12.5px;margin-bottom:8px;">作者：' + R.esc(auth || "研究组核验记录") + "</div>" +
            (s.doi ? ('<div style="font-size:12px;">DOI: <a href="https://doi.org/' + R.esc(s.doi) + '" target="_blank" rel="noopener">' + R.esc(s.doi) + "</a></div>") : "") +
            "</div>";
        }).join("") +
        "</div>";
    } else {
      const showLimit = st.kbLimit || 45;
      const shown = matched.slice(0, showLimit);
      contentHtml = '<div class="muted" style="margin-bottom:12px;font-size:13px;">已筛选出 <b>' + matched.length + "</b> 条知识卡片（点击任意卡片展开杂志级富文本解读）</div>" +
        '<div class="kb-card-grid">' +
        shown.map(function (e) {
          const isAnti = e.knowledge_tier === "failure_antipattern";
          const tCls = isAnti ? "antipattern" : (e.type === "evidence" ? "evidence" : (e.type === "framework" ? "framework" : ""));
          const tLabel = isAnti ? "反模式警示" : (TYPE_NAMES[e.type] || e.type);
          return '<article class="kb-card" data-open-entry="' + R.esc(e.id) + '">' +
            '  <div>' +
            '    <div class="kb-badges">' +
            '      <span class="badge fam">' + R.esc(FAMILY_NAMES[e.problem_family] || "通用") + "</span>" +
            '      <span class="badge ' + tCls + '">' + R.esc(tLabel) + "</span>" +
            "    </div>" +
            '    <h3 class="kb-card-title">' + R.esc(e.display_title) + "</h3>" +
            '    <p class="kb-card-summary">' + R.esc(e.clean_summary) + "</p>" +
            "  </div>" +
            '  <div class="kb-card-foot">' +
            '    <span>' + (e.relations_count > 0 ? ("关联 " + e.relations_count + " 项") : "基础条目") + "</span>" +
            '    <span style="color:var(--indigo);font-weight:500;">展开阅读 &rarr;</span>' +
            "  </div>" +
            "</article>";
        }).join("") +
        "</div>" +
        (matched.length > shown.length ? ('<div style="text-align:center;margin-top:22px;"><button type="button" class="btn" id="kb-load-more">展开更多条目（已显示 ' + shown.length + " / " + matched.length + "）</button></div>") : "");
    }

    return renderConstellation(data, st, R) +
      '<div class="filter-bar">' +
      '  <input id="kb-search-input" class="search-input" type="search" placeholder="输入关键词搜索（如：车队、出发、早停、装箱、紧度、负迁移、2-opt…）" value="' + R.esc(st.kbQuery || "") + '"/>' +
      '  <div style="display:flex;gap:6px;">' +
      '    <button type="button" class="btn sm ' + (subTab === "cards" ? "active" : "") + '" data-kb-subtab="cards">知识百科 (' + entries.length + ")</button>" +
      '    <button type="button" class="btn sm ' + (subTab === "sources" ? "active" : "") + '" data-kb-subtab="sources">参考文献 (' + sources.length + ")</button>" +
      "  </div>" +
      '  <div style="flex-basis:100%;display:flex;flex-wrap:wrap;gap:10px;align-items:center;">' +
      '    <div class="chip-group">' + famPills + "</div>" +
      '    <div class="chip-group">' + typePills + "</div>" +
      "  </div>" +
      "</div>" +
      contentHtml;
  }

  function renderDrawer(data, entryId, history, R) {
    const entry = (data.entries || []).find(function (e) { return e.id === entryId; });
    if (!entry) return "";
    const entryMap = {};
    (data.entries || []).forEach(function (e) { entryMap[e.id] = e; });
    const srcMap = {};
    (data.sources || []).forEach(function (s) { srcMap[s.id] = s; });

    const bp = entry.interface_blueprint;
    const bpHtml = bp ? ('<div class="blueprint-grid">' +
      '<div class="blueprint-box"><h4>外层算法骨架</h4><div>' + R.esc(bp.skeleton_role || "") + "</div></div>" +
      '<div class="blueprint-box"><h4>可进化决策函数接口</h4><div class="mono">' + R.esc(bp.evolvable_hook || "") + "</div></div>" +
      '<div class="blueprint-box"><h4>约束与不变式</h4><ul style="margin:4px 0 0;padding-left:18px;">' + (bp.invariants_and_constraints || []).map(function (x) { return "<li>" + R.esc(x) + "</li>"; }).join("") + "</ul></div>" +
      '<div class="blueprint-box"><h4>工程设计注意点</h4><ul style="margin:4px 0 0;padding-left:18px;">' + (bp.typical_pitfalls || []).map(function (x) { return "<li>" + R.esc(x) + "</li>"; }).join("") + "</ul></div>" +
      "</div>") : "";

    const mathList = entry.math_formulation || [];
    const mathHtml = mathList.length ? ('<h3 style="margin:20px 0 8px;font-size:15px;color:var(--indigo);">数学形式化表达</h3>' +
      mathList.map(function (m) {
        return '<div class="math-display" style="text-align:left;font-size:14.5px;"><div><b>' + R.esc(m.expr || "") + "</b></div>" +
          (m.preconditions ? ('<div class="muted" style="font-size:12.5px;margin-top:4px;font-family:var(--font-sans);">适用前提：' + R.esc(m.preconditions) + "</div>") : "") +
          "</div>";
      }).join("")) : "";

    const relIds = entry.related_entry_ids || [];
    const relHtml = relIds.length ? ('<div style="margin-top:24px;padding-top:18px;border-top:1px solid var(--border-warm);">' +
      '<h3 style="margin:0 0 8px;font-size:14.5px;">关联知识节点</h3><div class="rel-pills">' +
      relIds.map(function (rid) {
        const target = entryMap[rid];
        if (!target) return "";
        return '<button type="button" class="rel-pill" data-open-entry="' + R.esc(rid) + '">' + R.esc(target.display_title) + " &rarr;</button>";
      }).join("") +
      "</div></div>") : "";

    const srcIds = entry.source_refs || [];
    const srcHtml = srcIds.length ? ('<div style="margin-top:22px;padding-top:18px;border-top:1px solid var(--border-warm);">' +
      '<h3 style="margin:0 0 10px;font-size:14.5px;">支撑文献与研究来源</h3>' +
      srcIds.map(function (sid) {
        const s = srcMap[sid];
        if (!s) return "";
        return '<div class="source-card" style="margin-bottom:10px;padding:12px 16px;">' +
          '<div class="serif" style="font-weight:700;font-size:14.5px;">' + R.esc(s.display_title) + "</div>" +
          '<div class="muted" style="font-size:12.5px;margin-top:2px;">' + R.esc((s.authors || []).join(", ")) + " · " + R.esc(s.year || "") + (s.venue ? " · " + R.esc(s.venue) : "") + "</div>" +
          (s.doi ? ('<div style="font-size:12px;margin-top:4px;">DOI: <a href="https://doi.org/' + R.esc(s.doi) + '" target="_blank" rel="noopener">' + R.esc(s.doi) + "</a></div>") : "") +
          "</div>";
      }).join("") +
      "</div>") : "";

    return '<div class="drawer-topbar">' +
      '  <div style="display:flex;align-items:center;gap:10px;">' +
           (history.length > 1 ? '<button type="button" class="btn sm" id="drawer-back-btn">&larr; 返回上一条</button>' : "") +
      '    <span class="muted" style="font-size:13px;">' + R.esc(FAMILY_NAMES[entry.problem_family] || "通用") + " / " + R.esc(TYPE_NAMES[entry.type] || entry.type) + "</span>" +
      "  </div>" +
      '  <button type="button" class="btn sm" id="drawer-close-btn">关闭 &times;</button>' +
      "</div>" +
      '<div class="drawer-body"><div class="editorial-body">' +
      '  <h1 class="editorial-title">' + R.esc(entry.display_title) + "</h1>" +
      '  <div class="editorial-lead">' + R.esc(entry.clean_summary) + "</div>" +
         bpHtml + mathHtml +
         R.renderRichMarkdown(entry.clean_body || "") +
         relHtml + srcHtml +
      "</div></div>";
  }

  function bind(container, data, st, setState) {
    container.querySelectorAll("[data-g-fam]").forEach(function (el) {
      el.addEventListener("click", function () {
        const f = el.getAttribute("data-g-fam");
        setState({ kbFam: st.kbFam === f ? "" : f, kbLimit: 45 });
      });
    });
    container.querySelectorAll("[data-g-type]").forEach(function (el) {
      el.addEventListener("click", function () {
        const t = el.getAttribute("data-g-type");
        setState({ kbType: st.kbType === t ? "" : t, kbLimit: 45 });
      });
    });
    const gReset = container.querySelector("#graph-reset-btn");
    if (gReset) gReset.addEventListener("click", function () { setState({ kbFam: "", kbType: "" }); });

    const sIn = container.querySelector("#kb-search-input");
    if (sIn) {
      sIn.addEventListener("input", function () {
        const pos = sIn.selectionStart;
        setState({ kbQuery: sIn.value, kbLimit: 45 }, false, function (root) {
          const inp = root.querySelector("#kb-search-input");
          if (inp) { inp.focus(); try { inp.setSelectionRange(pos, pos); } catch (e) {} }
        });
      });
    }
    container.querySelectorAll("[data-kb-subtab]").forEach(function (b) {
      b.addEventListener("click", function () { setState({ kbSubTab: b.getAttribute("data-kb-subtab") }); });
    });
    container.querySelectorAll("[data-f-fam]").forEach(function (b) {
      b.addEventListener("click", function () { setState({ kbFam: b.getAttribute("data-f-fam"), kbLimit: 45 }); });
    });
    container.querySelectorAll("[data-f-type]").forEach(function (b) {
      b.addEventListener("click", function () { setState({ kbType: b.getAttribute("data-f-type"), kbLimit: 45 }); });
    });
    const moreBtn = container.querySelector("#kb-load-more");
    if (moreBtn) moreBtn.addEventListener("click", function () { setState({ kbLimit: (st.kbLimit || 45) + 45 }); });
  }

  window.KB_GRAPH_VIEW = {
    render: renderEncyclopedia,
    renderDrawer: renderDrawer,
    bind: bind,
    FAMILY_NAMES: FAMILY_NAMES,
    TYPE_NAMES: TYPE_NAMES
  };
})();
