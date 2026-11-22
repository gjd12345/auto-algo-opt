/* L1/L2 · Unified Benchmark Leaderboard, Paper Baselines, Pareto, Selection & Panorama Hub. */
(function () {
  "use strict";

  const CURATED_SUITES = {
    cvrp: [
      "cvrp_ext_cvrplib_abp_74",
      "cvrp_ext_cvrplib_x_100",
      "cvrp_ext_eohs_256",
      "cvrp_ext_reevo_scale",
      "cvrp_hist_p0_120",
      "cvrp_hist_hetero_288",
      "cvrp_final_accept_120"
    ],
    tsp: ["tsp_ext_tsplib_euc2d", "tsp_ext_eohs_128"],
    obp: ["obp_ext_eoh_weibull", "obp_ext_bpplib"]
  };

  const CURATED_ALGS = {
    cvrp: ["nn", "savings_pointwise", "s2_r5_spiral", "cw_parallel_merge", "cw_relocate_2opt", "eohs_cvrp_f1", "eohs_cvrp_set10_cpi", "heuragenix_min_cost_ins"],
    tsp: ["tsp_nn", "tsp_farthest_insertion", "tsp_nn_2opt", "eohs_tsp_f1", "eoh_tsp_f1"],
    obp: ["obp_first_fit", "obp_best_fit", "funsearch_obp_f1", "eoh_obp_f1", "eohs_obp_f1", "reevo_obp_f1"]
  };

  function renderGeoPreviewSvg(inst, family, L) {
    const W = 440, H = 280, pad = 24;
    if (family === "obp") {
      const hist = (inst.item_stats && inst.item_stats.ratio_histogram_10) || [];
      const maxH = Math.max(1, Math.max.apply(null, hist.concat([1])));
      const bw = (W - pad * 2) / Math.max(1, hist.length);
      const bars = hist.map(function (c, i) {
        const bh = (c / maxH) * (H - pad * 2 - 22);
        const x = pad + i * bw + 4, y = H - pad - bh;
        return '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + Math.max(4, bw - 8).toFixed(1) + '" height="' + bh.toFixed(1) + '" rx="2" fill="#165dff" opacity="0.82"/>' +
          '<text x="' + (x + bw / 2 - 4).toFixed(1) + '" y="' + (H - 8) + '" font-size="10" fill="#86909c" text-anchor="middle">' + (i * 10) + "%</text>";
      }).join("");
      return '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="260"><rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fafbfc" rx="6"/>' +
        '<text x="' + pad + '" y="18" font-size="12" font-weight="600" fill="#1d2129">' + L.esc(inst.instance_id) + " · 尺寸占箱容比 (C=" + L.esc(inst.capacity) + ", N=" + L.esc(inst.size) + ")</text>" + bars + "</svg>";
    }

    const pts = family === "tsp" ? (inst.coordinates || []) : ([inst.depot || [0, 0]].concat(inst.customer_coordinates || []));
    if (!pts.length) return '<div class="muted">暂无几何坐标</div>';
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    pts.forEach(function (p) {
      if (p[0] < minX) minX = p[0]; if (p[0] > maxX) maxX = p[0];
      if (p[1] < minY) minY = p[1]; if (p[1] > maxY) maxY = p[1];
    });
    const span = Math.max(1e-9, maxX - minX, maxY - minY);
    const scale = Math.min(W - pad * 2, H - pad * 2) / span;
    const ox = (W - (maxX - minX) * scale) / 2, oy = (H - (maxY - minY) * scale) / 2;
    const sx = function (x) { return ox + (x - minX) * scale; };
    const sy = function (y) { return H - (oy + (y - minY) * scale); };
    const demands = inst.demands || [];
    const maxQ = Math.max(1, Math.max.apply(null, demands.concat([1])));
    const dots = pts.map(function (p, idx) {
      const cx = sx(p[0]), cy = sy(p[1]);
      if (family === "cvrp" && idx === 0) return '<rect x="' + (cx - 4.5).toFixed(1) + '" y="' + (cy - 4.5).toFixed(1) + '" width="9" height="9" fill="#c2410c" stroke="#fff" stroke-width="1.2"/>';
      const r = (family === "cvrp" && demands[idx] !== undefined) ? (2.1 + 2.4 * (demands[idx] / maxQ)) : 2.5;
      return '<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="' + r.toFixed(1) + '" fill="#0f766e" opacity="0.78"/>';
    }).join("");
    return '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="260"><rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fafbfc" rx="6"/>' + dots +
      '<text x="' + pad + '" y="16" font-size="11.5" font-weight="600" fill="#1d2129">' + L.esc(inst.instance_id) + " (n=" + pts.length + ")</text></svg>";
  }

  function renderPanoramaTab(core, state, suiteBundle, fam, activeSuite, L) {
    const showAll = Boolean(state.expandAll);
    const famSuites = (core.suites || []).filter(function (s) { return s.problem_family === fam; });
    const displaySuites = showAll ? famSuites : famSuites.filter(function (s) { return (CURATED_SUITES[fam] || []).includes(s.suite_id); });
    const famAlgs = (core.algorithms || []).filter(function (a) { return a.problem_family === fam; });
    const displayAlgs = showAll ? famAlgs : famAlgs.filter(function (a) { return (CURATED_ALGS[fam] || []).includes(a.algorithm_id); });

    const matrixHeader = displayAlgs.map(function (a) {
      return '<th class="num" title="' + L.esc(a.algorithm_id) + '"><div>' + L.esc(L.algTitle(core, a.algorithm_id)) + '</div><div class="row-sub mono">' + L.esc(a.algorithm_id) + "</div></th>";
    }).join("");

    const matrixRows = displaySuites.map(function (s) {
      const sum = L.getSuiteSummary(core, s.suite_id);
      const effScope = L.resolveScope(sum, state.scope);
      const useCommon = effScope === "common_completed";
      const gaps = displayAlgs.map(function (a) {
        const st = L.getAlgStats(sum, a.algorithm_id, effScope);
        return st && st.mean_rel_gap !== null && st.mean_rel_gap !== undefined ? Number(st.mean_rel_gap) : null;
      });
      const valid = gaps.filter(function (g) { return g !== null; });
      const bestG = valid.length ? Math.min.apply(null, valid) : null;
      const cells = displayAlgs.map(function (a, i) {
        const st = L.getAlgStats(sum, a.algorithm_id, effScope);
        const ov = L.getAlgStats(sum, a.algorithm_id, "overall");
        const g = gaps[i];
        if (!st || g === null) return '<td class="num muted">—</td>';
        const isBest = bestG !== null && Math.abs(g - bestG) < 1e-6;
        const okTag = (!useCommon && ov && ov.ok_count < ov.n_instances) ? ('<span class="cell-sub">(' + ov.ok_count + "/" + ov.n_instances + ")</span>") : "";
        return '<td class="num cell-click ' + (isBest ? "cell-best" : "") + '" data-nav="page=benchmarks&family=' + L.esc(fam) + "&suite=" + L.esc(s.suite_id) + (useCommon ? "&scope=common_completed" : "") + '&tab=leaderboard">' +
          L.fmtPct(g, 2) + okTag + "</td>";
      }).join("");
      const scopeTag = useCommon ? (" · 共同交集 " + sum.common_completed_count + "/" + s.instance_count) : "";
      return '<tr data-nav="page=benchmarks&family=' + L.esc(fam) + "&suite=" + L.esc(s.suite_id) + '&tab=leaderboard">' +
        '<td><div class="row-title">' + L.esc(L.suiteTitle(s)) + '</div><div class="row-sub mono">' + L.esc(s.suite_id) + " · N=" + s.instance_count + scopeTag + " · " + L.esc(s.distance_convention) + "</div></td>" + cells + "</tr>";
    }).join("");

    let previewHtml = '<div class="muted">正在载入测试集 <code>' + L.esc(activeSuite.suite_id) + "</code> 算例坐标…</div>";
    if (suiteBundle && suiteBundle.suite && suiteBundle.suite.suite_id === activeSuite.suite_id) {
      const instances = suiteBundle.suite.instances || [];
      const curInstId = state.inst || (instances[0] && instances[0].instance_id) || "";
      const instObj = instances.find(function (x) { return x.instance_id === curInstId; }) || instances[0];
      const opts = instances.slice(0, 120).map(function (x) {
        return '<option value="' + L.esc(x.instance_id) + '"' + (instObj && x.instance_id === instObj.instance_id ? " selected" : "") + ">" + L.esc(x.instance_id) + " (n=" + (x.size || "") + ")</option>";
      }).join("");
      const bksNote = (instObj && instObj.bks_reported_cost !== undefined)
        ? ("官方 BKS = <b>" + instObj.bks_reported_cost + "</b> · 独立 <code>" + L.esc(activeSuite.distance_convention) + "</code> 重算 = <b>" + instObj.bks_recomputed_nint_cost + "</b>")
        : (instObj && instObj.opt_recomputed_nint !== undefined)
          ? ("官方 OPT = <b>" + instObj.reference_objective + "</b> · 重算 = <b>" + instObj.opt_recomputed_nint + "</b>")
          : ("参考基准：" + L.esc(instObj ? instObj.reference_kind : "") + " = " + L.fmtObj(instObj ? instObj.reference_objective : null));

      previewHtml = '<div class="grid-2">' +
        '  <div>' +
        '    <div class="controls-inline" style="margin-bottom:12px;"><span class="sec">算例预览：</span><select id="l1-inst-select">' + opts + "</select></div>" +
        '    <div class="diag-note" style="margin-top:0;margin-bottom:12px;">' + bksNote + '<div class="mono muted" style="margin-top:4px;">manifest: ' + L.esc((activeSuite.data_manifest_hash || "").slice(0, 20)) + "…</div></div>" +
        '    <div class="controls-inline"><button class="btn primary sm" data-nav="page=comparator&family=' + L.esc(fam) + "&suite=" + L.esc(activeSuite.suite_id) + "&inst=" + L.esc(instObj ? instObj.instance_id : "") + '">进入路线对照 →</button></div>' +
        "  </div>" +
        '  <div class="plot-box">' + (instObj ? renderGeoPreviewSvg(instObj, fam, L) : "") + "</div>" +
        "</div>";
    }

    return '<div class="panel">' +
      '  <div class="panel-head">' +
      '    <div><h2 class="panel-title">跨测试集 × 算法全景矩阵（' + L.esc((L.FAMILY_LABELS[fam] || {}).short || fam) + '）</h2><p class="panel-sub">统一 ' + L.esc(core.budget_ms) + " ms 预算下的平均相对参考差距，点击单元格跳转对应详表</p></div>" +
      '    <button class="btn sm ' + (showAll ? "active" : "") + '" id="l1-expand-btn">' + (showAll ? "收起为精选视角" : "展开全部 " + famSuites.length + " 套件与 " + famAlgs.length + " 算法") + "</button>" +
      "  </div>" +
      '  <div class="table-wrap"><table class="matrix-table"><thead><tr><th>测试集与公约</th>' + matrixHeader + "</tr></thead><tbody>" + matrixRows + "</tbody></table></div>" +
      "</div>" +
      '<div class="panel"><div class="panel-head"><h3 class="panel-title">算例几何与真值核验快照（' + L.esc(L.suiteTitle(activeSuite)) + "）</h3></div>" + previewHtml + "</div>";
  }

  function render(core, state, suiteBundle) {
    const L = window.WB_LABELS;
    const PARTS = window.WB_RESULTS_PARTS;
    const fam = state.family || "cvrp";
    const famSuites = (core.suites || []).filter(function (s) { return s.problem_family === fam; });
    const activeSuite = L.getSuite(core, state.suite) || famSuites[0] || core.suites[0];
    const suiteId = activeSuite.suite_id;
    const sum = L.getSuiteSummary(core, suiteId);
    const tab = state.tab || "leaderboard";
    const scope = L.resolveScope(sum, state.scope);
    const sortBy = state.sortBy || "mean_rel_gap";
    const sortDir = state.sortDir || "asc";

    const suiteOpts = core.suites.map(function (s) {
      const fTag = (L.FAMILY_LABELS[s.problem_family] && L.FAMILY_LABELS[s.problem_family].short) || s.problem_family;
      return '<option value="' + L.esc(s.suite_id) + '"' + (s.suite_id === suiteId ? " selected" : "") + ">" + L.esc(fTag) + " · " + L.esc(L.suiteTitle(s)) + " (N=" + s.instance_count + ")</option>";
    }).join("");

    const hasPartial = sum && sum.algorithms && Object.keys(sum.algorithms).some(function (aid) {
      const ov = L.getAlgStats(sum, aid, "overall");
      return ov && ov.ok_count < ov.n_instances;
    });
    const commonN = (sum && sum.common_completed_count) || 0;
    const commonToggle = (hasPartial && commonN > 0)
      ? '<label class="toggle-label"><input type="checkbox" id="bm-common-ck"' + (scope === "common_completed" ? " checked" : "") + "/> 仅看共同完成集 (" + L.jargon("N_common", commonN + "/" + activeSuite.instance_count) + ")</label>"
      : "";

    const tabs = [
      { id: "leaderboard", label: "本机同协议榜单" },
      { id: "published", label: "顶会论文原表对照" },
      { id: "pareto", label: "质量–耗时 Pareto 前沿" },
      { id: "selection", label: "实例级算法选择评估" },
      { id: "panorama", label: "全基准对比矩阵" }
    ];

    let bodyHtml = "";
    if (tab === "pareto") {
      bodyHtml = '<div class="panel">' +
        '  <div class="panel-head">' +
        '    <div><h2 class="panel-title">质量–耗时 Pareto 前沿（' + L.esc(L.suiteTitle(activeSuite)) + '）</h2><p class="panel-sub">横轴为求解 P50 耗时（对数刻度），纵轴为平均相对差距；点击散点直接查看路线对比</p></div>' +
        '    <div class="controls-inline"><button class="btn sm" id="l2-export-svg">导出 SVG</button><button class="btn sm" id="l2-export-png">导出 300 DPI PNG</button></div>' +
        "  </div>" +
        '  <div class="plot-box">' + PARTS.renderParetoSvg(core, suiteId, scope, L) + "</div>" +
        "</div>";
    } else if (tab === "published") {
      bodyHtml = PARTS.renderPublishedTrack(core, activeSuite, fam, Boolean(state.showAllPapers), L);
    } else if (tab === "selection") {
      bodyHtml = PARTS.renderSelectionPanel(core, activeSuite, state, L);
    } else if (tab === "panorama") {
      bodyHtml = renderPanoramaTab(core, state, suiteBundle, fam, activeSuite, L);
    } else {
      const algRows = Object.keys((sum && sum.algorithms) || {}).map(function (aid) {
        return { aid: aid, meta: L.getAlg(core, aid), st: L.getAlgStats(sum, aid, scope), ov: L.getAlgStats(sum, aid, "overall") };
      }).filter(function (r) { return Boolean(r.st); });

      algRows.sort(function (a, b) {
        let va = sortBy === "solve_ms_p50" ? a.st.solve_ms_p50 : sortBy === "mean_tour_length" ? a.st.mean_tour_length : a.st.mean_rel_gap;
        let vb = sortBy === "solve_ms_p50" ? b.st.solve_ms_p50 : sortBy === "mean_tour_length" ? b.st.mean_tour_length : b.st.mean_rel_gap;
        va = va === null || va === undefined ? 1e9 : Number(va);
        vb = vb === null || vb === undefined ? 1e9 : Number(vb);
        return sortDir === "desc" ? vb - va : va - vb;
      });

      const isFixedKSuite = activeSuite.vehicle_limit_policy === "fixed_k_unconstrained_eval";
      const bestGap = algRows.length && algRows[0].st.mean_rel_gap !== null && sortBy === "mean_rel_gap" && sortDir === "asc" ? Number(algRows[0].st.mean_rel_gap) : null;
      const trs = algRows.map(function (r) {
        const kbId = L.resolveAlgKbId(core, r.aid);
        const isPartial = r.ov.ok_count < r.ov.n_instances;
        const okBex = r.ov.ok_budget_exhausted_count !== undefined ? r.ov.ok_budget_exhausted_count : (r.ov.budget_exhausted_count || 0);
        const toCnt = r.ov.timeout_count !== undefined ? r.ov.timeout_count : (r.ov.n_instances - r.ov.ok_count);
        const convRate = r.ov.local_opt_convergence_rate;
        const convNote = (convRate !== null && convRate !== undefined && convRate < 1.0)
          ? (" · 收敛 " + L.fmtRatioAsPctPlain(Math.max(0, convRate), 0))
          : "";
        const okText = r.ov.ok_count + "/" + r.ov.n_instances +
          (toCnt > 0 ? " (超时 " + toCnt + ")" : okBex > 0 ? " (预算终止 " + okBex + ")" : "") +
          convNote;
        const isBest = bestGap !== null && r.st.mean_rel_gap !== null && Math.abs(Number(r.st.mean_rel_gap) - bestGap) < 1e-6;
        let exactKCell = "";
        if (isFixedKSuite) {
          const exCnt = r.st.exact_k_count;
          const exChk = r.st.exact_k_checked;
          const exGap = r.st.exact_k_mean_rel_gap;
          exactKCell = '<td class="num">' +
            (exCnt !== undefined && exChk ? (exCnt + "/" + exChk + " (" + L.fmtRatioAsPctPlain(r.st.exact_k_compliance_rate, 1) + ")" + (exGap !== null && exGap !== undefined ? ("<div class=\"row-sub\">" + L.fmtPct(exGap, 2) + "</div>") : "")) : "—") +
            "</td>";
        }
        return "<tr>" +
          '<td><div class="row-title">' + L.esc(L.algTitle(core, r.aid)) + '</div><div class="row-sub mono">' + L.esc(r.aid) + "</div></td>" +
          '<td class="sec">' + L.esc((r.meta && L.PARADIGM_LABELS[r.meta.paradigm]) || (r.meta && r.meta.paradigm) || "—") + "</td>" +
          '<td><span class="status-tag ' + (isPartial ? "warn" : "good") + '">' + L.esc(okText) + "</span></td>" +
          '<td class="num">' + L.fmtObj(r.st.mean_tour_length) + "</td>" +
          '<td class="num ' + (isBest ? "cell-best" : "") + '">' + L.fmtPct(r.st.mean_rel_gap, 2) + "</td>" +
          exactKCell +
          '<td class="num">' + L.fmtMs(r.st.solve_ms_p50) + " / " + L.fmtMs(r.st.solve_ms_p95) + "</td>" +
          '<td class="num">' + (r.st.total_voluntary_early_returns || 0) + "</td>" +
          '<td class="num">' + (kbId ? ('<button class="btn link sm" data-nav="page=knowledge&tab=library&entry=' + L.esc(kbId) + '">知识卡</button> ') : "") +
          '<button class="btn link sm" data-nav="page=comparator&family=' + L.esc(fam) + "&suite=" + L.esc(suiteId) + "&algA=" + L.esc(r.aid) + '">路线对照</button></td>' +
          "</tr>";
      }).join("");

      const p0Block = suiteId === "cvrp_hist_p0_120" ? PARTS.renderH003P0Spotlight(core, L) : "";
      const policyDesc = (L.POLICY_LABELS && L.POLICY_LABELS[activeSuite.vehicle_limit_policy]) || activeSuite.vehicle_limit_policy || "";

      bodyHtml = '<div class="panel">' +
        '  <div class="panel-head">' +
        '    <div><h2 class="panel-title">' + L.esc(L.suiteTitle(activeSuite)) + '</h2><p class="panel-sub">参考基准：' + L.esc(activeSuite.reference_kind) + " · 距离公约：" + L.esc(activeSuite.distance_convention) + (policyDesc ? (" · 车数口径：" + L.esc(policyDesc)) : "") + " · CPU 上限 " + L.esc(sum && sum.budget_ms) + " ms" + (scope === "common_completed" && commonN ? (" · 当前按共同完成集 N_common=" + commonN + "/" + activeSuite.instance_count + " 例同样本排名") : (hasPartial ? " · 当前为含部分完成算例的原始完成率统计" : "")) + "</p></div>" +
        '    <div class="controls-inline"><button class="btn sm" id="l2-export-latex">LaTeX 表</button><button class="btn sm" id="l2-export-csv">CSV</button><button class="btn sm" id="l2-export-json">JSON</button></div>' +
        "  </div>" +
        '  <div class="table-wrap"><table>' +
        '    <thead><tr><th>算法</th><th>范式</th><th>完成情况</th><th class="sortable num" data-sort="mean_tour_length">均目标值 ⇅</th><th class="sortable num" data-sort="mean_rel_gap">平均差距 ⇅</th>' + (isFixedKSuite ? '<th class="num">固定 k 合规 (==k · 同 k 均差)</th>' : "") + '<th class="sortable num" data-sort="solve_ms_p50">P50 / P95 ⇅</th><th class="num">主动早返</th><th class="num">操作</th></tr></thead>' +
        "    <tbody>" + trs + "</tbody>" +
        "  </table></div>" +
        '  <div id="l2-latex-preview" style="margin-top:14px;"></div>' +
        "</div>" +
        PARTS.renderTierBreakdown(core, suiteId, sum, L) +
        p0Block;
    }

    return '<div class="panel-head" style="margin-bottom:10px;">' +
      '  <div class="controls-inline"><span class="sec">测试集：</span><select id="l2-suite-select">' + suiteOpts + "</select>" + commonToggle + "</div>" +
      '  <div class="controls-inline"><button class="btn link sm" data-nav="page=knowledge&tab=stories&story=' + (suiteId === "cvrp_hist_hetero_288" ? "h010" : suiteId === "cvrp_hist_p0_120" ? "h003" : "r5") + '">关联机理分析 →</button></div>' +
      "</div>" +
      '<div class="subnav">' +
      tabs.map(function (t) { return '<button class="subnav-btn ' + (tab === t.id ? "active" : "") + '" data-tab="' + t.id + '">' + t.label + "</button>"; }).join("") +
      "</div>" +
      bodyHtml;
  }

  function bind(rootEl, core, state, nav, suiteBundle) {
    const L = window.WB_LABELS;
    const sSel = rootEl.querySelector("#l2-suite-select");
    if (sSel) {
      sSel.addEventListener("change", function () {
        const sObj = L.getSuite(core, sSel.value);
        nav({ suite: sSel.value, family: (sObj && sObj.problem_family) || state.family, scope: "", inst: "" });
      });
    }
    const ck = rootEl.querySelector("#bm-common-ck");
    if (ck) ck.addEventListener("change", function () { nav({ scope: ck.checked ? "common_completed" : "overall" }); });
    rootEl.querySelectorAll("[data-tab]").forEach(function (b) {
      b.addEventListener("click", function () { nav({ tab: b.getAttribute("data-tab") }); });
    });
    rootEl.querySelectorAll("th[data-sort]").forEach(function (th) {
      th.addEventListener("click", function () {
        const col = th.getAttribute("data-sort");
        nav({ sortBy: col, sortDir: (state.sortBy === col && state.sortDir === "asc") ? "desc" : "asc" });
      });
    });

    const expBtn = rootEl.querySelector("#l1-expand-btn");
    if (expBtn) expBtn.addEventListener("click", function () { nav({ expandAll: !state.expandAll }); });
    const instSel = rootEl.querySelector("#l1-inst-select");
    if (instSel) instSel.addEventListener("change", function () { nav({ inst: instSel.value }); });
    const paperBtn = rootEl.querySelector("#l2-toggle-all-papers");
    if (paperBtn) paperBtn.addEventListener("click", function () { nav({ showAllPapers: !state.showAllPapers }); });
    const selAn = rootEl.querySelector("#l2-sel-analysis");
    if (selAn) selAn.addEventListener("change", function () { nav({ selAnalysis: selAn.value, selProto: "" }); });
    const selPr = rootEl.querySelector("#l2-sel-proto");
    if (selPr) selPr.addEventListener("change", function () { nav({ selProto: selPr.value }); });

    const sid = state.suite || (core.suites[0] && core.suites[0].suite_id);
    const scope = state.scope || "overall";
    const texBtn = rootEl.querySelector("#l2-export-latex");
    if (texBtn) {
      texBtn.addEventListener("click", function () {
        const tex = window.WB_EXPORT.generateLatexLocalTable(core, sid, scope);
        const box = rootEl.querySelector("#l2-latex-preview");
        if (box) {
          box.innerHTML = '<div class="panel-head" style="margin-bottom:8px;"><span class="panel-title">LaTeX booktabs 源码</span>' +
            '<button class="btn sm primary" id="l2-dl-tex">下载 .tex</button></div><pre class="md-pre">' + L.esc(tex) + "</pre>";
          const dl = box.querySelector("#l2-dl-tex");
          if (dl) dl.addEventListener("click", function () { window.WB_EXPORT.downloadText(sid + "_" + scope + ".tex", tex); });
        }
      });
    }
    const csvBtn = rootEl.querySelector("#l2-export-csv");
    if (csvBtn) {
      csvBtn.addEventListener("click", function () {
        const recs = (suiteBundle && suiteBundle.records) || [];
        const cols = ["suite_id", "instance_id", "algorithm_id", "status", "tour_length", "reference_objective", "rel_gap", "solve_ms", "voluntary_early_return_count"];
        window.WB_EXPORT.exportCsv(recs, cols, sid + "_records.csv");
      });
    }
    const jsonBtn = rootEl.querySelector("#l2-export-json");
    if (jsonBtn) {
      jsonBtn.addEventListener("click", function () {
        window.WB_EXPORT.exportJson((suiteBundle && suiteBundle.records) || L.getSuiteSummary(core, sid), sid + "_records.json");
      });
    }
    const svgBtn = rootEl.querySelector("#l2-export-svg");
    if (svgBtn) svgBtn.addEventListener("click", function () { window.WB_EXPORT.exportSvg(rootEl.querySelector("#pareto-svg"), sid + "_pareto.svg"); });
    const pngBtn = rootEl.querySelector("#l2-export-png");
    if (pngBtn) pngBtn.addEventListener("click", function () { window.WB_EXPORT.exportPng300Dpi(rootEl.querySelector("#pareto-svg"), sid + "_pareto_300dpi.png"); });
  }

  window.WB_VIEWS = window.WB_VIEWS || {};
  window.WB_VIEWS.benchmarks = { render: render, bind: bind };
})();
