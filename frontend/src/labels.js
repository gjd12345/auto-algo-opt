/* Single-source label formatters, glossary tooltips, and dynamic metrics extractors. */
(function () {
  "use strict";

  const PALETTE = [
    "#165dff",
    "#0f766e",
    "#c2410c",
    "#475569",
    "#0284c7",
    "#7c3aed",
    "#b45309",
    "#0369a1"
  ];

  const FAMILY_LABELS = {
    cvrp: { short: "CVRP", name: "容量约束车辆路径问题 (CVRP)" },
    tsp: { short: "TSP", name: "旅行商问题 (TSP)" },
    obp: { short: "OBP", name: "在线一维装箱问题 (OBP)" }
  };

  const PARADIGM_LABELS = {
    sequential_construct: "顺序步进构造",
    parallel_merge: "并行路径合并",
    insertion: "全局最小代价插入",
    cluster_first: "先聚类后路径 (Sweep)",
    local_search: "合并 + 局部搜索",
    complementary_constructive_set: "互补构造集合 (CPI)",
    llm_ahd_framework: "LLM-AHD 框架",
    metaheuristic: "元启发式",
    neural_attention_reshaping: "NCO 注意力重塑",
    neural_local_search: "神经局部搜索",
    math_mechanism: "数学机理分析",
    selector_portfolio: "算法选择组合",
    ruin_recreate: "破坏修复 (LNS)",
    ruin_and_recreate: "破坏修复 (LNS)"
  };

  const TIER_LABELS = {
    verified_experiment: "本机实证结果",
    literature_abstract: "论文原表参照",
    local_implementation: "算法实现组件",
    math_observation: "数学机理解析",
    failure_antipattern: "边界反例与约束"
  };

  const SUITE_ROLE_LABELS = {
    external_top_venue: "文献同协议对照",
    external_or_standard: "OR 标准测试库",
    dev_search: "开发诊断集",
    selection_tuning: "算法选择训练集",
    historical_regression: "历史对照集",
    final_acceptance: "独立冻结验证集"
  };

  const EXPOSURE_LABELS = {
    external_public: "公开外部基准",
    public_standard: "公开标准基准",
    fresh_isolated: "独立隔离测试集",
    historically_exposed: "已开发回归集"
  };

  const SUITE_DISPLAY = {
    cvrp_ext_eohs_256: "EoH-S 多分布协议 (256 例)",
    cvrp_ext_reevo_scale: "ReEvo 跨规模合成集",
    cvrp_ext_cvrplib_abp_74: "CVRPLib Set A·B·P (74 例)",
    cvrp_ext_cvrplib_x_100: "Uchoa Set X (100 例)",
    tsp_ext_eohs_128: "EoH-S TSP 多分布 (128 例)",
    tsp_ext_tsplib_euc2d: "TSPLIB EUC_2D (18 例)",
    obp_ext_eoh_weibull: "Weibull 在线装箱 (173 例)",
    obp_ext_bpplib: "BPPLib 装箱标准库 (70 例)",
    cvrp_dev_hetero_24: "Dev-24 缩尺压力测试",
    cvrp_select_multiscale_64: "Selection Multiscale-64",
    cvrp_hist_p0_120: "P0 多规模盲测 (120 例)",
    cvrp_hist_hetero_288: "Hetero-288 多工况回归",
    cvrp_final_accept_120: "Final-Accept-120 独立验证",
    cvrp_m2_blind_120: "M2 启封盲测 (120 例)",
    cvrp_m3_blind_120: "M3 启封盲测 (120 例)",
    shared_diagnostic_6: "Shared-6 轨迹诊断集"
  };

  const ALG_DISPLAY = {
    nn: "最近邻构造 NN",
    savings_pointwise: "逐点节约 Savings",
    s2_r5_spiral: "R5 螺旋构造",
    s2_r7_iso: "R7 状态隔离规则",
    s2_ctrl_best: "黑盒对照组",
    s2_r3_rho: "R3 过拟合对照",
    v0: "P0 基线 V0",
    c: "Frozen C 规则",
    a: "早返原型 A",
    b: "探索变体 B",
    dd_load: "需求距离均衡",
    radial: "纯径向参考",
    cw_parallel_merge: "CW 并行合并",
    cw_2opt: "CW + 2-opt",
    cw_relocate_2opt: "CW + 局部搜索",
    eohs_cvrp_f1: "EoH-S 单规则 F1",
    eohs_cvrp_set10_cpi: "EoH-S 规则集 (CPI)",
    eoh_cvrp_f1: "EoH 单规则",
    heuragenix_min_cost_ins: "HeurAgenix 插入",
    s2_r4_cos: "R4 余弦角互补规则",
    cvrp_sweep_2opt: "真坐标极角扫描 + 2-opt",
    cvrp_farthest_insertion: "经典最远插入",
    i605_cvrp_c1_tworegime: "岛屿 C1 · 两段切换+早返",
    i605_cvrp_c8_radial_early: "岛屿 C8 · 径向偏置+早返",
    i605_cvrp_c17_phase_noreturn: "岛屿 C17 · 纯中程切换",
    i605_cvrp_c22_band_savings: "岛屿 C22 · 相对带节约",
    tsp_nn: "TSP 最近邻",
    tsp_farthest_insertion: "TSP 最远插入",
    tsp_nn_2opt: "TSP NN + 2-opt",
    eohs_tsp_f1: "EoH-S TSP 规则",
    eoh_tsp_f1: "EoH TSP 规则",
    i605_tsp_t1_rollout: "岛屿 T1 · 一步前瞻 Rollout",
    i605_tsp_t46_farness: "岛屿 T46 · 平均孤立度",
    i605_tsp_t69_dest_regret: "岛屿 T69 · 极速终点引力",
    i605_tsp_t81_norm_smooth: "岛屿 T81 · 无量纲平滑度",
    obp_first_fit: "First-Fit",
    obp_best_fit: "Best-Fit",
    eohs_obp_f1: "EoH-S 装箱规则",
    eoh_obp_f1: "EoH 装箱规则",
    funsearch_obp_f1: "FunSearch 装箱规则",
    reevo_obp_f1: "ReEvo 装箱规则",
    i605_obp_b1_exp_deadzone: "岛屿 B1 · 指数+死区惩罚",
    i605_obp_b50_sqrt_tier: "岛屿 B50 · 85%封箱阶跃",
    i605_obp_b16_log_half: "岛屿 B16 · 半满对数+冲顶",
    i605_obp_b117_hardcap_anti: "岛屿 B117 · 硬编码C=100反例"
  };

  const JARGON_GLOSS = {
    CPI: "Complementary Performance Index：规模为 K 的启发式集合在逐例取最优后再平均的事后指标，不同于单规则单次求解。",
    N_common: "共同完成交集：全部参与对比的算法都在 500 ms 预算内完成求解的算例交集，用于消除超时算法导致的样本偏差。",
    L1: "装箱理论下界：ceil(sum(item_sizes) / C)。",
    BKS: "Best Known Solution / OPT：标准库经核验的全局最优或已知最优整数解。",
    SBS: "Single Best Solver：在测试集上固定选用表现最好的单一算法。",
    VBS: "Virtual Best Solver (Oracle)：在每个算例上事后选取最优算法所对应的理论上界。",
    euc_2d_nint: "TSPLIB / CVRPLib 标准整数欧氏距离公约：floor(sqrt(dx^2 + dy^2) + 0.5)。",
    OOD: "Out-of-Distribution：训练分布之外的新规模或新空间集群工况。"
  };

  const POLICY_LABELS = {
    unconstrained: "自由车数 (仅容量可行)",
    min_vehicles_advisory: "参考车数 k (不强制上限)",
    free_fleet_min_k_lb: "自由车数 (k 为最小车数下界)",
    fixed_k_unconstrained_eval: "官方 BKS 为固定 k (当前自由车数对比 + ==k 合规统计)",
    strict_max_vehicles: "严格车数上限 (<=k)",
    not_applicable: "不适用"
  };

  function esc(val) {
    if (val === null || val === undefined) return "";
    return String(val)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fmtPct(ratio, digits) {
    if (ratio === null || ratio === undefined || !Number.isFinite(Number(ratio))) return "—";
    const d = digits === undefined ? 2 : digits;
    const pct = Number(ratio) * 100;
    return (pct > 0 ? "+" : "") + pct.toFixed(d) + "%";
  }

  function fmtRatioAsPctPlain(ratio, digits) {
    if (ratio === null || ratio === undefined || !Number.isFinite(Number(ratio))) return "—";
    return (Number(ratio) * 100).toFixed(digits === undefined ? 2 : digits) + "%";
  }

  function fmtValPct(pctVal, digits) {
    if (pctVal === null || pctVal === undefined || !Number.isFinite(Number(pctVal))) return "—";
    return Number(pctVal).toFixed(digits === undefined ? 2 : digits) + "%";
  }

  function fmtNum(val, digits) {
    if (val === null || val === undefined || !Number.isFinite(Number(val))) return "—";
    return Number(val).toFixed(digits === undefined ? 4 : digits);
  }

  function fmtObj(val) {
    if (val === null || val === undefined || !Number.isFinite(Number(val))) return "—";
    const n = Number(val);
    return Math.abs(n - Math.round(n)) < 1e-6 ? Math.round(n).toLocaleString("en-US") : n.toFixed(4);
  }

  function fmtMs(val) {
    if (val === null || val === undefined || !Number.isFinite(Number(val))) return "—";
    const n = Number(val);
    return n >= 100 ? n.toFixed(1) + " ms" : n.toFixed(2) + " ms";
  }

  function suiteTitle(suiteOrId) {
    const sid = typeof suiteOrId === "string" ? suiteOrId : (suiteOrId && suiteOrId.suite_id) || "";
    return SUITE_DISPLAY[sid] || (suiteOrId && suiteOrId.metadata && suiteOrId.metadata.title) || sid;
  }

  function algTitle(core, algId) {
    const a = getAlg(core, algId);
    return ALG_DISPLAY[algId] || (a && a.display_name) || algId;
  }

  function getSuite(core, suiteId) {
    return (core && core.suites || []).find((s) => s.suite_id === suiteId) || null;
  }

  function getAlg(core, algId) {
    return (core && core.algorithms || []).find((a) => a.algorithm_id === algId) || null;
  }

  function kbMap(core) {
    const m = {};
    (core && core.kb_entries || []).forEach((e) => { if (e && e.id) m[e.id] = e; });
    return m;
  }

  function resolveAlgKbId(core, algId) {
    const a = getAlg(core, algId);
    const map = kbMap(core);
    return (a && a.kb_entry_id && map[a.kb_entry_id]) ? a.kb_entry_id : "";
  }

  function getAlgMechanism(core, algId) {
    const kbId = resolveAlgKbId(core, algId);
    const entry = kbId ? kbMap(core)[kbId] : null;
    if (entry && entry.attributes && entry.attributes.interface_blueprint && entry.attributes.interface_blueprint.skeleton_role) {
      return entry.attributes.interface_blueprint.skeleton_role;
    }
    if (entry && entry.summary) return entry.summary;
    const a = getAlg(core, algId);
    return (a && a.description) || "—";
  }

  function jargon(key, label) {
    return '<span class="jargon-tip" title="' + esc(JARGON_GLOSS[key] || "") + '">' + esc(label || key) + "</span>";
  }

  function getSuiteSummary(core, suiteId) {
    return (core && core.summary && core.summary.suites && core.summary.suites[suiteId]) || null;
  }

  function hasPartialCompletion(suiteSum) {
    return Boolean(
      suiteSum &&
      suiteSum.common_completed_count &&
      suiteSum.n_instances &&
      suiteSum.common_completed_count < suiteSum.n_instances
    );
  }

  function resolveScope(suiteSum, requestedScope) {
    if (requestedScope === "overall") return "overall";
    if (requestedScope === "common_completed") {
      return (suiteSum && suiteSum.common_completed_count) ? "common_completed" : "overall";
    }
    return hasPartialCompletion(suiteSum) ? "common_completed" : "overall";
  }

  function getAlgStats(suiteSum, algId, scope) {
    if (!suiteSum || !suiteSum.algorithms || !suiteSum.algorithms[algId]) return null;
    const a = suiteSum.algorithms[algId];
    if (scope === "common_completed" && a.common_completed) return a.common_completed;
    if (scope === "strict_all_common_completed" && a.strict_all_common_completed) return a.strict_all_common_completed;
    return a.overall || null;
  }

  function computeHeroSnapshot(core) {
    const suites = (core && core.suites) || [];
    const kbEntries = (core && core.kb_entries) || [];
    const pub = (core && core.published_results) || {};
    const orGoldIds = ["cvrp_ext_cvrplib_abp_74", "cvrp_ext_cvrplib_x_100", "tsp_ext_tsplib_euc2d"];
    const orGoldInstances = suites
      .filter((s) => orGoldIds.includes(s.suite_id))
      .reduce((acc, s) => acc + Number(s.instance_count || 0), 0);

    const hp = (core && core.h003_preview) || null;
    const p0 = getSuiteSummary(core, "cvrp_hist_p0_120");
    const setX = getSuiteSummary(core, "cvrp_ext_cvrplib_x_100");
    const eohs256 = getSuiteSummary(core, "cvrp_ext_eohs_256");
    const fa120 = getSuiteSummary(core, "cvrp_final_accept_120");

    const analyses = (core && core.selection && core.selection.analyses) || {};
    const h288 = analyses.hetero_288__pointwise_plus_s2 || null;
    const faSel = analyses.final_accept_120__pointwise_plus_s2_frozen || null;
    const faProtoKey = faSel && faSel.protocols ? Object.keys(faSel.protocols)[0] : null;
    const stressRecs = (core && core.scale_stress && core.scale_stress.records) || [];

    function maxDrift(aid) {
      const rows = stressRecs.filter((r) => r.algorithm_id === aid && Number.isFinite(Number(r.scale_drift_pct)));
      return rows.length ? Math.max.apply(null, rows.map((r) => Math.abs(Number(r.scale_drift_pct)))) : null;
    }

    return {
      suiteCount: suites.length,
      algorithmCount: (core && core.algorithms || []).length,
      kbCount: kbEntries.length,
      sourcesCount: Number((core && core.sources_count) || 0),
      orGoldInstances: orGoldInstances,
      pubVerifiedCount: Number(pub.verified_count || 0),
      pubPendingCount: Number(pub.pending_count || 0),
      h003Summary: hp && hp.summary ? hp.summary : null,
      h003DepotOnly: hp && hp.depot_only ? hp.depot_only : null,
      r5P0: getAlgStats(p0, "s2_r5_spiral", "overall"),
      ctrlP0: getAlgStats(p0, "s2_ctrl_best", "overall"),
      nnP0: getAlgStats(p0, "nn", "overall"),
      setX: setX,
      xCommonN: setX ? Number(setX.common_completed_count || 0) : 0,
      r5XAll: getAlgStats(setX, "s2_r5_spiral", "overall"),
      r5XCommon: getAlgStats(setX, "s2_r5_spiral", "common_completed"),
      eohsF1XAll: getAlgStats(setX, "eohs_cvrp_f1", "overall"),
      eohsF1XCommon: getAlgStats(setX, "eohs_cvrp_f1", "common_completed"),
      cwRelXCommon: getAlgStats(setX, "cw_relocate_2opt", "common_completed"),
      cwRelXAll: getAlgStats(setX, "cw_relocate_2opt", "overall"),
      eohs256Cpi: getAlgStats(eohs256, "eohs_cvrp_set10_cpi", "overall"),
      cwRelFa: getAlgStats(fa120, "cw_relocate_2opt", "overall"),
      hxFa: getAlgStats(fa120, "heuragenix_min_cost_ins", "overall"),
      r5Fa: getAlgStats(fa120, "s2_r5_spiral", "overall"),
      h288: h288,
      h288Cv12: h288 && h288.protocols && h288.protocols.cv12 && h288.protocols.cv12.selectors ? h288.protocols.cv12.selectors.rf_reg : null,
      h288Loso3: h288 && h288.protocols && h288.protocols.loso3 && h288.protocols.loso3.selectors ? h288.protocols.loso3.selectors.rf_reg : null,
      faSel: faSel,
      faSelRf: (faProtoKey && faSel.protocols[faProtoKey].selectors) ? faSel.protocols[faProtoKey].selectors.rf_reg : null,
      driftC: maxDrift("c"),
      driftV0: maxDrift("v0"),
      driftR5: maxDrift("s2_r5_spiral")
    };
  }

  window.WB_LABELS = {
    PALETTE: PALETTE,
    FAMILY_LABELS: FAMILY_LABELS,
    PARADIGM_LABELS: PARADIGM_LABELS,
    TIER_LABELS: TIER_LABELS,
    SUITE_ROLE_LABELS: SUITE_ROLE_LABELS,
    EXPOSURE_LABELS: EXPOSURE_LABELS,
    POLICY_LABELS: POLICY_LABELS,
    esc: esc,
    fmtPct: fmtPct,
    fmtRatioAsPctPlain: fmtRatioAsPctPlain,
    fmtValPct: fmtValPct,
    fmtNum: fmtNum,
    fmtObj: fmtObj,
    fmtMs: fmtMs,
    suiteTitle: suiteTitle,
    algTitle: algTitle,
    getSuite: getSuite,
    getAlg: getAlg,
    kbMap: kbMap,
    resolveAlgKbId: resolveAlgKbId,
    getAlgMechanism: getAlgMechanism,
    jargon: jargon,
    getSuiteSummary: getSuiteSummary,
    hasPartialCompletion: hasPartialCompletion,
    resolveScope: resolveScope,
    getAlgStats: getAlgStats,
    computeHeroSnapshot: computeHeroSnapshot
  };
})();
