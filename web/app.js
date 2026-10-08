// Travel-China Copilot — front-end controller.
// All HTTP is plain fetch; the UI is intentionally framework-free so Render
// serves it as static files without a build step.

const $ = (id) => document.getElementById(id);

const state = {
  imageDataUrl: "",
  samples: [],
  lastResult: null,
  lastVision: null,
  dialTimer: null,
};

// ---------------------------------------------------------------------------
// UI strings — the chrome of the app itself (not the model/rule output, which
// is translated server-side). Only English and 简体中文 are supported.
// ---------------------------------------------------------------------------
const UI_STRINGS = {
  en: {
    brandSub: "On-site copilot for inbound travellers",
    heroTitle: "Know exactly what to do next.",
    heroSub: "Snap the sign, the machine or the ticket. Get the next action — not another translation.",
    chipModel: "<b>Model</b> reads the scene",
    chipRules: "<b>Rules</b> decide the deadline",
    chipZh: "<b>中文</b> ready to show staff",

    step1: "1 · Trip context",
    step1Hint: "Rules compare what's on site with your itinerary.",
    step2: "2 · Show the site",
    step3: "3 · Built-in cases",
    step3Hint: "Tap to load — the cases a translation app can't solve.",

    lblCity: "City",
    lblStation: "Departure station (planned)",
    lblTrain: "Train number",
    lblBooked: "Booked with",
    lblCarry: "Carry in my hand",
    carryNote: "passport · chinese_id · visa · booking_qr · cash · card",
    optPassport: "Passport (foreign)",
    optChineseId: "Chinese ID",
    optOther: "Other",
    optUnknown: "Not sure",

    btnPhoto: "Take photo",
    noImage: "No image yet",
    questionPh: 'Optional — what are you asking?\ne.g. "This machine won\'t accept me, what now?"',

    emptyTitle: "Your next move, in your language",
    emptyBody: "Snap or load a scene, fill in your trip — and get the exact next step, the document you need, and the real deadline.",

    verdicts: "Verdicts from the rule engine",
    stepsTitle: "Steps — in this order",
    phrasesTitle: "Show this to staff in 中文",
    missingTitle: "Missing items",
    aiTitle: "AI answer note",
    visionTitle: "What's on site (model read)",
    badgeRule: "rule",
    badgeModel: "model",

    dialHint: "Slide to watch the rule engine react — no model call",
    dialAria: "Minutes until departure",
    btnReset: "Reset",
    footer: "钉子头 · Team entry — 入境游 AI 创新",

    // dynamic fragments
    lblDeparture: "Departure",
    lblGateCloses: "Gate closes",
    lblArriveBy: "Arrive by",
    lblScene: "Scene",
    lblVerdict: "Rule engine verdict",
    bufferNote: "buffer for security + ID check",
    trainGone: "Train has already left",
    gateClosed: "Gate already closed",
    noTimePressure: "no time pressure",
    noDepartureKnown: "No departure time known for this scene.",
    minsLeft: "in {n} min",
    tomorrow: "(tomorrow)",
    departIn: "{n} min to departure",
    departInShort: "{n} min — gate closes in {m}",
    departed: "{n} min — your train has left",

    sevCritical: "CRITICAL",
    sevWarn: "WARN",
    sevInfo: "INFO",
    sevOk: "OK",

    noFindingsTitle: "No rule blocked you.",
    noFindingsBody: "No critical procedure, document or time issue detected for this scene.",
    noPhrases: "No ready-to-show phrases for this scene.",
    whyPrefix: "Why a normal translation app can't help here:",
    sceneModel: "Scene (model)",
    translationNote: "translation: {v}",
    degradedNote: "stage-1 model unavailable, scene from hint",
  },

  zh: {
    brandSub: "入境游客现场操作指引",
    heroTitle: "下一步该做什么，说清楚。",
    heroSub: "拍下指示牌、自助机或车票。得到可以直接执行的下一步——而不是又一段翻译。",
    chipModel: "<b>模型</b>看懂现场",
    chipRules: "<b>规则</b>判定截止时间",
    chipZh: "<b>中文</b>直接给工作人员看",

    step1: "1 · 行程信息",
    step1Hint: "规则会把现场情况和你的行程做比对。",
    step2: "2 · 拍下现场",
    step3: "3 · 内置案例",
    step3Hint: "点一下即可加载——翻译软件解决不了的场景。",

    lblCity: "城市",
    lblStation: "出发车站（计划）",
    lblTrain: "车次",
    lblBooked: "购票证件",
    lblCarry: "随身携带",
    carryNote: "护照 · 身份证 · 签证 · 订单二维码 · 现金 · 银行卡",
    optPassport: "护照（外籍）",
    optChineseId: "中国身份证",
    optOther: "其他",
    optUnknown: "不清楚",

    btnPhoto: "拍照",
    noImage: "还没有图片",
    questionPh: '选填——你想问什么？\n例如："这台机器不认我，怎么办？"',

    emptyTitle: "用你的语言，告诉你下一步",
    emptyBody: "拍下或加载一个场景，填好行程——得到明确的下一步、需要的证件，以及真实的截止时间。",

    verdicts: "规则引擎的结论",
    stepsTitle: "按这个顺序做",
    phrasesTitle: "给工作人员看的中文",
    missingTitle: "还缺什么",
    aiTitle: "AI 补充回答",
    visionTitle: "现场识别结果（模型读取）",
    badgeRule: "规则",
    badgeModel: "模型",

    dialHint: "拖动滑块，规则引擎实时响应——不调用模型",
    dialAria: "距离发车分钟数",
    btnReset: "重置",
    footer: "钉子头 · 参赛作品 — 入境游 AI 创新",

    lblDeparture: "发车",
    lblGateCloses: "停止检票",
    lblArriveBy: "建议到达",
    lblScene: "场景",
    lblVerdict: "规则引擎判定",
    bufferNote: "预留安检 + 实名核验的时间",
    trainGone: "列车已发车",
    gateClosed: "检票口已关闭",
    noTimePressure: "时间充裕",
    noDepartureKnown: "此场景没有已知的发车时间。",
    minsLeft: "还有 {n} 分钟",
    tomorrow: "（次日）",
    departIn: "距发车 {n} 分钟",
    departInShort: "{n} 分钟 — 检票口 {m} 分钟后关闭",
    departed: "{n} 分钟 — 你的车已经开了",

    sevCritical: "紧急",
    sevWarn: "警告",
    sevInfo: "提示",
    sevOk: "正常",

    noFindingsTitle: "没有规则阻止你。",
    noFindingsBody: "此场景未检测到证件、时间或流程上的关键问题。",
    noPhrases: "此场景没有可直接展示的短语。",
    whyPrefix: "为什么普通翻译软件解决不了：",
    sceneModel: "场景（模型）",
    translationNote: "翻译：{v}",
    degradedNote: "第一阶段模型不可用，场景来自预设",
  },
};

function t(key, vars) {
  const lang = ($("lang") && $("lang").value) || "en";
  let s = (UI_STRINGS[lang] && UI_STRINGS[lang][key]);
  if (s == null) s = UI_STRINGS.en[key];
  if (s == null) return key;
  if (vars) Object.keys(vars).forEach((k) => {
    s = s.replace(new RegExp("\\{" + k + "\\}", "g"), vars[k]);
  });
  return s;
}

const SEV_LABEL = { critical: "sevCritical", warn: "sevWarn", info: "sevInfo" };

function applyUiLang() {
  const lang = ($("lang") && $("lang").value) || "en";
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const v = UI_STRINGS[lang] && UI_STRINGS[lang][el.getAttribute("data-i18n")];
    if (v != null) el.textContent = v;
  });
  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    const v = UI_STRINGS[lang] && UI_STRINGS[lang][el.getAttribute("data-i18n-html")];
    if (v != null) el.innerHTML = v;
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    const v = UI_STRINGS[lang] && UI_STRINGS[lang][el.getAttribute("data-i18n-ph")];
    if (v != null) el.setAttribute("placeholder", v);
  });
  document.querySelectorAll("[data-i18n-ar]").forEach((el) => {
    const v = UI_STRINGS[lang] && UI_STRINGS[lang][el.getAttribute("data-i18n-ar")];
    if (v != null) el.setAttribute("aria-label", v);
  });

  renderSamples();
  if (state.lastResult) renderResult(state.lastResult);
}

// ---- bootstrapping ---------------------------------------------------------

async function init() {
  try {
    const r = await fetch("/api/samples");
    const j = await r.json();
    state.samples = j.samples || [];
  } catch (_) { state.samples = []; }
  // ?lang=zh in the URL starts the demo in Chinese (handy for sharing a link)
  const urlLang = new URLSearchParams(location.search).get("lang");
  if (urlLang && UI_STRINGS[urlLang]) $("lang").value = urlLang;
  applyUiLang();
  bindEvents();
  // fill from URL hash so a sample can be opened by URL
  if (location.hash.length > 1) {
    const id = location.hash.slice(1);
    const s = state.samples.find((x) => x.id === id);
    if (s) setTimeout(() => loadSample(s), 30);
  }
}

function bindEvents() {
  $("file").addEventListener("change", onFile);
  $("question").addEventListener("input", debounce(() => maybeRun("question"), 800));

  $("t-city").addEventListener("change", debounce(() => maybeRun("trip"), 400));
  $("t-station").addEventListener("change", debounce(() => maybeRun("trip"), 400));
  $("t-train").addEventListener("change", debounce(() => maybeRun("trip"), 400));
  $("t-booked").addEventListener("change", debounce(() => maybeRun("trip"), 400));
  $("t-docs").addEventListener("input", debounce(() => maybeRun("trip"), 600));

  $("lang").addEventListener("change", () => {
    applyUiLang();                                  // switch the UI chrome
    if (state.lastResult) translateOnly(state.lastResult);  // re-translate content
  });

  const dial = $("dial");
  dial.addEventListener("input", onDial);
  $("dial-now").addEventListener("click", () => {
    dial.value = 28;
    onDial();
  });
}

// ---- samples --------------------------------------------------------------

function renderSamples() {
  const root = $("samples");
  const lang = ($("lang") && $("lang").value) || "en";
  root.innerHTML = "";
  state.samples.forEach((s) => {
    const primary = lang === "zh" ? (s.title_zh || s.title) : s.title;
    const secondary = lang === "zh" ? s.title : (s.title_zh || "");
    const el = document.createElement("div");
    el.className = "sample";
    el.innerHTML = `
      <img src="/samples/${s.file}" alt="${escapeHtml(primary)}">
      <div class="meta">
        <div class="kick">${escapeHtml(s.kicker || "")}</div>
        <div class="title">${escapeHtml(primary)}</div>
        <div class="mini">${escapeHtml(secondary || "")}</div>
      </div>`;
    el.addEventListener("click", () => loadSample(s));
    root.appendChild(el);
  });
}

async function loadSample(s) {
  fillFormFromSample(s);
  const noDep = s.depart_in_minutes == null;
  const dm = noDep ? 60 : s.depart_in_minutes;
  $("dial").value = dm;
  $("dial-label").textContent = dialLabel(dm);
  state.noDepartTime = noDep;
  await setPreviewUrl(`/samples/${s.file}`);
  await run();
}

function fillFormFromSample(s) {
  const trip = s.trip || {};
  const lang = ($("lang") && $("lang").value) || "en";
  $("t-city").value = trip.city || "";
  $("t-station").value = trip.planned_station || "";
  $("t-train").value = trip.train_no || "";
  $("t-booked").value = trip.booked_with || "passport";
  $("t-docs").value = (trip.documents || ["passport"]).join(", ");
  $("question").value = (lang === "zh" && s.question_zh) ? s.question_zh : (s.question || "");
}

// ---- file / preview ------------------------------------------------------

async function onFile(ev) {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async () => {
    await setPreviewDataUrl(reader.result);
    await run();
  };
  reader.readAsDataURL(file);
}

async function setPreviewUrl(url) {
  // fetch and inline as data URL so upload works offline / on Render
  const r = await fetch(url);
  const b = await r.blob();
  const dataUrl = await blobToDataUrl(b);
  await setPreviewDataUrl(dataUrl);
}

async function setPreviewDataUrl(url) {
  state.imageDataUrl = url;
  const el = $("preview");
  el.style.backgroundImage = `url("${url}")`;
  el.innerHTML = "";
}

function blobToDataUrl(blob) {
  return new Promise((res, rej) => {
    const fr = new FileReader();
    fr.onload = () => res(fr.result);
    fr.onerror = rej;
    fr.readAsDataURL(blob);
  });
}

// ---- pipeline ------------------------------------------------------------

function collectTrip(opts) {
  opts = opts || {};
  const dm = $("dial").value;
  const departISO = opts.noDepartTime
    ? null
    : (dm ? computeDepartInMinutes(dm) : null);
  return {
    city: $("t-city").value || null,
    planned_station: $("t-station").value || null,
    train_no: $("t-train").value || null,
    depart_time: departISO,
    booked_with: $("t-booked").value,
    documents: ($("t-docs").value || "").split(",").map((x) => x.trim()).filter(Boolean),
    hotel: null,
    now_override: null,
  };
}

function computeDepartInMinutes(mins) {
  const now = new Date();
  const depart = new Date(now.getTime() + parseInt(mins, 10) * 60000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${depart.getFullYear()}-${pad(depart.getMonth() + 1)}-${pad(depart.getDate())} ` +
         `${pad(depart.getHours())}:${pad(depart.getMinutes())}`;
}
function computeDepartInMinutesStr(mins) {
  return computeDepartInMinutes(mins);
}

async function run() {
  if (!state.imageDataUrl) return;
  const body = {
    image: state.imageDataUrl,
    question: $("question").value || "",
    lang: $("lang").value || "en",
    ...collectTrip({ noDepartTime: state.noDepartTime }),
  };
  showThinking(true);
  try {
    const r = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    state.lastResult = data;
    state.lastVision = data.vision;
    renderResult(data);
  } catch (err) {
    renderError(err);
  } finally {
    showThinking(false);
  }
}

async function recompute() {
  if (!state.lastVision) return;
  const body = {
    vision: state.lastVision,
    question: $("question").value || "",
    lang: $("lang").value || "en",
    ...collectTrip({ noDepartTime: state.noDepartTime }),
    previous_note: state.lastResult ? state.lastResult.ai_note : "",
    previous_translation: state.lastResult ? state.lastResult.translation : "",
  };
  try {
    const r = await fetch("/api/recompute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    // keep the previous ai_note / translation since recompute skips LLM
    if (state.lastResult) {
      data.ai_note = state.lastResult.ai_note;
      data.translation = state.lastResult.translation;
    }
    state.lastResult = data;
    renderResult(data);
  } catch (_) { /* ignored — slider keeps moving */ }
}

async function translateOnly(prev) {
  // when only language changed, hit /api/recompute with current vision but ask
  // for a fresh translation; recompute skips ai_note, so the previous note
  // remains visible in the user's current language if we re-ran with the new lang.
  // simpler: re-run analyze is too heavy; instead rebuild a synthetic vision dict
  // that includes the previous translation but ask /api/recompute to translate.
  // We do this by tagging previous_translation="" and force_with_translation=true.
  if (!state.lastVision) return;
  const body = {
    vision: state.lastVision,
    question: $("question").value || "",
    lang: $("lang").value || "en",
    ...collectTrip(),
    previous_note: prev.ai_note || "",
    previous_translation: "",
    force_translation: true,
  };
  // /api/recompute ignores force_translation but we re-use the analyse path
  // to get a full fresh translation. The simplest: trigger full run again.
  // To keep latency low we fall back to recompute (which still translates).
  await recompute();
}

function maybeRun(reason) {
  if (reason === "trip" && state.lastVision) recompute();
  else if (reason === "question") recompute();
}

// ---- demo dial -----------------------------------------------------------

function onDial() {
  const v = parseInt($("dial").value, 10);
  $("dial-label").textContent = dialLabel(v);
  clearTimeout(state.dialTimer);
  state.dialTimer = setTimeout(recompute, 80);
}

function dialLabel(mins) {
  if (mins <= 0) return t("departed", { n: mins });
  if (mins <= 5) return t("departInShort", { n: mins, m: mins });
  return t("departIn", { n: mins });
}

// ---- rendering -----------------------------------------------------------

function showThinking(on) {
  document.body.style.cursor = on ? "progress" : "default";
}

function renderError(err) {
  $("placeholder").classList.remove("hidden");
  $("placeholder").textContent = "Failed: " + err.message;
}

function renderResult(r) {
  $("placeholder").classList.add("hidden");
  $("result").classList.remove("hidden");
  renderTiming(r);
  renderFindings(r.findings || []);
  renderSteps(r.steps || []);
  renderPhrases(r.findings || []);
  renderMissing(r.missing || []);
  renderAiNote(r);
  renderVision(r.vision || {});
}

function renderTiming(r) {
  const ti = r.timing || {};
  const lv = ti.level || "ok";
  const klass = lv === "danger" || lv === "gate_closed" || lv === "departed"
                ? "danger"
                : (lv === "warn" ? "warn" : "");
  const root = $("timing");
  if (!ti.has_departure) {
    root.innerHTML = `
      <div class="timer">
        <div class="label">${escapeHtml(t("lblScene"))}</div>
        <div class="value" style="font-size:18px;">${escapeHtml(r.scene_label || r.scene)}</div>
        <div class="sub">${escapeHtml(r.meta?.scene_from || "")}</div>
        <div class="ref">${r.meta?.elapsed_ms ?? "—"} ms</div>
      </div>
      <div class="timer">
        <div class="label">${escapeHtml(t("lblVerdict"))}</div>
        <div class="value" style="font-size:16px;">${lv === "ok" ? escapeHtml(t("noTimePressure")) : escapeHtml(lv)}</div>
        <div class="sub">${escapeHtml(t("noDepartureKnown"))}</div>
      </div>`;
    return;
  }
  const tomorrowTag = ti.is_tomorrow ? " " + t("tomorrow") : "";
  const m2dep = ti.minutes_to_departure;
  const m2close = ti.minutes_to_gate_close;
  const subForDepart = m2dep == null ? "" :
    (m2dep <= 0 ? escapeHtml(t("trainGone"))
                 : escapeHtml(t("minsLeft", { n: m2dep })) + tomorrowTag);
  const subForClose = m2close == null ? "" :
    (m2close <= 0 ? escapeHtml(t("gateClosed"))
                   : escapeHtml(t("minsLeft", { n: m2close })) + tomorrowTag);
  root.innerHTML = `
    <div class="timer">
      <div class="label">${escapeHtml(t("lblDeparture"))}</div>
      <div class="value">${escapeHtml(ti.depart_time || "—")}${tomorrowTag}</div>
      <div class="sub">${subForDepart}</div>
    </div>
    <div class="timer ${klass}">
      <div class="label">${escapeHtml(t("lblGateCloses"))}</div>
      <div class="value">${escapeHtml(ti.gate_close_time || "—")}</div>
      <div class="sub">${subForClose}</div>
      <div class="ref">${escapeHtml(ti.gate_close_rule || "")}</div>
    </div>
    <div class="timer">
      <div class="label">${escapeHtml(t("lblArriveBy"))}</div>
      <div class="value">${escapeHtml(ti.arrive_by || "—")}</div>
      <div class="sub">${escapeHtml(t("bufferNote"))}</div>
      <div class="ref">${escapeHtml(ti.arrive_rule || "")}</div>
    </div>
    <div class="timer">
      <div class="label">${escapeHtml(t("lblScene"))}</div>
      <div class="value" style="font-size:18px;">${escapeHtml(r.scene_label || r.scene)}</div>
      <div class="sub">${escapeHtml(r.meta?.scene_from || "")}</div>
      <div class="ref">${r.meta?.elapsed_ms ?? "—"} ms</div>
    </div>`;
}

function renderFindings(fs) {
  const root = $("findings");
  root.innerHTML = "";
  if (!fs.length) {
    root.innerHTML = `<div class="finding ok">
      <div class="top"><span class="tag">${escapeHtml(t("sevOk"))}</span>
        <h3>${escapeHtml(t("noFindingsTitle"))}</h3></div>
      <div class="body">${escapeHtml(t("noFindingsBody"))}</div></div>`;
    return;
  }
  fs.forEach((f) => {
    const sev = t(SEV_LABEL[f.severity] || "sevInfo");
    const el = document.createElement("div");
    el.className = `finding ${f.severity}`;
    el.innerHTML = `
      <div class="top">
        <span class="tag">${escapeHtml(sev)}</span>
        <h3>${escapeHtml(f.title)}</h3>
        <span class="ref">${escapeHtml(f.rule_ref || "")}</span>
      </div>
      <div class="body">${escapeHtml(f.detail)}</div>
      ${f.why_translation_fails ? `
        <div class="why">
          <strong>${escapeHtml(t("whyPrefix"))}</strong>
          ${escapeHtml(f.why_translation_fails)}
        </div>` : ""}`;
    root.appendChild(el);
  });
}

function renderSteps(ss) {
  const root = $("steps");
  root.innerHTML = "";
  ss.forEach((s) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="n">${escapeHtml(s.order)}</div>
      <div>
        <div class="action">${escapeHtml(s.action)}</div>
        <div class="detail">${escapeHtml(s.detail)}</div>
        <span class="rule-ref">${escapeHtml(s.rule_ref)}</span>
      </div>`;
    root.appendChild(li);
  });
}

function renderPhrases(fs) {
  const root = $("phrases");
  root.innerHTML = "";
  const items = fs.filter((f) => f.zh_phrase);
  if (!items.length) {
    root.innerHTML = `<div class="muted">${escapeHtml(t("noPhrases"))}</div>`;
    return;
  }
  items.forEach((f) => {
    const div = document.createElement("div");
    div.className = "phrase";
    div.innerHTML = `
      <div class="zh">${escapeHtml(f.zh_phrase)}</div>
      <div class="pinyin">${escapeHtml(f.zh_pinyin || "")}</div>
      <span class="rule-ref">${escapeHtml(f.rule_ref)}</span>`;
    root.appendChild(div);
  });
}

function renderMissing(ms) {
  const card = $("missing-card");
  const root = $("missing");
  root.innerHTML = "";
  if (!ms.length) { card.classList.add("hidden"); return; }
  card.classList.remove("hidden");
  ms.forEach((m) => {
    const div = document.createElement("div");
    div.className = "item";
    div.innerHTML = `<b>${escapeHtml(m.item)}</b><p>${escapeHtml(m.why)}</p>
                     <p class="muted">${escapeHtml(m.how_to_fix || "")}</p>`;
    root.appendChild(div);
  });
}

function renderAiNote(r) {
  const el = $("ai-note");
  el.textContent = (r.ai_note || "").trim() || "—";
  const m = $("ai-meta");
  const tr = r.translation || "en";
  const meta = r.meta || {};
  m.textContent = t("translationNote", { v: tr })
    + (meta.degraded ? "  ·  " + t("degradedNote") : "");
}

function renderVision(v) {
  const root = $("vision");
  const kv = [];
  kv.push([t("sceneModel"), `${v.confidence ? Math.round(v.confidence * 100) + "% " : ""}${v.scene_label_en || v.scene}`]);
  Object.entries(v.extracted || {})
    .filter(([k, val]) => val != null && val !== "")
    .forEach(([k, val]) => kv.push([k, String(val)]));
  if (v.traveler_situation) kv.push(["situation", v.traveler_situation]);
  root.innerHTML = `<div class="kv">${kv.map(([k, v2]) =>
    `<b>${escapeHtml(k)}</b><div>${escapeHtml(v2)}</div>`).join("")}</div>` +
    ((v.ocr_text || []).length
      ? `<div class="ocr">${escapeHtml((v.ocr_text || []).join("\n"))}</div>`
      : "");
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function debounce(fn, ms) {
  let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function noop() {}

init();