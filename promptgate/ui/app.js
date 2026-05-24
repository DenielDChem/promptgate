/* PGate v0.4 — Single-Page Application */

const BASE = "";

let _editorState = {existing: null, id: null};

// ── API client ────────────────────────────────────────────────────────────────

const api = {
  async get(path) {
    const r = await fetch(BASE + path);
    if (!r.ok) throw new Error((await r.json().catch(() => ({detail: r.statusText}))).detail);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(BASE + path, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({detail: r.statusText}))).detail);
    return r.json();
  },
  async del(path) {
    const r = await fetch(BASE + path, {method: "DELETE"});
    if (!r.ok) throw new Error((await r.json().catch(() => ({detail: r.statusText}))).detail);
    return r.json();
  },
};

// ── toast ─────────────────────────────────────────────────────────────────────

let _toastTimer = null;
function toast(msg, type = "ok") {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = `show ${type}`;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { el.className = ""; }, 3000);
}

// ── utils ─────────────────────────────────────────────────────────────────────

function escHtml(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function navigate(hash) {
  window.location.hash = hash;
}

// ── router ────────────────────────────────────────────────────────────────────

const routes = [
  { re: /^#\/prompts\/new$/, page: () => editorPage(null) },
  { re: /^#\/prompts\/(.+)\/run$/, page: (m) => runPage(m[1]) },
  { re: /^#\/prompts\/(.+)$/, page: (m) => editorPage(m[1]) },
  { re: /^#\/prompts$/, page: () => promptsPage() },
  { re: /^#\/chains\/(.+)$/, page: (m) => chainDetailPage(m[1]) },
  { re: /^#\/chains$/, page: () => chainsPage() },
  { re: /^(#\/?)?$/, page: () => promptsPage() },
];

function route() {
  const hash = window.location.hash || "#/prompts";
  for (const r of routes) {
    const m = hash.match(r.re);
    if (m) { r.page(m); return; }
  }
  render("<div class='empty'><h3>404 — Page not found</h3></div>");
}

function render(html) {
  document.getElementById("main").innerHTML = html;
  updateNav();
}

function updateNav() {
  const hash = window.location.hash || "#/prompts";
  document.querySelectorAll("nav a").forEach(a => {
    a.classList.toggle("active", hash.startsWith(a.getAttribute("href")));
  });
}

// ── prompts list ──────────────────────────────────────────────────────────────

async function promptsPage() {
  render(`<h1>Prompts</h1>
<div class="toolbar">
  <input class="search-input" id="search-q" placeholder="Search prompts…" type="search">
  <span class="spacer"></span>
  <button class="btn primary" onclick="navigate('#/prompts/new')">+ New Prompt</button>
</div>
<table class="prompt-table">
  <thead><tr><th>ID</th><th>Name</th><th>Tags</th><th>Model</th><th></th></tr></thead>
  <tbody id="prompt-rows"><tr><td colspan="5" style="color:var(--text-dim);padding:1.5rem">Loading…</td></tr></tbody>
</table>`);

  let allPrompts = [];
  try {
    allPrompts = await api.get("/api/prompts");
  } catch (e) {
    document.getElementById("prompt-rows").innerHTML = `<tr><td colspan="5" style="color:var(--err)">${escHtml(e.message)}</td></tr>`;
    return;
  }

  function renderRows(prompts) {
    if (!prompts.length) {
      document.getElementById("prompt-rows").innerHTML = `<tr><td colspan="5"><div class="empty"><h3>No prompts yet</h3><p>Click <strong>+ New Prompt</strong> to add one.</p></div></td></tr>`;
      return;
    }
    document.getElementById("prompt-rows").innerHTML = prompts.map(p => `
      <tr style="cursor:pointer" onclick="navigate('#/prompts/${escHtml(p.id)}')">
        <td><span class="prompt-id">${escHtml(p.id)}</span></td>
        <td style="color:var(--text-2)">${escHtml(p.name || "—")}</td>
        <td>${(p.tags || []).map(t => `<span class="tag">${escHtml(t)}</span>`).join("")}</td>
        <td style="font-family:var(--mono);font-size:12px;color:var(--text-dim)">${escHtml(p.model || "—")}</td>
        <td onclick="event.stopPropagation()"><div class="actions">
          <a class="btn btn-sm secondary" href="#/prompts/${escHtml(p.id)}/run">Run</a>
          <button class="btn btn-sm danger" onclick="deletePrompt('${escHtml(p.id)}')">Delete</button>
        </div></td>
      </tr>`).join("");
  }

  renderRows(allPrompts);

  document.getElementById("search-q").addEventListener("input", async (e) => {
    const q = e.target.value.trim();
    if (!q) { renderRows(allPrompts); return; }
    try {
      const results = await api.get(`/api/search?q=${encodeURIComponent(q)}&limit=20`);
      const ids = new Set(results.map(r => r.prompt_id));
      renderRows(allPrompts.filter(p => ids.has(p.id)));
    } catch (_) { renderRows(allPrompts); }
  });
}

async function deletePrompt(id) {
  if (!confirm(`Delete prompt "${id}"?`)) return;
  try {
    await api.del(`/api/prompts/${encodeURIComponent(id)}`);
    toast(`Deleted ${id}`);
    promptsPage();
  } catch (e) { toast(e.message, "err"); }
}

// ── editor page ───────────────────────────────────────────────────────────────

async function editorPage(id) {
  render(`<a class="back" href="#/prompts">← Back</a>
<h1>${id ? `Edit: ${escHtml(id)}` : "New Prompt"}</h1>

<div class="mode-toggle">
  <button id="mode-simple" onclick="setMode('simple')">Simple</button>
  <button id="mode-json" onclick="setMode('json')">JSON</button>
</div>

<div class="split-pane">
  <div id="editor-left"></div>
  <div>
    <div class="pane-header"><h2>Compiled Contract</h2></div>
    <pre class="compile-preview" id="compile-out">— press Compile —</pre>
    <p style="color:var(--text-dim);font-size:11px;margin-top:.5rem">Preview only — the model receives this compiled form when you Run.</p>
  </div>
</div>`);

  let existing = null;
  if (id) {
    try {
      existing = await api.get(`/api/prompts/${encodeURIComponent(id)}`);
    } catch (e) { toast(e.message, "err"); }
  }

  _editorState = {existing, id};
  const hasSchema = existing?.schema_ && Object.keys(existing.schema_).length > 0;
  setMode(hasSchema ? "json" : "simple");
}

function setMode(mode) {
  const {existing, id} = _editorState;
  document.querySelectorAll(".mode-toggle button").forEach(b => b.classList.remove("active"));
  document.getElementById(`mode-${mode}`).classList.add("active");

  const left = document.getElementById("editor-left");

  if (mode === "simple") {
    const tmpl = existing?.template ?? "";
    const eid  = existing?.id ?? id ?? "";
    const name = existing?.name ?? "";
    left.innerHTML = `
      <div class="field-row">
        <label>ID <span class="field-required">*</span></label>
        <input id="s-id" placeholder="my_prompt_v1" value="${escHtml(eid)}">
      </div>
      <div class="field-row">
        <label>Name</label>
        <input id="s-name" placeholder="Human-readable name" value="${escHtml(name)}">
      </div>
      <div class="field-row">
        <label>Prompt template <span class="field-required">*</span></label>
        <textarea class="mono" id="s-tmpl" placeholder="You are a helpful assistant.\n\nAnswer the question: {{ question }}">${escHtml(tmpl)}</textarea>
        <span class="field-hint">Use {{ variable }} for placeholders. Simple prompts accept any LLM output.</span>
      </div>
      <div style="display:flex;gap:.5rem;flex-wrap:wrap">
        <button class="btn primary" id="save-btn">Save</button>
        <button class="btn secondary" id="compile-btn">Compile</button>
        ${id ? `<a class="btn secondary" href="#/prompts/${escHtml(id)}/run">Run</a>` : ""}
      </div>`;

    document.getElementById("save-btn").addEventListener("click", () => saveSimple(id));
    document.getElementById("compile-btn").addEventListener("click", () => compileSimple(id));

  } else {
    const val = existing
      ? JSON.stringify(existing, null, 2)
      : '{\n  "id": "my_prompt_v1",\n  "name": "My Prompt",\n  "template": "Answer: {{ question }}",\n  "schema_": {\n    "type": "object",\n    "properties": {\n      "answer": { "type": "string" }\n    },\n    "required": ["answer"]\n  }\n}';

    left.innerHTML = `
      <div class="field-row">
        <label>PromptConfig JSON</label>
        <textarea class="mono" id="yaml-src">${escHtml(val)}</textarea>
      </div>
      <div style="display:flex;gap:.5rem;flex-wrap:wrap">
        <button class="btn primary" id="save-btn">Save</button>
        <button class="btn secondary" id="compile-btn">Compile</button>
        ${id ? `<a class="btn secondary" href="#/prompts/${escHtml(id)}/run">Run</a>` : ""}
      </div>`;

    document.getElementById("save-btn").addEventListener("click", () => saveJson(id));
    document.getElementById("compile-btn").addEventListener("click", () => compileJson(id));
  }
}

function buildSimpleObj() {
  const id   = document.getElementById("s-id").value.trim();
  const name = document.getElementById("s-name").value.trim();
  const tmpl = document.getElementById("s-tmpl").value.trim();
  if (!id)   { toast("ID required", "err"); return null; }
  if (!tmpl) { toast("Template required", "err"); return null; }
  return { id, name: name || id, template: tmpl, schema_: {} };
}

async function saveSimple() {
  const obj = buildSimpleObj();
  if (!obj) return;
  try {
    await api.post("/api/prompts", obj);
    toast("Saved " + obj.id);
    if (!_editorState.id) {
      _editorState.id = obj.id;
      _editorState.existing = obj;
      const runLink = document.querySelector("#editor-left a.btn");
      if (!runLink) {
        const btnRow = document.querySelector("#editor-left div[style]");
        if (btnRow) btnRow.insertAdjacentHTML("beforeend", `<a class="btn secondary" href="#/prompts/${escHtml(obj.id)}/run">Run</a>`);
      }
    }
  } catch (e) { toast(e.message, "err"); }
}

async function compileSimple() {
  const obj = buildSimpleObj();
  if (!obj) return;
  try {
    await api.post("/api/prompts", obj);
    const contract = await api.post("/api/compile", {prompt_id: obj.id, payload: {}});
    document.getElementById("compile-out").textContent = JSON.stringify(contract, null, 2);
  } catch (e) {
    document.getElementById("compile-out").textContent = "Error: " + e.message;
  }
}

async function saveJson() {
  const raw = document.getElementById("yaml-src").value.trim();
  try {
    const obj = JSON.parse(raw);
    await api.post("/api/prompts", obj);
    toast("Saved " + (obj.id || "prompt"));
    if (!_editorState.id && obj.id) {
      _editorState.id = obj.id;
      _editorState.existing = obj;
    }
  } catch (e) { toast(e.message, "err"); }
}

async function compileJson() {
  const raw = document.getElementById("yaml-src").value.trim();
  try {
    const obj = JSON.parse(raw);
    if (!obj.id) throw new Error("id field required");
    await api.post("/api/prompts", obj);
    const contract = await api.post("/api/compile", {prompt_id: obj.id, payload: {}});
    document.getElementById("compile-out").textContent = JSON.stringify(contract, null, 2);
  } catch (e) {
    document.getElementById("compile-out").textContent = "Error: " + e.message;
  }
}

// ── run page ──────────────────────────────────────────────────────────────────

async function runPage(id) {
  render(`<a class="back" href="#/prompts/${escHtml(id)}">← ${escHtml(id)}</a>
<h1>Run: ${escHtml(id)}</h1>
<div class="run-layout">
  <div class="run-form" id="run-form-area"><p style="color:var(--text-dim)">Loading…</p></div>
  <div>
    <div class="pane-header"><h2>Result</h2></div>
    <pre class="run-result" id="run-result">— press Run —</pre>
    <div class="result-meta" id="result-meta"></div>
    <p style="color:var(--text-dim);font-size:11px;margin-top:.75rem">The prompt template is sent as system instructions. "Your message" is the user turn. The model sees the compiled template, not the raw text.</p>
  </div>
</div>`);

  let prompt, models = [], profile = {name: "default", default_model: "", api_base: ""};
  try {
    [prompt, models, profile] = await Promise.all([
      api.get(`/api/prompts/${encodeURIComponent(id)}`),
      api.get("/api/models").catch(() => []),
      api.get("/api/profile").catch(() => ({name: "default", default_model: "", api_base: ""})),
    ]);
  } catch (e) { toast(e.message, "err"); return; }

  const schema   = prompt.schema_ || {};
  const props    = schema.properties || {};
  const required = new Set(schema.required || []);
  const hasSchema = Object.keys(props).length > 0;
  const defaultModel = prompt.model || profile.default_model || "";

  const modelOptions = models.length
    ? `<datalist id="model-list">${models.map(m => `<option value="${escHtml(m)}">`).join("")}</datalist>`
    : "";
  const profileHint = profile.api_base
    ? `Profile: <strong>${escHtml(profile.name)}</strong> · api_base: <code>${escHtml(profile.api_base)}</code>`
    : `Profile: <strong>${escHtml(profile.name)}</strong> · uses env vars (OPENAI_API_KEY etc.)`;

  document.getElementById("run-form-area").innerHTML = `
    ${modelOptions}
    <div class="field-row">
      <label>Model <span class="field-required">*</span></label>
      <input id="run-model" value="${escHtml(defaultModel)}" placeholder="openai/gpt-4o-mini" list="model-list">
      <span class="field-hint">${profileHint}</span>
    </div>
    ${hasSchema
      ? Object.entries(props).map(([k, v]) => `
        <div class="field-row">
          <label>${escHtml(k)}${required.has(k) ? ' <span class="field-required">*</span>' : ""}</label>
          ${v.type === "integer" || v.type === "number"
            ? `<input id="field-${escHtml(k)}" type="number" placeholder="${escHtml(v.description || v.type)}">`
            : v.enum
            ? `<select id="field-${escHtml(k)}">${v.enum.map(o => `<option value="${escHtml(o)}">${escHtml(o)}</option>`).join("")}</select>`
            : `<input id="field-${escHtml(k)}" type="text" placeholder="${escHtml(v.description || v.type || "")}">`}
          ${v.description ? `<span class="field-hint">${escHtml(v.description)}</span>` : ""}
        </div>`).join("")
      : `<div class="field-row">
          <label>Your message</label>
          <textarea id="run-user-msg" placeholder="Ask anything…" style="min-height:80px"></textarea>
         </div>`}
    <button class="btn primary" id="run-btn">▶ Run</button>`;

  document.getElementById("run-btn").addEventListener("click", async () => {
    const model = document.getElementById("run-model").value.trim();
    if (!model) { toast("Model required", "err"); return; }

    const payload = {};
    for (const k of Object.keys(props)) {
      const el = document.getElementById(`field-${k}`);
      if (!el) continue;
      const t = props[k].type;
      payload[k] = (t === "integer") ? parseInt(el.value, 10) : (t === "number") ? parseFloat(el.value) : el.value;
    }

    const userMsgEl = document.getElementById("run-user-msg");
    const userMessage = userMsgEl?.value.trim() || undefined;

    document.getElementById("run-btn").disabled = true;
    document.getElementById("run-result").textContent = "Running…";
    document.getElementById("result-meta").textContent = "";

    try {
      const res = await api.post("/api/run", {
        prompt_id: id,
        payload,
        model_id: model,
        max_retries: 3,
        ...(userMessage ? {user_message: userMessage} : {}),
      });
      const el = document.getElementById("run-result");
      el.textContent = typeof res.data === "string"
        ? res.data
        : JSON.stringify(res.data ?? res.raw_output, null, 2);
      el.className = "run-result " + (res.ok ? "ok" : "err");
      document.getElementById("result-meta").innerHTML =
        `<span class="${res.ok ? "badge ok" : "badge err"}">${res.ok ? "OK" : "FAIL"}</span>
         <span>attempts: ${res.attempts}</span>`;
    } catch (e) {
      document.getElementById("run-result").textContent = "Error: " + e.message;
      document.getElementById("run-result").className = "run-result err";
    } finally {
      document.getElementById("run-btn").disabled = false;
    }
  });
}

// ── chains list ───────────────────────────────────────────────────────────────

async function chainsPage() {
  render(`<h1>Chains</h1>
<table class="prompt-table">
  <thead><tr><th>ID</th><th>Name</th><th>Steps</th><th></th></tr></thead>
  <tbody id="chain-rows"><tr><td colspan="4" style="color:var(--text-dim);padding:1.5rem">Loading…</td></tr></tbody>
</table>`);

  let chains = [];
  try { chains = await api.get("/api/chains"); } catch (e) {
    document.getElementById("chain-rows").innerHTML = `<tr><td colspan="4" style="color:var(--err)">${escHtml(e.message)}</td></tr>`;
    return;
  }

  if (!chains.length) {
    document.getElementById("chain-rows").innerHTML = `<tr><td colspan="4"><div class="empty"><h3>No chains</h3><p>Use <code>pgate chain add &lt;file.yaml&gt;</code> to register one.</p></div></td></tr>`;
    return;
  }

  document.getElementById("chain-rows").innerHTML = chains.map(c => `
    <tr>
      <td><a class="prompt-id" href="#/chains/${escHtml(c.id)}">${escHtml(c.id)}</a></td>
      <td style="color:var(--text-2)">${escHtml(c.name || "—")}</td>
      <td style="color:var(--text-dim)">${(c.steps || []).length}</td>
      <td><div class="actions">
        <a class="btn btn-sm secondary" href="#/chains/${escHtml(c.id)}">View / Run</a>
      </div></td>
    </tr>`).join("");
}

// ── chain detail + run ────────────────────────────────────────────────────────

async function chainDetailPage(id) {
  render(`<a class="back" href="#/chains">← Chains</a><h1>${escHtml(id)}</h1><p style="color:var(--text-dim)">Loading…</p>`);

  let chain;
  try { chain = await api.get(`/api/chains/${encodeURIComponent(id)}`); } catch (e) {
    toast(e.message, "err"); return;
  }

  const steps = chain.steps || [];
  document.getElementById("main").innerHTML = `
<a class="back" href="#/chains">← Chains</a>
<h1>${escHtml(chain.name || chain.id)}</h1>
${chain.description ? `<p style="color:var(--text-2);margin-bottom:1rem;font-size:13px">${escHtml(chain.description)}</p>` : ""}
<div class="run-layout">
  <div>
    <h2>Steps</h2>
    <ul class="chain-steps">
      ${steps.map((s, i) => `
        <li class="chain-step">
          <span class="step-num">${i + 1}</span>
          <div>
            <div class="step-id">${escHtml(s.prompt_id)}</div>
            ${s.model ? `<div style="font-size:11px;color:var(--text-dim)">${escHtml(s.model)}</div>` : ""}
          </div>
          ${s.output_as ? `<span class="step-arrow">→ ${escHtml(s.output_as)}</span>` : ""}
        </li>`).join("")}
    </ul>
    <div class="field-row">
      <label>Initial Payload (JSON)</label>
      <textarea class="mono" id="chain-payload" style="min-height:80px">{}</textarea>
    </div>
    <button class="btn primary" id="chain-run-btn">▶ Run Chain</button>
  </div>
  <div>
    <div class="pane-header"><h2>Result</h2></div>
    <pre class="run-result" id="chain-result">— press Run Chain —</pre>
    <div class="result-meta" id="chain-meta"></div>
  </div>
</div>`;

  document.getElementById("chain-run-btn").addEventListener("click", async () => {
    let payload = {};
    try { payload = JSON.parse(document.getElementById("chain-payload").value || "{}"); } catch (e) {
      toast("Invalid JSON payload", "err"); return;
    }
    document.getElementById("chain-run-btn").disabled = true;
    document.getElementById("chain-result").textContent = "Running chain…";
    try {
      const res = await api.post(`/api/chains/${encodeURIComponent(id)}/run`, {payload, max_retries_per_step: 3});
      const el = document.getElementById("chain-result");
      el.textContent = JSON.stringify(res.context, null, 2);
      el.className = "run-result " + (res.ok ? "ok" : "err");
      document.getElementById("chain-meta").innerHTML =
        `<span class="${res.ok ? "badge ok" : "badge err"}">${res.ok ? "OK" : "FAIL"}</span>
         <span>steps: ${res.steps_run}</span>
         ${res.failed_step ? `<span style="color:var(--err)">failed at: ${escHtml(res.failed_step)}</span>` : ""}`;
    } catch (e) {
      document.getElementById("chain-result").textContent = "Error: " + e.message;
      document.getElementById("chain-result").className = "run-result err";
    } finally {
      document.getElementById("chain-run-btn").disabled = false;
    }
  });
}

// ── boot ──────────────────────────────────────────────────────────────────────

document.body.insertAdjacentHTML("beforeend", `<div id="toast"></div>`);

window.addEventListener("hashchange", route);
route();
