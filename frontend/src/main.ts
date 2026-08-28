import "./styles.css";

type FieldOption = { value: string | number; label: string };
type AssessmentField = {
  name: string;
  label: string;
  field_type: "number" | "select";
  hint?: string;
  minimum?: number;
  maximum?: number;
  options: FieldOption[];
};
type TriageResponse = {
  state_token: string;
  response: string;
  status: "collecting" | "ready" | "emergency" | "unsupported";
  condition?: string;
  required_fields: AssessmentField[];
  emergency: boolean;
  disclaimer: string;
  decision?: {
    action: "respond" | "ask_question" | "call_tool" | "explain_result" | "escalate" | "unsupported";
    tool?: string;
    source: "rules" | "qwen";
    missing_fields: string[];
    mode?: "conversation" | "wellness" | "symptom_interview" | "screening";
  };
  known_fields: Record<string, string | number>;
};
type Prediction = {
  condition: string;
  band: "lower" | "elevated" | "indeterminate";
  probability: number | null;
  model_version: string;
  validation_status: string;
  limitations: string[];
  report_token: string;
};
type ModelSummary = {
  slug: string;
  name: string;
  status: "validated" | "research" | "legacy" | "unavailable";
  version: string;
  description: string;
  metrics?: Record<string, number>;
};
type ToolSummary = {
  slug: string;
  name: string;
  kind: string;
  version: string;
  deployment_status: "available" | "experimental" | "planned" | "unavailable";
  callable: boolean;
  description: string;
  required_fields: string[];
  supported_population: string;
};
type ChatMessage = { text: string; role: "assistant" | "user" | "alert"; createdAt: number };
type PersistedSession = {
  version: 1;
  savedAt: number;
  stateToken: string | null;
  locale: string;
  messages: ChatMessage[];
  lastTriage: TriageResponse | null;
};

const STORAGE_KEY = "healthai.chat.v1";
const INITIAL_MESSAGE = "Describe what you are experiencing naturally. I can run a structured clinical-intake protocol, reason over the confirmed details, discuss general wellness, or prepare an evidence-backed research screening.";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const chatForm = document.querySelector<HTMLFormElement>("#chat-form")!;
const messageInput = document.querySelector<HTMLTextAreaElement>("#message-input")!;
const messages = document.querySelector<HTMLDivElement>("#messages")!;
const fieldsHost = document.querySelector<HTMLDivElement>("#assessment-fields")!;
const locale = document.querySelector<HTMLSelectElement>("#locale")!;
const resetButton = document.querySelector<HTMLButtonElement>("#reset-session")!;
const voiceButton = document.querySelector<HTMLButtonElement>("#voice-button")!;
const xrayButton = document.querySelector<HTMLButtonElement>("#xray-button")!;
const xrayInput = document.querySelector<HTMLInputElement>("#xray-input")!;
const composerStatus = document.querySelector<HTMLElement>("#composer-status")!;
const views = document.querySelectorAll<HTMLElement>("[data-view]");
const viewButtons = document.querySelectorAll<HTMLButtonElement>("[data-view-target]");
const primaryNavButtons = document.querySelectorAll<HTMLButtonElement>(".primary-nav [data-view-target]");
const pipelineState = document.querySelector<HTMLElement>("#pipeline-state")!;
const entityGrid = document.querySelector<HTMLElement>("#entity-grid")!;
const triagePanel = document.querySelector<HTMLElement>("#triage-panel")!;
const stageSafety = document.querySelector<HTMLButtonElement>("#stage-safety")!;
const stageExtraction = document.querySelector<HTMLElement>("#stage-extraction")!;
const stageOrchestration = document.querySelector<HTMLElement>("#stage-orchestration")!;
const stageVerification = document.querySelector<HTMLElement>("#stage-verification")!;
const stageButtons = document.querySelectorAll<HTMLButtonElement>("[data-stage-target]");
const pipelineSteps = [...document.querySelectorAll<HTMLElement>(".pipeline-stepper > span")];
const liveToolCount = document.querySelector<HTMLElement>("#live-tool-count")!;
const evaluationRuntime = document.querySelector<HTMLElement>("#evaluation-runtime")!;
const registryRuntime = document.querySelector<HTMLElement>("#registry-runtime")!;
const registryBody = document.querySelector<HTMLElement>("#model-registry-body")!;
const refreshEvaluation = document.querySelector<HTMLButtonElement>("#refresh-evaluation")!;
const researchButtons = document.querySelectorAll<HTMLButtonElement>("[data-research-target]");

let stateToken: string | null = null;
let reportToken: string | null = null;
let activeCondition: string | null = null;
let recorder: MediaRecorder | null = null;
let chunks: Blob[] = [];
let stopTimer: number | null = null;
let lastInputChannel = "Text";
let selectedXray: File | null = null;
let conversationLog: ChatMessage[] = [];
let lastTriage: TriageResponse | null = null;
let thinkingMessage: HTMLDivElement | null = null;
let thinkingTimer: number | null = null;

type VoiceButtonState = "ready" | "recording" | "transcribing" | "unavailable";

const setVoiceButtonState = (state: VoiceButtonState) => {
  const content = {
    ready: { icon: "mic", title: "Speak symptoms", detail: "Private · Moonshine ASR" },
    recording: { icon: "stop", title: "Stop recording", detail: "Listening · maximum 30 seconds" },
    transcribing: { icon: "graphic_eq", title: "Transcribing", detail: "On-device medical voice AI" },
    unavailable: { icon: "mic_off", title: "Voice unavailable", detail: "Run make dev-api-voice" },
  }[state];
  voiceButton.classList.toggle("recording", state === "recording");
  voiceButton.classList.toggle("transcribing", state === "transcribing");
  voiceButton.classList.toggle("unavailable", state === "unavailable");
  voiceButton.disabled = state === "transcribing" || state === "unavailable";
  voiceButton.innerHTML = `<span class="voice-orb-icon"><span class="material-symbols-outlined">${content.icon}</span></span><span class="voice-label"><strong>${content.title}</strong><small>${content.detail}</small></span><span class="voice-wave" aria-hidden="true"><i></i><i></i><i></i><i></i></span>`;
};

const escapeHtml = (value: string) => value.replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[character] ?? character));

const persistSession = () => {
  try {
    const payload: PersistedSession = {
      version: 1,
      savedAt: Date.now(),
      stateToken,
      locale: locale.value,
      messages: conversationLog.slice(-60),
      lastTriage,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Browsers can disable storage; the live session remains usable in memory.
  }
};

const conditionNames: Record<string, string> = {
  heart: "Heart risk",
  diabetes: "Early diabetes signs",
  kidney: "Kidney-disease pattern",
  liver: "Liver-disease pattern",
};
const conditionLabel = (condition?: string | null) => condition ? conditionNames[condition] ?? condition : "Pending";

if ("scrollRestoration" in history) history.scrollRestoration = "manual";

const showView = (name: string, updateHash = true) => {
  const target = [...views].some((view) => view.dataset.view === name) ? name : "lab";
  views.forEach((view) => {
    const active = view.dataset.view === target;
    view.hidden = !active;
    view.classList.toggle("active", active);
  });
  primaryNavButtons.forEach((button) => button.classList.toggle("active", button.dataset.viewTarget === target));
  if (updateHash) history.replaceState(null, "", target === "lab" ? location.pathname : `#${target}`);
  window.scrollTo({ top: 0, behavior: "auto" });
  window.setTimeout(() => window.scrollTo({ top: 0, behavior: "auto" }), 0);
  if (target === "assessment") window.setTimeout(() => messageInput.focus({ preventScroll: true }), 50);
};

viewButtons.forEach((button) => button.addEventListener("click", () => showView(button.dataset.viewTarget ?? "lab")));
const initialView = location.hash.slice(1);
showView(initialView || "lab", false);

const selectStageButton = (name: string) => stageButtons.forEach((button) => button.classList.toggle("selected", button.dataset.stageTarget === name));

const setStage = (index: number, status: "current" | "complete" = "current") => {
  const stages = [stageSafety, stageExtraction, stageOrchestration, stageVerification];
  stages.forEach((stage, stageIndex) => {
    stage.classList.toggle("done", stageIndex < index || (stageIndex === index && status === "complete"));
    stage.classList.toggle("active", stageIndex === index && status === "current");
  });
  pipelineSteps.forEach((step, stepIndex) => {
    step.classList.toggle("complete", stepIndex < index || (stepIndex === index && status === "complete"));
    step.classList.toggle("current", stepIndex === index && status === "current");
  });
};

const stageGuides: Record<string, { icon: string; kicker: string; title: string; copy: string; points: string[] }> = {
  safety: { icon: "security", kicker: "Stage 01", title: "Safety gate", copy: "Urgent-language rules run before extraction or model routing. A match bypasses every research tool.", points: ["Emergency rules are deterministic", "Escalation points to immediate human care", "No risk score is shown during escalation"] },
  extraction: { icon: "content_cut", kicker: "Stage 02", title: "Structured extraction", copy: "The current build identifies a supported intent and then asks for the exact schema required by that tool.", points: ["Text and reviewed voice transcripts supported", "No hidden or inferred clinical values", "Required fields stay visible before execution"] },
  orchestration: { icon: "account_tree", kicker: "Stage 03", title: "Allowlisted orchestration", copy: "Qwen handles conversation and proposes routes; only artifact-backed specialist tools can execute after deterministic policy validation.", points: ["Rules router remains the tested fallback", "Policy validation blocks incomplete or invented calls", "Legacy and unavailable models cannot be invoked"] },
  verification: { icon: "fact_check", kicker: "Stage 04", title: "Result verification", copy: "The result travels with its model version, validation status, limitations and exportable provenance.", points: ["Bounded screening language", "PDF and Excel reports", "No diagnostic or treatment claim"] },
};

stageButtons.forEach((button) => button.addEventListener("click", () => {
  const name = button.dataset.stageTarget ?? "extraction";
  const guide = stageGuides[name];
  selectStageButton(name);
  triagePanel.innerHTML = `<article class="triage-route stage-guide"><span class="material-symbols-outlined">${guide.icon}</span><small>${guide.kicker}</small><h3>${guide.title}</h3><p>${guide.copy}</p><ul>${guide.points.map((point) => `<li>${point}</li>`).join("")}</ul></article>`;
  triagePanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}));

researchButtons.forEach((button) => button.addEventListener("click", () => {
  const target = button.dataset.researchTarget;
  if (!target) return;
  researchButtons.forEach((item) => item.classList.toggle("active", item === button));
  document.querySelector<HTMLElement>(`#${target}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
}));

const renderTrace = (safety: "Guarded" | "Clear" | "Escalated", condition?: string | null, detail = "Message evaluated") => {
  entityGrid.innerHTML = `
    <article class="entity-card"><small>Input channel</small><strong>${escapeHtml(lastInputChannel)}</strong><span>${escapeHtml(detail)}</span></article>
    <article class="entity-card"><small>Safety status</small><strong>${safety}</strong><span>${safety === "Escalated" ? "Models bypassed" : "Emergency rules evaluated"}</span></article>
    <article class="entity-card"><small>Tool route</small><strong>${conditionLabel(condition)}</strong><span>${condition ? "Allowlisted tool selected" : "No tool invoked"}</span></article>`;
};

const renderTriageState = (result: TriageResponse) => {
  if (result.emergency) {
    pipelineState.textContent = "Safety escalation";
    setStage(0);
    selectStageButton("safety");
    renderTrace("Escalated", null, "Urgent language detected");
    triagePanel.innerHTML = `<article class="triage-alert"><span class="material-symbols-outlined">emergency</span><small>Immediate action</small><h3>Models were bypassed</h3><p>${escapeHtml(result.response)}</p><strong>India emergency services: 112</strong></article>`;
    return;
  }
  if (result.status === "ready" && result.condition) {
    pipelineState.textContent = "Tool selected";
    setStage(2);
    selectStageButton("orchestration");
    renderTrace("Clear", result.condition);
    const router = result.decision?.source === "qwen" ? "Qwen JSON router" : "Deterministic router";
    triagePanel.innerHTML = `<article class="triage-route"><span class="material-symbols-outlined">route</span><small>Allowlisted route · ${router}</small><h3>${conditionLabel(result.condition)}</h3><p>${result.required_fields.length} structured inputs are required before inference.</p><ul><li>Safety gate passed</li><li>Registry and schema policy passed</li><li>Human confirmation required</li></ul></article>`;
    return;
  }
  if (result.decision?.mode === "symptom_interview") {
    pipelineState.textContent = "Symptom follow-up";
    setStage(1);
    selectStageButton("extraction");
    renderTrace("Clear", null, "Non-diagnostic interview");
    const reasoner = result.decision.source === "qwen" ? "Qwen question selector" : "Deterministic protocol";
    triagePanel.innerHTML = `<article class="triage-route"><span class="material-symbols-outlined">clinical_notes</span><small>Clinical intake active · ${reasoner}</small><h3>Stateful symptom reasoning</h3><p>The intake tool accumulates confirmed measurements, timing, severity, associated symptoms and risk context before producing a bounded disposition.</p><ul><li>Partial answers preserved as structured evidence</li><li>Qwen selects within reviewed question pathways</li><li>Deterministic emergency and disposition policy enforced</li></ul></article>`;
    return;
  }
  pipelineState.textContent = "More context required";
  setStage(1);
  selectStageButton("extraction");
  renderTrace("Clear", null);
  triagePanel.innerHTML = `<div class="empty-state"><span class="material-symbols-outlined">forum</span><h3>Continue naturally</h3><p>Describe any symptom or wellness concern. HealthAI will run the safety gate, select a reviewed intake pathway and use a predictive model only when its required inputs are appropriate.</p></div>`;
};

const resetWorkspace = () => {
  lastInputChannel = "Text";
  pipelineState.textContent = "Safety gate ready";
  setStage(0);
  selectStageButton("safety");
  entityGrid.innerHTML = `<article class="entity-card"><small>Input channel</small><strong>Text or voice</strong><span>Awaiting message</span></article><article class="entity-card"><small>Safety status</small><strong>Guarded</strong><span>Runs before routing</span></article><article class="entity-card"><small>Tool route</small><strong>Pending</strong><span>No tool selected</span></article>`;
  const guide = stageGuides.safety;
  triagePanel.innerHTML = `<article class="triage-route stage-guide"><span class="material-symbols-outlined">${guide.icon}</span><small>${guide.kicker}</small><h3>${guide.title}</h3><p>${guide.copy}</p><ul>${guide.points.map((point) => `<li>${point}</li>`).join("")}</ul></article>`;
};

const addMessage = (text: string, role: "assistant" | "user" | "alert" = "assistant", save = true, createdAt = Date.now()) => {
  const element = document.createElement("div");
  element.className = `message ${role}`;
  element.innerHTML = role === "user"
    ? `<div><p>${escapeHtml(text)}</p><small>You · now</small></div>`
    : `<span class="assistant-avatar ${role === "alert" ? "" : "message-voice-avatar"}">${role === "alert" ? "!" : '<span class="material-symbols-outlined">graphic_eq</span>'}</span><div><p>${escapeHtml(text)}</p><small>${role === "alert" ? "Safety gate" : "HealthAI"} · now</small></div>`;
  messages.append(element);
  if (save) {
    conversationLog.push({ text, role, createdAt });
    persistSession();
  }
  messages.scrollTo({ top: messages.scrollHeight, behavior: "smooth" });
};

const beginThinking = () => {
  if (thinkingMessage) return;
  const labels = ["Checking safety signals", "Matching the right pathway", "Preparing a safe response"];
  let labelIndex = 0;
  const element = document.createElement("div");
  element.className = "message assistant thinking-message";
  element.setAttribute("role", "status");
  element.setAttribute("aria-label", "HealthAI is processing your message");
  element.innerHTML = `
    <span class="assistant-avatar message-voice-avatar thinking-avatar"><span class="material-symbols-outlined">neurology</span></span>
    <div class="thinking-bubble">
      <span class="thinking-label">${labels[0]}</span>
      <span class="thinking-dots" aria-hidden="true"><i></i><i></i><i></i></span>
      <small>HealthAI is processing · safety and routing controls active</small>
    </div>`;
  messages.append(element);
  thinkingMessage = element;
  thinkingTimer = window.setInterval(() => {
    labelIndex = (labelIndex + 1) % labels.length;
    element.querySelector<HTMLElement>(".thinking-label")!.textContent = labels[labelIndex];
  }, 900);
  messages.scrollTo({ top: messages.scrollHeight, behavior: "smooth" });
};

const endThinking = () => {
  if (thinkingTimer !== null) window.clearInterval(thinkingTimer);
  thinkingTimer = null;
  thinkingMessage?.remove();
  thinkingMessage = null;
};

const setBusy = (busy: boolean, label = "Structuring your message…") => {
  chatForm.classList.toggle("busy", busy);
  messageInput.disabled = busy;
  const availableInputs = voiceButton.disabled ? "text input" : "text or voice";
  composerStatus.textContent = busy ? label : `${locale.value === "hi" ? "हिन्दी" : "English"} · ${availableInputs}`;
};

const apiError = async (response: Response) => {
  try {
    const payload = await response.json();
    if (response.status === 429) return payload.detail ?? "Request limit reached. Please wait briefly and try again.";
    if (response.status >= 500) return "The medical reasoner took too long to respond. Your saved conversation is safe—please try again.";
    return payload.detail ?? "The request could not be completed.";
  } catch {
    return "The request could not be completed.";
  }
};

const submitTriage = async (text: string) => {
  setBusy(true);
  beginThinking();
  pipelineState.textContent = "Evaluating safety";
  const path = stateToken ? "/api/v1/triage/message" : "/api/v1/triage/start";
  const body: Record<string, string> = { message: text, locale: locale.value };
  if (stateToken) body.state_token = stateToken;
  try {
    const response = await fetch(`${apiBase}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(await apiError(response));
    const result = await response.json() as TriageResponse;
    stateToken = result.state_token;
    lastTriage = result;
    endThinking();
    addMessage(result.response, result.emergency ? "alert" : "assistant");
    renderTriageState(result);
    if (result.status === "ready" && result.condition) renderAssessment(result.condition, result.required_fields, result.known_fields);
    if (result.emergency) fieldsHost.hidden = true;
    persistSession();
  } catch (error) {
    endThinking();
    addMessage(error instanceof Error ? error.message : "The agent is temporarily unavailable.", "alert");
  } finally {
    endThinking();
    setBusy(false);
  }
};

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;
  lastInputChannel = messageInput.dataset.inputChannel === "voice" ? "Voice · Moonshine ASR" : "Text";
  delete messageInput.dataset.inputChannel;
  addMessage(text, "user");
  messageInput.value = "";
  await submitTriage(text);
});

locale.addEventListener("change", () => { setBusy(false); persistSession(); });
resetButton.addEventListener("click", () => {
  endThinking();
  stateToken = null;
  reportToken = null;
  activeCondition = null;
  selectedXray = null;
  conversationLog = [];
  lastTriage = null;
  localStorage.removeItem(STORAGE_KEY);
  xrayInput.value = "";
  fieldsHost.hidden = true;
  fieldsHost.replaceChildren();
  messages.innerHTML = `<div class="message assistant"><span class="assistant-avatar message-voice-avatar"><span class="material-symbols-outlined">graphic_eq</span></span><div><p>${INITIAL_MESSAGE}</p><small>HealthAI · now</small></div></div>`;
  resetWorkspace();
});

const renderAssessment = (condition: string, fields: AssessmentField[], knownFields: Record<string, string | number> = {}) => {
  activeCondition = condition;
  const form = document.createElement("form");
  form.className = "inline-assessment";
  form.innerHTML = `
    <div class="inline-head"><div><span>Tool selected</span><h3>${escapeHtml(conditionLabel(condition))}</h3></div><small>${fields.length} required inputs</small></div>
    <p class="review-copy">Enter reliable information and review every value before running this research model.</p>
    ${Object.keys(knownFields).length ? `<div class="prefill-note"><span class="material-symbols-outlined">auto_awesome</span><span><strong>${Object.keys(knownFields).length} values extracted</strong><small>Review every highlighted value before running the model.</small></span></div>` : ""}
    <div class="dynamic-fields">${fields.map((field) => renderField(field, knownFields[field.name])).join("")}</div>
    <label class="consent-check"><input type="checkbox" required><span>I confirm these values and understand this is not a diagnosis.</span></label>
    <button class="button primary full" type="submit">Run allowlisted tool <span>→</span></button>`;
  form.addEventListener("submit", handlePrediction);
  fieldsHost.replaceChildren(form);
  fieldsHost.hidden = false;
  setTimeout(() => fieldsHost.scrollIntoView({ behavior: "smooth", block: "nearest" }), 50);
};

const renderField = (field: AssessmentField, knownValue?: string | number) => {
  const common = `name="${field.name}" required aria-label="${escapeHtml(field.label)}"`;
  const hasKnownValue = knownValue !== undefined && knownValue !== null;
  const control = field.field_type === "select"
    ? `<select ${common} class="${hasKnownValue ? "ai-prefilled" : ""}"><option value="" ${hasKnownValue ? "" : "selected"} disabled>Select</option>${field.options.map((option) => `<option value="${option.value}" ${String(option.value) === String(knownValue) ? "selected" : ""}>${escapeHtml(option.label)}</option>`).join("")}</select>`
    : `<input ${common} class="${hasKnownValue ? "ai-prefilled" : ""}" type="number" step="any" ${field.minimum !== undefined ? `min="${field.minimum}"` : ""} ${field.maximum !== undefined ? `max="${field.maximum}"` : ""} ${hasKnownValue ? `value="${escapeHtml(String(knownValue))}"` : ""} placeholder="Enter value">`;
  return `<label><span>${escapeHtml(field.label)}${hasKnownValue ? '<em class="extracted-tag">AI extracted</em>' : ""}</span>${control}${field.hint ? `<small>${escapeHtml(field.hint)}</small>` : ""}</label>`;
};

async function handlePrediction(event: SubmitEvent) {
  event.preventDefault();
  if (!activeCondition) return;
  const form = event.currentTarget as HTMLFormElement;
  const formData = new FormData(form);
  const inputs: Record<string, number> = {};
  for (const [name, value] of formData.entries()) {
    if (name !== "consent") inputs[name] = Number(value);
  }
  const button = form.querySelector<HTMLButtonElement>("button[type=submit]")!;
  button.disabled = true;
  button.textContent = "Running verified tool…";
  pipelineState.textContent = "Running specialist tool";
  setStage(3);
  selectStageButton("verification");
  try {
    const response = await fetch(`${apiBase}/api/v1/assessments/${activeCondition}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ inputs, state_token: stateToken }),
    });
    if (!response.ok) throw new Error(await apiError(response));
    const result = await response.json() as Prediction;
    reportToken = result.report_token;
    renderResult(result);
  } catch (error) {
    addMessage(error instanceof Error ? error.message : "The research model could not run.", "alert");
    button.disabled = false;
    button.innerHTML = "Run allowlisted tool <span>→</span>";
    pipelineState.textContent = "Tool run failed";
    setStage(2);
    selectStageButton("orchestration");
  }
}

const renderResult = (result: Prediction) => {
  const probability = result.probability === null ? "Not available" : `${Math.round(result.probability * 100)}% model score`;
  const isImage = result.condition === "pneumonia";
  fieldsHost.innerHTML = `<div class="screening-result ${result.band}">
    <div class="result-signal"><span>${result.band === "elevated" ? "↑" : "✓"}</span></div>
    <div class="result-main"><span>${isImage ? "Pediatric X-ray research" : "Screening complete"} · ${escapeHtml(result.validation_status)}</span><h3>${result.band === "elevated" ? "Elevated pattern identified" : "No elevated pattern identified"}</h3><p>${probability}. ${isImage ? "This 28×28 benchmark model is not suitable for adults and cannot replace a radiologist." : "This result can be wrong and does not establish or rule out a condition."}</p>
      <div class="result-actions"><button data-export="pdf">Download PDF</button><button data-export="xlsx">Download Excel</button></div>
      <small>${escapeHtml(result.model_version)}</small>
    </div></div>`;
  fieldsHost.querySelectorAll<HTMLButtonElement>("[data-export]").forEach((button) => button.addEventListener("click", () => downloadReport(button.dataset.export!)));
  pipelineState.textContent = "Screening verified";
  setStage(3, "complete");
  selectStageButton("verification");
  triagePanel.innerHTML = `<article class="triage-route result-summary"><span class="material-symbols-outlined">fact_check</span><small>Screening complete</small><h3>${result.band === "elevated" ? "Elevated pattern" : "No elevated pattern"}</h3><p>${probability}. This is a research output, not a diagnosis.</p><ul><li>${escapeHtml(result.model_version)}</li><li>${escapeHtml(result.validation_status)}</li><li>PDF and Excel provenance available</li></ul></article>`;
};

xrayButton.addEventListener("click", () => xrayInput.click());

xrayInput.addEventListener("change", () => {
  const file = xrayInput.files?.[0] ?? null;
  if (!file) return;
  if (!["image/jpeg", "image/png"].includes(file.type) || file.size > 8 * 1024 * 1024) {
    addMessage("Choose a JPEG or PNG chest X-ray smaller than 8 MB.", "alert");
    xrayInput.value = "";
    return;
  }
  selectedXray = file;
  fieldsHost.hidden = false;
  fieldsHost.innerHTML = `<article class="image-review-card"><span class="material-symbols-outlined">radiology</span><div><small>Image selected · human confirmation required</small><h3>Pediatric chest X-ray research model</h3><p><strong>${escapeHtml(file.name)}</strong> · ${(file.size / 1024).toFixed(0)} KB</p><p>This tool was evaluated only on low-resolution pediatric benchmark images. It cannot diagnose pneumonia or interpret adult X-rays.</p><label class="consent-check"><input id="xray-consent" type="checkbox"><span>I confirm this is a pediatric chest X-ray and understand the research limitations.</span></label><div class="result-actions"><button id="run-xray" type="button" disabled>Run reviewed image tool</button><button id="cancel-xray" type="button">Cancel</button></div></div></article>`;
  const consent = fieldsHost.querySelector<HTMLInputElement>("#xray-consent")!;
  const run = fieldsHost.querySelector<HTMLButtonElement>("#run-xray")!;
  consent.addEventListener("change", () => { run.disabled = !consent.checked; });
  fieldsHost.querySelector<HTMLButtonElement>("#cancel-xray")!.addEventListener("click", () => {
    selectedXray = null;
    xrayInput.value = "";
    fieldsHost.hidden = true;
    fieldsHost.replaceChildren();
  });
  run.addEventListener("click", runPneumoniaImage);
  fieldsHost.scrollIntoView({ behavior: "smooth", block: "nearest" });
});

const runPneumoniaImage = async () => {
  if (!selectedXray) return;
  const run = fieldsHost.querySelector<HTMLButtonElement>("#run-xray")!;
  run.disabled = true;
  run.textContent = "Running pediatric image model…";
  pipelineState.textContent = "Running image specialist";
  setStage(3);
  selectStageButton("verification");
  lastInputChannel = "Reviewed chest X-ray";
  renderTrace("Clear", null, "Image consent confirmed");
  const body = new FormData();
  body.append("image", selectedXray);
  try {
    const response = await fetch(`${apiBase}/api/v1/images/pneumonia/predict`, { method: "POST", body, credentials: "include" });
    if (!response.ok) throw new Error(await apiError(response));
    const result = await response.json() as Prediction;
    reportToken = result.report_token;
    renderResult(result);
  } catch (error) {
    addMessage(error instanceof Error ? error.message : "The image research tool could not run.", "alert");
    run.disabled = false;
    run.textContent = "Run reviewed image tool";
  }
};

const downloadReport = async (format: string) => {
  if (!reportToken) return;
  try {
    const response = await fetch(`${apiBase}/api/v1/reports/${format}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ report_token: reportToken }),
    });
    if (!response.ok) throw new Error(await apiError(response));
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `healthai-report.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    addMessage(error instanceof Error ? error.message : "The report could not be generated.", "alert");
  }
};

const encodePcm16Wav = (samples: Float32Array, sampleRate: number): Blob => {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeText = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index));
  };
  writeText(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
};

const convertRecordingToWav = async (recording: Blob): Promise<Blob> => {
  const sourceContext = new AudioContext();
  try {
    const decoded = await sourceContext.decodeAudioData(await recording.arrayBuffer());
    const sampleRate = 16_000;
    const frameCount = Math.max(1, Math.ceil(decoded.duration * sampleRate));
    const offline = new OfflineAudioContext(1, frameCount, sampleRate);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const rendered = await offline.startRendering();
    return encodePcm16Wav(rendered.getChannelData(0), sampleRate);
  } finally {
    await sourceContext.close();
  }
};

voiceButton.addEventListener("click", async () => {
  if (recorder?.state === "recording") {
    recorder.stop();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    addMessage("Voice recording is not supported by this browser.", "alert");
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    chunks = [];
    recorder = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "" });
    recorder.addEventListener("dataavailable", (event) => { if (event.data.size) chunks.push(event.data); });
    recorder.addEventListener("stop", async () => {
      stream.getTracks().forEach((track) => track.stop());
      if (stopTimer) window.clearTimeout(stopTimer);
      setVoiceButtonState("transcribing");
      await uploadVoice(new Blob(chunks, { type: recorder?.mimeType || "audio/webm" }));
    });
    recorder.start();
    setVoiceButtonState("recording");
    composerStatus.textContent = "Recording · maximum 30 seconds";
    stopTimer = window.setTimeout(() => recorder?.stop(), 30_000);
  } catch {
    addMessage("Microphone access was not granted.", "alert");
  }
});

const uploadVoice = async (blob: Blob) => {
  setBusy(true, "Transcribing privately with Moonshine ASR…");
  let transcriptReady = false;
  try {
    const wav = await convertRecordingToWav(blob);
    const form = new FormData();
    form.append("audio", wav, "recording.wav");
    const response = await fetch(`${apiBase}/api/v1/voice/transcribe`, { method: "POST", body: form, credentials: "include" });
    if (!response.ok) throw new Error(await apiError(response));
    const result = await response.json() as { transcript: string };
    messageInput.value = result.transcript;
    messageInput.dataset.inputChannel = "voice";
    messageInput.focus();
    lastInputChannel = "Voice · Moonshine ASR";
    pipelineState.textContent = "Transcript ready for review";
    renderTrace("Guarded", null, "Transcript not sent yet");
    transcriptReady = true;
  } catch (error) {
    addMessage(error instanceof Error ? error.message : "Voice transcription is unavailable.", "alert");
  } finally {
    setVoiceButtonState("ready");
    setBusy(false);
    if (transcriptReady) composerStatus.textContent = "Voice transcript ready · review before sending";
  }
};

const setRuntimeBadge = (element: HTMLElement, state: "ready" | "failed" | "loading", label: string) => {
  element.classList.toggle("ready", state === "ready");
  element.classList.toggle("failed", state === "failed");
  element.innerHTML = `<i></i>${escapeHtml(label)}`;
};

const renderRegistry = (models: ModelSummary[], tools: ToolSummary[], voiceAvailable: boolean, qwenAvailable: boolean) => {
  const toolRows = tools.map((tool) => {
    const architecture = tool.kind === "predictive_model" ? "Specialist model" : tool.kind === "retrieval" ? "Bounded reasoner" : tool.kind;
    const role = tool.kind === "predictive_model" ? `Screening · ${tool.required_fields.length || "image"} inputs` : "Conversation support · no risk score";
    const runtime = tool.callable ? (tool.kind === "predictive_model" ? "CPU runtime" : "Qwen + policy gate") : "Blocked by evaluation gate";
    const status = tool.callable ? "Callable" : tool.deployment_status === "planned" ? "Planned · blocked" : "Unavailable";
    return `<tr><td><strong>${escapeHtml(tool.name)}</strong><small class="table-note">${escapeHtml(tool.description)}</small></td><td>${architecture}<small class="table-note">${escapeHtml(tool.version)}</small></td><td>${role}</td><td>${runtime}</td><td><span class="status-chip ${tool.callable ? "success" : "danger"}">${status}</span></td></tr>`;
  }).join("");
  const blockedRows = models.filter((model) => model.status === "legacy" && model.slug !== "pneumonia").map((model) => {
    const architecture = model.slug === "pneumonia" ? "Legacy Keras CNN" : "Legacy pickle";
    return `<tr><td><strong>${escapeHtml(model.name)}</strong><small class="table-note">${escapeHtml(model.description)}</small></td><td>${architecture}<small class="table-note">${escapeHtml(model.version)}</small></td><td>Provenance only</td><td>Not loaded</td><td><span class="status-chip danger">Blocked legacy</span></td></tr>`;
  }).join("");
  registryBody.innerHTML = `${toolRows}${blockedRows}<tr><td><strong>Moonshine ASR</strong><small class="table-note">Tiny Streaming English model</small></td><td>34M streaming</td><td>Reviewed voice transcript</td><td>Local CPU service</td><td><span class="status-chip ${voiceAvailable ? "success" : ""}">${voiceAvailable ? "Available" : "Separate service"}</span></td></tr><tr><td><strong>Qwen3-0.6B</strong><small class="table-note">Constrained JSON routing with deterministic fallback</small></td><td>Q8 GGUF · llama.cpp</td><td>Conversation, extraction and tool proposals</td><td>Docker Model Runner</td><td><span class="status-chip ${qwenAvailable ? "success" : ""}">${qwenAvailable ? "Active locally" : "Rules fallback"}</span></td></tr>`;
};

const loadRuntimeEvidence = async () => {
  setRuntimeBadge(evaluationRuntime, "loading", "Checking local runtime");
  setRuntimeBadge(registryRuntime, "loading", "Loading registry");
  refreshEvaluation.disabled = true;
  try {
    const [healthResponse, modelsResponse, toolsResponse] = await Promise.all([
      fetch(`${apiBase}/health`),
      fetch(`${apiBase}/api/v1/models`),
      fetch(`${apiBase}/api/v1/tools`),
    ]);
    if (!healthResponse.ok || !modelsResponse.ok || !toolsResponse.ok) throw new Error("Local runtime did not respond.");
    const health = await healthResponse.json() as { voice_available?: boolean; qwen_available?: boolean; orchestrator_backend?: string };
    const payload = await modelsResponse.json() as { models?: ModelSummary[] };
    const toolPayload = await toolsResponse.json() as { tools?: ToolSummary[] };
    const models = payload.models ?? [];
    const tools = toolPayload.tools ?? [];
    const callable = tools.filter((tool) => tool.callable);
    for (const model of models) {
      const badge = document.querySelector<HTMLElement>(`[data-model-status="${model.slug}"]`);
      if (!badge) continue;
      badge.textContent = model.status === "research" ? "Research model" : model.status;
      badge.classList.toggle("available", model.status === "research" || model.status === "validated");
    }
    liveToolCount.textContent = String(callable.length);
    renderRegistry(models, tools, Boolean(health.voice_available), Boolean(health.qwen_available));
    setRuntimeBadge(evaluationRuntime, "ready", `${callable.length} tools registered locally`);
    setRuntimeBadge(registryRuntime, "ready", `${tools.length} registered · ${callable.length} callable`);
    if (health.voice_available) {
      setVoiceButtonState("ready");
      voiceButton.setAttribute("aria-label", "Record medical symptoms for up to 30 seconds using local Moonshine ASR");
    } else {
      setVoiceButtonState("unavailable");
      voiceButton.setAttribute("aria-label", "Moonshine voice runs as a separate service and is not attached to this local API");
      composerStatus.textContent = `${locale.value === "hi" ? "हिन्दी" : "English"} · text input`;
    }
  } catch {
    setRuntimeBadge(evaluationRuntime, "failed", "Local runtime unavailable");
    setRuntimeBadge(registryRuntime, "failed", "Registry unavailable");
    liveToolCount.textContent = "—";
    setVoiceButtonState("unavailable");
    voiceButton.setAttribute("aria-label", "Medical voice AI is unavailable because the local API did not respond");
  } finally {
    refreshEvaluation.disabled = false;
  }
};

refreshEvaluation.addEventListener("click", loadRuntimeEvidence);
const restoreSession = () => {
  try {
    const restored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null") as PersistedSession | null;
    if (!restored || restored.version !== 1 || !Array.isArray(restored.messages) || restored.messages.length === 0) return;
    stateToken = restored.stateToken;
    lastTriage = restored.lastTriage;
    if (restored.locale === "en" || restored.locale === "hi") locale.value = restored.locale;
    conversationLog = restored.messages.slice(-60);
    messages.replaceChildren();
    conversationLog.forEach((message) => addMessage(message.text, message.role, false, message.createdAt));
    if (lastTriage) {
      renderTriageState(lastTriage);
      if (lastTriage.status === "ready" && lastTriage.condition) {
        renderAssessment(lastTriage.condition, lastTriage.required_fields, lastTriage.known_fields);
      }
    }
    composerStatus.textContent = `${locale.value === "hi" ? "हिन्दी" : "English"} · conversation restored from this browser`;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
};

restoreSession();
void loadRuntimeEvidence();
