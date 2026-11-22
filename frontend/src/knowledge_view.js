/* L3 · Distill-Style Warm-Paper Mechanism Stream + Full Structured KB Reader. */
(function () {
  "use strict";

  const STORIES = {
    h003: { id: "h003", kbId: "evidence-cvrp-depot-start-phase-h003", label: "1. 出发步相变 (H-003)", title: "仓库出发步 α=1 相位反转与反事实替换" },
    h001: { id: "h001", kbId: "evidence-cvrp-scale-collapse-h001", label: "2. 标度不变性 (H-001)", title: "绝对带宽门控 × O(1/s²) 载荷导致的缩尺崩塌" },
    r5: { id: "r5", kbId: "evidence-cvrp-stage2-math-discoveries-h004-h009", label: "3. 主动早返 (R5)", title: "无量纲内旋与容量自适应主动早返阈值" },
    h010: { id: "h010", kbId: "evidence-cvrp-selection-complementarity-h010", label: "4. 互补边界 (H-010)", title: "折外选择边界与单步接口范式上限" }
  };

  function dist2d(a, b) {
    return Math.hypot(a[0] - b[0], a[1] - b[1]);
  }

  function renderH003Body(core, alpha, L) {
    const hp = core.h003_preview;
    const inst = hp.instances.find(function (x) { return x.id === hp.example; }) || hp.instances[0];
    const depot = inst.coords[0];
    const all = [];
    for (let j = 1; j < inst.coords.length; j++) {
      const dj = dist2d(depot, inst.coords[j]);
      all.push({ j: j, d0: dj, score: (1 - alpha) * dj, q: inst.demands[j], coord: inst.coords[j] });
    }
    all.sort(function (a, b) { return a.score - b.score; });
    const top5 = all.slice(0, 5);
    const maxS = Math.max(1e-6, Math.max.apply(null, top5.map(function (c) { return Math.abs(c.score); })));
    const picks = {};
    top5.slice(0, 3).forEach(function (c) { picks[c.j] = true; });

    const W = 400, H = 260, pad = 24;
    const sx = function (x) { return pad + x * (W - pad * 2); };
    const sy = function (y) { return H - pad - y * (H - pad * 2); };
    const lineCol = alpha > 1 ? "#0f766e" : (Math.abs(alpha - 1) < 0.005 ? "#94a3b8" : "#c2410c");
    const lines = top5.slice(0, 3).map(function (c) {
      return '<line x1="' + sx(depot[0]).toFixed(1) + '" y1="' + sy(depot[1]).toFixed(1) + '" x2="' + sx(c.coord[0]).toFixed(1) + '" y2="' + sy(c.coord[1]).toFixed(1) + '" stroke="' + lineCol + '" stroke-width="1.8" stroke-dasharray="4,3"/>';
    }).join("");
    const dots = inst.coords.map(function (p, idx) {
      if (idx === 0) return '<rect x="' + (sx(p[0]) - 4.5).toFixed(1) + '" y="' + (sy(p[1]) - 4.5).toFixed(1) + '" width="9" height="9" fill="#1d2129"/>';
      const isPick = Boolean(picks[idx]);
      return '<circle cx="' + sx(p[0]).toFixed(1) + '" cy="' + sy(p[1]).toFixed(1) + '" r="' + (isPick ? 4.5 : 2.3) + '" fill="' + (isPick ? lineCol : "#94a3b8") + '" opacity="' + (isPick ? "0.95" : "0.5") + '"/>';
    }).join("");

    const bars = top5.map(function (c) {
      const pct = Math.min(100, (Math.abs(c.score) / maxS) * 100);
      return '<div style="margin-bottom:8px;"><div style="display:flex;justify-content:space-between;font-size:12.5px;"><span>客户 #' + c.j + " (d0=" + c.d0.toFixed(3) + ')</span><span class="mono">' + c.score.toFixed(4) + '</span></div><div class="rank-bar-track"><div class="rank-bar-fill" style="width:' + pct.toFixed(1) + "%;background:" + lineCol + ';"></div></div></div>';
    }).join("");

    const stateDesc = Math.abs(alpha - 1) < 0.005 ? "α = 1.00：所有候选得分恒为 0（临界中性）"
      : alpha < 1 ? "α < 1：最近邻优先（近端先出，远端残留至尾部）" : "α > 1：远端优先（先赴外围，回程顺路服务近郊）";

    return '<div style="font-size:13px;font-weight:600;color:' + lineCol + ';margin-bottom:10px;">' + L.esc(stateDesc) + "</div>" +
      '<div class="grid-2"><div class="plot-box"><svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="235"><rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fafbfc"/>' + lines + dots + "</svg></div><div>" + bars + "</div></div>";
  }

  function renderH001Body(core, scaleVal, L) {
    const recs = (core.scale_stress && core.scale_stress.records) || [];
    const byAlg = {};
    recs.forEach(function (r) {
      const aid = r.algorithm_id;
      byAlg[aid] = Math.max(byAlg[aid] || 0, Math.abs(Number(r.scale_drift_pct || 0)));
    });
    const order = ["c", "eohs_cvrp_f1", "v0", "s2_r5_spiral", "s2_r7_iso", "nn", "cw_relocate_2opt"];
    return order.filter(function (id) { return byAlg[id] !== undefined; }).map(function (aid) {
      const real = byAlg[aid];
      const est = aid === "c" ? Math.min(250, real * Math.pow(0.001 / Math.max(1e-4, scaleVal), 1.4))
        : (real > 0 ? real * Math.min(2, 0.001 / Math.max(1e-4, scaleVal)) : 0);
      const shown = Math.abs(scaleVal - 0.001) < 1e-6 ? real : est;
      const col = shown > 1 ? "var(--terra)" : "var(--teal)";
      return "<tr><td>" + L.esc(L.algTitle(core, aid)) + '</td><td class="num">' + real.toFixed(2) + '%</td><td class="num" style="color:' + col + ';font-weight:600;">' + shown.toFixed(2) + "%</td></tr>";
    }).join("");
  }

  function renderR5Body(pressPct) {
    const p = pressPct / 100, tau = 0.25 + 0.5 * p;
    const W = 500, H = 200, pl = 46, pr = 20, pt = 18, pb = 34;
    const px = pl + p * (W - pl - pr), py = H - pb - Math.min(1, tau) * (H - pt - pb);
    return '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="190" style="background:#fafbfc;border:1px solid #e5e7eb;border-radius:6px;">' +
      '<line x1="' + pl + '" y1="' + (H - pb) + '" x2="' + (W - pr) + '" y2="' + (H - pb) + '" stroke="#cbd5e1"/>' +
      '<line x1="' + pl + '" y1="' + pt + '" x2="' + pl + '" y2="' + (H - pb) + '" stroke="#cbd5e1"/>' +
      '<line x1="' + pl + '" y1="' + (H - pb - 0.25 * (H - pt - pb)).toFixed(1) + '" x2="' + (W - pr) + '" y2="' + (H - pb - 0.75 * (H - pt - pb)).toFixed(1) + '" stroke="#c2410c" stroke-width="2"/>' +
      '<circle cx="' + px.toFixed(1) + '" cy="' + py.toFixed(1) + '" r="5" fill="#165dff" stroke="#fff" stroke-width="1.5"/>' +
      '<text x="' + (pl + 12) + '" y="' + (pt + 16) + '" font-size="11.5" fill="#0f766e">阈值上方：顺路继续访问可行客户</text>' +
      '<text x="' + (pl + 12) + '" y="' + (H - pb - 10) + '" font-size="11.5" fill="#c2410c">阈值下方：触发主动早返 (return 0)</text>' +
      "</svg>";
  }

  function renderBlueprintGrid(entry, L) {
    const bp = entry && entry.attributes && entry.attributes.interface_blueprint;
    if (!bp) return "";
    return '<div class="blueprint-grid">' +
      '<div class="blueprint-box"><h4>外层骨架 (Skeleton)</h4><div>' + L.esc(bp.skeleton_role || "") + "</div></div>" +
      '<div class="blueprint-box"><h4>进化入口 (Evolvable Hook)</h4><div class="mono">' + L.esc(bp.evolvable_hook || "") + "</div></div>" +
      '<div class="blueprint-box"><h4>数学不变式</h4><ul>' + (bp.invariants_and_constraints || []).map(function (x) { return "<li>" + L.esc(x) + "</li>"; }).join("") + "</ul></div>" +
      '<div class="blueprint-box"><h4>工程约束提示</h4><ul>' + (bp.typical_pitfalls || []).map(function (x) { return "<li>" + L.esc(x) + "</li>"; }).join("") + "</ul></div>" +
      "</div>";
  }

  function renderStoryView(core, state, L) {
    const key = (state.topic && STORIES[state.topic]) ? state.topic : (state.story && STORIES[state.story]) ? state.story : "h003";
    const meta = STORIES[key];
    const map = L.kbMap(core);
    const entry = map[meta.kbId];
    const alpha = state.mlAlpha !== undefined ? Number(state.mlAlpha) : 1.15;
    const scaleVal = state.mlScale !== undefined ? Number(state.mlScale) : 0.001;
    const pressPct = state.mlPress !== undefined ? Number(state.mlPress) : 65;

    let labHtml = "";
    if (key === "h003" && core.h003_preview) {
      labHtml = '<div class="formula-center"><i>s</i><sub>α</sub>(0, <i>j</i>) = (1 − α) <i>d</i>(0, <i>j</i>)</div>' +
        '<div class="microlab-frame">' +
        '  <div class="controls-inline" style="justify-content:space-between;margin-bottom:8px;"><span>径向偏置参数 α = <b id="ml-alpha-val" class="mono">' + alpha.toFixed(2) + '</b></span><div class="controls-inline"><button class="btn sm" data-alpha-preset="0.80">0.80 (近邻优先)</button><button class="btn sm active" data-alpha-preset="1.15">1.15 (远端优先)</button></div></div>' +
        '  <input id="ml-alpha-slider" type="range" min="0.60" max="1.40" step="0.01" value="' + alpha.toFixed(2) + '"/>' +
        '  <div id="ml-h003-out" style="margin-top:12px;">' + renderH003Body(core, alpha, L) + "</div>" +
        "</div>";
    } else if (key === "h001") {
      labHtml = '<div class="formula-center"><i>f</i>(λ<i>D</i>, <i>q</i>, <i>Q</i>) = λ<sup><i>k</i></sup> <i>f</i>(<i>D</i>, <i>q</i>, <i>Q</i>)</div>' +
        '<div class="microlab-frame">' +
        '  <div class="controls-inline" style="justify-content:space-between;margin-bottom:8px;"><span>坐标缩放比例 s = <b class="mono" id="ml-scale-val">' + scaleVal.toFixed(4) + '×</b></span><div class="controls-inline"><button class="btn sm" data-scale-preset="0.001">10⁻³× (压力实测)</button><button class="btn sm" data-scale-preset="1">1× (原尺度)</button></div></div>' +
        '  <input id="ml-scale-slider" type="range" min="-3.0" max="0.5" step="0.5" value="' + Math.log10(scaleVal).toFixed(1) + '"/>' +
        '  <div class="table-wrap" style="margin-top:12px;"><table><thead><tr><th>算法</th><th class="num">实测 10⁻³× 漂移</th><th class="num">当前比例估算漂移</th></tr></thead><tbody id="ml-h001-out">' + renderH001Body(core, scaleVal, L) + "</tbody></table></div>" +
        "</div>";
    } else if (key === "r5") {
      const anti = map["evidence-cvrp-antipattern-falsified-hypotheses"];
      labHtml = '<div class="formula-center">return 0 &nbsp;⟺&nbsp; 1 − ρ<sub>best</sub> &lt; 0.25 + 0.50 · <i>p</i></div>' +
        '<div class="microlab-frame">' +
        '  <div class="controls-inline" style="justify-content:space-between;margin-bottom:8px;"><span>容量压力比 p = mean(<i>q</i><sub>F</sub>) / <i>Q</i><sub>rem</sub></span><span class="mono" id="ml-press-lbl">' + pressPct + "% → τ = " + (0.25 + 0.5 * pressPct / 100).toFixed(3) + "</span></div>" +
        '  <input id="ml-press-slider" type="range" min="10" max="100" step="5" value="' + pressPct + '"/>' +
        '  <div id="ml-r5-out" style="margin-top:10px;">' + renderR5Body(pressPct) + "</div>" +
        (anti ? ('<div class="diag-note" style="margin-top:12px;">反模式对照（<code>' + L.esc(anti.id) + "</code>）：" + L.esc(anti.summary) + "</div>") : "") +
        "</div>";
    } else {
      labHtml = '<div class="grid-2">' +
        '  <div><h3 style="font-size:14px;margin:0 0 6px;">单步构造契约 (EoH-S)</h3>' + renderBlueprintGrid(map["method-lit-ahd-eohs"], L) + "</div>" +
        '  <div><h3 style="font-size:14px;margin:0 0 6px;">全解算子契约 (HeurAgenix)</h3>' + renderBlueprintGrid(map["method-lit-ahd-heuragenix"], L) + "</div>" +
        "</div>";
    }

    const bpEntry = (entry && entry.attributes && entry.attributes.interface_blueprint) ? entry : map["method-cvrp-s2-r5-spiral"];

    return '<div class="editorial-col">' +
      '  <div class="crumb-line">机理专题 / ' + L.esc(meta.kbId) + "</div>" +
      '  <div class="subnav" style="margin-bottom:18px;">' +
      Object.keys(STORIES).map(function (k) { return '<button class="subnav-btn ' + (k === key ? "active" : "") + '" data-story="' + k + '">' + L.esc(STORIES[k].label) + "</button>"; }).join("") +
      "  </div>" +
      '  <h2 class="serif" style="font-size:21px;margin:0 0 8px;">' + L.esc(meta.title) + "</h2>" +
      '  <p class="sec" style="margin:0 0 14px;">' + L.esc((entry && entry.summary) || "") + "</p>" +
      labHtml +
      renderBlueprintGrid(bpEntry, L) +
      (entry ? ('<details class="source-box"><summary>查看知识条目完整 Markdown 原文与源码索引</summary><pre class="md-pre" style="margin-top:10px;">' + L.esc(entry.body || "") + "</pre></details>") : "") +
      '  <div class="controls-inline" style="margin-top:16px;">' +
      '    <button class="btn sm" data-nav="page=comparator&suite=shared_diagnostic_6&algA=s2_r5_spiral&algB=cw_relocate_2opt&preset=early_return">查看轨迹回放 →</button>' +
      '    <button class="btn sm" data-nav="page=knowledge&tab=library&entry=' + L.esc(meta.kbId) + '">在知识库中打开全文</button>' +
      "  </div>" +
      "</div>";
  }

  function renderLibraryView(core, state, L) {
    const entries = core.kb_entries || [];
    const q = (state.kbQuery || "").trim().toLowerCase();
    const fFam = state.kbFam || "", fTier = state.kbTier || "", fMode = state.kbMode || "";

    const matched = entries.filter(function (e) {
      const attrs = e.attributes || {};
      if (fFam && String(e.problem_family || "") !== fFam) return false;
      if (fTier && String(attrs.knowledge_tier || "") !== fTier) return false;
      if (fMode === "local_recomputed" && !(attrs.evidence_bindings && attrs.evidence_bindings.length)) return false;
      if (fMode === "paper_reported_reference" && !(attrs.paper_reported_results && attrs.paper_reported_results.length)) return false;
      if (q && ![e.id, e.title, e.summary, (e.tags || []).join(" "), e.body].join(" ").toLowerCase().includes(q)) return false;
      return true;
    });

    const activeId = (state.entry && matched.some(function (e) { return e.id === state.entry; })) ? state.entry : ((matched[0] && matched[0].id) || (entries[0] && entries[0].id));
    const activeEntry = entries.find(function (e) { return e.id === activeId; }) || matched[0];

    const listHtml = matched.slice(0, 140).map(function (e) {
      const attrs = e.attributes || {};
      const tLbl = (attrs.knowledge_tier && (L.TIER_LABELS[attrs.knowledge_tier] || attrs.knowledge_tier)) || e.type;
      return '<div class="kb-list-item ' + (activeEntry && e.id === activeEntry.id ? "active" : "") + '" data-kb-id="' + L.esc(e.id) + '">' +
        '<div class="kb-list-title">' + L.esc(e.title) + '</div><div class="kb-list-meta">' + L.esc(tLbl) + " · " + L.esc(String(e.problem_family || "").toUpperCase()) + "</div></div>";
    }).join("");

    let detailHtml = '<div class="panel muted">未找到匹配的知识条目</div>';
    if (activeEntry) {
      const attrs = activeEntry.attributes || {};
      const evRows = (attrs.evidence_bindings || []).map(function (b) {
        return '<tr><td class="mono"><a href="#page=benchmarks&suite=' + L.esc(b.suite_id) + '">' + L.esc(L.suiteTitle(b.suite_id)) + '</a></td><td class="mono">' + L.esc(L.algTitle(core, b.algorithm_id)) + "</td><td>" + L.esc(b.metric) + '</td><td class="num">' + L.esc(b.value) + "</td></tr>";
      }).join("");
      const prRows = (attrs.paper_reported_results || []).map(function (p) {
        return "<tr><td>" + L.esc(p.paper_source_id) + " (" + L.esc(p.table_ref) + ")</td><td>" + L.esc(p.method_name || p.method_id) + '</td><td class="num">' + (p.value === null || p.value === undefined ? "待提取" : L.esc(p.value)) + "</td><td>" + L.esc(p.verification_status || "") + "</td></tr>";
      }).join("");

      detailHtml = '<div class="panel">' +
        '<div class="crumb-line">' + L.esc(String(activeEntry.problem_family || "").toUpperCase()) + " / " + L.esc((attrs.knowledge_tier && L.TIER_LABELS[attrs.knowledge_tier]) || activeEntry.type) + " / " + L.esc(activeEntry.id) + "</div>" +
        '<h2 class="serif" style="margin:0 0 8px;font-size:19px;">' + L.esc(activeEntry.title) + "</h2>" +
        '<p class="sec">' + L.esc(activeEntry.summary) + "</p>" +
        renderBlueprintGrid(activeEntry, L) +
        (evRows ? ('<h3 style="font-size:13.5px;margin:16px 0 8px;">本机实测证据绑定</h3><div class="table-wrap"><table><thead><tr><th>测试集</th><th>算法</th><th>指标</th><th class="num">数值</th></tr></thead><tbody>' + evRows + "</tbody></table></div>") : "") +
        (prRows ? ('<h3 style="font-size:13.5px;margin:16px 0 8px;">论文原表绑定</h3><div class="table-wrap"><table><thead><tr><th>文献位置</th><th>方法</th><th class="num">原表值</th><th>状态</th></tr></thead><tbody>' + prRows + "</tbody></table></div>") : "") +
        '<details open class="source-box"><summary>完整正文与工程关联</summary><pre class="md-pre" style="margin-top:8px;">' + L.esc(activeEntry.body || "") + "</pre></details>" +
        "</div>";
    }

    const opt = function (v, cur, lbl) { return '<option value="' + L.esc(v) + '"' + (v === cur ? " selected" : "") + ">" + L.esc(lbl) + "</option>"; };
    return '<div class="panel-head" style="margin-bottom:14px;">' +
      '  <div class="controls-inline">' +
      '    <input id="kb-search-in" type="search" placeholder="检索关键词 / ID / 算子…" value="' + L.esc(state.kbQuery || "") + '" style="min-width:220px;"/>' +
      '    <select id="kb-f-fam">' + opt("", fFam, "全部问题族") + opt("cvrp", fFam, "CVRP") + opt("tsp", fFam, "TSP") + opt("obp", fFam, "OBP") + opt("unknown", fFam, "通用") + "</select>" +
      '    <select id="kb-f-tier">' + opt("", fTier, "全部知识层级") + Object.keys(L.TIER_LABELS).map(function (k) { return opt(k, fTier, L.TIER_LABELS[k]); }).join("") + "</select>" +
      '    <select id="kb-f-mode">' + opt("", fMode, "全部证据轨道") + opt("local_recomputed", fMode, "本机复跑证据") + opt("paper_reported_reference", fMode, "论文原表证据") + "</select>" +
      "  </div>" +
      '  <span class="sec mono" style="font-size:12.5px;">匹配 ' + matched.length + " / " + entries.length + "</span>" +
      "</div>" +
      '<div class="kb-grid"><div class="kb-list-panel">' + (listHtml || '<div class="muted" style="padding:14px;">无匹配条目</div>') + "</div><div>" + detailHtml + "</div></div>";
  }

  function render(core, state) {
    const L = window.WB_LABELS;
    const subTab = state.tab === "library" ? "library" : "stories";
    const total = (core.kb_entries || []).length;
    const subNav = '<div class="subnav" style="max-width:840px;margin:0 auto 18px;">' +
      '<button class="subnav-btn ' + (subTab === "stories" ? "active" : "") + '" data-kb-tab="stories">代表机理专题 (4)</button>' +
      '<button class="subnav-btn ' + (subTab === "library" ? "active" : "") + '" data-kb-tab="library">完整知识条目库 (' + total + ")</button>" +
      "</div>";
    return subNav + (subTab === "library" ? renderLibraryView(core, state, L) : renderStoryView(core, state, L));
  }

  function bind(rootEl, core, state, nav) {
    rootEl.querySelectorAll("[data-kb-tab]").forEach(function (el) { el.addEventListener("click", function () { nav({ tab: el.getAttribute("data-kb-tab") }); }); });
    rootEl.querySelectorAll("[data-story]").forEach(function (el) { el.addEventListener("click", function () { nav({ story: el.getAttribute("data-story"), tab: "stories" }); }); });

    const alphaSl = rootEl.querySelector("#ml-alpha-slider");
    if (alphaSl) {
      alphaSl.addEventListener("input", function () {
        const val = Number(alphaSl.value);
        state.mlAlpha = val;
        const valEl = rootEl.querySelector("#ml-alpha-val"), outEl = rootEl.querySelector("#ml-h003-out");
        if (valEl) valEl.textContent = val.toFixed(2);
        if (outEl) outEl.innerHTML = renderH003Body(core, val, window.WB_LABELS);
      });
    }
    rootEl.querySelectorAll("[data-alpha-preset]").forEach(function (el) {
      el.addEventListener("click", function () { nav({ mlAlpha: Number(el.getAttribute("data-alpha-preset")) }); });
    });

    const scaleSl = rootEl.querySelector("#ml-scale-slider");
    if (scaleSl) {
      scaleSl.addEventListener("input", function () {
        const val = Math.pow(10, Number(scaleSl.value));
        state.mlScale = val;
        const vEl = rootEl.querySelector("#ml-scale-val"), oEl = rootEl.querySelector("#ml-h001-out");
        if (vEl) vEl.textContent = val.toFixed(4) + "×";
        if (oEl) oEl.innerHTML = renderH001Body(core, val, window.WB_LABELS);
      });
    }
    rootEl.querySelectorAll("[data-scale-preset]").forEach(function (el) {
      el.addEventListener("click", function () { nav({ mlScale: Number(el.getAttribute("data-scale-preset")) }); });
    });

    const pressSl = rootEl.querySelector("#ml-press-slider");
    if (pressSl) {
      pressSl.addEventListener("input", function () {
        const val = Number(pressSl.value);
        state.mlPress = val;
        const lEl = rootEl.querySelector("#ml-press-lbl"), oEl = rootEl.querySelector("#ml-r5-out");
        if (lEl) lEl.textContent = val + "% → τ = " + (0.25 + 0.5 * val / 100).toFixed(3);
        if (oEl) oEl.innerHTML = renderR5Body(val);
      });
    }

    const qIn = rootEl.querySelector("#kb-search-in");
    if (qIn) {
      qIn.addEventListener("keydown", function (ev) { if (ev.key === "Enter") nav({ kbQuery: qIn.value }); });
      qIn.addEventListener("change", function () { nav({ kbQuery: qIn.value }); });
    }
    const fFam = rootEl.querySelector("#kb-f-fam");
    if (fFam) fFam.addEventListener("change", function () { nav({ kbFam: fFam.value, entry: "" }); });
    const fTier = rootEl.querySelector("#kb-f-tier");
    if (fTier) fTier.addEventListener("change", function () { nav({ kbTier: fTier.value, entry: "" }); });
    const fMode = rootEl.querySelector("#kb-f-mode");
    if (fMode) fMode.addEventListener("change", function () { nav({ kbMode: fMode.value, entry: "" }); });
    rootEl.querySelectorAll("[data-kb-id]").forEach(function (el) {
      el.addEventListener("click", function () { nav({ entry: el.getAttribute("data-kb-id") }); });
    });
  }

  window.WB_VIEWS = window.WB_VIEWS || {};
  window.WB_VIEWS.knowledge = { render: render, bind: bind };
})();
