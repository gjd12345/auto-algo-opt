/* Curated Academic Exhibition Hall + Presentation Mode SPA Coordinator (Zero Internal Jargon). */
(function () {
  "use strict";

  const BREAKTHROUGHS = [
    {
      num: "核心突破 01",
      metric: "430 / 430 双预算全通",
      title: "多尺度几何–规模联合探针与跨尺度零溃败",
      desc: "针对小规模代理评估遮蔽超大规模退化的问题，引入高需求波动、高偏心率、强聚类联合压力探针与预算感知早退机制，在 500 ms 与 2000 ms 严格截止下实现 430 题零超时完赛。",
      actionLabel: "进入复杂度逃逸微实验",
      nav: { page: "microlabs", lab: "scale_escape" },
      kbId: "evidence-m6-wave2-c2-multiscale-430-20261127"
    },
    {
      num: "核心突破 02",
      metric: "54.0% → 93.1%",
      title: "容量紧度阻塞界与车队感知硬契约",
      desc: "从容量利用率 ρ 与不可分需求分拆特性出发，证明整路合并阻塞边界；引入路径数罚项与最轻路线强制拆解重插后，官方基准精确车队合规率实现近 40 个百分点的跃升。",
      actionLabel: "体验紧度阻塞微实验",
      nav: { page: "microlabs", lab: "fleet_tightness" },
      kbId: "evidence-m6-wave3-c1-exact-k-contract-20261127"
    },
    {
      num: "核心突破 03",
      metric: "路径缩短 7.97%",
      title: "仓库出发步径向相变与反事实归因",
      desc: "通过单步决策反事实替换证实：仅逆转每条路径出发第一步从近邻转向远端（α > 1 相变），后续所有构造与改进规则不变，即可在 200 节点规模达到 40 胜 0 负。",
      actionLabel: "调节 α 观测相变点",
      nav: { page: "microlabs", lab: "depot_phase" },
      kbId: "evidence-cvrp-depot-start-phase-h003"
    },
    {
      num: "核心突破 04",
      metric: "Set X 零负迁移",
      title: "跨运行门控精炼记忆与防反馈污染",
      desc: "建立统一基准与归因硬核验，揭示单轮赢家在线写回会沿复用链逐轮放大偶然噪声；采用经跨尺度筛查冻结后的离线精炼知识只读注入，高难基准全数种子零负迁移。",
      actionLabel: "对比方差演化曲线",
      nav: { page: "microlabs", lab: "memory_variance" },
      kbId: "evidence-m6-wave4-b3-clean-memory-kb-20261127"
    },
    {
      num: "核心突破 05",
      metric: "平均节省 12.0% 请求",
      title: "停滞重启与风险上界自适应早停解耦",
      desc: "严格分离全局预算早停与局部盆地重启决策，通过条件预期改进上界刻画继续搜索的边际收益，在少耗 12.0% 搜索请求的约束下维持完整盲测质量帕累托前沿。",
      actionLabel: "查看对应实证档案",
      kbId: "evidence-m6-wave2-b1-decoupled-pareto-20261127"
    },
    {
      num: "核心突破 06",
      metric: "0 绕过 · 89.86% 有效",
      title: "严格截止双端点口径与零绕过数值沙箱",
      desc: "分离截止前获解与截止前合规返回双观测端点，消除未截断超时漏罚；强化无泄露数值沙箱提示与报错自修复，在 30 组受控消融中达成零绕过、全完赛交付。",
      actionLabel: "阅读统一评价框架",
      kbId: "theory-m6-waves1to4-unified-framework-20261127"
    }
  ];

  const THEOREMS = [
    {
      cls: "",
      tag: "定理一 · 评测边界与估算等价条件",
      title: "双端点截止不变量与零超时等价性",
      formula: "P<sub>i</sub><sup>m</sup> = R<sub>i</sub><sup>m</sup> L<sub>i</sub><sup>m</sup> + (1 &minus; R<sub>i</sub><sup>m</sup>) &middot; 2 Ref<sub>i</sub> &nbsp;(&forall;i: R<sub>i</sub><sup>m</sup>=1 &rArr; 全样本得分与双完赛配对完全等价)",
      desc: "统一时钟下契约合规返回指示变量不大于首次获解指示变量。一旦对照双方均达 100% 严格完赛，惩罚项归零，差异纯反映路径质量。"
    },
    {
      cls: "teal",
      tag: "定理二 · 车队契约与不可分阻塞界",
      title: "紧容量下整路合并阻塞与负荷离散下界",
      formula: "&Sigma;(<i>u</i><sub>j</sub> &minus; &rho;)<sup>2</sup> &ge; [<i>K</i> / (<i>K</i> &minus; 1)] &middot; (<i>m</i> &minus; &rho;)<sup>2</sup> &nbsp;&nbsp;|&nbsp;&nbsp; min<sub>a&lt;b</sub>(<i>l</i><sub>a</sub> + <i>l</i><sub>b</sub>) &gt; <i>Q</i>",
      desc: "总需求未超车队上限不代表整路合并可行。只要最轻两条路径之和突破载重上限，静态合并便必然多出冗余车辆，必须引入跨路重插与最轻路拆解。"
    },
    {
      cls: "terra",
      tag: "定理三 · 诊断门控保真与饱和效应",
      title: "满完赛条件下的诊断模态收益上界",
      formula: "|&Delta;<sub>rel</sub>| &le; &Sigma;<sub>i&isin;A</sub> (&epsilon;<sub>i</sub> &middot; L<sub>base,i</sub>) / &Sigma;<sub>i</sub> L<sub>base,i</sub>",
      desc: "当数值诊断工具杜绝零证据绕过且各对照臂均达自由车队满完赛时，不同辅助模态的成本差异被受影响算例集合上的微调幅值严格封顶。"
    },
    {
      cls: "amber",
      tag: "定理四 · 跨运行记忆信噪比临界准则",
      title: "赢家复用方差递归与离线冻结占优条件",
      formula: "&Phi;(<i>s</i> / &nu;) &le; (1 &minus; <i>p</i>)&#8467; / (<i>pg</i> + (1 &minus; <i>p</i>)&#8467;), &nbsp;&nbsp; V<sub>W</sub>(<i>t</i>) = &sigma;<sub>W</sub><sup>2</sup> &Sigma;<sub>j=0..t&minus;1</sub> <i>a</i><sup>2j</sup>",
      desc: "开发期单轮偶然获胜策略若直接写回并逐轮复用，噪声方差按级数递增并击穿信噪比门槛；经跨尺度门控筛查后冻结的离线精炼策略则避免负迁移。"
    }
  ];

  const SLIDES = [
    {
      kicker: "01 / 08 · 研究全景",
      title: "面向组合优化启发式自动设计的机理知识体系",
      body: "我们将分散在多问题族、百余篇经典文献与大量严格受控实验中的规律，凝练为一套“问题结构 — 算法接口 — 数学定理 — 边界反例”严格绑定的结构化知识库，支撑高效、可解释且不随规模崩塌的求解器演化。",
      points: [
        { h: "四维严格隔离基准", p: "开发集、筛选集、独立盲测集与经典开源基准全链路隔离，单种子内配对统计检验，不混池夸大样本量。" },
        { h: "零黑话学术可复用结构", p: "365 条结构化知识沉淀与 132 篇核验文献双向交叉索引，统一绑定外层算法骨架与可进化决策接口。" }
      ]
    },
    {
      kicker: "02 / 08 · 评测基准规范化",
      title: "严格截止双端点与无竞争单核计时审计",
      body: "针对既往实证中偶发的超时未截断漏罚与并发墙钟抖动，建立以“首次可行”与“契约合规返回”分离为核心的评测公理，并在单核无竞争环境下重测全部 430 道核心算例。",
      points: [
        { h: "修正超时漏罚与交互解耦", p: "精确捕捉阈值边界处的微秒级超限，明确区分搜索阶段时限与最终评测时限对交付得分的非线性交互影响。" },
        { h: "定位大规模超时瓶颈", p: "单核剖面发现千点级复杂算例仅局部邻域精修即可消耗 751.17 ms，直接催生后续的复杂度剪枝方案。" }
      ]
    },
    {
      kicker: "03 / 08 · 跨尺度联合突破",
      title: "几何–规模联合压力探针实现 430/430 全通",
      body: "仅依据小规模或单维边际指标筛选演化算子，容易掩盖非均匀需求分布与二次复杂度分支的逃逸风险。引入联合探针与时间感知早退后，在 500 ms 与 2000 ms 双预算下全部通关。",
      points: [
        { h: "500 ms 严格截止零超时", p: "高难度百题基准完赛率由 98/100 提升至 100/100，430 题全景评测实现全通过并统计显著优于对照基线。" },
        { h: "反例驱动边界护栏", p: "构造“边际分布完全一致而联合支撑不交导致质量反转”的数学反例，从原理上锁死片面代理评估漏洞。" }
      ]
    },
    {
      kicker: "04 / 08 · 车队硬约束突破",
      title: "容量紧度阻塞理论与指定车队精确求解",
      body: "自由车队模式下达到 100% 完赛后，指定固定车辆数 K 仍是独立的可行性门槛。揭示整路合并阻塞界并设计车队感知契约，显著打通紧容量与极紧容量瓶颈。",
      points: [
        { h: "174 题官方基准合规率跃升", p: "精确车队合规数量从 94/174（54.0%）大幅提高至 162/174（93.1%），430 题多尺度全集稳定在 417–419 题。" },
        { h: "紧度与最大需求双重预警", p: "在紧度高于 0.98 区间，当最大单客需求占比超过 0.20 时，无契约方法超车风险高达 83.1%（49/59）。" }
      ]
    },
    {
      kicker: "05 / 08 · 空间动力学机理",
      title: "仓库出发步径向相变：从近邻诱惑到远端破局",
      body: "通过冻结全部后续改进算子、仅替换第一步仓库出发排序的反事实实验，证明看似微小的局部径向参数符号翻转（α < 1 转向 α > 1）会触发全局路线结构的宏观相变。",
      points: [
        { h: "整体路径缩短 7.97%", p: "独立盲测 120 题达到 94 胜 0 平 26 负，在 200 客户规模子集实现 40 胜 0 负的碾压式改善。" },
        { h: "消除标度敏感崩溃陷阱", p: "同步识别绝对带宽门控在坐标缩尺下导致的性能坍塌机制，强制所有距离与弧长评分无量纲归一化。" }
      ]
    },
    {
      kicker: "06 / 08 · 搜索过程自适应控制",
      title: "局部盆地重启与风险上界自适应早停解耦",
      body: "将跳出局部最优的停滞重启策略与终止全局搜索的早停判据彻底解耦，基于未来预期改进的条件风险上界动态决策停止时机。",
      points: [
        { h: "搜索效率帕累托前沿", p: "三颗随机种子实际消耗 [93, 94, 77] 次请求，在平均节省 12.0% 交互预算下保持盲测质量优势。" },
        { h: "策略延续性重标定准则", p: "严格界定重启改变了后续搜索分布，因而停止风险上界必须随延续策略动态重标定。" }
      ]
    },
    {
      kicker: "07 / 08 · 闭环消融与跨运行迁移",
      title: "零绕过数值沙箱与离线门控精炼防负迁移",
      body: "堵住跳过定量证据的流程旁路并强化脚本自修复，验证诊断有效率提升至 89.86%（试点达 100%）；在统一基准与归因零报警下，对比四种跨运行记忆策略。",
      points: [
        { h: "高难度 Set X 零负迁移", p: "离线跨尺度门控精炼只读策略在全部 3 颗种子均跑赢基线（均值 65,965.24 vs 66,094.83），终极盲测两颗种子显著占优。" },
        { h: "揭示单轮赢家反馈放大效应", p: "严密推导出噪声按级数累计导致信噪比击穿的解析阈值，彻底厘清了此前在线写回策略波动与回退的根源。" }
      ]
    },
    {
      kicker: "08 / 08 · 知识库全景汇总",
      title: "理论自洽、实证洁净的离线可复用知识资产",
      body: "全部实验产物与数学推导均经过独立数值验证脚本逐行复核，打包为不可变离线知识发布版，支持一键生成学术展馆以供答辩评阅、新课题迁移与持续演进。",
      points: [
        { h: "一键复用于未来版本", p: "通过标准命令行工具可由任意经校验的知识发布包直接构建交互式展馆，断网环境下双击即可完整演示。" },
        { h: "下一步自由探索", p: "您可以切换至「交互微实验」亲自调节数学参数，或在「知识图谱与百科」下钻阅读全部 365 条知识详情。" }
      ]
    }
  ];

  function renderHome(data, R) {
    const counts = data.counts || {};
    const hero = '<section class="hero-card">' +
      '  <div class="hero-kicker">学术研究知识展馆 · 结构化机理与实证白皮书</div>' +
      '  <h1 class="hero-title">组合优化自适应进化算法知识体系与核心理论突破</h1>' +
      '  <p class="hero-lead">本展馆汇集了带容量车辆路径、旅行商、在线装箱与背包等经典组合优化问题上的构造机理、跨尺度泛化约束、严格时限评测公理与数理反例证明。全部结论均在独立盲测集与单种子配对统计框架下核验通过，可直接用于学术汇报与工程接口检索。</p>' +
      '  <div class="hero-actions">' +
      '    <button type="button" class="btn primary" data-go-page="microlabs">进入 4 大交互微实验 &rarr;</button>' +
      '    <button type="button" class="btn" data-go-page="graph">探索知识图谱与 365 条百科</button>' +
      '    <button type="button" class="btn" id="hero-present-btn">开启大屏答辩演示模式</button>' +
      "  </div>" +
      '  <div class="kpi-strip">' +
      '    <div class="kpi-item"><div class="kpi-value">' + R.esc(counts.entries || 365) + '</div><div class="kpi-label">结构化知识条目</div><div class="kpi-note">涵盖问题、方法、实现、理论与实证</div></div>' +
      '    <div class="kpi-item"><div class="kpi-value teal">' + R.esc(counts.sources || 132) + '</div><div class="kpi-label">交叉核验文献来源</div><div class="kpi-note">核心顶刊论文与受控实验档案</div></div>' +
      '    <div class="kpi-item"><div class="kpi-value teal">430 / 430</div><div class="kpi-label">跨尺度全集严格完赛</div><div class="kpi-note">500 ms 与 2000 ms 双预算零超时</div></div>' +
      '    <div class="kpi-item"><div class="kpi-value terra">93.1%</div><div class="kpi-label">官方基准精确车队合规</div><div class="kpi-note">指定车辆数约束由 54.0% 大幅跃升</div></div>' +
      "  </div>" +
      "</section>";

    const btCards = '<div class="section-head"><div>' +
      '<div class="section-eyebrow">CURATED BREAKTHROUGHS</div>' +
      '<h2 class="section-title">六大核心研究突破</h2>' +
      '<p class="section-sub">点击卡片可直接进入对应交互微实验，或展开完整实证卡片与支撑数据。</p>' +
      "</div></div>" +
      '<div class="breakthrough-grid">' +
      BREAKTHROUGHS.map(function (b) {
        return '<div class="bt-card" ' + (b.nav ? ('data-jump-lab="' + b.nav.lab + '"') : ('data-open-entry="' + R.esc(b.kbId) + '"')) + ">" +
          '  <div>' +
          '    <div class="bt-top"><span class="bt-num">' + R.esc(b.num) + '</span><span class="bt-metric">' + R.esc(b.metric) + "</span></div>" +
          '    <h3 class="bt-title">' + R.esc(b.title) + "</h3>" +
          '    <p class="bt-desc">' + R.esc(b.desc) + "</p>" +
          "  </div>" +
          '  <div class="bt-foot"><span>' + R.esc(b.actionLabel) + " &rarr;</span>" +
          (b.kbId ? ('<span data-open-entry="' + R.esc(b.kbId) + '" style="color:var(--ink-muted);font-weight:400;text-decoration:underline;">实证档案</span>') : "") +
          "</div>" +
          "</div>";
      }).join("") +
      "</div>";

    const thCards = '<div class="section-head"><div>' +
      '<div class="section-eyebrow">UNIFIED THEORETICAL FRAMEWORK</div>' +
      '<h2 class="section-title">四大统一数学定理与边界条件</h2>' +
      '<p class="section-sub">从评测可观测性、不可分容量组合界到跨运行反馈噪声传播，所有公式均通过独立数值脚本符号验证。</p>' +
      '</div><button type="button" class="btn sm" data-open-entry="theory-m6-waves1to4-unified-framework-20261127">阅读完整理论与反例证明 &rarr;</button></div>' +
      '<div class="theorem-grid">' +
      THEOREMS.map(function (t) {
        return '<div class="theorem-card ' + t.cls + '">' +
          '  <div class="theorem-tag">' + R.esc(t.tag) + "</div>" +
          '  <h3 class="theorem-title">' + R.esc(t.title) + "</h3>" +
          '  <div class="formula-pill">' + t.formula + "</div>" +
          '  <p style="font-size:13.5px;color:var(--ink-sec);margin:0;">' + R.esc(t.desc) + "</p>" +
          "</div>";
      }).join("") +
      "</div>";

    return hero + btCards + thCards;
  }

  function renderPresentation(slideIdx, R) {
    const idx = Math.max(0, Math.min(SLIDES.length - 1, slideIdx));
    const s = SLIDES[idx];
    const dots = SLIDES.map(function (_, i) {
      return '<button type="button" class="slide-dot ' + (i === idx ? "active" : "") + '" data-slide-dot="' + i + '" aria-label="第 ' + (i + 1) + ' 页"></button>';
    }).join("");

    return '<div class="present-bar">' +
      '  <div class="serif" style="font-weight:700;font-size:16px;">学术答辩演示模式 · 组合优化知识体系总览</div>' +
      '  <button type="button" class="btn sm" id="present-exit-btn">退出演示模式 (Esc)</button>' +
      "</div>" +
      '<div class="present-stage"><div class="slide-card">' +
      '  <div class="slide-kicker">' + R.esc(s.kicker) + "</div>" +
      '  <h1 class="slide-title">' + R.esc(s.title) + "</h1>" +
      '  <p class="slide-body">' + R.esc(s.body) + "</p>" +
      '  <div class="slide-points">' +
         s.points.map(function (pt) {
           return '<div class="slide-point"><h4>' + R.esc(pt.h) + '</h4><div style="font-size:14.5px;color:var(--ink-sec);">' + R.esc(pt.p) + "</div></div>";
         }).join("") +
      "  </div>" +
      "</div></div>" +
      '<div class="present-foot">' +
      '  <button type="button" class="btn" id="slide-prev-btn"' + (idx === 0 ? " disabled" : "") + ">&larr; 上一页</button>" +
      '  <div class="slide-dots">' + dots + "</div>" +
      '  <button type="button" class="btn primary" id="slide-next-btn">' + (idx === SLIDES.length - 1 ? "完成并回到展厅" : "下一页 &rarr;") + "</button>" +
      "</div>";
  }

  function init() {
    const data = window.__KB_PORTAL_DATA__;
    const R = window.KB_RENDERERS;
    const M = window.KB_MICROLABS;
    const G = window.KB_GRAPH_VIEW;
    const appRoot = document.getElementById("portal-app");
    if (!data || !R || !M || !G) {
      appRoot.innerHTML = '<div style="padding:40px;text-align:center;">未加载到完整离线知识库数据包 <code>portal_data.js</code>，请确认使用完整生成目录打开。</div>';
      return;
    }

    let state = {
      page: "home",
      lab: "depot_phase",
      labAlpha: 1.15,
      labRho: 0.96,
      labDmax: 0.22,
      labScaleN: 500,
      labAmp: 1.25,
      labNu: 0.80,
      kbFam: "",
      kbType: "",
      kbQuery: "",
      kbSubTab: "cards",
      kbLimit: 45,
      drawerId: "",
      drawerHistory: [],
      present: false,
      slideIdx: 0
    };

    function openEntry(entryId) {
      if (!entryId) return;
      const hist = state.drawerHistory.slice();
      if (hist[hist.length - 1] !== entryId) hist.push(entryId);
      state.drawerId = entryId;
      state.drawerHistory = hist;
      renderDrawerOnly();
    }

    function renderDrawerOnly() {
      const backdrop = document.getElementById("drawer-backdrop");
      const panel = document.getElementById("drawer-panel");
      if (!state.drawerId) {
        backdrop.classList.add("hidden");
        panel.innerHTML = "";
        return;
      }
      backdrop.classList.remove("hidden");
      panel.innerHTML = G.renderDrawer(data, state.drawerId, state.drawerHistory, R);
      const closeBtn = panel.querySelector("#drawer-close-btn");
      if (closeBtn) closeBtn.addEventListener("click", function () {
        state.drawerId = ""; state.drawerHistory = []; renderDrawerOnly();
      });
      const backBtn = panel.querySelector("#drawer-back-btn");
      if (backBtn) backBtn.addEventListener("click", function () {
        const hist = state.drawerHistory.slice(0, -1);
        state.drawerHistory = hist;
        state.drawerId = hist[hist.length - 1] || "";
        renderDrawerOnly();
      });
      panel.querySelectorAll("[data-open-entry]").forEach(function (el) {
        el.addEventListener("click", function (ev) {
          ev.stopPropagation();
          openEntry(el.getAttribute("data-open-entry"));
        });
      });
    }

    function renderPresentationOnly() {
      const overlay = document.getElementById("present-overlay");
      if (!state.present) {
        overlay.classList.add("hidden");
        overlay.innerHTML = "";
        return;
      }
      overlay.classList.remove("hidden");
      overlay.innerHTML = renderPresentation(state.slideIdx, R);
      const exitBtn = overlay.querySelector("#present-exit-btn");
      if (exitBtn) exitBtn.addEventListener("click", function () { setState({ present: false }); });
      const prevBtn = overlay.querySelector("#slide-prev-btn");
      if (prevBtn) prevBtn.addEventListener("click", function () { setState({ slideIdx: Math.max(0, state.slideIdx - 1) }); });
      const nextBtn = overlay.querySelector("#slide-next-btn");
      if (nextBtn) nextBtn.addEventListener("click", function () {
        if (state.slideIdx >= SLIDES.length - 1) setState({ present: false, slideIdx: 0 });
        else setState({ slideIdx: state.slideIdx + 1 });
      });
      overlay.querySelectorAll("[data-slide-dot]").forEach(function (d) {
        d.addEventListener("click", function () { setState({ slideIdx: Number(d.getAttribute("data-slide-dot")) }); });
      });
    }

    function setState(patch, keepScroll, postHook) {
      const y = keepScroll ? window.scrollY : null;
      Object.assign(state, patch);
      render();
      if (y !== null) window.scrollTo(0, y);
      else if (patch.page) window.scrollTo(0, 0);
      if (postHook) postHook(appRoot);
    }

    function render() {
      const navHtml = [
        { id: "home", label: "学术展厅" },
        { id: "microlabs", label: "交互微实验" },
        { id: "graph", label: "知识图谱与百科" }
      ].map(function (n) {
        return '<button type="button" class="nav-pill ' + (state.page === n.id ? "active" : "") + '" data-nav-page="' + n.id + '">' + R.esc(n.label) + "</button>";
      }).join("");

      const headerHtml = '<header class="portal-header"><div class="header-inner">' +
        '  <div class="brand" data-nav-page="home">' +
        '    <div class="brand-mark"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 21 7 21 17 12 22 3 17 3 7"/><circle cx="12" cy="12" r="2.5" fill="currentColor"/></svg></div>' +
        '    <div><span class="brand-title">组合优化学术知识展馆</span><span class="brand-sub">结构化机理 · 交互微实验 · 实证文献图谱</span></div>' +
        "  </div>" +
        '  <nav class="nav-pills">' + navHtml + "</nav>" +
        '  <div class="header-actions">' +
        '    <button type="button" class="btn primary sm" id="top-present-btn">答辩演示模式</button>' +
        "  </div>" +
        "</div></header>";

      let mainHtml = "";
      if (state.page === "home") mainHtml = renderHome(data, R);
      else if (state.page === "microlabs") mainHtml = M.render(data, state, R);
      else mainHtml = G.render(data, state, R);

      appRoot.innerHTML = headerHtml + '<main class="portal-main">' + mainHtml + "</main>";

      appRoot.querySelectorAll("[data-nav-page]").forEach(function (el) {
        el.addEventListener("click", function () {
          setState({ page: el.getAttribute("data-nav-page") });
        });
      });
      appRoot.querySelectorAll("[data-go-page]").forEach(function (el) {
        el.addEventListener("click", function () {
          setState({ page: el.getAttribute("data-go-page") });
        });
      });
      appRoot.querySelectorAll("[data-jump-lab]").forEach(function (el) {
        el.addEventListener("click", function () {
          setState({ page: "microlabs", lab: el.getAttribute("data-jump-lab") });
        });
      });
      appRoot.querySelectorAll("[data-open-entry]").forEach(function (el) {
        el.addEventListener("click", function (ev) {
          ev.stopPropagation();
          openEntry(el.getAttribute("data-open-entry"));
        });
      });

      const pBtn = appRoot.querySelector("#top-present-btn");
      if (pBtn) pBtn.addEventListener("click", function () { setState({ present: true }); });
      const hpBtn = appRoot.querySelector("#hero-present-btn");
      if (hpBtn) hpBtn.addEventListener("click", function () { setState({ present: true }); });

      if (state.page === "microlabs") M.bind(appRoot, data, state, setState, R);
      else if (state.page === "graph") G.bind(appRoot, data, state, setState, R);

      renderDrawerOnly();
      renderPresentationOnly();
    }

    document.getElementById("drawer-backdrop").addEventListener("click", function (ev) {
      if (ev.target && ev.target.id === "drawer-backdrop") {
        state.drawerId = ""; state.drawerHistory = []; renderDrawerOnly();
      }
    });

    window.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") {
        if (state.present) { setState({ present: false }); return; }
        if (state.drawerId) { state.drawerId = ""; state.drawerHistory = []; renderDrawerOnly(); }
      } else if (state.present && ev.key === "ArrowRight") {
        setState({ slideIdx: Math.min(SLIDES.length - 1, state.slideIdx + 1) });
      } else if (state.present && ev.key === "ArrowLeft") {
        setState({ slideIdx: Math.max(0, state.slideIdx - 1) });
      }
    });

    render();
  }

  window.KB_PORTAL_APP = { init: init, BREAKTHROUGHS: BREAKTHROUGHS, SLIDES: SLIDES };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
