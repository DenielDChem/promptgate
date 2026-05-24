/* PGate v0.4 — Single-Page Application */

const BASE = "";

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
  <div class="search-wrapper">
    <img src="img/icon_search.png" class="search-icon" alt="">
    <input class="search-input" id="search-q" placeholder="Search prompts…" type="search">
  </div>
  <span class="spacer"></span>
  <button class="btn" onclick="navigate('#/prompts/new')">
    <img src="img/icon_quill.png" class="btn-icon" alt=""> New Prompt
  </button>
</div>
<table class="prompt-table framed">
  <thead><tr><th>ID</th><th>Name</th><th>Tags</th><th>Model</th><th></th></tr></thead>
  <tbody id="prompt-rows"><tr><td colspan="5" style="color:var(--ink-faded);padding:1.5rem">Loading…</td></tr></tbody>
</table>`);

  let allPrompts = [];
  try {
    allPrompts = await api.get("/api/prompts");
  } catch (e) {
    document.getElementById("prompt-rows").innerHTML = `<tr><td colspan="5" style="color:var(--danger)">${escHtml(e.message)}</td></tr>`;
    return;
  }

  function renderRows(prompts) {
    if (!prompts.length) {
      document.getElementById("prompt-rows").innerHTML = `<tr><td colspan="5"><div class="empty"><h3>No prompts yet</h3><p>Click <strong>+ New Prompt</strong> to add one.</p></div></td></tr>`;
      return;
    }
    document.getElementById("prompt-rows").innerHTML = prompts.map(p => `
      <tr>
        <td><a class="prompt-id" href="#/prompts/${escHtml(p.id)}">${escHtml(p.id)}</a></td>
        <td>${escHtml(p.name || "—")}</td>
        <td>${(p.tags || []).map(t => `<span class="tag">${escHtml(t)}</span>`).join(" ")}</td>
        <td style="font-family:'Courier Prime',monospace;font-size:12px;color:var(--ink-faded)">${escHtml(p.model || "—")}</td>
        <td><div class="actions">
          <a class="btn btn-sm secondary" href="#/prompts/${escHtml(p.id)}/run">
            <img src="img/icon_run.png" class="btn-icon" alt=""> Run
          </a>
          <button class="btn btn-sm danger" onclick="deletePrompt('${escHtml(p.id)}')">
            <img src="img/icon_trash.png" class="btn-icon" alt="">
          </button>
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
<div class="split-pane">
  <div>
    <div class="field-row">
      <label>JSON (PromptConfig)</label>
      <textarea class="mono" id="yaml-src" placeholder='{"id":"my_v1","name":"My Prompt","template":"Hello {{ name }}","schema_":{"type":"object","properties":{"greeting":{"type":"string"}},"required":["greeting"]}}'></textarea>
    </div>
    <div style="display:flex;gap:.5rem;flex-wrap:wrap">
      <button class="btn" id="save-btn">
        <img src="img/icon_save.png" class="btn-icon" alt=""> Save
      </button>
      <button class="btn secondary" id="compile-btn">
        <img src="img/icon_scroll.png" class="btn-icon" alt=""> Compile
      </button>
      ${id ? `<a class="btn secondary" href="#/prompts/${escHtml(id)}/run"><img src="img/icon_run.png" class="btn-icon" alt=""> Run</a>` : ""}
    </div>
  </div>
  <div>
    <div class="pane-header"><h2>Compiled Contract</h2></div>
    <pre class="compile-preview" id="compile-out">— press Compile Preview —</pre>
  </div>
</div>`);

  if (id) {
    try {
      const p = await api.get(`/api/prompts/${encodeURIComponent(id)}`);
      document.getElementById("yaml-src").value = JSON.stringify(p, null, 2);
    } catch (e) { toast(e.message, "err"); }
  }

  document.getElementById("save-btn").addEventListener("click", async () => {
    const raw = document.getElementById("yaml-src").value.trim();
    try {
      const obj = JSON.parse(raw);
      await api.post("/api/prompts", obj);
      toast("Saved " + (obj.id || "prompt"));
      navigate("#/prompts");
    } catch (e) { toast(e.message, "err"); }
  });

  document.getElementById("compile-btn").addEventListener("click", async () => {
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
  });
}

// ── run page ──────────────────────────────────────────────────────────────────

async function runPage(id) {
  render(`<a class="back" href="#/prompts/${escHtml(id)}">← ${escHtml(id)}</a>
<h1>Run: ${escHtml(id)}</h1>
<div class="run-layout">
  <div class="run-form" id="run-form-area"><p style="color:var(--text-dim)">Loading schema…</p></div>
  <div>
    <div class="pane-header"><h2>Result</h2></div>
    <pre class="run-result" id="run-result">— press Run —</pre>
    <div class="result-meta" id="result-meta"></div>
  </div>
</div>`);

  let prompt;
  try {
    prompt = await api.get(`/api/prompts/${encodeURIComponent(id)}`);
  } catch (e) { toast(e.message, "err"); return; }

  const schema = prompt.schema_ || {};
  const props = schema.properties || {};
  const required = new Set(schema.required || []);
  const modelDefault = prompt.model || "";

  document.getElementById("run-form-area").innerHTML = `
    <div class="field-row">
      <label>Model</label>
      <input id="run-model" value="${escHtml(modelDefault)}" placeholder="openai/gpt-4o-mini">
    </div>
    ${Object.entries(props).map(([k, v]) => `
    <div class="field-row">
      <label>${escHtml(k)}${required.has(k) ? ' <span class="field-required">*</span>' : ""}</label>
      ${v.type === "integer" || v.type === "number"
        ? `<input id="field-${escHtml(k)}" type="number" placeholder="${escHtml(v.description || v.type)}">`
        : v.enum
        ? `<select id="field-${escHtml(k)}">${v.enum.map(o => `<option value="${escHtml(o)}">${escHtml(o)}</option>`).join("")}</select>`
        : `<input id="field-${escHtml(k)}" type="text" placeholder="${escHtml(v.description || v.type || "")}">`}
      ${v.description ? `<span class="field-hint">${escHtml(v.description)}</span>` : ""}
    </div>`).join("")}
    <button class="btn" id="run-btn">
      <img src="img/icon_run.png" class="btn-icon" alt=""> Run
    </button>`;

  document.getElementById("run-btn").addEventListener("click", async () => {
    const model = document.getElementById("run-model").value.trim();
    if (!model) { toast("Model required", "err"); return; }
    const payload = {};
    for (const k of Object.keys(props)) {
      const el = document.getElementById(`field-${k}`);
      if (!el) continue;
      const raw = el.value;
      const t = props[k].type;
      payload[k] = (t === "integer") ? parseInt(raw, 10) : (t === "number") ? parseFloat(raw) : raw;
    }
    document.getElementById("run-btn").disabled = true;
    document.getElementById("run-result").textContent = "Running…";
    document.getElementById("result-meta").textContent = "";
    try {
      const res = await api.post("/api/run", {
        prompt_id: id,
        payload,
        model_id: model,
        max_retries: 3,
      });
      const el = document.getElementById("run-result");
      el.textContent = JSON.stringify(res.data ?? res.raw_output, null, 2);
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
<table class="prompt-table framed">
  <thead><tr><th>ID</th><th>Name</th><th>Steps</th><th></th></tr></thead>
  <tbody id="chain-rows"><tr><td colspan="4" style="color:var(--ink-faded);padding:1.5rem">Loading…</td></tr></tbody>
</table>`);

  let chains = [];
  try { chains = await api.get("/api/chains"); } catch (e) {
    document.getElementById("chain-rows").innerHTML = `<tr><td colspan="4" style="color:var(--danger)">${escHtml(e.message)}</td></tr>`;
    return;
  }

  if (!chains.length) {
    document.getElementById("chain-rows").innerHTML = `<tr><td colspan="4"><div class="empty"><h3>No chains</h3><p>Use <code>pgate chain add &lt;file.yaml&gt;</code> to register one.</p></div></td></tr>`;
    return;
  }

  document.getElementById("chain-rows").innerHTML = chains.map(c => `
    <tr>
      <td><a class="prompt-id" href="#/chains/${escHtml(c.id)}">${escHtml(c.id)}</a></td>
      <td>${escHtml(c.name || "—")}</td>
      <td>${(c.steps || []).length}</td>
      <td><div class="actions">
        <a class="btn btn-sm secondary" href="#/chains/${escHtml(c.id)}">
          <img src="img/icon_chain.png" class="btn-icon" alt=""> View / Run
        </a>
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
${chain.description ? `<p style="color:var(--text-dim);margin-bottom:1rem">${escHtml(chain.description)}</p>` : ""}
<div class="run-layout">
  <div>
    <h2>Steps</h2>
    <ul class="chain-steps" style="margin-bottom:1rem">
      ${steps.map((s, i) => `
        <li class="chain-step">
          <span class="step-num">${i + 1}</span>
          <div>
            <div class="step-id">${escHtml(s.prompt_id)}</div>
            ${s.model ? `<div style="font-size:11px;color:var(--text-dim)">${escHtml(s.model)}</div>` : ""}
          </div>
          ${s.output_as ? `<span class="step-arrow">→ <code>${escHtml(s.output_as)}</code></span>` : ""}
        </li>`).join("")}
    </ul>
    <div class="field-row">
      <label>Initial Payload (JSON)</label>
      <textarea class="mono" id="chain-payload" style="min-height:100px">{}</textarea>
    </div>
    <button class="btn" id="chain-run-btn">
      <img src="img/icon_run.png" class="btn-icon" alt=""> Run Chain
    </button>
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
         ${res.failed_step ? `<span style="color:var(--danger)">failed at: ${escHtml(res.failed_step)}</span>` : ""}`;
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
