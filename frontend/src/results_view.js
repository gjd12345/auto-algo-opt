/* Shared Results Sub-Renderers: Pareto SVG, Tier Breakdown, Published Tables, Selection Panel. */
(function () {
  "use strict";

  function renderParetoSvg(core, suiteId, scope, L) {
    const sum = L.getSuiteSummary(core, suiteId);
    if (!sum || !sum.algorithms) return '<div class="muted">暂无数据</div>';
    const pts = Object.keys(sum.algorithms).map(function (aid, i) {
      const st = L.getAlgStats(sum, aid, scope);
      const ov = L.getAlgStats(sum, aid, "overall");
      if (!st || st.mean_rel_gap === null || st.solve_ms_p50 === null) return null;
      return {
        aid: aid,
        label: L.algTitle(core, aid),
        gapPct: Number(st.mean_rel_gap) * 100,
        ms: Math.max(0.05, Number(st.solve_ms_p50)),
        color: L.PALETTE[i % L.PALETTE.length],
        ok: ov ? ov.ok_count : 0,
        n: ov ? ov.n_instances : 0
      };
    }).filter(Boolean);
    if (!pts.length) return '<div class="muted">暂无可绘图点</div>';

    const sortedByMs = pts.slice().sort(function (a, b) { return a.ms - b.ms; });
    const frontier = [];
    let bestGap = Infinity;
    sortedByMs.forEach(function (p) {
      if (p.gapPct < bestGap) { bestGap = p.gapPct; frontier.push(p); }
    });

    const W = 780, H = 360, pl = 68, pr = 40, pt = 28, pb = 50;
    const minLog = Math.log10(Math.min.apply(null, pts.map(function (p) { return p.ms; })));
    const maxLog = Math.log10(Math.max.apply(null, pts.map(function (p) { return p.ms; })));
    const spanLog = Math.max(0.5, maxLog - minLog);
    const gaps = pts.map(function (p) { return p.gapPct; });
    const minG = Math.min.apply(null, gaps), maxG = Math.max.apply(null, gaps);
    const padG = Math.max(1.5, (maxG - minG) * 0.12);
    const gLo = minG - padG, gHi = maxG + padG;

    const sx = function (ms) { return pl + ((Math.log10(ms) - minLog) / spanLog) * (W - pl - pr); };
    const sy = function (g) { return H - pb - ((g - gLo) / Math.max(1e-6, gHi - gLo)) * (H - pt - pb); };

    const grid = [];
    for (let i = 0; i <= 4; i++) {
      const yg = gLo + ((gHi - gLo) * i) / 4;
      const y = sy(yg);
      grid.push('<line x1="' + pl + '" y1="' + y.toFixed(1) + '" x2="' + (W - pr) + '" y2="' + y.toFixed(1) + '" stroke="#e5e7eb"/>');
      grid.push('<text x="' + (pl - 8) + '" y="' + (y + 4).toFixed(1) + '" font-size="11" fill="#86909c" text-anchor="end">' + yg.toFixed(1) + "%</text>");
    }
    [0.1, 1, 10, 100, 500].forEach(function (tickMs) {
      const l = Math.log10(tickMs);
      if (l >= minLog - 0.12 && l <= maxLog + 0.12) {
        const x = Math.max(pl, Math.min(W - pr, sx(tickMs)));
        grid.push('<line x1="' + x.toFixed(1) + '" y1="' + pt + '" x2="' + x.toFixed(1) + '" y2="' + (H - pb) + '" stroke="#e5e7eb"/>');
        grid.push('<text x="' + x.toFixed(1) + '" y="' + (H - pb + 18) + '" font-size="11" fill="#86909c" text-anchor="middle">' + tickMs + "ms</text>");
      }
    });

    const fPath = frontier.length > 1
      ? '<polyline fill="none" stroke="#165dff" stroke-width="1.8" stroke-dasharray="4,3" points="' + frontier.map(function (p) { return sx(p.ms).toFixed(1) + "," + sy(p.gapPct).toFixed(1); }).join(" ") + '"/>'
      : "";

    const circles = pts.map(function (p) {
      const cx = sx(p.ms), cy = sy(p.gapPct), isF = frontier.indexOf(p) >= 0;
      return '<g style="cursor:pointer;" data-nav="page=comparator&suite=' + L.esc(suiteId) + "&algA=" + L.esc(p.aid) + '">' +
        '<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="' + (isF ? 6 : 4.5) + '" fill="' + (isF ? "#165dff" : "#94a3b8") + '" stroke="#fff" stroke-width="1.5"/>' +
        '<text x="' + (cx + 8).toFixed(1) + '" y="' + (cy + 3.5).toFixed(1) + '" font-size="11.5" font-weight="' + (isF ? "600" : "400") + '" fill="#1d2129">' + L.esc(p.label) + " (" + p.gapPct.toFixed(1) + "%)</text>" +
        "</g>";
    }).join("");

    return '<svg id="pareto-svg" viewBox="0 0 ' + W + " " + H + '" width="100%" height="360">' +
      '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fafbfc" rx="6"/>' +
      grid.join("") +
      '<line x1="' + pl + '" y1="' + (H - pb) + '" x2="' + (W - pr) + '" y2="' + (H - pb) + '" stroke="#cbd5e1"/>' +
      '<line x1="' + pl + '" y1="' + pt + '" x2="' + pl + '" y2="' + (H - pb) + '" stroke="#cbd5e1"/>' +
      '<text x="' + ((pl + W - pr) / 2) + '" y="' + (H - 12) + '" font-size="12" fill="#4e5969" text-anchor="middle">求解耗时中位数 P50 (ms，对数刻度)</text>' +
      '<text x="18" y="' + ((pt + H - pb) / 2) + '" font-size="12" fill="#4e5969" text-anchor="middle" transform="rotate(-90 18 ' + ((pt + H - pb) / 2) + ')">相对差距 % Gap (越低越优)</text>' +
      fPath + circles + "</svg>";
  }

  function renderTierBreakdown(core, suiteId, sum, L) {
    if (!sum || !sum.algorithms) return "";
    const algs = Object.keys(sum.algorithms);
    let bucketField = "by_scale", title = "多规模分档质量对照";
    if (suiteId === "cvrp_ext_cvrplib_x_100") {
      bucketField = "by_x_tier";
      title = "Set X 三档规模分组（X-S 100–250 / X-M 251–500 / X-L 501–1000）";
    } else if (suiteId === "cvrp_ext_cvrplib_abp_74") {
      bucketField = "by_cvrplib_set";
      title = "CVRPLib 子集 A / B / P 分组对照";
    } else if (suiteId.indexOf("obp_") === 0) {
      bucketField = "by_obp_regime";
      title = "OBP 容量与流长分组对照";
    }

    const keysSet = {};
    algs.forEach(function (aid) {
      const m = sum.algorithms[aid][bucketField];
      if (m) Object.keys(m).forEach(function (k) { keysSet[k] = true; });
    });
    const tierKeys = Object.keys(keysSet);
    if (!tierKeys.length) return "";

    const bodyRows = algs.map(function (aid) {
      const m = sum.algorithms[aid][bucketField] || {};
      const cells = tierKeys.map(function (tk) {
        const st = m[tk];
        if (!st) return '<td class="num muted">—</td>';
        const okNote = st.ok_count < st.n_instances ? (' <span class="muted">(' + st.ok_count + "/" + st.n_instances + ")</span>") : "";
        return '<td class="num">' + L.fmtPct(st.mean_rel_gap, 2) + okNote + "</td>";
      }).join("");
      return '<tr><td><div class="row-title">' + L.esc(L.algTitle(core, aid)) + '</div><div class="row-sub mono">' + L.esc(aid) + "</div></td>" + cells + "</tr>";
    }).join("");

    return '<div class="panel"><div class="panel-head"><h3 class="panel-title">' + L.esc(title) + '</h3></div>' +
      '<div class="table-wrap"><table><thead><tr><th>算法</th>' + tierKeys.map(function (k) { return '<th class="num">' + L.esc(k) + "</th>"; }).join("") +
      "</tr></thead><tbody>" + bodyRows + "</tbody></table></div></div>";
  }

  function renderPublishedTrack(core, suite, fam, showAllPapers, L) {
    const pub = (core.published_results && core.published_results.records) || [];
    const filtered = showAllPapers ? pub : pub.filter(function (r) {
      return r.suite_id === suite.suite_id || r.problem_family === fam;
    });

    const rows = filtered.map(function (r) {
      const isPend = r.verification_status !== "verified_from_paper_table" || r.value === null || r.value === undefined;
      const valDisplay = isPend
        ? '<span class="muted">原表未提供数值</span>'
        : ('<span class="mono" style="font-weight:600;">' + L.fmtNum(r.value, r.unit === "percent" ? 2 : r.unit === "score" ? 3 : 4) + (r.unit === "percent" ? "%" : "") + "</span>");
      const statusHtml = isPend
        ? '<span class="status-tag">待提取</span>'
        : '<span class="status-tag good">原表核实</span>';
      return "<tr>" +
        '<td><div class="row-title">' + L.esc(r.paper_citation) + '</div><div class="row-sub mono">' + L.esc(r.table_ref) + " · " + L.esc(r.subset) + "</div></td>" +
        '<td><div>' + L.esc(r.method_display_name) + '</div><div class="row-sub">' + L.esc(L.PARADIGM_LABELS[r.paradigm] || r.paradigm) + "</div></td>" +
        '<td class="mono">' + L.esc(r.metric_name) + "</td>" +
        '<td class="num">' + valDisplay + "</td>" +
        "<td>" + statusHtml + "</td>" +
        '<td class="sec" style="font-size:12px;max-width:340px;">' + L.esc(r.protocol_boundary_note) + "</td>" +
        "</tr>";
    }).join("");

    return '<div class="panel">' +
      '<div class="panel-head">' +
      '  <div>' +
      '    <h2 class="panel-title">顶会论文原表参照（物理隔离对照）</h2>' +
      '    <p class="panel-sub">保留异机硬件、10 规则 ' + L.jargon("CPI", "CPI") + ' 与线上推理口径边界，不与本机 ' + L.esc(core.budget_ms) + " ms 复跑混排。当前展示 " + filtered.length + " / 共 " + pub.length + " 条。</p>" +
      "  </div>" +
      '  <div class="controls-inline"><button class="btn sm" id="l2-toggle-all-papers">' + (showAllPapers ? "仅看关联基准原表" : "展开全部顶会记录") + "</button></div>" +
      "</div>" +
      '<div class="table-wrap" style="max-height:540px;overflow-y:auto;"><table>' +
      '<thead><tr><th>文献与表号定位</th><th>发表方法与范式</th><th>指标</th><th class="num">原表值</th><th>状态</th><th>协议边界说明</th></tr></thead>' +
      "<tbody>" + (rows || '<tr><td colspan="6" class="muted">当前问题族暂无绑定原表条目</td></tr>') + "</tbody>" +
      "</table></div></div>";
  }

  function renderH003P0Spotlight(core, L) {
    const hp = core.h003_preview;
    if (!hp || !hp.summary) return "";
    const s = hp.summary;
    const bySize = hp.by_size || {};
    const rows = ["50", "100", "200"].map(function (sz) {
      const b = bySize[sz];
      if (!b) return "";
      return "<tr><td>n = " + sz + " (N=" + b.n + ")</td>" +
        '<td class="num">' + L.fmtNum(b.means[0], 4) + "</td>" +
        '<td class="num">' + L.fmtNum(b.means[1], 4) + "</td>" +
        '<td class="num" style="color:var(--teal);font-weight:600;">-' + L.fmtRatioAsPctPlain(b.rel_gain, 2) + "</td>" +
        '<td class="num">[' + L.fmtRatioAsPctPlain(b.ci95[0], 2) + ", " + L.fmtRatioAsPctPlain(b.ci95[1], 2) + "]</td>" +
        '<td class="num">' + b.wtl.wins + " / " + b.wtl.losses + "</td></tr>";
    }).join("");

    return '<div class="panel">' +
      '<div class="panel-head">' +
      '  <div><h3 class="panel-title">P0-120 配对检验：原始 V0 vs 出仓解耦改写</h3><p class="panel-sub">整体相对降幅 -' + L.fmtRatioAsPctPlain(s.rel_gain, 2) + "（95% CI [" + L.fmtRatioAsPctPlain(s.ci95[0], 2) + ", " + L.fmtRatioAsPctPlain(s.ci95[1], 2) + "]，胜/负 " + s.wtl.wins + "/" + s.wtl.losses + "）</p></div>" +
      '  <button class="btn sm" data-nav="page=knowledge&tab=stories&story=h003">进入 H-003 机理页 →</button>' +
      "</div>" +
      '<div class="table-wrap"><table><thead><tr><th>规模分组</th><th class="num">V0 均值</th><th class="num">解耦改写均值</th><th class="num">相对降幅</th><th class="num">95% Bootstrap CI</th><th class="num">胜 / 负</th></tr></thead>' +
      "<tbody>" + rows + "</tbody></table></div></div>";
  }

  function renderSelectionPanel(core, suite, state, L) {
    const analyses = (core.selection && core.selection.analyses) || {};
    const keys = Object.keys(analyses);
    if (!keys.length) return '<div class="panel muted">暂无算法选择记录</div>';
    let selKey = state.selAnalysis;
    if (!selKey || !analyses[selKey]) selKey = keys.find(function (k) { return analyses[k].suite_id === suite.suite_id; }) || keys[0];
    const analysis = analyses[selKey];
    const protoKeys = Object.keys(analysis.protocols || {});
    let protoKey = state.selProto;
    if (!protoKey || !analysis.protocols[protoKey]) protoKey = protoKeys[0];
    const proto = analysis.protocols[protoKey];

    const selEntries = Object.keys(proto.selectors || {}).map(function (sid) { return proto.selectors[sid]; });
    const selRows = selEntries.map(function (s) {
      const hl = s.selector_id === "rf_reg" || s.selector_id === "oracle_vbs";
      const picksSummary = s.picks ? Object.keys(s.picks).map(function (k) { return k + ":" + s.picks[k]; }).join(", ") : "—";
      const gainColor = (s.gain_vs_sbs || 0) > 0 ? "var(--teal)" : (s.gain_vs_sbs || 0) < 0 ? "var(--terra)" : "var(--ink)";
      return '<tr' + (hl ? ' class="active-row"' : "") + ">" +
        '<td>' + L.esc(s.selector_id) + (s.uses_features ? ' <span class="status-tag">特征驱动</span>' : "") + "</td>" +
        '<td class="num">' + L.fmtNum(s.mean, 4) + "</td>" +
        '<td class="num" style="color:' + gainColor + ';font-weight:600;">' + L.fmtPct(s.gain_vs_sbs, 2) + "</td>" +
        '<td class="num">' + L.fmtPct(s.gap_to_vbs, 2) + "</td>" +
        '<td class="num">' + (s.p_boot_one_sided !== null && s.p_boot_one_sided !== undefined ? L.fmtNum(s.p_boot_one_sided, 4) : "—") + "</td>" +
        '<td class="num">' + (s.mistake_count_vs_oracle !== undefined ? (s.mistake_count_vs_oracle + "/" + s.n_instances) : "—") + "</td>" +
        '<td class="num">' + L.fmtNum(s.mean_feat_ms, 2) + " + " + L.fmtNum(s.mean_infer_ms, 2) + " + " + L.fmtNum(s.mean_solve_ms, 2) + " = <b>" + L.fmtMs(s.mean_total_ms) + "</b></td>" +
        '<td class="mono muted" style="font-size:11px;">' + L.esc(picksSummary) + "</td>" +
        "</tr>";
    }).join("");

    const decMap = proto.per_instance_decisions || {};
    const decKey = (state.selModel && decMap[state.selModel]) ? state.selModel : (decMap.rf_reg ? "rf_reg" : Object.keys(decMap)[0]);
    const decisions = (decKey ? decMap[decKey] : []) || [];
    const mistakes = decisions.filter(function (d) { return d.is_mistake_vs_oracle; })
      .slice().sort(function (a, b) { return Number(b.regret_rel || 0) - Number(a.regret_rel || 0); });

    const mistakeRows = mistakes.slice(0, 30).map(function (d) {
      return "<tr>" +
        '<td class="mono">' + L.esc(d.instance_id) + "</td>" +
        '<td class="num">' + d.size + "</td>" +
        "<td>" + L.esc(d.spatial) + "</td>" +
        '<td class="mono">' + L.esc(L.algTitle(core, d.selected_algorithm)) + " (" + L.fmtNum(d.selected_cost, 4) + ")</td>" +
        '<td class="mono" style="color:var(--teal);">' + L.esc(L.algTitle(core, d.oracle_algorithm)) + " (" + L.fmtNum(d.oracle_cost, 4) + ")</td>" +
        '<td class="num" style="color:var(--terra);">' + L.fmtPct(d.regret_rel, 2) + "</td>" +
        '<td><button class="btn link sm" data-nav="page=comparator&suite=' + L.esc(analysis.suite_id) + "&inst=" + L.esc(d.instance_id) + "&algA=" + L.esc(d.selected_algorithm) + "&algB=" + L.esc(d.oracle_algorithm) + '">路线对照</button></td>' +
        "</tr>";
    }).join("");

    return '<div class="summary-bar">' +
      '  <div class="summary-item"><div class="k">全局 ' + L.jargon("SBS", "SBS") + '</div><div class="v">' + L.esc(analysis.global_sbs_algorithm) + '</div><div class="s">总长 ' + L.fmtNum(analysis.global_sbs_total, 2) + "</div></div>" +
      '  <div class="summary-item"><div class="k">理论 ' + L.jargon("VBS", "Oracle VBS") + '</div><div class="v">' + L.fmtNum(analysis.global_vbs_total, 2) + '</div><div class="s">样本数 N=' + analysis.n_instances + "</div></div>" +
      '  <div class="summary-item"><div class="k">池内互补间隙</div><div class="v">' + L.fmtRatioAsPctPlain(analysis.global_sbs_gap_to_vbs, 2) + '</div><div class="s">候选数 ' + (analysis.members || []).length + "</div></div>" +
      '  <div class="summary-item"><div class="k">失误例 (' + L.esc(decKey || "") + ')</div><div class="v">' + mistakes.length + "/" + decisions.length + '</div><div class="s">相对事后最优遗憾</div></div>' +
      "</div>" +
      '<div class="panel">' +
      '  <div class="panel-head">' +
      '    <div><h2 class="panel-title">实例级算法选择评估</h2><p class="panel-sub">严格分离特征提取、推理与求解三段耗时，区分同分布交叉验证与独立迁移泛化边界</p></div>' +
      '    <div class="controls-inline">' +
      '      <select id="l2-sel-analysis">' + keys.map(function (k) { return '<option value="' + L.esc(k) + '"' + (k === selKey ? " selected" : "") + ">" + L.esc(k) + " (" + L.esc(analyses[k].evaluation_mode) + ")</option>"; }).join("") + "</select>" +
      '      <select id="l2-sel-proto">' + protoKeys.map(function (pk) { return '<option value="' + L.esc(pk) + '"' + (pk === protoKey ? " selected" : "") + ">" + L.esc(pk) + " (folds=" + analysis.protocols[pk].n_folds + ")</option>"; }).join("") + "</select>" +
      "    </div>" +
      "  </div>" +
      '  <div class="table-wrap"><table>' +
      '    <thead><tr><th>策略 / 选择器</th><th class="num">均路程</th><th class="num">相对 SBS 变化</th><th class="num">距 VBS</th><th class="num">p 值</th><th class="num">失误样本</th><th class="num">分离计时 (特征+推理+求解)</th><th>选出分布</th></tr></thead>' +
      "    <tbody>" + selRows + "</tbody>" +
      "  </table></div>" +
      '  <details class="source-box"><summary>展开最大遗憾失误样本（' + L.esc(decKey || "") + "，显示前 " + Math.min(30, mistakes.length) + " / 共 " + mistakes.length + " 例）</summary>" +
      '    <div class="table-wrap" style="margin-top:10px;max-height:360px;overflow-y:auto;"><table>' +
      '      <thead><tr><th>算例</th><th class="num">n</th><th>空间分布</th><th>选出算法 (Obj)</th><th>Oracle 最优 (Obj)</th><th class="num">选择遗憾</th><th>查看</th></tr></thead>' +
      "      <tbody>" + (mistakeRows || '<tr><td colspan="7" class="muted">当前协议下零失误样本</td></tr>') + "</tbody>" +
      "    </table></div>" +
      "  </details>" +
      "</div>";
  }

  window.WB_RESULTS_PARTS = {
    renderParetoSvg: renderParetoSvg,
    renderTierBreakdown: renderTierBreakdown,
    renderPublishedTrack: renderPublishedTrack,
    renderH003P0Spotlight: renderH003P0Spotlight,
    renderSelectionPanel: renderSelectionPanel
  };

  // Preserve compatibility for #page=results hashes by routing through unified benchmarks view.
  window.WB_VIEWS = window.WB_VIEWS || {};
  window.WB_VIEWS.results = {
    render: function (core, state, bundle) { return window.WB_VIEWS.benchmarks.render(core, state, bundle); },
    bind: function (el, core, state, nav, bundle) { return window.WB_VIEWS.benchmarks.bind(el, core, state, nav, bundle); }
  };
})();
