/* Main SPA Coordinator: Single-Row Topbar, Progressive View Routing, Offline Script Bundle Loader. */
(function () {
  "use strict";

  const PAGE_META = {
    overview: "总览",
    benchmarks: "基准对比",
    comparator: "路线对照",
    knowledge: "机理与知识库"
  };

  function parseHash() {
    const raw = (window.location.hash || "").replace(/^#/, "");
    const params = new URLSearchParams(raw);
    const rawPage = params.get("page") || "overview";
    const normPage = rawPage === "results" ? "benchmarks" : rawPage;
    return {
      page: PAGE_META[normPage] ? normPage : "overview",
      family: params.get("family") || "cvrp",
      suite: params.get("suite") || "",
      tab: params.get("tab") || "",
      scope: params.get("scope") || "",
      sortBy: params.get("sortBy") || "mean_rel_gap",
      sortDir: params.get("sortDir") || "asc",
      inst: params.get("inst") || "",
      algA: params.get("algA") || "",
      algB: params.get("algB") || "",
      preset: params.get("preset") || "",
      cmpFocus: params.get("cmpFocus") || "focus",
      showOpt: params.get("showOpt") === "1",
      stepIdx: params.get("stepIdx") !== null ? Number(params.get("stepIdx")) : -1,
      hlRoute: params.get("hlRoute") !== null ? Number(params.get("hlRoute")) : -1,
      story: params.get("story") || "h003",
      topic: params.get("topic") || "",
      entry: params.get("entry") || "",
      kbQuery: params.get("kbQuery") || "",
      kbFam: params.get("kbFam") || "",
      kbTier: params.get("kbTier") || "",
      kbMode: params.get("kbMode") || "",
      expandAll: params.get("expandAll") === "1",
      showAllPapers: params.get("showAllPapers") === "1",
      selAnalysis: params.get("selAnalysis") || "",
      selProto: params.get("selProto") || "",
      present: params.get("present") === "1",
      mlAlpha: params.get("mlAlpha") !== null ? Number(params.get("mlAlpha")) : 1.15,
      mlScale: params.get("mlScale") !== null ? Number(params.get("mlScale")) : 0.001,
      mlPress: params.get("mlPress") !== null ? Number(params.get("mlPress")) : 65
    };
  }

  function serializeHash(st) {
    const p = new URLSearchParams();
    p.set("page", st.page || "overview");
    if (st.family && st.family !== "cvrp") p.set("family", st.family);
    if (st.suite) p.set("suite", st.suite);
    if (st.tab) p.set("tab", st.tab);
    if (st.scope) p.set("scope", st.scope);
    if (st.sortBy && st.sortBy !== "mean_rel_gap") p.set("sortBy", st.sortBy);
    if (st.sortDir && st.sortDir !== "asc") p.set("sortDir", st.sortDir);
    if (st.inst) p.set("inst", st.inst);
    if (st.algA) p.set("algA", st.algA);
    if (st.algB) p.set("algB", st.algB);
    if (st.preset) p.set("preset", st.preset);
    if (st.cmpFocus && st.cmpFocus !== "focus") p.set("cmpFocus", st.cmpFocus);
    if (st.showOpt) p.set("showOpt", "1");
    if (st.stepIdx !== undefined && st.stepIdx >= 0) p.set("stepIdx", String(st.stepIdx));
    if (st.hlRoute !== undefined && st.hlRoute >= 0) p.set("hlRoute", String(st.hlRoute));
    if (st.story && st.story !== "h003") p.set("story", st.story);
    if (st.entry) p.set("entry", st.entry);
    if (st.kbQuery) p.set("kbQuery", st.kbQuery);
    if (st.kbFam) p.set("kbFam", st.kbFam);
    if (st.kbTier) p.set("kbTier", st.kbTier);
    if (st.kbMode) p.set("kbMode", st.kbMode);
    if (st.expandAll) p.set("expandAll", "1");
    if (st.showAllPapers) p.set("showAllPapers", "1");
    if (st.selAnalysis) p.set("selAnalysis", st.selAnalysis);
    if (st.selProto) p.set("selProto", st.selProto);
    if (st.present) p.set("present", "1");
    return "#" + p.toString();
  }

  let currentState = parseHash();
  const loadingBundles = {};

  function ensureSuiteBundle(suiteId, onReady) {
    window.__WB_SUITE_BUNDLES__ = window.__WB_SUITE_BUNDLES__ || {};
    if (!suiteId) { onReady(null); return; }
    if (window.__WB_SUITE_BUNDLES__[suiteId]) { onReady(window.__WB_SUITE_BUNDLES__[suiteId]); return; }
    if (loadingBundles[suiteId]) return;
    loadingBundles[suiteId] = true;
    const sc = document.createElement("script");
    sc.src = "./workbench_data/suite_" + encodeURIComponent(suiteId) + ".js";
    sc.onload = function () { loadingBundles[suiteId] = false; onReady(window.__WB_SUITE_BUNDLES__[suiteId] || null); };
    sc.onerror = function () { loadingBundles[suiteId] = false; onReady(null); };
    document.head.appendChild(sc);
  }

  function defaultSuiteForFamily(core, fam) {
    const preferred = { cvrp: "cvrp_ext_cvrplib_x_100", tsp: "tsp_ext_tsplib_euc2d", obp: "obp_ext_eoh_weibull" };
    if (preferred[fam] && window.WB_LABELS.getSuite(core, preferred[fam])) return preferred[fam];
    const match = (core.suites || []).find(function (s) { return s.problem_family === fam; });
    return (match && match.suite_id) || (core.suites[0] && core.suites[0].suite_id) || "";
  }

  function renderTopbar(core, state) {
    const L = window.WB_LABELS;
    const topEl = document.getElementById("app-topbar");
    const fam = state.family || "cvrp";
    const famBtns = ["cvrp", "tsp", "obp"].map(function (f) {
      return '<button type="button" class="' + (f === fam ? "active" : "") + '" data-family="' + f + '">' + L.esc(L.FAMILY_LABELS[f].short) + "</button>";
    }).join("");

    const navOrder = ["overview", "benchmarks", "comparator", "knowledge"];
    const navLinks = navOrder.map(function (p) {
      return '<button type="button" class="nav-link ' + (state.page === p ? "active" : "") + '" data-page="' + p + '">' + L.esc(PAGE_META[p]) + "</button>";
    }).join("");

    topEl.innerHTML = [
      '<div class="topbar-inner">',
      '  <div class="topbar-left">',
      '    <div class="brand">',
      '      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#165dff" stroke-width="1.9"><polygon points="12 2.5 20.5 7.5 20.5 16.5 12 21.5 3.5 16.5 3.5 7.5"/><circle cx="12" cy="12" r="2.2" fill="#165dff" stroke="none"/><line x1="12" y1="2.5" x2="12" y2="9.8"/><line x1="20.5" y1="16.5" x2="14" y2="13"/><line x1="3.5" y1="16.5" x2="10" y2="13"/></svg>',
      '      <span>OptBench · 组合优化研究工作台</span>',
      '    </div>',
      '    <div class="seg">' + famBtns + "</div>",
      "  </div>",
      '  <nav class="nav-tabs">' + navLinks + "</nav>",
      '  <div class="topbar-actions">',
      '    <span class="release-tag">' + L.esc(core.budget_ms) + " ms · " + L.esc(core.release_id || "") + "</span>",
      '    <button type="button" class="btn sm ' + (state.present ? "active" : "") + '" id="top-present-btn">' + (state.present ? "退出宽屏" : "宽屏") + "</button>",
      "  </div>",
      "</div>"
    ].join("\n");

    topEl.querySelectorAll("[data-family]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const nf = btn.getAttribute("data-family");
        navigate({ family: nf, suite: defaultSuiteForFamily(core, nf), inst: "", algA: "", algB: "", stepIdx: -1, hlRoute: -1 });
      });
    });
    topEl.querySelectorAll("[data-page]").forEach(function (btn) {
      btn.addEventListener("click", function () { navigate({ page: btn.getAttribute("data-page"), tab: "" }); });
    });
    const pBtn = topEl.querySelector("#top-present-btn");
    if (pBtn) pBtn.addEventListener("click", function () { navigate({ present: !state.present }); });
  }

  function bindGlobalNav(container) {
    container.querySelectorAll("[data-nav]").forEach(function (el) {
      if (el.__wbBoundNav) return;
      el.__wbBoundNav = true;
      el.addEventListener("click", function (ev) {
        ev.preventDefault();
        const p = new URLSearchParams(el.getAttribute("data-nav") || "");
        const patch = {};
        p.forEach(function (v, k) {
          if (v === "true") patch[k] = true;
          else if (v === "false") patch[k] = false;
          else patch[k] = v;
        });
        navigate(patch);
      });
    });
  }

  function renderApp() {
    const core = window.__WB_CORE__;
    const mainEl = document.getElementById("app-main");
    if (!core) {
      mainEl.innerHTML = '<div class="panel">未检测到 <code>workbench_data/core.js</code> 数据包。请确认通过完整打包输出目录打开。</div>';
      return;
    }

    if (!currentState.suite) currentState.suite = defaultSuiteForFamily(core, currentState.family);
    document.body.classList.toggle("presentation-mode", Boolean(currentState.present));

    renderTopbar(core, currentState);

    const page = currentState.page || "overview";
    const view = (window.WB_VIEWS && window.WB_VIEWS[page]) || window.WB_VIEWS.overview;
    const activeSuiteId = currentState.suite;
    const needsBundle = page === "benchmarks" || page === "comparator";

    if (needsBundle && activeSuiteId && !(window.__WB_SUITE_BUNDLES__ && window.__WB_SUITE_BUNDLES__[activeSuiteId])) {
      mainEl.innerHTML = view.render(core, currentState, null);
      bindGlobalNav(mainEl);
      if (view.bind) view.bind(mainEl, core, currentState, navigate, null);
      ensureSuiteBundle(activeSuiteId, function (bundle) {
        if (currentState.suite === activeSuiteId) {
          mainEl.innerHTML = view.render(core, currentState, bundle);
          bindGlobalNav(mainEl);
          if (view.bind) view.bind(mainEl, core, currentState, navigate, bundle);
        }
      });
      return;
    }

    const bundle = (window.__WB_SUITE_BUNDLES__ && activeSuiteId) ? window.__WB_SUITE_BUNDLES__[activeSuiteId] : null;
    mainEl.innerHTML = view.render(core, currentState, bundle);
    bindGlobalNav(mainEl);
    if (view.bind) view.bind(mainEl, core, currentState, navigate, bundle);
  }

  function navigate(patch, silentInPlace) {
    const cleanPatch = Object.assign({}, patch);
    if (cleanPatch.page === "results") cleanPatch.page = "benchmarks";
    if (cleanPatch.page && cleanPatch.page !== currentState.page) {
      if (cleanPatch.tab === undefined) cleanPatch.tab = "";
      if (cleanPatch.preset === undefined) cleanPatch.preset = "";
      if (cleanPatch.stepIdx === undefined) cleanPatch.stepIdx = -1;
      if (cleanPatch.hlRoute === undefined) cleanPatch.hlRoute = -1;
    }
    if (cleanPatch.suite && cleanPatch.suite !== currentState.suite && cleanPatch.inst === undefined) {
      cleanPatch.inst = "";
    }
    currentState = Object.assign({}, currentState, cleanPatch);
    if (!silentInPlace) {
      const nextHash = serializeHash(currentState);
      if (window.location.hash !== nextHash) window.history.replaceState(null, "", nextHash);
    }
    renderApp();
  }

  window.addEventListener("hashchange", function () { currentState = parseHash(); renderApp(); });
  document.addEventListener("DOMContentLoaded", renderApp);
  if (document.readyState !== "loading") renderApp();
})();
