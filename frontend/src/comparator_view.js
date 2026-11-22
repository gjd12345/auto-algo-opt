/* L2 · 66/34 Route & Packing Comparator, Directional Departure Plot & Dynamic Trace Replay. */
(function () {
  "use strict";

  function computeSharedBounds(inst, family) {
    const pts = family === "tsp"
      ? (inst.coordinates || [])
      : ([inst.depot || [0, 0]].concat(inst.customer_coordinates || []));
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    pts.forEach(function (p) {
      if (p[0] < minX) minX = p[0]; if (p[0] > maxX) maxX = p[0];
      if (p[1] < minY) minY = p[1]; if (p[1] > maxY) maxY = p[1];
    });
    if (!Number.isFinite(minX)) return { minX: 0, maxX: 1, minY: 0, maxY: 1, pts: pts };
    return { minX: minX, maxX: maxX, minY: minY, maxY: maxY, pts: pts };
  }

  function normCvrpRoute(r) {
    if (!r || !r.length) return [];
    const out = r.slice();
    if (out[0] !== 0) out.unshift(0);
    if (out[out.length - 1] !== 0) out.push(0);
    return out;
  }

  function drawSpatialSvg(svgId, inst, family, routeData, rec, primaryColor, bounds, optOverlay, highlightIdx, focusOnly, traceUpTo, L) {
    const W = 480, H = 390, pad = 28;
    const span = Math.max(1e-9, bounds.maxX - bounds.minX, bounds.maxY - bounds.minY);
    const scale = Math.min(W - pad * 2, H - pad * 2) / span;
    const ox = (W - (bounds.maxX - bounds.minX) * scale) / 2;
    const oy = (H - (bounds.maxY - bounds.minY) * scale) / 2;
    const sx = function (x) { return ox + (x - bounds.minX) * scale; };
    const sy = function (y) { return H - (oy + (y - bounds.minY) * scale); };

    const grid = [];
    for (let i = 0; i <= 4; i++) {
      const gx = ox + ((bounds.maxX - bounds.minX) * scale * i) / 4;
      const gy = H - (oy + ((bounds.maxY - bounds.minY) * scale * i) / 4);
      grid.push('<line x1="' + gx.toFixed(1) + '" y1="' + pad + '" x2="' + gx.toFixed(1) + '" y2="' + (H - pad) + '" stroke="#e5e7eb"/>');
      grid.push('<line x1="' + pad + '" y1="' + gy.toFixed(1) + '" x2="' + (W - pad) + '" y2="' + gy.toFixed(1) + '" stroke="#e5e7eb"/>');
    }

    // Explicit Timeout / Missing Solution Frame
    const emptyRoutes = family === "tsp"
      ? !(routeData && routeData.tour && routeData.tour.length)
      : !(routeData && routeData.routes && routeData.routes.length);
    if ((rec && rec.status && rec.status !== "ok") || emptyRoutes) {
      const dots = bounds.pts.map(function (p, idx) {
        if (family === "cvrp" && idx === 0) return "";
        return '<circle cx="' + sx(p[0]).toFixed(1) + '" cy="' + sy(p[1]).toFixed(1) + '" r="1.5" fill="#94a3b8" opacity="0.5"/>';
      }).join("");
      const msTxt = rec && rec.solve_ms !== null && rec.solve_ms !== undefined ? L.fmtMs(rec.solve_ms) : "—";
      const stTxt = rec && rec.status ? rec.status : "no_solution";
      return '<svg id="' + L.esc(svgId) + '" viewBox="0 0 ' + W + " " + H + '" width="100%" height="365">' +
        '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fafbfc" rx="6"/>' +
        grid.join("") + dots +
        '<rect x="' + (W / 2 - 140) + '" y="' + (H / 2 - 28) + '" width="280" height="56" rx="6" fill="#fffefa" stroke="#c2410c"/>' +
        '<text x="' + (W / 2) + '" y="' + (H / 2 - 4) + '" text-anchor="middle" font-size="12.5" font-weight="600" fill="#c2410c">预算约束边界 (' + L.esc(stTxt) + " · " + L.esc(msTxt) + ")</text>" +
        '<text x="' + (W / 2) + '" y="' + (H / 2 + 16) + '" text-anchor="middle" font-size="11.5" fill="#4e5969">时限内未生成完整可行路径，保持真实状态显示</text>' +
        "</svg>";
    }

    const layers = [];
    // Dashed BKS/OPT reference overlay
    if (optOverlay) {
      const refs = family === "tsp"
        ? (optOverlay.tour ? [optOverlay.tour[0] === optOverlay.tour[optOverlay.tour.length - 1] ? optOverlay.tour : optOverlay.tour.concat([optOverlay.tour[0]])] : [])
        : ((optOverlay.routes || (Array.isArray(optOverlay) ? optOverlay : [])).map(normCvrpRoute));
      refs.forEach(function (r) {
        const ptsAttr = r.map(function (idx) {
          const p = bounds.pts[idx];
          return p ? (sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1)) : null;
        }).filter(Boolean).join(" ");
        if (ptsAttr) layers.push('<polyline fill="none" stroke="#94a3b8" stroke-opacity="0.6" stroke-width="1.3" stroke-dasharray="4,3" points="' + ptsAttr + '"/>');
      });
    }

    let focalRoute = null;
    if (family === "tsp") {
      const rawT = routeData.tour;
      const closed = rawT[0] === rawT[rawT.length - 1] ? rawT : rawT.concat([rawT[0]]);
      const ptsAttr = closed.map(function (i) {
        return bounds.pts[i] ? (sx(bounds.pts[i][0]).toFixed(1) + "," + sy(bounds.pts[i][1]).toFixed(1)) : "";
      }).filter(Boolean).join(" ");
      layers.push('<polyline fill="none" stroke="' + primaryColor + '" stroke-width="1.9" points="' + ptsAttr + '"/>');
      focalRoute = closed;
    } else {
      const targetIdx = (highlightIdx >= 0 && highlightIdx < routeData.routes.length) ? highlightIdx : 0;
      focalRoute = normCvrpRoute(routeData.routes[targetIdx]);
      // Draw non-focal routes first (dimmed when focusing or when a specific route row is selected)
      routeData.routes.forEach(function (r, rIdx) {
        if (rIdx === targetIdx) return;
        const nr = normCvrpRoute(r);
        const ptsAttr = nr.map(function (i) { return bounds.pts[i] ? (sx(bounds.pts[i][0]).toFixed(1) + "," + sy(bounds.pts[i][1]).toFixed(1)) : ""; }).filter(Boolean).join(" ");
        const op = (highlightIdx >= 0 || focusOnly) ? "0.22" : "0.78";
        const wd = (highlightIdx >= 0 || focusOnly) ? "1.05" : "1.55";
        layers.push('<polyline fill="none" stroke="' + primaryColor + '" stroke-opacity="' + op + '" stroke-width="' + wd + '" points="' + ptsAttr + '"/>');
      });
      // Focal route on top
      const fAttr = focalRoute.map(function (i) { return bounds.pts[i] ? (sx(bounds.pts[i][0]).toFixed(1) + "," + sy(bounds.pts[i][1]).toFixed(1)) : ""; }).filter(Boolean).join(" ");
      layers.push('<polyline fill="none" stroke="' + primaryColor + '" stroke-width="2.2" points="' + fAttr + '"/>');
    }

    // Active step replay overlay (preserving chronological partial decisions & voluntary returns)
    let activeStepBadge = null;
    if (traceUpTo && traceUpTo.steps && traceUpTo.steps.length) {
      traceUpTo.steps.forEach(function (st) {
        const p1 = bounds.pts[st.current_node], p2 = bounds.pts[st.next_node];
        if (!p1 || !p2) return;
        const isVol = st.action_type === "voluntary_early_return";
        layers.push('<line x1="' + sx(p1[0]).toFixed(1) + '" y1="' + sy(p1[1]).toFixed(1) + '" x2="' + sx(p2[0]).toFixed(1) + '" y2="' + sy(p2[1]).toFixed(1) + '" stroke="' + (isVol ? "#c2410c" : "#165dff") + '" stroke-width="' + (isVol ? "2.6" : "2.1") + '"' + (isVol ? ' stroke-dasharray="5,3"' : "") + "/>");
      });
      const last = traceUpTo.steps[traceUpTo.steps.length - 1];
      activeStepBadge = last;
      const curP = bounds.pts[last.next_node];
      if (curP) {
        layers.push('<circle cx="' + sx(curP[0]).toFixed(1) + '" cy="' + sy(curP[1]).toFixed(1) + '" r="6" fill="none" stroke="' + (last.action_type === "voluntary_early_return" ? "#c2410c" : "#165dff") + '" stroke-width="2.2"/>');
      }
    }

    // Customer & depot nodes
    const focalSet = {};
    if (focalRoute) focalRoute.forEach(function (n) { focalSet[n] = true; });
    const smallDot = bounds.pts.length > 140;
    const nodes = bounds.pts.map(function (p, idx) {
      const cx = sx(p[0]), cy = sy(p[1]);
      if (family === "cvrp" && idx === 0) {
        return '<rect x="' + (cx - 4.5).toFixed(1) + '" y="' + (cy - 4.5).toFixed(1) + '" width="9" height="9" fill="#1d2129" transform="rotate(45 ' + cx.toFixed(1) + " " + cy.toFixed(1) + ')"/>';
      }
      const inFocal = Boolean(focalSet[idx]);
      return '<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="' + (inFocal ? (smallDot ? 2.1 : 2.6) : (smallDot ? 1.2 : 1.7)) + '" fill="#ffffff" stroke="' + (inFocal ? primaryColor : "#86909c") + '" stroke-width="' + (inFocal ? "1.3" : "0.8") + '"/>';
    }).join("");

    // Departure arrow & anti-overlap first-visit badge (adopted from showcase visual polish)
    let arrowSvg = "";
    if (family === "cvrp" && focalRoute && focalRoute.length >= 2 && bounds.pts[0] && bounds.pts[focalRoute[1]]) {
      const dPt = bounds.pts[0], fPt = bounds.pts[focalRoute[1]];
      const x0 = sx(dPt[0]), y0 = sy(dPt[1]), x1 = sx(fPt[0]), y1 = sy(fPt[1]);
      const ang = Math.atan2(y1 - y0, x1 - x0);
      const mx = x0 + 0.58 * (x1 - x0), my = y0 + 0.58 * (y1 - y0);
      const tri = [[6.5, ang], [6.5, ang + 2.52], [6.5, ang - 2.52]].map(function ( pair) {
        return (mx + pair[0] * Math.cos(pair[1])).toFixed(1) + "," + (my + pair[0] * Math.sin(pair[1])).toFixed(1);
      }).join(" ");
      arrowSvg += '<polygon points="' + tri + '" fill="' + primaryColor + '"/>';
      arrowSvg += '<circle cx="' + x1.toFixed(1) + '" cy="' + y1.toFixed(1) + '" r="4.2" fill="' + primaryColor + '" stroke="#ffffff" stroke-width="1.3"/>';
      if (!smallDot || focusOnly) {
        const alignLeft = x1 > x0;
        const label = activeStepBadge && activeStepBadge.action_type === "voluntary_early_return"
          ? "早返"
          : ("#" + String(focalRoute[1]).padStart(2, "0"));
        arrowSvg += '<text x="' + (x1 + (alignLeft ? -7 : 7)).toFixed(1) + '" y="' + (y1 + 4).toFixed(1) + '" text-anchor="' + (alignLeft ? "end" : "start") + '" font-size="11" font-weight="600" fill="' + primaryColor + '" stroke="#fafbfc" stroke-width="3" paint-order="stroke">' + L.esc(label) + "</text>";
      }
    }

    return '<svg id="' + L.esc(svgId) + '" viewBox="0 0 ' + W + " " + H + '" width="100%" height="365">' +
      '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fafbfc" rx="6"/>' +
      grid.join("") + layers.join("") + nodes + arrowSvg + "</svg>";
  }

  function drawObpSvg(svgId, routeData, inst, primaryColor, L) {
    const W = 480, H = 300, pad = 32;
    const fills = (routeData && routeData.sample_bin_fills) || [];
    if (!fills.length) return '<div class="muted" style="padding:20px;">无箱位填充记录</div>';
    const show = fills.slice(0, 32);
    const bw = (W - pad * 2) / show.length;
    const bars = show.map(function (f, i) {
      const ratio = Math.max(0, Math.min(1, Number(f)));
      const bh = ratio * (H - pad * 2 - 20);
      const x = pad + i * bw + 1.5, y = H - pad - bh;
      const col = ratio >= 0.9 ? primaryColor : ratio >= 0.7 ? "#64748b" : "#c2410c";
      return '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + Math.max(2, bw - 3).toFixed(1) + '" height="' + bh.toFixed(1) + '" rx="2" fill="' + col + '"/>';
    }).join("");
    return '<svg id="' + L.esc(svgId) + '" viewBox="0 0 ' + W + " " + H + '" width="100%" height="285">' +
      '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fafbfc" rx="6"/>' +
      '<line x1="' + pad + '" y1="' + (pad + 18) + '" x2="' + (W - pad) + '" y2="' + (pad + 18) + '" stroke="#94a3b8" stroke-dasharray="4,3"/>' +
      '<text x="' + (W - pad) + '" y="' + (pad + 13) + '" font-size="10.5" fill="#4e5969" text-anchor="end">容量 100% (C=' + L.esc(inst.capacity) + ")</text>" +
      bars + "</svg>";
  }

  function pickPresetInstance(suiteBundle, algA, algB, presetKind) {
    const recs = (suiteBundle && suiteBundle.records) || [];
    const byA = {}, byB = {};
    recs.forEach(function (r) {
      if (r.algorithm_id === algA) byA[r.instance_id] = r;
      if (r.algorithm_id === algB) byB[r.instance_id] = r;
    });
    const pairs = Object.keys(byA).filter(function (id) { return byB[id]; }).map(function (id) { return { id: id, a: byA[id], b: byB[id] }; });
    if (!pairs.length) return null;
    if (presetKind === "early_return") {
      pairs.sort(function (x, y) { return Number(y.a.voluntary_early_return_count || 0) - Number(x.a.voluntary_early_return_count || 0); });
      if (Number(pairs[0].a.voluntary_early_return_count || 0) > 0) return pairs[0].id;
      const alt = recs.filter(function (r) { return Number(r.voluntary_early_return_count || 0) > 0; })
        .sort(function (x, y) { return Number(y.voluntary_early_return_count) - Number(x.voluntary_early_return_count); });
      if (alt.length) return alt[0].instance_id;
    }
    if (presetKind === "worst_loss") {
      const toPair = pairs.find(function (p) { return p.a.status !== "ok" || p.b.status !== "ok"; });
      if (toPair) return toPair.id;
      pairs.sort(function (x, y) { return (Number(y.a.rel_gap || 0) - Number(y.b.rel_gap || 0)) - (Number(x.a.rel_gap || 0) - Number(x.b.rel_gap || 0)); });
      return pairs[0].id;
    }
    const okPairs = pairs.filter(function (p) { return p.a.status === "ok" && p.b.status === "ok" && p.a.rel_gap !== null && p.b.rel_gap !== null; });
    const pool = okPairs.length ? okPairs : pairs;
    pool.sort(function (x, y) { return (Number(x.a.rel_gap || 0) - Number(x.b.rel_gap || 0)) - (Number(y.a.rel_gap || 0) - Number(y.b.rel_gap || 0)); });
    return pool[0].id;
  }

  function render(core, state, suiteBundle) {
    const L = window.WB_LABELS;
    const fam = state.family || "cvrp";
    const famSuites = (core.suites || []).filter(function (s) { return s.problem_family === fam; });
    const activeSuite = L.getSuite(core, state.suite) || famSuites[0] || core.suites[0];
    const suiteId = activeSuite.suite_id;

    if (!suiteBundle || !suiteBundle.suite || suiteBundle.suite.suite_id !== suiteId) {
      return '<div class="panel">正在载入测试集 <code>' + L.esc(suiteId) + "</code> 算例坐标与路径…</div>";
    }

    const algs = activeSuite.algorithms_evaluated || [];
    const algA = (state.algA && algs.includes(state.algA)) ? state.algA : (algs.includes("s2_r5_spiral") ? "s2_r5_spiral" : algs[0]);
    let algB = (state.algB && algs.includes(state.algB)) ? state.algB : (algs.includes("cw_relocate_2opt") ? "cw_relocate_2opt" : (algs[1] || algs[0]));
    if (algA === algB && algs.length > 1) algB = algs.find(function (x) { return x !== algA; }) || algA;

    const instances = suiteBundle.suite.instances || [];
    let instId = state.inst;
    if (!instId || !instances.some(function (x) { return x.instance_id === instId; })) {
      instId = pickPresetInstance(suiteBundle, algA, algB, state.preset || "best_gain") || (instances[0] && instances[0].instance_id);
    }
    const instObj = instances.find(function (x) { return x.instance_id === instId; }) || instances[0];
    const instRoutes = (suiteBundle.routes && suiteBundle.routes.routes_by_instance && suiteBundle.routes.routes_by_instance[instId]) || {};
    const routeA = instRoutes[algA] || null, routeB = instRoutes[algB] || null;
    const optOverlay = state.showOpt ? (fam === "tsp" ? instRoutes.__opt__ : (instRoutes.__bks__ || (instObj.bks_routes ? { routes: instObj.bks_routes } : null))) : null;

    const recA = (suiteBundle.records || []).find(function (r) { return r.instance_id === instId && r.algorithm_id === algA; }) || null;
    const recB = (suiteBundle.records || []).find(function (r) { return r.instance_id === instId && r.algorithm_id === algB; }) || null;

    const tracesByInst = (suiteBundle.traces && suiteBundle.traces.traces_by_instance && suiteBundle.traces.traces_by_instance[instId]) || {};
    const traceAlg = tracesByInst[algA] ? algA : (tracesByInst[algB] ? algB : null);
    const traceSteps = traceAlg ? tracesByInst[traceAlg] : null;
    let stepIdx = state.stepIdx !== undefined && state.stepIdx !== null ? Number(state.stepIdx) : -1;
    if (traceSteps && stepIdx < 0 && state.preset === "early_return") {
      const firstVol = traceSteps.findIndex(function (s) { return s.action_type === "voluntary_early_return"; });
      if (firstVol >= 0) stepIdx = firstVol;
    }
    if (traceSteps && stepIdx >= traceSteps.length) stepIdx = traceSteps.length - 1;
    const activeSlice = (traceSteps && stepIdx >= 0) ? { alg: traceAlg, steps: traceSteps.slice(0, stepIdx + 1) } : null;
    const focusOnly = state.cmpFocus !== "all";
    const hi = state.hlRoute !== undefined && state.hlRoute !== null ? Number(state.hlRoute) : -1;

    let canvasInner = "";
    if (fam === "obp") {
      canvasInner = '<div class="dual-plots">' +
        '  <div><div class="plot-title">' + L.esc(L.algTitle(core, algA)) + '</div><div class="plot-sub">箱容 C=' + L.esc(instObj.capacity) + '</div><div class="plot-box">' + drawObpSvg("cmp-svg-a", routeA, instObj, "#0f766e", L) + "</div></div>" +
        '  <div><div class="plot-title">' + L.esc(L.algTitle(core, algB)) + '</div><div class="plot-sub">箱容 C=' + L.esc(instObj.capacity) + '</div><div class="plot-box">' + drawObpSvg("cmp-svg-b", routeB, instObj, "#c2410c", L) + "</div></div>" +
        "</div>";
    } else {
      const bounds = computeSharedBounds(instObj, fam);
      canvasInner = '<div class="dual-plots">' +
        '  <div><div class="plot-title">' + L.esc(L.algTitle(core, algA)) + '</div><div class="plot-sub">' + (recA && recA.status === "ok" ? (L.fmtObj(recA.tour_length) + " · " + L.fmtPct(recA.rel_gap, 2)) : "未完成/超时") + '</div><div class="plot-box">' + drawSpatialSvg("cmp-svg-a", instObj, fam, routeA, recA, "#0f766e", bounds, optOverlay, hi, focusOnly, traceAlg === algA ? activeSlice : null, L) + "</div></div>" +
        '  <div><div class="plot-title">' + L.esc(L.algTitle(core, algB)) + '</div><div class="plot-sub">' + (recB && recB.status === "ok" ? (L.fmtObj(recB.tour_length) + " · " + L.fmtPct(recB.rel_gap, 2)) : "未完成/超时") + '</div><div class="plot-box">' + drawSpatialSvg("cmp-svg-b", instObj, fam, routeB, recB, "#c2410c", bounds, optOverlay, hi, focusOnly, traceAlg === algB ? activeSlice : null, L) + "</div></div>" +
        "</div>";
    }

    let scrubberHtml = "";
    if (traceSteps && traceSteps.length) {
      const curSt = stepIdx >= 0 ? traceSteps[stepIdx] : null;
      const volCount = traceSteps.filter(function (s) { return s.action_type === "voluntary_early_return"; }).length;
      const statusInfo = curSt
        ? ("第 " + (stepIdx + 1) + "/" + traceSteps.length + " 步 · Route #" + (curSt.route_idx + 1) + " (" + curSt.current_node + " → " + curSt.next_node + ") · Q=" + curSt.rest_capacity_before + "→" + curSt.rest_capacity_after + (curSt.action_type === "voluntary_early_return" ? " · 触发主动早返" : ""))
        : ("轨迹总步数 " + traceSteps.length + "（含 " + volCount + " 次主动早返，拖动或点击跳转查看）");
      scrubberHtml = '<div class="scrubber-bar">' +
        '  <input id="cmp-step-slider" type="range" min="-1" max="' + (traceSteps.length - 1) + '" step="1" value="' + stepIdx + '"/>' +
        '  <div class="scrubber-controls">' +
        '    <div class="controls-inline">' +
        '      <button class="btn sm" id="cmp-step-reset">总览</button>' +
        '      <button class="btn sm" id="cmp-step-prev">上一步</button>' +
        '      <button class="btn sm" id="cmp-step-next">下一步</button>' +
        '      <button class="btn sm active" id="cmp-step-next-vol">跳至主动早返 (' + volCount + ")</button>" +
        "    </div>" +
        '    <span class="mono">' + L.esc(statusInfo) + "</span>" +
        "  </div>" +
        "</div>";
    }

    // Inspector right card (3 KPIs + compact clickable route load table + concise diagnostic note)
    let diffCls = "";
    let gapTxt = "—";
    if (recA && recB && recA.status === "ok" && recB.status === "ok" && recB.tour_length) {
      const d = (recA.tour_length - recB.tour_length) / recB.tour_length;
      diffCls = d < -1e-6 ? "good" : d > 1e-6 ? "warn" : "";
      gapTxt = L.fmtPct(recA.rel_gap, 2) + " vs " + L.fmtPct(recB.rel_gap, 2);
    }

    let routeMiniHtml = "";
    if (fam === "cvrp" && routeA && routeA.routes && routeA.routes.length) {
      const cap = Number(instObj.capacity || 1), loads = routeA.route_loads || [], dists = routeA.route_distances || [];
      const rows = routeA.routes.slice(0, 10).map(function (r, rIdx) {
        const ld = loads[rIdx] !== undefined ? loads[rIdx] : 0;
        const pct = Math.min(100, (ld / cap) * 100);
        const active = hi === rIdx ? " active" : "";
        return '<tr class="route-mini-row' + active + '" data-hl-route="' + (hi === rIdx ? -1 : rIdx) + '">' +
          '<td class="mono">#' + (rIdx + 1) + "</td>" +
          '<td><span class="load-bar"><span class="load-fill" style="width:' + pct.toFixed(0) + '%;"></span></span><span class="mono">' + ld + "/" + cap + "</span></td>" +
          '<td class="num">' + (dists[rIdx] !== undefined ? L.fmtNum(dists[rIdx], 2) : "—") + "</td>" +
          "</tr>";
      }).join("");
      routeMiniHtml = '<h3 style="font-size:13.5px;font-weight:600;margin:16px 0 8px;">Algorithm A 路线负荷（点击高亮）</h3>' +
        '<div class="table-wrap"><table class="route-mini-table"><thead><tr><th>车次</th><th>载重 / Q</th><th class="num">路程</th></tr></thead><tbody>' + rows + "</tbody></table></div>" +
        (routeA.routes.length > 10 ? ('<div class="muted" style="font-size:11.5px;margin-top:6px;">仅列前 10 条（共 ' + routeA.routes.length + " 条）</div>") : "");
    }

    let diagText = "同一实例输入下的双算法结构对照；图内箭头标示焦距路径的仓口出发首跳。";
    if ((recA && recA.status !== "ok") || (recB && recB.status !== "ok")) {
      diagText = "存在预算耗时上限截断（A: " + (recA ? recA.status : "—") + " / B: " + (recB ? recB.status : "—") + "），如实呈现未完成边界。";
    } else if (fam === "cvrp" && recA && recB) {
      const vrA = recA.voluntary_early_return_count || 0, vrB = recB.voluntary_early_return_count || 0;
      diagText = "路线数 A=" + (recA.route_count || "—") + " vs B=" + (recB.route_count || "—") + "，主动早返 A=" + vrA + " 次 / B=" + vrB + " 次；可叠加官方 BKS (" + L.fmtObj(instObj.reference_objective) + ") 检查尾部绕行。";
    }

    const kbA = L.resolveAlgKbId(core, algA), kbB = L.resolveAlgKbId(core, algB);

    return [
      '<div class="cmp-bar">',
      '  <div class="controls-inline">',
      '    <select id="cmp-suite-sel">' + core.suites.map(function (s) { return '<option value="' + L.esc(s.suite_id) + '"' + (s.suite_id === suiteId ? " selected" : "") + ">" + L.esc(L.suiteTitle(s)) + "</option>"; }).join("") + "</select>",
      '    <select id="cmp-inst-sel">' + instances.slice(0, 150).map(function (x) { return '<option value="' + L.esc(x.instance_id) + '"' + (x.instance_id === instId ? " selected" : "") + ">" + L.esc(x.instance_id) + " (n=" + x.size + ")</option>"; }).join("") + "</select>",
      '    <select id="cmp-alg-a">' + algs.map(function (id) { return '<option value="' + L.esc(id) + '"' + (id === algA ? " selected" : "") + ">A: " + L.esc(L.algTitle(core, id)) + "</option>"; }).join("") + "</select>",
      '    <select id="cmp-alg-b">' + algs.map(function (id) { return '<option value="' + L.esc(id) + '"' + (id === algB ? " selected" : "") + ">B: " + L.esc(L.algTitle(core, id)) + "</option>"; }).join("") + "</select>",
      "  </div>",
      '  <div class="controls-inline">',
      '    <button class="btn sm" id="cmp-preset-gain">改善例</button>',
      '    <button class="btn sm" id="cmp-preset-loss">边界/超时例</button>',
      fam === "cvrp" ? '<button class="btn sm" id="cmp-preset-early">早返例</button>' : "",
      fam !== "obp" ? ('<label class="toggle-label"><input type="checkbox" id="cmp-focus-ck"' + (focusOnly ? " checked" : "") + "/> 重点路线聚焦</label>") : "",
      fam !== "obp" ? ('<label class="toggle-label"><input type="checkbox" id="cmp-opt-overlay"' + (state.showOpt ? " checked" : "") + "/> 叠加官方参考</label>") : "",
      "  </div>",
      "</div>",

      '<div class="cmp-split">',
      '  <div class="canvas-panel">',
      canvasInner,
      scrubberHtml,
      "  </div>",
      '  <aside class="inspector-card">',
      '    <div class="panel-head" style="margin-bottom:8px;"><h3 class="panel-title">算例检验指标</h3><div class="controls-inline"><button class="btn link sm" id="cmp-export-svg-a">SVG</button><button class="btn link sm" id="cmp-export-png-a">PNG</button></div></div>',
      '    <div class="kpi-row"><span class="kpi-k">目标长度 (A / B)</span><span class="kpi-v ' + diffCls + '">' + (recA && recA.status === "ok" ? L.fmtObj(recA.tour_length) : "超时") + " vs " + (recB && recB.status === "ok" ? L.fmtObj(recB.tour_length) : "超时") + "</span></div>",
      '    <div class="kpi-row"><span class="kpi-k">相对参考差距</span><span class="kpi-v">' + L.esc(gapTxt) + "</span></div>",
      '    <div class="kpi-row"><span class="kpi-k">求解耗时</span><span class="kpi-v">' + (recA ? L.fmtMs(recA.solve_ms) : "—") + " vs " + (recB ? L.fmtMs(recB.solve_ms) : "—") + "</span></div>",
      routeMiniHtml,
      '    <div class="diag-note">' + L.esc(diagText) + "</div>",
      (kbA || kbB) ? ('<div class="controls-inline" style="margin-top:12px;">' + (kbA ? '<button class="btn sm" data-nav="page=knowledge&tab=library&entry=' + L.esc(kbA) + '">A 知识卡</button>' : "") + (kbB ? '<button class="btn sm" data-nav="page=knowledge&tab=library&entry=' + L.esc(kbB) + '">B 知识卡</button>' : "") + "</div>") : "",
      "  </aside>",
      "</div>"
    ].join("\n");
  }

  function bind(rootEl, core, state, nav, suiteBundle) {
    const L = window.WB_LABELS;
    const sSel = rootEl.querySelector("#cmp-suite-sel");
    if (sSel) sSel.addEventListener("change", function () {
      const s = L.getSuite(core, sSel.value);
      nav({ suite: sSel.value, family: (s && s.problem_family) || state.family, inst: "", stepIdx: -1, hlRoute: -1 });
    });
    const iSel = rootEl.querySelector("#cmp-inst-sel");
    if (iSel) iSel.addEventListener("change", function () { nav({ inst: iSel.value, stepIdx: -1, hlRoute: -1 }); });
    const aSel = rootEl.querySelector("#cmp-alg-a");
    if (aSel) aSel.addEventListener("change", function () { nav({ algA: aSel.value, stepIdx: -1, hlRoute: -1 }); });
    const bSel = rootEl.querySelector("#cmp-alg-b");
    if (bSel) bSel.addEventListener("change", function () { nav({ algB: bSel.value, stepIdx: -1 }); });

    const algs = (L.getSuite(core, state.suite) || {}).algorithms_evaluated || [];
    const curA = (state.algA && algs.includes(state.algA)) ? state.algA : (algs.includes("s2_r5_spiral") ? "s2_r5_spiral" : algs[0]);
    const curB = (state.algB && algs.includes(state.algB)) ? state.algB : (algs.includes("cw_relocate_2opt") ? "cw_relocate_2opt" : (algs[1] || algs[0]));

    const gBtn = rootEl.querySelector("#cmp-preset-gain");
    if (gBtn) gBtn.addEventListener("click", function () { nav({ inst: pickPresetInstance(suiteBundle, curA, curB, "best_gain") || "", preset: "best_gain", stepIdx: -1, hlRoute: -1 }); });
    const lBtn = rootEl.querySelector("#cmp-preset-loss");
    if (lBtn) lBtn.addEventListener("click", function () { nav({ inst: pickPresetInstance(suiteBundle, curA, curB, "worst_loss") || "", preset: "worst_loss", stepIdx: -1, hlRoute: -1 }); });
    const eBtn = rootEl.querySelector("#cmp-preset-early");
    if (eBtn) eBtn.addEventListener("click", function () {
      const targetId = pickPresetInstance(suiteBundle, curA, curB, "early_return") || "";
      const trInst = (suiteBundle && suiteBundle.traces && suiteBundle.traces.traces_by_instance && suiteBundle.traces.traces_by_instance[targetId]) || {};
      const tList = trInst[curA] || trInst.s2_r5_spiral || null;
      const firstVol = Array.isArray(tList) ? tList.findIndex(function (s) { return s.action_type === "voluntary_early_return"; }) : -1;
      nav({ inst: targetId, preset: "early_return", stepIdx: firstVol >= 0 ? firstVol : -1, hlRoute: -1 });
    });

    const fCk = rootEl.querySelector("#cmp-focus-ck");
    if (fCk) fCk.addEventListener("change", function () { nav({ cmpFocus: fCk.checked ? "focus" : "all" }); });
    const optCk = rootEl.querySelector("#cmp-opt-overlay");
    if (optCk) optCk.addEventListener("change", function () { nav({ showOpt: optCk.checked }); });
    rootEl.querySelectorAll("[data-hl-route]").forEach(function (el) {
      el.addEventListener("click", function () { nav({ hlRoute: Number(el.getAttribute("data-hl-route")) }); });
    });

    const instId = state.inst || ((suiteBundle && suiteBundle.suite && suiteBundle.suite.instances[0] && suiteBundle.suite.instances[0].instance_id) || "");
    const tMap = (suiteBundle && suiteBundle.traces && suiteBundle.traces.traces_by_instance && suiteBundle.traces.traces_by_instance[instId]) || {};
    const tAlg = tMap[curA] ? curA : (tMap[curB] ? curB : null);
    const steps = tAlg ? tMap[tAlg] : null;
    const curIdx = state.stepIdx !== undefined && state.stepIdx !== null ? Number(state.stepIdx) : -1;

    const slider = rootEl.querySelector("#cmp-step-slider");
    if (slider) slider.addEventListener("change", function () { nav({ stepIdx: Number(slider.value) }); });
    const rBtn = rootEl.querySelector("#cmp-step-reset");
    if (rBtn) rBtn.addEventListener("click", function () { nav({ stepIdx: -1 }); });
    const pBtn = rootEl.querySelector("#cmp-step-prev");
    if (pBtn && steps) pBtn.addEventListener("click", function () { nav({ stepIdx: Math.max(-1, curIdx - 1) }); });
    const nBtn = rootEl.querySelector("#cmp-step-next");
    if (nBtn && steps) nBtn.addEventListener("click", function () { nav({ stepIdx: Math.min(steps.length - 1, curIdx + 1) }); });
    const vBtn = rootEl.querySelector("#cmp-step-next-vol");
    if (vBtn && steps) {
      vBtn.addEventListener("click", function () {
        let nxt = steps.findIndex(function (s, idx) { return idx > curIdx && s.action_type === "voluntary_early_return"; });
        if (nxt < 0) nxt = steps.findIndex(function (s) { return s.action_type === "voluntary_early_return"; });
        if (nxt >= 0) nav({ stepIdx: nxt });
      });
    }

    const svgBtn = rootEl.querySelector("#cmp-export-svg-a");
    if (svgBtn) svgBtn.addEventListener("click", function () { window.WB_EXPORT.exportSvg(rootEl.querySelector("#cmp-svg-a"), instId + "_" + curA + ".svg"); });
    const pngBtn = rootEl.querySelector("#cmp-export-png-a");
    if (pngBtn) pngBtn.addEventListener("click", function () { window.WB_EXPORT.exportPng300Dpi(rootEl.querySelector("#cmp-svg-a"), instId + "_" + curA + "_300dpi.png"); });
  }

  window.WB_VIEWS = window.WB_VIEWS || {};
  window.WB_VIEWS.comparator = { render: render, bind: bind };
})();
