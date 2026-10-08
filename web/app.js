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

const SEV_LABEL = {
  critical: "CRITICAL", warn: "WARN", info: "INFO",
};

// ---- bootstrapping ---------------------------------------------------------

async function init() {
  try {
    const r = await fetch("/api/samples");
    const j = await r.json();
    state.samples = j.samples || [];
  } catch (_) { state.samples = []; }
  renderSamples();
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
    if (state.lastResult) translateOnly(state.lastResult);
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
  root.innerHTML = "";
  state.samples.forEach((s) => {
    const el = document.createElement("div");
    el.className = "sample";
    el.innerHTML = `
      <img src="/samples/${s.file}" alt="${s.title}">
      <div class="meta">
        <div class="kick">${escapeHtml(s.kicker || "")}</div>
        <div class="title">${escapeHtml(s.title)}</div>
        <div class="mini">${escapeHtml(s.title_zh || "")}</div>
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
  const t = s.trip || {};
  $("t-city").value = t.city || "";
  $("t-station").value = t.planned_station || "";
  $("t-train").value = t.train_no || "";
  $("t-booked").value = t.booked_with || "passport";
  $("t-docs").value = (t.documents || ["passport"]).join(", ");
  $("question").value = s.question || "";
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
  if (mins <= 0) return `${mins} min — your train has left`;
  if (mins <= 5) return `${mins} min — gate closes in ${mins}`;
  return `${mins} min to departure`;
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
  const t = r.timing || {};
  const lv = t.level || "ok";
  const klass = lv === "danger" || lv === "gate_closed" || lv === "departed"
                ? "danger"
                : (lv === "warn" ? "warn" : "");
  const root = $("timing");
  if (!t.has_departure) {
    root.innerHTML = `
      <div class="timer">
        <div class="label">Scene</div>
        <div class="value" style="font-size:18px;">${escapeHtml(r.scene_label || r.scene)}</div>
        <div class="sub">${escapeHtml(r.meta?.scene_from || "")}</div>
        <div class="ref">${r.meta?.elapsed_ms ?? "—"} ms</div>
      </div>
      <div class="timer">
        <div class="label">Rule engine verdict</div>
        <div class="value" style="font-size:16px;">${t.level === "ok" ? "no time pressure" : t.level}</div>
        <div class="sub">No departure time known for this scene.</div>
      </div>`;
    return;
  }
  const tm = t.is_tomorrow ? " tomorrow" : "";
  const m2dep = t.minutes_to_departure;
  const m2close = t.minutes_to_gate_close;
  const subForDepart = m2dep == null ? "" :
    (m2dep <= 0 ? "Train has already left"
                 : `in ${m2dep} min${t.is_tomorrow ? " (tomorrow)" : ""}`);
  const subForClose = m2close == null ? "" :
    (m2close <= 0 ? "Gate already closed"
                   : `in ${m2close} min${t.is_tomorrow ? " (tomorrow)" : ""}`);
  root.innerHTML = `
    <div class="timer">
      <div class="label">Departure</div>
      <div class="value">${escapeHtml(t.depart_time || "—")}${tm}</div>
      <div class="sub">${subForDepart}</div>
    </div>
    <div class="timer ${klass}">
      <div class="label">Gate closes</div>
      <div class="value">${escapeHtml(t.gate_close_time || "—")}</div>
      <div class="sub">${subForClose}</div>
      <div class="ref">${escapeHtml(t.gate_close_rule || "")}</div>
    </div>
    <div class="timer">
      <div class="label">Arrive by</div>
      <div class="value">${escapeHtml(t.arrive_by || "—")}</div>
      <div class="sub">buffer for security + ID check</div>
      <div class="ref">${escapeHtml(t.arrive_rule || "")}</div>
    </div>
    <div class="timer">
      <div class="label">Scene</div>
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
      <div class="top"><span class="tag">OK</span>
        <h3>No rule blocked you.</h3></div>
      <div class="body">No critical procedure, document or time issue detected for this scene.</div></div>`;
    return;
  }
  fs.forEach((f) => {
    const sev = SEV_LABEL[f.severity] || f.severity.toUpperCase();
    const el = document.createElement("div");
    el.className = `finding ${f.severity}`;
    el.innerHTML = `
      <div class="top">
        <span class="tag">${sev}</span>
        <h3>${escapeHtml(f.title)}</h3>
        <span class="ref">${escapeHtml(f.rule_ref || "")}</span>
      </div>
      <div class="body">${escapeHtml(f.detail)}</div>
      ${f.why_translation_fails ? `
        <div class="why">
          <strong>Why a normal translation app can't help here:</strong>
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
      <div class="action">${escapeHtml(s.action)}</div>
      <div class="detail">${escapeHtml(s.detail)}</div>
      <span class="rule-ref">${escapeHtml(s.rule_ref)}</span>`;
    root.appendChild(li);
  });
}

function renderPhrases(fs) {
  const root = $("phrases");
  root.innerHTML = "";
  const items = fs.filter((f) => f.zh_phrase);
  if (!items.length) {
    root.innerHTML = `<div class="muted">No ready-to-show phrases for this scene.</div>`;
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
  m.textContent = `translation: ${tr}${meta.degraded ? "  ·  stage-1 model unavailable, scene from hint" : ""}`;
}

function renderVision(v) {
  const root = $("vision");
  const kv = [];
  kv.push(["Scene (model)", `${v.confidence ? Math.round(v.confidence * 100) + "% " : ""}${v.scene_label_en || v.scene}`]);
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