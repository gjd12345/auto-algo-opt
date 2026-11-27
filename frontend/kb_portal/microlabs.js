/* Four Interactive Academic Microlabs (Zero Internal Jargon, Pure SVG Visualizations). */
(function () {
  "use strict";

  const LAB_LIST = [
    {
      id: "depot_phase",
      kicker: "交互微实验 1 · 构造动力学",
      title: "仓库出发步的径向相变",
      subtitle: "理解为何路径第一步从近邻转向远端客户，能让总路程整体下降 7.97%"
    },
    {
      id: "fleet_tightness",
      kicker: "交互微实验 2 · 组合可行域",
      title: "容量紧度与指定车队硬约束",
      subtitle: "洞察不可分需求下的合并阻塞边界，为何显式感知车数可使合规率跃升至 93.1%"
    },
    {
      id: "scale_escape",
      kicker: "交互微实验 3 · 跨尺度泛化",
      title: "复杂度逃逸与联合筛查边界",
      subtitle: "观察小规模线性代理如何在千点算例骤然超限，及几何–规模联合探针如何实现 430/430 全通"
    },
    {
      id: "memory_variance",
      kicker: "交互微实验 4 · 记忆演化权衡",
      title: "离线精炼只读与在线写回的方差演化",
      subtitle: "验证为何在严格门控下，离线蒸馏只读策略能在百题高难度基准上实现零负迁移"
    }
  ];

  function renderDepotLab(data, st, R) {
    const alpha = st.labAlpha !== undefined ? Number(st.labAlpha) : 1.15;
    const hp = data.h003_preview;
    const inst = (hp && hp.instances && (hp.instances.find(function (x) { return x.id === hp.example; }) || hp.instances[0])) || null;
    if (!inst) return '<div class="muted">暂无算例几何预览数据</div>';

    const depot = inst.coords[0];
    const items = [];
    for (let j = 1; j < inst.coords.length; j++) {
      const d0 = Math.hypot(depot[0] - inst.coords[j][0], depot[1] - inst.coords[j][1]);
      items.push({ j: j, d0: d0, score: (1 - alpha) * d0, coord: inst.coords[j], q: inst.demands[j] });
    }
    items.sort(function (a, b) { return a.score - b.score; });
    const top5 = items.slice(0, 5);
    const maxS = Math.max(1e-5, Math.max.apply(null, top5.map(function (c) { return Math.abs(c.score); })));
    const col = alpha > 1.005 ? "#0f766e" : (alpha < 0.995 ? "#b84a27" : "#78716c");
    const statusText = Math.abs(alpha - 1) <= 0.005
      ? "临界中性点（α = 1.00）：所有候选第一步得分恒为零，策略完全退化"
      : (alpha < 1
        ? "近邻优先区（α < 1.00）：先服务仓库周边，外围孤立远点被迫在尾部高代价往返"
        : "远端协同区（α > 1.00）：先赴外围最远区域构架主干，返程顺路吸收近郊客户");

    const W = 440, H = 290, pad = 26;
    const sx = function (x) { return pad + x * (W - 2 * pad); };
    const sy = function (y) { return H - pad - y * (H - 2 * pad); };
    const picked = {};
    top5.slice(0, 3).forEach(function (c) { picked[c.j] = true; });

    const rays = top5.slice(0, 3).map(function (c) {
      return '<line x1="' + sx(depot[0]).toFixed(1) + '" y1="' + sy(depot[1]).toFixed(1) + '" x2="' + sx(c.coord[0]).toFixed(1) + '" y2="' + sy(c.coord[1]).toFixed(1) + '" stroke="' + col + '" stroke-width="2" stroke-dasharray="5,3"/>';
    }).join("");
    const nodes = inst.coords.map(function (pt, idx) {
      if (idx === 0) {
        return '<rect x="' + (sx(pt[0]) - 6).toFixed(1) + '" y="' + (sy(pt[1]) - 6).toFixed(1) + '" width="12" height="12" rx="2" fill="#1c1917"/>' +
               '<text x="' + (sx(pt[0]) + 9).toFixed(1) + '" y="' + (sy(pt[1]) + 4).toFixed(1) + '" font-size="11.5" font-weight="700" fill="#1c1917">仓库</text>';
      }
      const hot = Boolean(picked[idx]);
      return '<circle cx="' + sx(pt[0]).toFixed(1) + '" cy="' + sy(pt[1]).toFixed(1) + '" r="' + (hot ? 5.2 : 2.8) + '" fill="' + (hot ? col : "#a8a29e") + '" opacity="' + (hot ? "0.96" : "0.55") + '"/>';
    }).join("");

    const bars = top5.map(function (c) {
      const pct = Math.min(100, (Math.abs(c.score) / maxS) * 100);
      return '<div style="margin-bottom:10px;">' +
        '<div style="display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:3px;"><span>客户 #' + c.j + '（仓距 ' + c.d0.toFixed(3) + '，需求 ' + c.q + '）</span><span class="mono" style="color:' + col + ';font-weight:600;">' + c.score.toFixed(4) + "</span></div>" +
        '<div style="height:7px;background:#e6e1d6;border-radius:999px;overflow:hidden;"><div style="height:100%;width:' + pct.toFixed(1) + '%;background:' + col + ';border-radius:999px;"></div></div>' +
        "</div>";
    }).join("");

    return '<div class="formula-pill">出发优先级得分：<i>s</i><sub>&alpha;</sub>(0, <i>j</i>) = (1 &minus; &alpha;) &middot; <i>d</i>(0, <i>j</i>) &nbsp;&nbsp;|&nbsp;&nbsp; 最小化选择优先出发客户</div>' +
      '<div class="lab-grid">' +
      '  <div class="plot-frame">' +
      '    <div style="font-size:13px;font-weight:600;color:' + col + ';margin-bottom:10px;">' + R.esc(statusText) + "</div>" +
      '    <svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="275">' +
      '      <rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fcfbf8" rx="8"/>' +
             rays + nodes +
      "    </svg>" +
      '    <div class="muted" style="font-size:12px;margin-top:6px;">真实多尺度算例空间拓扑：高亮三点为当前 &alpha; 参数下优先派出的首批客户。</div>' +
      "  </div>" +
      '  <div class="control-box">' +
      '    <div class="slider-row">' +
      '      <label><span>径向偏置参数 &alpha;</span><span class="mono" id="lab-alpha-lbl">' + alpha.toFixed(2) + "</span></label>" +
      '      <input id="lab-alpha-slider" type="range" min="0.60" max="1.40" step="0.01" value="' + alpha.toFixed(2) + '"/>' +
      '      <div style="display:flex;gap:8px;margin-top:8px;">' +
      '        <button type="button" class="btn sm ' + (alpha < 0.99 ? "active" : "") + '" data-alpha-preset="0.80">0.80 · 近邻先发</button>' +
      '        <button type="button" class="btn sm ' + (Math.abs(alpha - 1) <= 0.01 ? "active" : "") + '" data-alpha-preset="1.00">1.00 · 相变临界点</button>' +
      '        <button type="button" class="btn sm ' + (alpha > 1.01 ? "active" : "") + '" data-alpha-preset="1.15">1.15 · 远端破局</button>' +
      "      </div>" +
      "    </div>" +
      '    <h4 style="margin:12px 0 8px;font-size:13.5px;">得分最优前 5 候选客户</h4>' +
           bars +
      '    <div class="insight-callout"><b>反事实对比实证：</b>在 120 题独立盲测中，仅翻转每条路径“仓库出发第一步”的径向排序（后续策略完全冻结），即可让总路径长度显著缩短 <b>7.97%</b>（94 胜 0 平 26 负，在 200 节点规模上达到 <b>40 胜 0 负</b>）。</div>' +
      "  </div>" +
      "</div>";
  }

  function renderTightnessLab(st) {
    const rho = st.labRho !== undefined ? Number(st.labRho) : 0.96;
    const dmax = st.labDmax !== undefined ? Number(st.labDmax) : 0.22;

    // Empirical failure curve calibrated from observed high-tightness overshoots:
    // For rho in [0.98, 1.00]: <0.10 -> 8/21 (38.1%), 0.10-0.20 -> 17/34 (50.0%), >=0.20 -> 49/59 (83.1%)
    const baseFailPct = Math.max(4, Math.min(92,
      (rho - 0.72) * 185 * (0.45 + 1.8 * dmax)
    ));
    const minPairBlocked = rho > 0.5 && (2 * (1 - dmax * 0.4) > 1.0) && rho > 0.88;
    const balanceRatio = Math.max(0, (1.0 - rho) * 100);

    const W = 440, H = 260, pl = 48, pr = 22, pt = 22, pb = 38;
    const sx = function (x) { return pl + ((x - 0.75) / 0.25) * (W - pl - pr); };
    const sy = function (y) { return H - pb - (y / 100) * (H - pt - pb); };

    // Draw three reference empirical bars at high tightness + live curve marker
    const curX = sx(Math.min(1, Math.max(0.75, rho)));
    const curY = sy(baseFailPct);

    return '<div class="formula-pill">&rho; = &Sigma;<i>q</i><sub>i</sub> / (<i>K</i> &middot; <i>Q</i>) &nbsp;&nbsp;|&nbsp;&nbsp; 整路合并阻塞条件：min<sub>a&lt;b</sub>(<i>l</i><sub>a</sub> + <i>l</i><sub>b</sub>) &gt; <i>Q</i></div>' +
      '<div class="lab-grid">' +
      '  <div class="plot-frame">' +
      '    <div style="font-size:13px;font-weight:600;color:var(--indigo);margin-bottom:8px;">高紧度区间（&rho; &isin; [0.98, 1.00]）最大需求占比与无约束超车实测风险</div>' +
      '    <svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="250">' +
      '      <rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fcfbf8" rx="8"/>' +
      '      <line x1="' + pl + '" y1="' + (H - pb) + '" x2="' + (W - pr) + '" y2="' + (H - pb) + '" stroke="#d4cdbd"/>' +
      '      <line x1="' + pl + '" y1="' + pt + '" x2="' + pl + '" y2="' + (H - pb) + '" stroke="#d4cdbd"/>' +
      '      <text x="' + (W / 2) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="11.5" fill="#78716c">总容量利用率（容量紧度 &rho;）</text>' +
      '      <text x="14" y="' + (H / 2) + '" text-anchor="middle" font-size="11.5" fill="#78716c" transform="rotate(-90 14 ' + (H / 2) + ')">无契约超车风险 (%)</text>' +
             // Reference shaded danger zone rho >= 0.95
      '      <rect x="' + sx(0.95).toFixed(1) + '" y="' + pt + '" width="' + (W - pr - sx(0.95)).toFixed(1) + '" height="' + (H - pt - pb) + '" fill="#b84a27" opacity="0.08"/>' +
      '      <text x="' + (sx(0.95) + 4).toFixed(1) + '" y="' + (pt + 14) + '" font-size="11" fill="#b84a27">极紧容量区 (&rho; &ge; 0.95)</text>' +
             // Empirical reference markers at rho=0.99
      '      <circle cx="' + sx(0.99).toFixed(1) + '" cy="' + sy(38.1).toFixed(1) + '" r="4" fill="#0f766e"/>' +
      '      <circle cx="' + sx(0.99).toFixed(1) + '" cy="' + sy(50.0).toFixed(1) + '" r="4" fill="#b47b1e"/>' +
      '      <circle cx="' + sx(0.99).toFixed(1) + '" cy="' + sy(83.1).toFixed(1) + '" r="4" fill="#b84a27"/>' +
             // Live operating point
      '      <line x1="' + curX.toFixed(1) + '" y1="' + pt + '" x2="' + curX.toFixed(1) + '" y2="' + (H - pb) + '" stroke="#2b4c7e" stroke-dasharray="4,3"/>' +
      '      <circle cx="' + curX.toFixed(1) + '" cy="' + curY.toFixed(1) + '" r="7" fill="#2b4c7e" stroke="#fff" stroke-width="2"/>' +
      '      <text x="' + Math.min(W - 130, curX + 10).toFixed(1) + '" y="' + Math.max(pt + 16, curY - 10).toFixed(1) + '" font-size="12" font-weight="700" fill="#2b4c7e">估算风险 ≈ ' + baseFailPct.toFixed(1) + '%</text>' +
      "    </svg>" +
      '    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px;font-size:12px;">' +
      '      <div style="background:#ecf7f5;padding:7px 9px;border-radius:6px;"><b>&delta;<sub>max</sub> &lt; 0.10</b><br>实测超车 8/21 (38.1%)</div>' +
      '      <div style="background:#fcf6ea;padding:7px 9px;border-radius:6px;"><b>0.10 &le; &delta;<sub>max</sub> &lt; 0.20</b><br>实测超车 17/34 (50.0%)</div>' +
      '      <div style="background:#fdf1ec;padding:7px 9px;border-radius:6px;"><b>&delta;<sub>max</sub> &ge; 0.20</b><br>实测超车 49/59 (83.1%)</div>' +
      "    </div>" +
      "  </div>" +
      '  <div class="control-box">' +
      '    <div class="slider-row">' +
      '      <label><span>容量紧度 &rho; = &Sigma;q<sub>i</sub> / (KQ)</span><span class="mono">' + rho.toFixed(2) + "</span></label>" +
      '      <input id="lab-rho-slider" type="range" min="0.75" max="1.00" step="0.01" value="' + rho.toFixed(2) + '"/>' +
      "    </div>" +
      '    <div class="slider-row">' +
      '      <label><span>最大单客需求占比 &delta;<sub>max</sub> = max q<sub>i</sub> / Q</span><span class="mono">' + dmax.toFixed(2) + "</span></label>" +
      '      <input id="lab-dmax-slider" type="range" min="0.05" max="0.35" step="0.01" value="' + dmax.toFixed(2) + '"/>' +
      "    </div>" +
      '    <div style="background:#fff;border:1px solid var(--border-warm);border-radius:8px;padding:12px 14px;font-size:13px;">' +
      '      <div><b>每车平均剩余裕度：</b><span class="mono">' + balanceRatio.toFixed(1) + '%</span></div>' +
      '      <div style="margin-top:4px;"><b>整路合并可行性：</b>' + (minPairBlocked ? '<span style="color:var(--terra);font-weight:600;">易触发整路合并阻塞（须跨路线客户重排）</span>' : '<span style="color:var(--teal);font-weight:600;">常规整路合并通道畅通</span>') + "</div>" +
      "    </div>" +
      '    <div class="insight-callout"><b>理论与实证闭环：</b>即使满足 &rho; &le; 1 且单客不超载，不可分客户需求仍会堵死静态整路合并。引入<b>路径数惩罚与最轻路线强制拆解重插</b>后，官方 174 题基准的指定车队合规率从 <b>54.0% (94/174)</b> 跃升至 <b>93.1% (162/174)</b>。</div>' +
      "  </div>" +
      "</div>";
  }

  function renderScaleEscapeLab(st) {
    const nVal = st.labScaleN !== undefined ? Number(st.labScaleN) : 500;
    const tBaseline = nVal / 5.0;
    const tEscape = nVal / 5.0 + (nVal > 200 ? (nVal * nVal) / 500.0 : 0);
    const over = tEscape > 500;

    const W = 440, H = 260, pl = 52, pr = 22, pt = 22, pb = 38;
    const sx = function (n) { return pl + ((n - 50) / 950) * (W - pl - pr); };
    const sy = function (ms) { return H - pb - Math.min(1, ms / 1400) * (H - pt - pb); };

    let ptsBase = [], ptsEsc = [];
    for (let n = 50; n <= 1000; n += 25) {
      ptsBase.push(sx(n).toFixed(1) + "," + sy(n / 5.0).toFixed(1));
      const te = n / 5.0 + (n > 200 ? (n * n) / 500.0 : 0);
      ptsEsc.push(sx(n).toFixed(1) + "," + sy(te).toFixed(1));
    }

    return '<div class="formula-pill">反例模型：<i>T</i>(<i>n</i>) = <i>n</i>/5 + 1[<i>n</i> &gt; 200] &middot; <i>n</i><sup>2</sup>/500 ms &nbsp;&nbsp;|&nbsp;&nbsp; 严守 500 ms 截止线</div>' +
      '<div class="lab-grid">' +
      '  <div class="plot-frame">' +
      '    <div style="font-size:13px;font-weight:600;color:' + (over ? "var(--terra)" : "var(--teal)") + ';margin-bottom:8px;">' +
             (over ? "触发复杂度逃逸！n=" + nVal + " 时耗时 " + tEscape.toFixed(0) + " ms，已跌穿 500 ms 严格截止线" : "处于安全窗口内：n=" + nVal + " 时耗时 " + tEscape.toFixed(0) + " ms ≤ 500 ms") +
      "    </div>" +
      '    <svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="250">' +
      '      <rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fcfbf8" rx="8"/>' +
             // 500 ms deadline
      '      <line x1="' + pl + '" y1="' + sy(500).toFixed(1) + '" x2="' + (W - pr) + '" y2="' + sy(500).toFixed(1) + '" stroke="#b84a27" stroke-width="1.6" stroke-dasharray="6,4"/>' +
      '      <text x="' + (pl + 6) + '" y="' + (sy(500) - 6).toFixed(1) + '" font-size="11" font-weight="600" fill="#b84a27">500 ms 严格截止时限</text>' +
             // n=200 dev boundary
      '      <line x1="' + sx(200).toFixed(1) + '" y1="' + pt + '" x2="' + sx(200).toFixed(1) + '" y2="' + (H - pb) + '" stroke="#b47b1e" stroke-dasharray="4,3"/>' +
      '      <text x="' + (sx(200) + 4).toFixed(1) + '" y="' + (pt + 14) + '" font-size="11" fill="#b47b1e">小规模代理上限 (n=200)</text>' +
      '      <polyline fill="none" stroke="#0f766e" stroke-width="2" points="' + ptsBase.join(" ") + '"/>' +
      '      <polyline fill="none" stroke="#2b4c7e" stroke-width="2.5" points="' + ptsEsc.join(" ") + '"/>' +
      '      <circle cx="' + sx(nVal).toFixed(1) + '" cy="' + sy(tEscape).toFixed(1) + '" r="6" fill="' + (over ? "#b84a27" : "#2b4c7e") + '" stroke="#fff" stroke-width="2"/>' +
      "    </svg>" +
      "  </div>" +
      '  <div class="control-box">' +
      '    <div class="slider-row">' +
      '      <label><span>部署算例规模（客户数 n）</span><span class="mono">n = ' + nVal + "</span></label>" +
      '      <input id="lab-scale-slider" type="range" min="50" max="1000" step="25" value="' + nVal + '"/>' +
      '      <div style="display:flex;gap:8px;margin-top:8px;">' +
      '        <button type="button" class="btn sm" data-scalen-preset="100">n = 100 (开发代理)</button>' +
      '        <button type="button" class="btn sm" data-scalen-preset="500">n = 500 (逃逸门槛)</button>' +
      '        <button type="button" class="btn sm" data-scalen-preset="936">n = 936 (超大型实测)</button>' +
      "      </div>" +
      "    </div>" +
      '    <div style="background:#fff;border:1px solid var(--border-warm);border-radius:8px;padding:12px 14px;font-size:13px;">' +
      '      <div><b>受控基线预估耗时：</b><span class="mono">' + tBaseline.toFixed(1) + " ms</span></div>" +
      '      <div style="margin-top:4px;"><b>二次分支逃逸耗时：</b><span class="mono" style="color:' + (over ? "var(--terra)" : "var(--teal)") + ';font-weight:700;">' + tEscape.toFixed(1) + " ms</span></div>" +
      "    </div>" +
      '    <div class="insight-callout warn"><b>为何单测边际分布不够？</b>对超大型算例剖面显示，仅邻域局部精修阶段即可耗时 <b>751.17 ms</b>（总计 943.22 ms）。将高需求波动、高偏心率、强聚类与大尺度纳入<b>联合压力探针 + 预算感知早退</b>后，模型在 500 ms 与 2000 ms 双预算均达成 <b>430/430 全通</b>。</div>' +
      "  </div>" +
      "</div>";
  }

  function renderMemoryLab(st) {
    const aCoef = st.labAmp !== undefined ? Number(st.labAmp) : 1.25;
    const nu = st.labNu !== undefined ? Number(st.labNu) : 0.80;
    const rounds = [1, 2, 3, 4, 5];
    const onlineVar = [];
    let acc = 0;
    for (let t = 0; t < rounds.length; t++) {
      acc += Math.pow(aCoef, 2 * t) * Math.pow(nu, 2);
      onlineVar.push(acc);
    }
    const frozenVar = 0.65;
    const maxV = Math.max(4, onlineVar[onlineVar.length - 1] * 1.1);

    const W = 440, H = 250, pl = 48, pr = 22, pt = 22, pb = 38;
    const sx = function (idx) { return pl + (idx / 4) * (W - pl - pr); };
    const sy = function (v) { return H - pb - Math.min(1, v / maxV) * (H - pt - pb); };

    const ptsOn = rounds.map(function (_, i) { return sx(i).toFixed(1) + "," + sy(onlineVar[i]).toFixed(1); }).join(" ");
    const frozenY = sy(frozenVar).toFixed(1);
    const snr = 1.0 / Math.sqrt(Math.max(0.01, onlineVar[2]));

    return '<div class="formula-pill"><i>V</i><sub>W</sub>(<i>t</i>) = &sigma;<sub>W</sub><sup>2</sup> &Sigma;<sub>j=0..t&minus;1</sub> <i>a</i><sup>2j</sup> &nbsp;&nbsp;|&nbsp;&nbsp; 离线占优临界：&Phi;(<i>s</i>/&nu;) &le; (1&minus;<i>p</i>)&#8467; / (<i>pg</i> + (1&minus;<i>p</i>)&#8467;)</div>' +
      '<div class="lab-grid">' +
      '  <div class="plot-frame">' +
      '    <div style="font-size:13px;font-weight:600;color:var(--indigo);margin-bottom:8px;">跨轮次复用累积误差方差曲线（在线写回 vs 冻结离线精炼）</div>' +
      '    <svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="240">' +
      '      <rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fcfbf8" rx="8"/>' +
      '      <line x1="' + pl + '" y1="' + (H - pb) + '" x2="' + (W - pr) + '" y2="' + (H - pb) + '" stroke="#d4cdbd"/>' +
      '      <line x1="' + pl + '" y1="' + pt + '" x2="' + pl + '" y2="' + (H - pb) + '" stroke="#d4cdbd"/>' +
      '      <line x1="' + pl + '" y1="' + frozenY + '" x2="' + (W - pr) + '" y2="' + frozenY + '" stroke="#0f766e" stroke-width="2.2" stroke-dasharray="6,3"/>' +
      '      <text x="' + (pl + 6) + '" y="' + (Number(frozenY) - 6).toFixed(1) + '" font-size="11.5" font-weight="600" fill="#0f766e">冻结离线精炼只读（恒定方差）</text>' +
      '      <polyline fill="none" stroke="#b84a27" stroke-width="2.6" points="' + ptsOn + '"/>' +
             rounds.map(function (r, i) {
               return '<circle cx="' + sx(i).toFixed(1) + '" cy="' + sy(onlineVar[i]).toFixed(1) + '" r="4.5" fill="#b84a27"/>' +
                      '<text x="' + sx(i).toFixed(1) + '" y="' + (H - pb + 16) + '" text-anchor="middle" font-size="11" fill="#78716c">第' + r + '轮</text>';
             }).join("") +
      "    </svg>" +
      "  </div>" +
      '  <div class="control-box">' +
      '    <div class="slider-row">' +
      '      <label><span>赢家复用反馈增益系数 a</span><span class="mono">a = ' + aCoef.toFixed(2) + "</span></label>" +
      '      <input id="lab-amp-slider" type="range" min="0.50" max="1.60" step="0.05" value="' + aCoef.toFixed(2) + '"/>' +
      "    </div>" +
      '    <div class="slider-row">' +
      '      <label><span>开发集单轮筛选噪声 &sigma;<sub>W</sub></span><span class="mono">' + nu.toFixed(2) + "</span></label>" +
      '      <input id="lab-nu-slider" type="range" min="0.20" max="1.20" step="0.05" value="' + nu.toFixed(2) + '"/>' +
      "    </div>" +
      '    <div style="background:#fff;border:1px solid var(--border-warm);border-radius:8px;padding:12px 14px;font-size:13px;">' +
      '      <div><b>第 3 轮时在线有效信噪比 s/&nu;：</b><span class="mono">' + snr.toFixed(3) + "</span></div>" +
      '      <div style="margin-top:4px;"><b>大规模 Set X 100 题实证均值：</b><br>离线门控精炼只读 <b style="color:var(--teal);">65,965.24</b>（3/3 种子零负迁移） vs 在线即时写回 <b style="color:var(--terra);">66,136.49</b></div>' +
      "    </div>" +
      '    <div class="insight-callout"><b>结论：</b>在线单轮开发赢家在被写入知识库并跨轮复用后，会把偶然噪声按几何级数放大，越过信噪比临界线导致负迁移；离线充分筛查后冻结注入可锁死方差膨胀。</div>' +
      "  </div>" +
      "</div>";
  }

  function render(data, st, R) {
    const activeId = st.lab || "depot_phase";
    const tabsHtml = LAB_LIST.map(function (lab) {
      return '<button type="button" class="lab-tab ' + (lab.id === activeId ? "active" : "") + '" data-lab-id="' + lab.id + '">' +
        '<div class="lab-tab-kicker">' + R.esc(lab.kicker) + "</div>" +
        '<div class="lab-tab-title">' + R.esc(lab.title) + "</div>" +
        "</button>";
    }).join("");

    const activeMeta = LAB_LIST.find(function (l) { return l.id === activeId; }) || LAB_LIST[0];
    let bodyHtml = "";
    if (activeId === "depot_phase") bodyHtml = renderDepotLab(data, st, R);
    else if (activeId === "fleet_tightness") bodyHtml = renderTightnessLab(st);
    else if (activeId === "scale_escape") bodyHtml = renderScaleEscapeLab(st);
    else bodyHtml = renderMemoryLab(st);

    return '<div class="section-head" style="margin-top:0;"><div>' +
      '<div class="section-eyebrow">INTERACTIVE MICRO-LABORATORIES</div>' +
      '<h1 class="section-title">核心机理与边界条件交互微实验</h1>' +
      '<p class="section-sub">拖动参数直接观测数学相变、合并阻塞界、复杂度逃逸与记忆反馈方差演变——无需看枯燥表格。</p>' +
      "</div></div>" +
      '<div class="lab-tabs">' + tabsHtml + "</div>" +
      '<div class="lab-stage">' +
      '  <h2 class="serif" style="margin:0 0 4px;font-size:21px;">' + R.esc(activeMeta.title) + "</h2>" +
      '  <p class="muted" style="margin:0 0 14px;font-size:14px;">' + R.esc(activeMeta.subtitle) + "</p>" +
         bodyHtml +
      "</div>";
  }

  function bind(container, data, st, setState, R) {
    container.querySelectorAll("[data-lab-id]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setState({ lab: btn.getAttribute("data-lab-id") });
      });
    });

    const alphaSlider = container.querySelector("#lab-alpha-slider");
    if (alphaSlider) {
      alphaSlider.addEventListener("input", function () {
        setState({ labAlpha: Number(alphaSlider.value) }, true);
      });
    }
    container.querySelectorAll("[data-alpha-preset]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setState({ labAlpha: Number(btn.getAttribute("data-alpha-preset")) });
      });
    });

    const rhoSlider = container.querySelector("#lab-rho-slider");
    if (rhoSlider) rhoSlider.addEventListener("input", function () { setState({ labRho: Number(rhoSlider.value) }, true); });
    const dmaxSlider = container.querySelector("#lab-dmax-slider");
    if (dmaxSlider) dmaxSlider.addEventListener("input", function () { setState({ labDmax: Number(dmaxSlider.value) }, true); });

    const scaleSlider = container.querySelector("#lab-scale-slider");
    if (scaleSlider) scaleSlider.addEventListener("input", function () { setState({ labScaleN: Number(scaleSlider.value) }, true); });
    container.querySelectorAll("[data-scalen-preset]").forEach(function (btn) {
      btn.addEventListener("click", function () { setState({ labScaleN: Number(btn.getAttribute("data-scalen-preset")) }); });
    });

    const ampSlider = container.querySelector("#lab-amp-slider");
    if (ampSlider) ampSlider.addEventListener("input", function () { setState({ labAmp: Number(ampSlider.value) }, true); });
    const nuSlider = container.querySelector("#lab-nu-slider");
    if (nuSlider) nuSlider.addEventListener("input", function () { setState({ labNu: Number(nuSlider.value) }, true); });
  }

  window.KB_MICROLABS = {
    render: render,
    bind: bind,
    LAB_LIST: LAB_LIST
  };
})();
