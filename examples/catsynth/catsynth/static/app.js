const state = { mode: "policy", scenarios: [], breeds: [], rules: [], selected: null };

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

function toast(msg) {
  let t = $(".toast");
  if (!t) {
    t = el("div", "toast");
    t.setAttribute("role", "status");
    t.setAttribute("aria-live", "polite");
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2200);
}

// --- tabs -------------------------------------------------------------------
async function activateTab(tabId, updateHash = true) {
  const tab = document.querySelector(`.tab[data-tab="${tabId}"]`);
  const panel = $("#" + tabId);
  if (!tab || !panel) return;
  document.querySelectorAll(".tab").forEach((t) => {
    const active = t === tab;
    t.classList.toggle("active", active);
    t.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p === panel));
  if (updateHash) history.replaceState(null, "", `#${tabId}`);
  if (tabId === "corpus") await loadCorpus();
  if (tabId === "rules") await loadRules();
  if (tabId === "sketch") await loadSketch();
  if (tabId === "gate") await loadGateRuns();
  if (tabId === "playground") initPlayground();
}

document.querySelectorAll(".tab").forEach((tab) =>
  tab.addEventListener("click", () => activateTab(tab.dataset.tab)));

window.addEventListener("hashchange", () => {
  const tabId = location.hash.replace(/^#/, "");
  if (tabId) activateTab(tabId, false);
});

// Home guided-tour buttons jump straight to the live tab that runs the step.
document.querySelectorAll("[data-goto]").forEach((btn) =>
  btn.addEventListener("click", () => activateTab(btn.dataset.goto)));

// --- mode toggle ------------------------------------------------------------
document.querySelectorAll("#mode-toggle .seg").forEach((seg) => {
  seg.addEventListener("click", () => {
    document.querySelectorAll("#mode-toggle .seg").forEach((s) => s.classList.remove("active"));
    seg.classList.add("active");
    state.mode = seg.dataset.mode;
    if (state.selected) selectScenario(state.selected);
  });
});

// --- scenarios --------------------------------------------------------------
async function loadScenarios() {
  [state.scenarios, state.breeds, state.rules] = await Promise.all([
    api("/api/scenarios"), api("/api/breeds"), api("/api/rules"),
  ]);
  const list = $("#scenario-list");
  list.innerHTML = "";
  state.scenarios.forEach((s) => {
    const li = el("li");
    li.dataset.id = s.scenario_id;
    li.setAttribute("role", "button");
    li.tabIndex = 0;
    li.innerHTML = `<span class="sid">${esc(s.scenario_id)}</span>
      ${s.promoted ? `<span class="badge promoted" role="button" tabindex="0"
        title="An operator-approved CE for this scenario is in archive A and regression set R — click to view it">approved CE ↗</span>` : ""}
      <span class="slabel">${esc(s.label)}</span>`;
    li.addEventListener("click", () => selectScenario(s.scenario_id));
    li.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        selectScenario(s.scenario_id);
      }
    });
    const badge = li.querySelector(".badge.promoted");
    if (badge) {
      const jump = (e) => { e.stopPropagation(); showCorpusForScenario(s.scenario_id); };
      badge.addEventListener("click", jump);
      badge.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") jump(e); });
    }
    list.appendChild(li);
  });
  if (!state.selected && state.scenarios.some((s) => s.scenario_id === "allergy_lapcat")) {
    await selectScenario("allergy_lapcat");
  }
}

function traitRows(sc) {
  const traits = ["allergies", "work_hours", "home_size", "young_children",
    "activity_level", "noise_tolerance", "experience"];
  const prefs = ["wants_size", "wants_affection", "wants_fluffy"];
  const row = (k) => `<span class="k">${k}</span><span>${esc(sc[k])}</span>`;
  let html = `<div class="kv">${traits.map(row).join("")}</div>`;
  html += `<div style="margin-top:8px" class="kv">${prefs.map(row).join("")}</div>`;
  if (sc.narrative_note)
    html += `<div class="wiki" style="margin-top:10px"><strong>narrative note:</strong> “${esc(sc.narrative_note)}”</div>`;
  return html;
}

function recCard(rec, breedDetail) {
  const op = rec.operation;
  const cls = op === "abstain" ? "abstain" : "recommend";
  let head = op === "recommend"
    ? `<span class="breed-name">${esc(rec.breed)}</span>`
    : `<span class="breed-name">— ${op} —</span>`;
  let chips = (rec.cited_rules || []).map((r) => `<span class="chip rule">${esc(r)}</span>`).join("");
  let wiki = "";
  if (breedDetail) {
    const b = breedDetail;
    const attrs = ["size", "energy", "shedding", "grooming", "sociability", "vocal", "affection"]
      .map((a) => `<span class="chip">${a}: ${esc(b[a])}</span>`).join("");
    const flags = `<span class="chip">${b.hypoallergenic ? "hypoallergenic" : "not hypoallergenic"}</span>
      <span class="chip">${b.good_with_children ? "good with kids" : "not for kids"}</span>
      <span class="chip">${b.fluffy ? "fluffy" : "sleek"}</span>`;
    wiki = `<div class="chips" style="margin-top:10px">${attrs}${flags}</div>`;
    if (b.summary)
      wiki += `<div class="wiki">${esc(b.summary.slice(0, 320))}${b.summary.length > 320 ? "…" : ""}
        ${b.wiki_url ? `<a href="${esc(b.wiki_url)}" target="_blank">Wikipedia ↗</a>` : ""}</div>`;
  }
  return `<div class="card">
    <h3>Proposed recommendation <span class="op-pill ${cls}">${esc(op)}</span>
      <span class="chip">oracle: ${esc(rec.oracle)}</span></h3>
    <div class="rec ${cls}">
      ${head}
      <div style="margin-top:6px;color:var(--muted)">${esc(rec.rationale)}</div>
      <div class="chips" style="margin-top:8px">${chips || '<span class="chip">no rules in force</span>'}</div>
      ${wiki}
    </div>
    <details><summary>trace</summary><pre>${esc(JSON.stringify(rec.trace, null, 2))}</pre></details>
  </div>`;
}

function correctionForm(sc, rec) {
  const expectedBreedOpts = state.breeds.map((b) =>
    `<option value="${esc(b.name)}"${b.name === rec.breed ? " selected" : ""}>${esc(b.name)}</option>`).join("");
  const temptingBreedOpts = state.breeds.map((b) =>
    `<option value="${esc(b.name)}">${esc(b.name)}</option>`).join("");
  const ruleChecks = state.rules.map((r) =>
    `<label style="display:inline-flex;gap:6px;align-items:center;width:auto;margin-right:12px">
      <input type="checkbox" style="width:auto" name="cited" value="${esc(r.id)}"
        ${(rec.cited_rules || []).includes(r.id) ? "checked" : ""}/> ${esc(r.id)}</label>`).join("");
  return `<div class="correction">
    <h3>SME correction → operator approval</h3>
    <p class="form-note">Review the corrected output, tempting wrong repair, and missing sketch rule. This teaching action adds a local A = R row; it does not invoke Developer or revise SKETCH.md.</p>
    <label for="c-op">Expected operation</label>
    <select id="c-op">
      <option value="recommend"${rec.operation === "recommend" ? " selected" : ""}>recommend</option>
      <option value="abstain"${rec.operation === "abstain" ? " selected" : ""}>abstain</option>
      <option value="escalate"${rec.operation === "escalate" ? " selected" : ""}>escalate</option>
    </select>
    <label for="c-breed">Expected breed</label>
    <select id="c-breed"><option value="">(none)</option>${expectedBreedOpts}</select>
    <label>Cited rules (policy-bearing)</label>
    <div style="padding:8px 0">${ruleChecks}</div>
    <label for="c-tempting">Tempting wrong breed (optional)</label>
    <select id="c-tempting"><option value="" selected>(none)</option>${temptingBreedOpts}</select>
    <label for="c-violated">Violated rule id (optional)</label>
    <input id="c-violated" placeholder="e.g. allergy_requires_hypoallergenic" />
    <label for="c-clause">Sketch clause</label>
    <input id="c-clause" placeholder="e.g. FR-1 allergy override" />
    <label for="c-note">Note / reason</label>
    <textarea id="c-note" placeholder="Why is the tempting repair wrong?"></textarea>
    <div class="row"><button class="btn primary" id="promote-btn">Approve local CE</button></div>
  </div>`;
}

async function selectScenario(id) {
  state.selected = id;
  document.querySelectorAll("#scenario-list li").forEach((li) =>
    {
      const selected = li.dataset.id === id;
      li.classList.toggle("selected", selected);
      li.setAttribute("aria-pressed", String(selected));
    });
  const data = await api(`/api/suggest/${id}?mode=${state.mode}`);
  const sc = data.scenario;
  const detail = $("#review-detail");
  detail.innerHTML = `
    <div class="card"><h3>${esc(sc.label)} <span class="sid" style="color:var(--accent)">${esc(sc.scenario_id)}</span></h3>
      ${traitRows(sc)}</div>
    ${recCard(data.recommendation, data.breed_detail)}
    ${correctionForm(sc, data.recommendation)}`;

  $("#promote-btn").addEventListener("click", () => promote(id));
}

async function promote(scenario_id) {
  const cited = Array.from(document.querySelectorAll('input[name="cited"]:checked')).map((c) => c.value);
  const op = $("#c-op").value;
  const breed = $("#c-breed").value || null;
  const tempting = $("#c-tempting").value
    ? { operation: "recommend", breed: $("#c-tempting").value, cited_rules: [], rationale: "tempting repair" }
    : null;
  const body = {
    scenario_id,
    expected: { operation: op, breed: op === "recommend" ? breed : null, cited_rules: cited, rationale: "SME-corrected" },
    tempting,
    violated_rule: $("#c-violated").value,
    sketch_clause: $("#c-clause").value,
    note: $("#c-note").value,
  };
  try {
    await api("/api/corpus", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    toast("Local CE approved; Developer was not invoked");
    await loadScenarios();
    document.querySelectorAll("#scenario-list li").forEach((li) =>
      li.classList.toggle("selected", li.dataset.id === scenario_id));
  } catch (e) { toast("Error: " + e.message); }
}

// --- gate -------------------------------------------------------------------
$("#run-gate-policy").addEventListener("click", () => runGate("policy"));
$("#run-gate-naive").addEventListener("click", () => runGate("naive"));

async function runGate(mode) {
  const summary = await api(`/api/gate/run?mode=${mode}`, { method: "POST" });
  renderGate(summary);
  loadGateRuns();
}

function renderGate(s) {
  const box = $("#gate-results");
  const banner = `<div class="banner ${s.passed ? "pass" : "fail"}">
    Gate (${esc(s.mode)} mode): ${s.passed ? "PASS" : "FAIL"} — ${s.passed_count}/${s.total} cases</div>`;
  let rows = s.cases.map((c) => {
    const bf = c.compare.fields;
    const cmp = ["operation", "breed", "cited_rules"].map((k) =>
      `${k}: ${bf[k].match ? "✓" : `✗ (exp ${JSON.stringify(bf[k].expected)}, got ${JSON.stringify(bf[k].actual)})`}`).join("<br/>");
    return `<tr>
      <td><span class="sid" style="color:var(--accent)">${esc(c.scenario_id)}</span><br/><span class="muted">${esc(c.sketch_clause)}</span></td>
      <td class="status ${c.replay.passed ? "pass" : "fail"}">${c.replay.passed ? "PASS" : "FAIL"}<br/><span class="muted" style="font-weight:400">${esc(c.replay.detail)}</span></td>
      <td class="status ${c.compare.passed ? "pass" : "fail"}">${c.compare.passed ? "PASS" : "FAIL"}<br/><span class="muted" style="font-weight:400">${cmp}</span></td>
      <td>${esc(c.interpretation)}</td>
    </tr>`;
  }).join("");
  box.innerHTML = banner + `<table>
    <thead><tr><th>Case</th><th>Replay (state)</th><th>Compare (policy)</th><th>Interpretation</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

async function loadGateRuns() {
  const runs = await api("/api/gate/runs");
  $("#gate-runs").innerHTML = runs.length
    ? `<table><thead><tr><th>#</th><th>when</th><th>mode</th><th>result</th><th>failed</th></tr></thead><tbody>${
        runs.map((r) => `<tr><td>${r.id}</td><td class="muted">${esc(r.created_at)}</td>
          <td><code>${esc(r.resolver_mode)}</code></td>
          <td class="status ${r.passed ? "pass" : "fail"}">${r.passed ? "PASS" : "FAIL"}</td>
          <td class="muted">${esc((r.summary.failed_cases || []).join(", ") || "—")}</td></tr>`).join("")}
      </tbody></table>`
    : '<p class="muted">No runs yet.</p>';
}

// --- corpus / rules / sketch ------------------------------------------------
async function loadCorpus() {
  const corpus = await api("/api/corpus");
  $("#corpus-list").innerHTML = corpus.map((c) => `
    <div class="card" data-scenario="${esc(c.scenario_id)}">
      <div class="card-head">
        <h3><span class="sid" style="color:var(--accent)">${esc(c.scenario_id)}</span>
          <span class="chip">${esc(c.sketch_clause)}</span></h3>
        <button class="btn btn-sm btn-danger" data-del="${c.id}" data-label="${esc(c.scenario_id)}">Delete</button>
      </div>
      <div class="kv">
        <span class="k">expected</span><span><span class="op-pill">${esc(c.expected.operation)}</span> ${esc(c.expected.breed || "")}
          <span class="chips">${(c.expected.cited_rules || []).map((r) => `<span class="chip rule">${esc(r)}</span>`).join("")}</span></span>
        <span class="k">tempting</span><span>${c.tempting ? `${esc(c.tempting.operation)} ${esc(c.tempting.breed || "")}` : "—"}</span>
        <span class="k">violated</span><span>${esc(c.violated_rule || "—")}</span>
        <span class="k">note</span><span>${esc(c.note || "")}</span>
      </div>
    </div>`).join("") || '<p class="muted">The CE archive and regression set are empty.</p>';
  $("#corpus-list").querySelectorAll("[data-del]").forEach((btn) =>
    btn.addEventListener("click", () => confirmDeleteCorpus(Number(btn.dataset.del), btn.dataset.label)));
}

// Switch to the CE archive/regression tab and highlight the entry(ies) for one scenario.
async function showCorpusForScenario(scenarioId) {
  await activateTab("corpus");
  const cards = Array.from($("#corpus-list").querySelectorAll(`.card[data-scenario="${scenarioId}"]`));
  if (!cards.length) { toast(`No approved CE found for ${scenarioId}.`); return; }
  cards.forEach((card) => {
    card.classList.remove("flash");
    void card.offsetWidth;  // restart the animation if it was already applied
    card.classList.add("flash");
    setTimeout(() => card.classList.remove("flash"), 1600);
  });
  cards[0].scrollIntoView({ behavior: "smooth", block: "center" });
}

function confirmDeleteCorpus(id, label) {
  confirmModal({
    title: "Delete local CE?",
    body: `This removes <strong>${esc(label)}</strong> (id ${id}) from the current SQLite projection of archive A and regression set R. Reseeding restores repository fixtures.`,
    confirmLabel: "Delete",
    onConfirm: async () => {
      try {
        await api(`/api/corpus/${id}`, { method: "DELETE" });
        toast(`Deleted local CE ${id}.`);
        loadCorpus();
      } catch (e) {
        toast(`Delete failed: ${e.message}`);
      }
    },
  });
}

function confirmModal({ title, body, confirmLabel = "Confirm", onConfirm }) {
  const overlay = el("div", "modal-overlay");
  overlay.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <h3 id="modal-title">${esc(title)}</h3>
      <div class="modal-body">${body}</div>
      <div class="modal-actions">
        <button class="btn" data-act="cancel">Cancel</button>
        <button class="btn btn-danger" data-act="confirm">${esc(confirmLabel)}</button>
      </div>
    </div>`;
  const close = () => { overlay.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  overlay.querySelector('[data-act="cancel"]').addEventListener("click", close);
  overlay.querySelector('[data-act="confirm"]').addEventListener("click", async () => {
    close();
    await onConfirm();
  });
  document.addEventListener("keydown", onKey);
  document.body.appendChild(overlay);
  overlay.querySelector('[data-act="confirm"]').focus();
}

async function loadRules() {
  const rules = state.rules.length ? state.rules : await api("/api/rules");
  $("#rules-list").innerHTML = `<table>
    <thead><tr><th>id</th><th>kind</th><th>trigger (owner trait)</th><th>targets (cat)</th><th>reason</th></tr></thead>
    <tbody>${rules.map((r) => `<tr>
      <td><code>${esc(r.id)}</code></td>
      <td><span class="op-pill ${r.kind === "forbid" ? "abstain" : ""}">${esc(r.kind)}</span></td>
      <td><code>${esc(r.trait)} ${esc(r.trait_op)} ${esc(r.trait_value)}</code></td>
      <td><code>${esc(r.cat_attribute)} ${esc(r.cat_op)} ${esc(r.cat_value)}</code></td>
      <td class="muted">${esc(r.reason)}</td></tr>`).join("")}</tbody></table>`;
}

async function loadSketch() {
  const { markdown } = await api("/api/sketch");
  $("#sketch-body").innerHTML = renderMarkdown(markdown);
}

function renderMarkdown(md) {
  const lines = md.split("\n");
  let html = "", inCode = false;
  let para = [], quote = [], items = null, listTag = null;
  const inline = (t) => esc(t)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  const flushPara = () => { if (para.length) { html += `<p>${inline(para.join(" "))}</p>`; para = []; } };
  const flushQuote = () => { if (quote.length) { html += `<blockquote>${inline(quote.join(" "))}</blockquote>`; quote = []; } };
  const flushList = () => {
    if (items) html += `<${listTag}>` + items.map((t) => `<li>${inline(t)}</li>`).join("") + `</${listTag}>`;
    items = null;
    listTag = null;
  };
  const appendListItem = (tag, text) => {
    if (items && listTag !== tag) flushList();
    items = items || [];
    listTag = tag;
    items.push(text);
  };
  const flushAll = () => { flushPara(); flushQuote(); flushList(); };
  for (const raw of lines) {
    if (raw.trim().startsWith("```")) { flushAll(); inCode = !inCode; html += inCode ? "<pre>" : "</pre>"; continue; }
    if (inCode) { html += esc(raw) + "\n"; continue; }
    const heading = raw.match(/^(#{1,6}) /);
    if (heading) { flushAll(); const lvl = heading[1].length; html += `<h${lvl}>${inline(raw.slice(lvl + 1))}</h${lvl}>`; }
    else if (/^> /.test(raw)) { flushPara(); flushList(); quote.push(raw.slice(2)); }
    else if (/^\s*[-*] /.test(raw)) { flushPara(); flushQuote(); appendListItem("ul", raw.replace(/^\s*[-*] /, "")); }
    else if (/^\s*\d+\. /.test(raw)) { flushPara(); flushQuote(); appendListItem("ol", raw.replace(/^\s*\d+\. /, "")); }
    else if (raw.trim() === "") { flushAll(); }
    // A non-blank plain line continues whichever block is open (wrapped text),
    // otherwise it starts a new paragraph.
    else if (items) { items[items.length - 1] += " " + raw.trim(); }
    else if (quote.length) { quote[quote.length - 1] += " " + raw.trim(); }
    else { para.push(raw.trim()); }
  }
  flushAll();
  return html;
}

// --- playground -------------------------------------------------------------
const pg = { mode: "policy", backend: "mock", inited: false };

function initPlayground() {
  if (pg.inited) return;
  pg.inited = true;

  document.querySelectorAll("#pg-mode .seg").forEach((seg) =>
    seg.addEventListener("click", () => {
      document.querySelectorAll("#pg-mode .seg").forEach((s) => s.classList.remove("active"));
      seg.classList.add("active"); pg.mode = seg.dataset.mode;
    }));

  document.querySelectorAll("#pg-backend .seg").forEach((seg) =>
    seg.addEventListener("click", () => {
      document.querySelectorAll("#pg-backend .seg").forEach((s) => s.classList.remove("active"));
      seg.classList.add("active"); pg.backend = seg.dataset.backend;
      $("#pg-model-wrap").style.display = pg.backend === "local" ? "" : "none";
    }));

  $("#pg-form").addEventListener("submit", (e) => { e.preventDefault(); sendPlayground(); });

  loadLlmStatus();
}

async function loadLlmStatus() {
  const status = $("#pg-llm-status");
  try {
    const s = await api("/api/llm");
    const sel = $("#pg-model");
    sel.innerHTML = s.models.map((m) => `<option${m === s.default_model ? " selected" : ""}>${esc(m)}</option>`).join("")
      || `<option value="${esc(s.default_model)}">${esc(s.default_model)}</option>`;
    status.innerHTML = s.available
      ? `<span style="color:var(--pass)">● Local API up</span> at <code>${esc(s.base_url)}</code> (${s.models.length} model${s.models.length === 1 ? "" : "s"})`
      : `<span style="color:var(--fail)">● Local API unreachable</span> at <code>${esc(s.base_url)}</code> — mock still works`;
  } catch (e) { status.textContent = "Could not query the local API."; }
}

function readProfileForm() {
  const f = $("#pg-form");
  const val = (n) => f.elements[n].value;
  const chk = (n) => f.elements[n].checked;
  return {
    label: "ad-hoc request",
    allergies: val("allergies"), work_hours: val("work_hours"), home_size: val("home_size"),
    activity_level: val("activity_level"), noise_tolerance: val("noise_tolerance"),
    experience: val("experience"), wants_size: val("wants_size") || null,
    young_children: chk("young_children"), wants_affection: chk("wants_affection"),
    wants_fluffy: chk("wants_fluffy"), narrative_note: val("narrative_note") || null,
    mode: pg.mode, oracle_b: pg.backend, llm_model: f.elements["llm_model"]?.value || null,
  };
}

async function sendPlayground() {
  const body = readProfileForm();
  const box = $("#pg-result");
  const btn = $("#pg-submit");
  btn.disabled = true;
  box.innerHTML = `<p class="muted"><span class="spin"></span> Resolving${
    body.oracle_b === "local" && body.narrative_note ? " (calling local model…)" : ""}</p>`;
  try {
    const data = await api("/api/test-suggest", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const rec = data.recommendation;
    let ob = "";
    const bt = rec.trace && rec.trace.oracle_b;
    if (bt && bt.used) {
      ob = `<div class="card"><h3>Oracle B <span class="chip">${esc(bt.backend || "")}</span></h3>
        <div class="kv">
          <span class="k">tags</span><span>${(bt.tags || []).map((t) => `<span class="chip rule">${esc(t)}</span>`).join("") || "—"}</span>
          <span class="k">soft rules</span><span>${(bt.derived_rule_ids || []).join(", ") || "—"}</span>
        </div>
        <details open><summary>raw completion</summary><pre>${esc(bt.raw_completion || "")}</pre></details></div>`;
    }
    box.innerHTML = recCard(rec, data.breed_detail) + ob;
  } catch (e) {
    box.innerHTML = `<div class="banner fail">${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
}

async function start() {
  await loadScenarios();
  const requestedTab = location.hash.replace(/^#/, "");
  const tabId = document.querySelector(`.tab[data-tab="${requestedTab}"]`) ? requestedTab : "home";
  await activateTab(tabId, false);
  const runMode = new URLSearchParams(location.search).get("run");
  if (tabId === "gate" && (runMode === "policy" || runMode === "naive")) await runGate(runMode);
}

start();
