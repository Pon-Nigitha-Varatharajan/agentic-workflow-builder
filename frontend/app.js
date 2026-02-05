// =========================
// Config
// =========================
const API_BASE = "http://127.0.0.1:8000";

// Allowed hackathon models
const MODELS = ["kimi-k2p5", "kimi-k2-instruct-0905"];
const CRITERIA_TYPES = ["contains", "regex", "json_valid"];
const CONTEXT_MODES = ["full", "code_only"];

// =========================
// DOM
// =========================
const apiBaseText = document.getElementById("api-base-text");
const btnRefresh = document.getElementById("btn-refresh");

const pageList = document.getElementById("page-list");
const pageEditor = document.getElementById("page-editor");

const toastEl = document.getElementById("toast");

const newWorkflowName = document.getElementById("new-workflow-name");
const btnCreateWorkflow = document.getElementById("btn-create-workflow");
const btnNewWorkflow = document.getElementById("btn-new-workflow");

const workflowListEl = document.getElementById("workflow-list");
const wfCountEl = document.getElementById("wf-count");

// editor
const btnBack = document.getElementById("btn-back");
const btnSaveWorkflow = document.getElementById("btn-save-workflow");
const btnDeleteWorkflow = document.getElementById("btn-delete-workflow");
const btnAddStep = document.getElementById("btn-add-step");
const editorTitle = document.getElementById("editor-title");
const editorSubtitle = document.getElementById("editor-subtitle");
const editorName = document.getElementById("editor-name");
const stepsContainer = document.getElementById("steps-container");
// run viewer (list page)
const runPanel = document.getElementById("run-panel");
const runMeta = document.getElementById("run-meta");
const runStatus = document.getElementById("run-status");
const runCurrentStep = document.getElementById("run-current-step");
const runOutput = document.getElementById("run-output");
const btnStopPoll = document.getElementById("btn-stop-poll");

apiBaseText.textContent = API_BASE;

// =========================
// State
// =========================
let workflows = [];
let currentWorkflow = null; // full workflow object with steps
let currentWorkflowId = null;

// =========================
// Helpers
// =========================
function showToast(msg, type = "ok") {
  toastEl.className = `toast ${type === "ok" ? "ok" : "err"}`;
  toastEl.textContent = msg;
  toastEl.classList.remove("hidden");
  setTimeout(() => toastEl.classList.add("hidden"), 2500);
}

function fmtDate(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

function goToList() {
  pageEditor.classList.add("hidden");
  pageList.classList.remove("hidden");
  currentWorkflow = null;
  currentWorkflowId = null;
  editorName.value = "";
  stepsContainer.innerHTML = "";
}

function goToEditor() {
  pageList.classList.add("hidden");
  pageEditor.classList.remove("hidden");
}

// =========================
// API
// =========================
async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `GET ${path} failed`);
  }
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `POST ${path} failed`);
  }
  return res.json();
}

async function apiPut(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `PUT ${path} failed`);
  }
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `DELETE ${path} failed`);
  }
  // some delete endpoints may return {} or no body
  try {
    return await res.json();
  } catch {
    return {};
  }
}

// =========================
// Render: Workflow List
// =========================
function renderWorkflowList() {
  workflowListEl.innerHTML = "";
  wfCountEl.textContent = `${workflows.length}`;

  if (workflows.length === 0) {
    const empty = document.createElement("div");
    empty.className = "muted small";
    empty.textContent = "No workflows yet. Create one above.";
    workflowListEl.appendChild(empty);
    return;
  }

  workflows.forEach((wf) => {
    const item = document.createElement("div");
    item.className = "list-item";

    const left = document.createElement("div");
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = wf.name;

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = `id=${wf.id} • created=${fmtDate(wf.created_at)} • steps=${wf.step_count ?? wf.steps?.length ?? "-"}`;

    left.appendChild(name);
    left.appendChild(meta);

    const right = document.createElement("div");
    right.className = "row gap";

    const btnOpen = document.createElement("button");
    btnOpen.className = "btn primary";
    btnOpen.textContent = "Open";
    btnOpen.onclick = () => openWorkflow(wf.id);

    // ✅ ADD THIS: Run button
    const btnRun = document.createElement("button");
    btnRun.className = "btn";
    btnRun.textContent = "Run";
    btnRun.onclick = () => runWorkflow(wf.id);

    const btnDel = document.createElement("button");
    btnDel.className = "btn danger";
    btnDel.textContent = "Delete";
    btnDel.onclick = () => deleteWorkflow(wf.id, wf.name);

    right.appendChild(btnOpen);
    right.appendChild(btnRun);
    right.appendChild(btnDel);

    item.appendChild(left);
    item.appendChild(right);
    workflowListEl.appendChild(item);
  });
}

// =========================
// Render: Steps Editor
// =========================
function renderSteps() {
  stepsContainer.innerHTML = "";

  const steps = currentWorkflow?.steps ?? [];
  if (steps.length === 0) {
    const empty = document.createElement("div");
    empty.className = "muted small";
    empty.textContent = "No steps yet. Click “Add Step”.";
    stepsContainer.appendChild(empty);
    return;
  }

  steps.forEach((step, idx) => {
    const card = document.createElement("div");
    card.className = "step-card";

    // top row: title + reorder controls
    const top = document.createElement("div");
    top.className = "step-top";

    const title = document.createElement("div");
    title.className = "step-title";
    title.textContent = `Step ${idx + 1} (order=${step.step_order})`;

    const controls = document.createElement("div");
    controls.className = "row gap";

    const up = document.createElement("button");
    up.className = "btn";
    up.textContent = "↑";
    up.disabled = idx === 0;
    up.onclick = () => moveStep(idx, -1);

    const down = document.createElement("button");
    down.className = "btn";
    down.textContent = "↓";
    down.disabled = idx === steps.length - 1;
    down.onclick = () => moveStep(idx, +1);

    const remove = document.createElement("button");
    remove.className = "btn danger";
    remove.textContent = "Remove";
    remove.onclick = () => removeStep(idx);

    controls.appendChild(up);
    controls.appendChild(down);
    controls.appendChild(remove);

    top.appendChild(title);
    top.appendChild(controls);

    // content fields
    const hr = document.createElement("div");
    hr.className = "hr";

    const gridTop = document.createElement("div");
    gridTop.className = "grid-3";

    // model
    const modelWrap = document.createElement("div");
    modelWrap.className = "kv";
    modelWrap.innerHTML = `<label class="label">Model</label>`;
    const modelSel = document.createElement("select");
    modelSel.className = "select";
    MODELS.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      if (step.model === m) opt.selected = true;
      modelSel.appendChild(opt);
    });
    modelSel.onchange = (e) => {
      step.model = e.target.value;
    };
    modelWrap.appendChild(modelSel);

    // context_mode
    const ctxWrap = document.createElement("div");
    ctxWrap.className = "kv";
    ctxWrap.innerHTML = `<label class="label">Context Mode</label>`;
    const ctxSel = document.createElement("select");
    ctxSel.className = "select";
    CONTEXT_MODES.forEach((cm) => {
      const opt = document.createElement("option");
      opt.value = cm;
      opt.textContent = cm;
      if (step.context_mode === cm) opt.selected = true;
      ctxSel.appendChild(opt);
    });
    ctxSel.onchange = (e) => {
      step.context_mode = e.target.value;
    };
    ctxWrap.appendChild(ctxSel);

    // retries
    const retryWrap = document.createElement("div");
    retryWrap.className = "kv";
    retryWrap.innerHTML = `<label class="label">Max Retries</label>`;
    const retryInput = document.createElement("input");
    retryInput.className = "input";
    retryInput.type = "number";
    retryInput.min = "0";
    retryInput.max = "10";
    retryInput.value = step.max_retries ?? 0;
    retryInput.oninput = (e) => {
      step.max_retries = parseInt(e.target.value || "0", 10);
    };
    retryWrap.appendChild(retryInput);

    gridTop.appendChild(modelWrap);
    gridTop.appendChild(ctxWrap);
    gridTop.appendChild(retryWrap);

    const gridMid = document.createElement("div");
    gridMid.className = "grid-2 mt-12";

    // criteria type
    const ctypeWrap = document.createElement("div");
    ctypeWrap.className = "kv";
    ctypeWrap.innerHTML = `<label class="label">Criteria Type</label>`;
    const ctypeSel = document.createElement("select");
    ctypeSel.className = "select";
    CRITERIA_TYPES.forEach((ct) => {
      const opt = document.createElement("option");
      opt.value = ct;
      opt.textContent = ct;
      if (step.criteria_type === ct) opt.selected = true;
      ctypeSel.appendChild(opt);
    });
    ctypeSel.onchange = (e) => {
      step.criteria_type = e.target.value;
      // if json_valid, criteria_value can be empty
      renderSteps(); // re-render to adjust placeholder
    };
    ctypeWrap.appendChild(ctypeSel);

    // criteria value
    const cvalWrap = document.createElement("div");
    cvalWrap.className = "kv";
    cvalWrap.innerHTML = `<label class="label">Criteria Value</label>`;
    const cvalInput = document.createElement("input");
    cvalInput.className = "input";
    cvalInput.value = step.criteria_value ?? "";
    cvalInput.placeholder =
      step.criteria_type === "contains"
        ? "keyword (e.g., pytest)"
        : step.criteria_type === "regex"
        ? "regex pattern (e.g., ```python[\\s\\S]*```)"
        : "leave empty for json_valid";
    cvalInput.disabled = step.criteria_type === "json_valid";
    cvalInput.oninput = (e) => {
      step.criteria_value = e.target.value;
    };
    cvalWrap.appendChild(cvalInput);

    gridMid.appendChild(ctypeWrap);
    gridMid.appendChild(cvalWrap);

    // prompt
    const promptWrap = document.createElement("div");
    promptWrap.className = "kv mt-12";
    promptWrap.innerHTML = `<label class="label">Prompt</label>`;
    const promptTa = document.createElement("textarea");
    promptTa.className = "textarea";
    promptTa.value = step.prompt ?? "";
    promptTa.placeholder = "Write what the LLM should do...";
    promptTa.oninput = (e) => {
      step.prompt = e.target.value;
    };
    promptWrap.appendChild(promptTa);

    card.appendChild(top);
    card.appendChild(hr);
    card.appendChild(gridTop);
    card.appendChild(gridMid);
    card.appendChild(promptWrap);

    stepsContainer.appendChild(card);
  });
}

// =========================
// Actions
// =========================
async function loadWorkflows() {
  try {
    workflows = await apiGet("/workflows");
    renderWorkflowList();
  } catch (e) {
    showToast(`Failed to load workflows: ${e.message}`, "err");
  }
}

async function createWorkflow() {
  const name = (newWorkflowName.value || "").trim();
  if (!name) {
    showToast("Please enter a workflow name.", "err");
    return;
  }

  try {
    const payload = { name, steps: [] };
    const created = await apiPost("/workflows", payload);
    showToast(`Created: ${created.name}`, "ok");
    newWorkflowName.value = "";
    await loadWorkflows();
  } catch (e) {
    showToast(`Create failed: ${e.message}`, "err");
  }
}

async function deleteWorkflow(id, name) {
  const ok = confirm(`Delete workflow "${name}"? This cannot be undone.`);
  if (!ok) return;

  try {
    await apiDelete(`/workflows/${id}`);
    showToast("Deleted workflow", "ok");
    await loadWorkflows();
  } catch (e) {
    showToast(`Delete failed: ${e.message}`, "err");
  }
}

async function openWorkflow(id) {
  try {
    const wf = await apiGet(`/workflows/${id}`);
    currentWorkflow = wf;
    currentWorkflowId = wf.id;

    editorTitle.textContent = "Workflow Editor";
    editorSubtitle.textContent = `id=${wf.id} • created=${fmtDate(wf.created_at)}`;

    editorName.value = wf.name ?? "";
    // ensure steps exist
    currentWorkflow.steps = (wf.steps ?? []).slice().sort((a, b) => a.step_order - b.step_order);

    goToEditor();
    renderSteps();
  } catch (e) {
    showToast(`Open failed: ${e.message}`, "err");
  }
}

function addStep() {
  if (!currentWorkflow) return;

  const steps = currentWorkflow.steps ?? [];
  const nextOrder = steps.length + 1;

  steps.push({
    // id/workflow_id will be assigned by backend on save
    step_order: nextOrder,
    model: MODELS[0],
    prompt: "",
    criteria_type: "contains",
    criteria_value: "SUCCESS",
    max_retries: 1,
    context_mode: "full",
  });

  currentWorkflow.steps = steps;
  renderSteps();
}

function removeStep(idx) {
  if (!currentWorkflow) return;
  currentWorkflow.steps.splice(idx, 1);
  // re-number step_order
  currentWorkflow.steps.forEach((s, i) => (s.step_order = i + 1));
  renderSteps();
}

function moveStep(idx, delta) {
  const steps = currentWorkflow.steps;
  const newIdx = idx + delta;
  if (newIdx < 0 || newIdx >= steps.length) return;

  const tmp = steps[idx];
  steps[idx] = steps[newIdx];
  steps[newIdx] = tmp;

  // re-number step_order
  steps.forEach((s, i) => (s.step_order = i + 1));
  renderSteps();
}

async function saveWorkflow() {
  if (!currentWorkflowId || !currentWorkflow) return;

  const name = (editorName.value || "").trim();
  if (!name) {
    showToast("Workflow name cannot be empty.", "err");
    return;
  }

  // basic validation
  for (const s of currentWorkflow.steps ?? []) {
    if (!MODELS.includes(s.model)) {
      showToast(`Unsupported model in step_order=${s.step_order}`, "err");
      return;
    }
    if (!s.prompt || !s.prompt.trim()) {
      showToast(`Step ${s.step_order} prompt is empty.`, "err");
      return;
    }
    if (!CRITERIA_TYPES.includes(s.criteria_type)) {
      showToast(`Step ${s.step_order} criteria_type invalid.`, "err");
      return;
    }
    if (s.criteria_type !== "json_valid" && (!s.criteria_value || !s.criteria_value.trim())) {
      showToast(`Step ${s.step_order} criteria_value required.`, "err");
      return;
    }
  }

  try {
    const payload = {
      name,
      steps: (currentWorkflow.steps ?? []).map((s) => ({
        step_order: s.step_order,
        model: s.model,
        prompt: s.prompt,
        criteria_type: s.criteria_type,
        criteria_value: s.criteria_type === "json_valid" ? "" : (s.criteria_value ?? ""),
        max_retries: s.max_retries ?? 0,
        context_mode: s.context_mode ?? "full",
      })),
    };

    const updated = await apiPut(`/workflows/${currentWorkflowId}`, payload);
    showToast("Saved workflow ✅", "ok");

    // refresh list view count/meta
    await loadWorkflows();

    // refresh editor data too (keeps IDs consistent)
    currentWorkflow = updated;
    currentWorkflow.steps = (updated.steps ?? []).slice().sort((a, b) => a.step_order - b.step_order);
    editorName.value = updated.name ?? "";
    editorSubtitle.textContent = `id=${updated.id} • created=${fmtDate(updated.created_at)}`;
    renderSteps();
  } catch (e) {
    showToast(`Save failed: ${e.message}`, "err");
  }
}
let pollTimer = null;

async function runWorkflow(workflowId) {
  try {
    // show panel immediately
    runPanel.classList.remove("hidden");
    runMeta.textContent = "Starting...";
    runStatus.textContent = "RUNNING";
    runCurrentStep.textContent = "—";
    runOutput.textContent = "—";

    // ✅ FIXED URL
    const res = await fetch(`${API_BASE}/runs/workflows/${workflowId}/run`, {
      method: "POST",
    });

    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || "Failed to start run");
    }

    const data = await res.json();
    const runId = data.run_id;

    runMeta.textContent = `run_id=${runId} • workflow_id=${workflowId}`;
    showToast(`Run started: ${runId}`, "ok");

    startPolling(runId);
  } catch (e) {
    showToast(`Run failed to start: ${e.message}`, "err");
    console.error(e);
  }
}

function startPolling(runId) {
  // stop any previous poll
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/runs/${runId}`);
      if (!res.ok) return;

      const run = await res.json();

      runStatus.textContent = run.status ?? "—";

      // Determine "current step" + latest output from run.steps
      const steps = run.steps ?? [];
      let current = null;

      // If still running, show the last step attempt; if completed, show last step
      if (steps.length > 0) {
        current = steps[steps.length - 1];
      }

      if (current) {
        runCurrentStep.textContent = `step_order=${current.step_order} • attempt=${current.attempt_no} • ${current.status}`;
        runOutput.textContent = current.output || current.error || "—";
      } else {
        runCurrentStep.textContent = "—";
        runOutput.textContent = "—";
      }
      renderRunHistory(run);

      // Stop polling when done
      if (run.status !== "RUNNING") {
        clearInterval(pollTimer);
        pollTimer = null;
        showToast(`Run finished: ${run.status}`, "ok");
      }
    } catch (e) {
      console.error("Polling error:", e);
    }
  }, 1000);
}

btnStopPoll.onclick = () => {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
  showToast("Polling stopped", "ok");
};

async function deleteCurrentWorkflow() {
  if (!currentWorkflowId || !currentWorkflow) return;
  const ok = confirm(`Delete workflow "${currentWorkflow.name}"? This cannot be undone.`);
  if (!ok) return;

  try {
    await apiDelete(`/workflows/${currentWorkflowId}`);
    showToast("Deleted workflow", "ok");
    goToList();
    await loadWorkflows();
  } catch (e) {
    showToast(`Delete failed: ${e.message}`, "err");
  }
}

// =========================
// Wire buttons
// =========================
btnRefresh.onclick = () => loadWorkflows();

btnNewWorkflow.onclick = () => {
  newWorkflowName.focus();
};

btnCreateWorkflow.onclick = () => createWorkflow();

btnBack.onclick = () => goToList();

btnAddStep.onclick = () => addStep();

btnSaveWorkflow.onclick = () => saveWorkflow();

btnDeleteWorkflow.onclick = () => deleteCurrentWorkflow();

// =========================
// Boot
// =========================
goToList();
loadWorkflows();
// =========================
// Render: Full Step History
// =========================
// Expects `run` shaped like your backend response from GET /runs/{run_id}:
// run = { id, workflow_id, status, started_at, ended_at, steps: [ {step_order, attempt_no, status, criteria_result, output, error, prompt_used, ...}, ... ] }
//
// Requires these DOM nodes to exist:
// const runStepsEl = document.getElementById("run-steps");   // container for history
// const runOutput  = document.getElementById("run-output");  // your "Latest Output" panel
// const runCurrentStep = document.getElementById("run-current-step"); // label
// const runStatus = document.getElementById("run-status");   // label

function escapeHtml(s) {
  return (s ?? "").toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function short(s, n = 160) {
  s = (s ?? "").toString();
  return s.length > n ? s.slice(0, n) + "…" : s;
}

// Pick the most recent RunStep row (highest step_order, then highest attempt_no)
function getLatestRunStep(run) {
  const arr = Array.isArray(run?.steps) ? run.steps : [];
  if (!arr.length) return null;
  return arr.slice().sort((a, b) => {
    if (a.step_order !== b.step_order) return a.step_order - b.step_order;
    return a.attempt_no - b.attempt_no;
  })[arr.length - 1];
}

// Group run.steps by step_order and sort attempts inside each group
function groupByStep(runSteps) {
  const groups = new Map();
  for (const rs of runSteps) {
    const k = rs.step_order ?? 0;
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(rs);
  }
  // sort keys
  const keys = Array.from(groups.keys()).sort((a, b) => a - b);
  // sort attempts for each step
  for (const k of keys) {
    groups.get(k).sort((a, b) => (a.attempt_no ?? 0) - (b.attempt_no ?? 0));
  }
  return { keys, groups };
}

/**
 * Renders full run history into #run-steps
 * - Shows each step (by step_order)
 * - Shows every attempt with status + criteria_result + error
 * - Click an attempt to view its full output in the "Latest Output" panel
 */
function renderRunHistory(run) {
  const runStepsEl = document.getElementById("run-steps");
  const runOutput = document.getElementById("run-output");
  const runCurrentStep = document.getElementById("run-current-step");
  const runStatus = document.getElementById("run-status");

  if (!runStepsEl) {
    console.error("Missing #run-steps element in HTML");
    return;
  }

  const stepsArr = Array.isArray(run?.steps) ? run.steps : [];
  runStepsEl.innerHTML = "";

  // Status + current step summary (optional)
  if (runStatus) runStatus.textContent = run?.status ?? "—";

  const latest = getLatestRunStep(run);
  if (runCurrentStep) {
    runCurrentStep.textContent = latest
      ? `step_order=${latest.step_order} • attempt=${latest.attempt_no} • ${latest.status}`
      : "—";
  }
  if (runOutput) runOutput.textContent = latest?.output ?? latest?.error ?? "—";

  if (stepsArr.length === 0) {
    runStepsEl.innerHTML = `<div class="muted small">No run steps yet. (Still starting?)</div>`;
    return;
  }

  const { keys, groups } = groupByStep(stepsArr);

  // Build UI
  for (const stepOrder of keys) {
    const attempts = groups.get(stepOrder);

    // Step container
    const stepBox = document.createElement("div");
    stepBox.className = "run-step-box";

    const header = document.createElement("div");
    header.className = "run-step-header";

    const title = document.createElement("div");
    title.className = "run-step-title";
    title.textContent = `Step ${stepOrder}`;

    // derive step result = last attempt status
    const lastAttempt = attempts[attempts.length - 1];
    const badge = document.createElement("span");
    badge.className = `badge ${String(lastAttempt.status).toLowerCase()}`;
    badge.textContent = lastAttempt.status;

    header.appendChild(title);
    header.appendChild(badge);

    const list = document.createElement("div");
    list.className = "run-attempts";

    // Attempts
    for (const a of attempts) {
      const row = document.createElement("div");
      row.className = "run-attempt-row";
      row.tabIndex = 0;

      const left = document.createElement("div");
      left.className = "run-attempt-left";
      left.innerHTML = `
        <div class="run-attempt-line">
          <span class="muted">Attempt</span> <b>#${a.attempt_no}</b>
          <span class="dot">•</span>
          <span class="status">${escapeHtml(a.status)}</span>
        </div>
        <div class="run-attempt-meta muted small">
          ${escapeHtml(a.criteria_result ?? "")}
          ${a.error ? ` <span class="dot">•</span> <span class="errtxt">${escapeHtml(short(a.error, 120))}</span>` : ""}
        </div>
      `;

      const right = document.createElement("div");
      right.className = "run-attempt-right";
      right.innerHTML = `<div class="muted small">Click to view output</div>`;

      row.appendChild(left);
      row.appendChild(right);

      // Clicking an attempt shows its output in the main output panel
      row.onclick = () => {
        if (runOutput) runOutput.textContent = a.output ?? a.error ?? "—";
        if (runCurrentStep) runCurrentStep.textContent = `step_order=${a.step_order} • attempt=${a.attempt_no} • ${a.status}`;
      };

      // Keyboard accessibility (Enter)
      row.onkeydown = (ev) => {
        if (ev.key === "Enter") row.click();
      };

      list.appendChild(row);
    }

    stepBox.appendChild(header);
    stepBox.appendChild(list);
    runStepsEl.appendChild(stepBox);
  }
}