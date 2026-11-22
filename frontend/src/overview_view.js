/* L0 · Low-density Canvas Header, Cross-Suite Matrix & Visual Directory. */
(function () {
  "use strict";

  const OVERVIEW_CFG = {
    cvrp: {
      suites: [
        "cvrp_ext_cvrplib_abp_74",
        "cvrp_ext_cvrplib_x_100",
        "cvrp_ext_eohs_256",
        "cvrp_hist_p0_120",
        "cvrp_final_accept_120"
      ],
      algs: ["nn", "eohs_cvrp_f1", "s2_r5_spiral", "cw_relocate_2opt", "heuragenix_min_cost_ins"]
    },
    tsp: {
      suites: ["tsp_ext_tsplib_euc2d", "tsp_ext_eohs_128"],
      algs: ["tsp_nn", "eoh_tsp_f1", "eohs_tsp_f1", "tsp_nn_2opt"]
    },
    obp: {
      suites: ["obp_ext_eoh_weibull", "obp_ext_bpplib"],
      algs: ["obp_first_fit", "obp_best_fit", "funsearch_obp_f1", "eohs_obp_f1"]
    }
  };

  function drawCvrpMiniCover(core) {
    const hp = core.h003_preview;
    if (!hp || !hp.instances || !hp.instances.length) {
      return '<div class="muted" style="font-size:12px;">P0-120 出发步路线结构对比</div>';
    }
    const inst = hp.instances.find(function (x) { return x.id === hp.example; }) || hp.instances[0];
    const pts = inst.coords || [];
    const rOrig = (inst.routes && inst.routes[0] && inst.routes[0][0]) || [];
    const rNew = (inst.routes && inst.routes[1] && inst.routes[1][0]) || [];
    const W = 310, H = 114, size = 94, ox = (W - size) / 2, oy = (H - size) / 2;
    const px = function (p) { return [ox + p[0] * size, oy + (1 - p[1]) * size]; };
    function poly(r, col, dash) {
      const s = r.map(function (idx) {
        const c = pts[idx];
        return c ? px(c).map(function (v) { return v.toFixed(1); }).join(",") : "";
      }).filter(Boolean).join(" ");
      return s ? '<polyline fill="none" stroke="' + col + '" stroke-width="1.6" ' + (dash ? 'stroke-dasharray="3,2" ' : "") + 'points="' + s + '"/>' : "";
    }
    const dep = pts[0] ? px(pts[0]) : [W / 2, H / 2];
    return '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="114">' +
      poly(rOrig, "#4e5969", true) +
      poly(rNew, "#165dff", false) +
      '<rect x="' + (dep[0] - 3.5).toFixed(1) + '" y="' + (dep[1] - 3.5).toFixed(1) + '" width="7" height="7" fill="#1d2129" transform="rotate(45 ' + dep[0].toFixed(1) + " " + dep[1].toFixed(1) + ')"/>' +
      "</svg>";
  }

  function drawBarMiniCover(core, suiteId, algs, L) {
    const sum = L.getSuiteSummary(core, suiteId);
    if (!sum || !sum.algorithms) return '<div class="muted" style="font-size:12px;">—</div>';
    const items = algs.map(function (aid) {
      const st = L.getAlgStats(sum, aid, "overall");
      if (!st || st.mean_rel_gap === null || st.mean_rel_gap === undefined) return null;
      return { label: L.algTitle(core, aid), pct: Math.max(0.5, Number(st.mean_rel_gap) * 100) };
    }).filter(Boolean);
    if (!items.length) return '<div class="muted" style="font-size:12px;">—</div>';
    const maxPct = Math.max.apply(null, items.map(function (x) { return x.pct; }));
    const minPct = Math.min.apply(null, items.map(function (x) { return x.pct; }));
    const W = 310, H = 114, padX = 112, rightPad = 48;
    const rowH = (H - 16) / items.length;
    const rows = items.map(function (it, idx) {
      const bw = Math.max(8, (it.pct / Math.max(1e-6, maxPct)) * (W - padX - rightPad));
      const y = 10 + idx * rowH;
      const isBest = Math.abs(it.pct - minPct) < 1e-6;
      return '<text x="' + (padX - 8) + '" y="' + (y + rowH * 0.62).toFixed(1) + '" text-anchor="end" font-size="10.5" fill="#4e5969">' + L.esc(it.label) + "</text>" +
        '<rect x="' + padX + '" y="' + (y + 3).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + Math.max(6, rowH - 8).toFixed(1) + '" rx="2" fill="' + (isBest ? "#165dff" : "#94a3b8") + '"/>' +
        '<text x="' + (padX + bw + 5).toFixed(1) + '" y="' + (y + rowH * 0.62).toFixed(1) + '" font-size="10" font-family="monospace" fill="' + (isBest ? "#165dff" : "#4e5969") + '">+' + it.pct.toFixed(1) + "%</text>";
    }).join("");
    return '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="114">' + rows + "</svg>";
  }

  function render(core, state) {
    const L = window.WB_LABELS;
    const snap = L.computeHeroSnapshot(core);
    const fam = state.family || "cvrp";
    const cfg = OVERVIEW_CFG[fam] || OVERVIEW_CFG.cvrp;
    const scope = state.scope || "overall";

    const hasPartial = cfg.suites.some(function (sid) {
      const s = L.getSuiteSummary(core, sid);
      return s && s.common_completed_count && s.common_completed_count < s.n_instances;
    });

    const rowsHtml = cfg.suites.map(function (sid) {
      const sum = L.getSuiteSummary(core, sid);
      const sMeta = L.getSuite(core, sid);
      if (!sum || !sMeta) return "";
      const useCommon = scope === "common_completed" && sum.common_completed_count && sum.common_completed_count < sum.n_instances;
      const effScope = useCommon ? "common_completed" : "overall";

      const vals = cfg.algs.map(function (aid) {
        const st = L.getAlgStats(sum, aid, effScope);
        const ov = L.getAlgStats(sum, aid, "overall");
        return { aid: aid, gap: st ? st.mean_rel_gap : null, ok: ov ? ov.ok_count : sum.n_instances, n: sum.n_instances };
      });
      const valid = vals.filter(function (v) { return v.gap !== null && v.gap !== undefined; }).map(function (v) { return Number(v.gap); });
      const minGap = valid.length ? Math.min.apply(null, valid) : null;

      const subText = useCommon
        ? ("共同完成 " + sum.common_completed_count + "/" + sum.n_instances + " 例")
        : (sum.n_instances + " 例 · " + L.esc(sMeta.distance_convention));

      const cells = vals.map(function (v) {
        if (v.gap === null || v.gap === undefined) return '<td class="num muted">—</td>';
        const isBest = minGap !== null && Math.abs(Number(v.gap) - minGap) < 1e-6;
        const partial = (!useCommon && v.ok < v.n) ? ('<span class="cell-sub">(' + v.ok + "/" + v.n + ")</span>") : "";
        const navScope = (!useCommon && v.ok < v.n) ? "&scope=common_completed" : "";
        return '<td class="num cell-click ' + (isBest ? "cell-best" : "") + '" data-nav="page=benchmarks&family=' + L.esc(fam) + "&suite=" + L.esc(sid) + navScope + '">' +
          L.fmtPct(v.gap, 2) + partial + "</td>";
      }).join("");

      return '<tr data-nav="page=benchmarks&family=' + L.esc(fam) + "&suite=" + L.esc(sid) + '">' +
        '<td><div class="row-title">' + L.esc(L.suiteTitle(sMeta)) + '</div><div class="row-sub">' + subText + "</div></td>" +
        cells + "</tr>";
    }).join("");

    const xCommonGap = snap.cwRelXCommon ? L.fmtRatioAsPctPlain(snap.cwRelXCommon.mean_rel_gap, 2) : "—";
    const h003Gain = snap.h003Summary ? L.fmtRatioAsPctPlain(snap.h003Summary.rel_gain, 2) : "—";

    return [
      '<section class="overview-header">',
      '  <h1>组合优化求解基准与算法机理工作台</h1>',
      '  <p class="subtitle">面向 CVRP、TSP 与 OBP 的统一 ' + L.esc(core.budget_ms) + ' ms 同协议评测、双解结构对照与可复现算法知识库</p>',
      '  <div class="fact-strip">',
      '    <div class="fact-item"><b>' + snap.suiteCount + '</b> 套标准基准套件</div>',
      '    <div class="fact-item"><b>' + snap.orGoldInstances + '</b> 例官方 OR 零误差核验</div>',
      '    <div class="fact-item"><b>' + snap.kbCount + '</b> 条结构化算法知识</div>',
      '  </div>',
      '</section>',

      '<section class="panel">',
      '  <div class="panel-head">',
      '    <div>',
      '      <h2 class="panel-title">代表基准集与算法范式对比（' + L.esc((L.FAMILY_LABELS[fam] || {}).short || fam) + '）</h2>',
      '      <p class="panel-sub">数值为平均相对参考差距（越低越优；点击任意行或数值查看详表与论文原表对照）</p>',
      '    </div>',
      '    <div class="controls-inline">',
      hasPartial ? ('<label class="toggle-label"><input type="checkbox" id="ov-common-ck"' + (scope === "common_completed" ? " checked" : "") + "/> 仅看共同完成集</label>") : "",
      '      <button class="btn link" data-nav="page=benchmarks&family=' + L.esc(fam) + '&tab=panorama&expandAll=true">展开全部 ' + snap.suiteCount + ' 套件 →</button>',
      '    </div>',
      '  </div>',
      '  <div class="table-wrap">',
      '    <table class="matrix-table">',
      '      <thead><tr><th>基准测试集</th>' + cfg.algs.map(function (a) { return '<th class="num" title="' + L.esc(a) + '">' + L.esc(L.algTitle(core, a)) + "</th>"; }).join("") + "</tr></thead>",
      '      <tbody>' + rowsHtml + "</tbody>",
      '    </table>',
      '  </div>',
      '</section>',

      '<section class="cover-grid">',
      '  <article class="cover-card">',
      '    <div class="cover-head"><div class="cover-code">CVRP</div><h3>容量约束车辆路径</h3><p>顺序规则机理（H-003 / H-001 / R5）与并行局部搜索上界</p></div>',
      '    <div class="cover-plot">' + drawCvrpMiniCover(core) + "</div>",
      '    <ul class="cover-links">',
      '      <li><button type="button" data-nav="page=knowledge&tab=stories&story=h003"><span>P0-120 出发步相变 (H-003)</span><span class="mono">-' + h003Gain + "</span></button></li>",
      '      <li><button type="button" data-nav="family=cvrp&page=comparator&suite=shared_diagnostic_6&algA=s2_r5_spiral&algB=cw_relocate_2opt&preset=early_return"><span>Shared-6 主动早返轨迹</span><span class="mono">回放</span></button></li>',
      '      <li><button type="button" data-nav="family=cvrp&page=benchmarks&suite=cvrp_ext_cvrplib_x_100&scope=common_completed"><span>Set X 交集 (' + snap.xCommonN + '/100)</span><span class="mono">' + xCommonGap + "</span></button></li>",
      '    </ul>',
      '  </article>',

      '  <article class="cover-card">',
      '    <div class="cover-head"><div class="cover-code">TSP</div><h3>旅行商闭合巡回</h3><p>TSPLIB EUC_2D 官方最优路线对比与 2-opt 改进幅度</p></div>',
      '    <div class="cover-plot">' + drawBarMiniCover(core, "tsp_ext_tsplib_euc2d", OVERVIEW_CFG.tsp.algs, L) + "</div>",
      '    <ul class="cover-links">',
      '      <li><button type="button" data-nav="family=tsp&page=benchmarks&suite=tsp_ext_tsplib_euc2d"><span>TSPLIB EUC_2D 标准榜单</span><span class="mono">18 例</span></button></li>',
      '      <li><button type="button" data-nav="family=tsp&page=comparator&suite=tsp_ext_tsplib_euc2d&inst=eil51&algA=tsp_nn_2opt&algB=eohs_tsp_f1&showOpt=1"><span>eil51 闭合路线对照</span><span class="mono">OPT 426</span></button></li>',
      '      <li><button type="button" data-nav="family=tsp&page=benchmarks&suite=tsp_ext_eohs_128"><span>EoH-S TSP 多分布协议</span><span class="mono">128 例</span></button></li>',
      '    </ul>',
      '  </article>',

      '  <article class="cover-card">',
      '    <div class="cover-head"><div class="cover-code">OBP</div><h3>在线一维装箱</h3><p>Weibull 在线流与 BPPLib 填充效率及理论 L1 下界对比</p></div>',
      '    <div class="cover-plot">' + drawBarMiniCover(core, "obp_ext_eoh_weibull", OVERVIEW_CFG.obp.algs, L) + "</div>",
      '    <ul class="cover-links">',
      '      <li><button type="button" data-nav="family=obp&page=benchmarks&suite=obp_ext_eoh_weibull"><span>Weibull 在线装箱榜单</span><span class="mono">173 例</span></button></li>',
      '      <li><button type="button" data-nav="family=obp&page=comparator&suite=obp_ext_eoh_weibull&algA=obp_best_fit&algB=eohs_obp_f1"><span>箱位填充分布对照</span><span class="mono">L1 对照</span></button></li>',
      '      <li><button type="button" data-nav="family=obp&page=benchmarks&suite=obp_ext_bpplib"><span>BPPLib 标准装箱库</span><span class="mono">70 例</span></button></li>',
      '    </ul>',
      '  </article>',
      '</section>'
    ].join("\n");
  }

  function bind(rootEl, core, state, nav) {
    const ck = rootEl.querySelector("#ov-common-ck");
    if (ck) {
      ck.addEventListener("change", function () {
        nav({ scope: ck.checked ? "common_completed" : "overall" });
      });
    }
  }

  window.WB_VIEWS = window.WB_VIEWS || {};
  window.WB_VIEWS.overview = { render: render, bind: bind };
})();
