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
  model_name: string;
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
  release: string;
  version: string;
  base_model: string;
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
const WARMUP_KEY = "healthai.reasoner-warm.v1";
const INITIAL_MESSAGE = "Describe what you are experiencing naturally. I can run a structured clinical-intake protocol, reason over the confirmed details, discuss general wellness, or prepare an evidence-backed research screening.";
const STARTER_PROMPTS_HTML = `<div class="starter-prompts" aria-label="Example questions">
  <button type="button" data-starter-prompt="I want to explore the heart-risk research screening."><span class="material-symbols-outlined">cardiology</span><span><strong>Explore heart risk</strong><small>Open Cardio 2.0 workflow</small></span><i>→</i></button>
  <button type="button" data-starter-prompt="Could the diabetes research screening fit my concern?"><span class="material-symbols-outlined">glucose</span><span><strong>Check diabetes signs</strong><small>Open Glyco 2.0 workflow</small></span><i>→</i></button>
  <button type="button" data-starter-prompt="I have kidney or liver lab results. Which research screening fits?"><span class="material-symbols-outlined">labs</span><span><strong>Review laboratory results</strong><small>Kidney or liver pathway</small></span><i>→</i></button>
</div>`;

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const warmReasoner = () => {
  try {
    const lastWarm = Number(sessionStorage.getItem(WARMUP_KEY) ?? 0);
    if (Date.now() - lastWarm < 10 * 60 * 1000) return;
    // Mark before dispatch to deduplicate reloads. Failure is intentionally silent:
    // warm-up is only a latency optimization and never creates conversation state.
    sessionStorage.setItem(WARMUP_KEY, String(Date.now()));
  } catch {
    // Storage can be disabled; one best-effort request is still safe.
  }
  void fetch(`${apiBase}/api/v1/runtime/warm`, {
    method: "POST",
    credentials: "include",
    keepalive: true,
  }).catch(() => undefined);
};

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
const modelsRuntime = document.querySelector<HTMLElement>("#models-runtime")!;
const modelsGallery = document.querySelector<HTMLElement>("#models-gallery")!;
const playgroundIdentity = document.querySelector<HTMLElement>("#playground-identity")!;
const playgroundStage = document.querySelector<HTMLElement>("#playground-stage")!;
const refreshModels = document.querySelector<HTMLButtonElement>("#refresh-models")!;
const exploreModels = document.querySelector<HTMLButtonElement>("#explore-models")!;
const modelFilterButtons = document.querySelectorAll<HTMLButtonElement>("[data-model-filter]");
const registryRuntime = document.querySelector<HTMLElement>("#registry-runtime")!;
const registryBody = document.querySelector<HTMLElement>("#model-registry-body")!;
const researchButtons = document.querySelectorAll<HTMLButtonElement>("[data-research-target]");
const simulationMessage = document.querySelector<HTMLTextAreaElement>("#sim-message")!;
const simulationRun = document.querySelector<HTMLButtonElement>("#run-simulation")!;
const simulationPresets = document.querySelectorAll<HTMLButtonElement>("[data-sim-prompt]");
const simulationStatus = document.querySelector<HTMLElement>("#sim-runtime-status")!;
const simulationTrace = document.querySelector<HTMLElement>("#sim-trace")!;
const simulationRequestState = document.querySelector<HTMLElement>("#sim-request-state")!;
const simulationLatency = document.querySelector<HTMLElement>("#sim-latency")!;
const simulationReasonerDetail = document.querySelector<HTMLElement>("#sim-reasoner-detail")!;
const simulationModelNodes = document.querySelectorAll<HTMLElement>("[data-model-node]");
const simulationRouter = document.querySelector<HTMLElement>("#sim-router")!;
const simulationAction = document.querySelector<HTMLElement>("#sim-action")!;
const simulationTool = document.querySelector<HTMLElement>("#sim-tool")!;
const simulationFields = document.querySelector<HTMLElement>("#sim-fields")!;
const simulationResponse = document.querySelector<HTMLElement>("#sim-response")!;
const architectureNodes = document.querySelectorAll<HTMLButtonElement>("[data-architecture-stage]");
const architectureInspector = document.querySelector<HTMLElement>("#architecture-inspector")!;
const contactForm = document.querySelector<HTMLFormElement>("#contact-form")!;
const contactReady = document.querySelector<HTMLElement>("#contact-ready")!;
const contactMailto = document.querySelector<HTMLAnchorElement>("#contact-mailto")!;

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
    ready: { icon: "mic", title: "Speak symptoms", detail: "HealthAI Voice 1.0 · private" },
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
  heart: "HealthAI Cardio 2.0",
  diabetes: "HealthAI Glyco 2.0",
  kidney: "HealthAI Renal 2.0",
  liver: "HealthAI Hepatic 2.0",
};
const conditionLabel = (condition?: string | null) => condition ? conditionNames[condition] ?? condition : "Pending";

if ("scrollRestoration" in history) history.scrollRestoration = "manual";

const showView = (name: string, updateHash = true) => {
  const requested = name === "evaluation" ? "models" : name;
  const target = [...views].some((view) => view.dataset.view === requested) ? requested : "lab";
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

// Start the private reasoner while the visitor is still reading the landing page,
// just after the first visual render has had an opportunity to paint.
window.setTimeout(warmReasoner, 400);

viewButtons.forEach((button) => button.addEventListener("click", () => showView(button.dataset.viewTarget ?? "lab")));
const initialView = location.hash.slice(1);
showView(initialView || "lab", initialView === "evaluation");
window.addEventListener("hashchange", () => {
  const requestedView = location.hash.slice(1) || "lab";
  showView(requestedView, requestedView === "evaluation");
});

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

const architectureDetails: Record<string, { icon: string; kicker: string; title: string; copy: string; facts: [string, string][] }> = {
  safety: { icon: "security", kicker: "Stage 01 · deterministic policy", title: "Emergency language pre-empts every model.", copy: "This rule engine executes before Qwen, symptom protocols, or ONNX inference. A match produces an escalation response and later stages are bypassed.", facts: [["Input", "Normalized user text"], ["Authority", "Deterministic rules"], ["Failure mode", "Bypass all models"]] },
  extraction: { icon: "data_object", kicker: "Stage 02 · evidence-bound state", title: "Only explicit evidence enters typed state.", copy: "The router may extract values only when supported by the user’s text. Pydantic contracts and field evidence prevent invented measurements from reaching a specialist tool.", facts: [["Input", "Reviewed text / transcript"], ["Contract", "TriageResponse schema"], ["Output", "Known and missing fields"]] },
  orchestration: { icon: "account_tree", kicker: "Stage 03 · registry authorization", title: "A proposal is not permission to execute.", copy: "HealthAI Reasoner or the deterministic fallback can propose an action. The policy layer accepts only registered tool slugs with complete, schema-valid arguments.", facts: [["Proposal", "Rules or Qwen JSON"], ["Authority", "Tool registry"], ["Fallback", "Fail closed"]] },
  verification: { icon: "fact_check", kicker: "Stage 04 · bounded provenance", title: "The output travels with its evidence boundary.", copy: "Responses and model results expose the selected action, validation status, release ID, limitations, and report provenance instead of presenting generated text as a clinical fact.", facts: [["Runtime", "Typed API response"], ["Models", "Versioned ONNX"], ["Boundary", "Not a diagnosis"]] },
};

const renderArchitectureDetail = (name: string) => {
  const detail = architectureDetails[name] ?? architectureDetails.safety;
  architectureNodes.forEach((node) => {
    const active = node.dataset.architectureStage === name;
    node.classList.toggle("active", active);
    node.setAttribute("aria-selected", String(active));
  });
  architectureInspector.innerHTML = `<div class="inspector-signal"><span class="material-symbols-outlined">${detail.icon}</span><i></i></div><small>${detail.kicker}</small><h3>${detail.title}</h3><p>${detail.copy}</p><dl>${detail.facts.map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join("")}</dl>`;
};

architectureNodes.forEach((node) => node.addEventListener("click", () => renderArchitectureDetail(node.dataset.architectureStage ?? "safety")));

const waitForSimulationFrame = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));
let architectureAutoplay = true;
let architectureAutoTimer: number | null = null;
let architectureRunId = 0;

type ArchitectureRoute = {
  model: "heart" | "diabetes" | "kidney" | "liver" | "pneumonia" | "general";
  label: string;
  behavior: string;
  contract: string;
  reason: string;
  signals: string[];
};

const findArchitectureRoute = (message: string): ArchitectureRoute => {
  const text = message.toLowerCase();
  const signals = [
    [/x-?ray|radiograph|pneumonia/, "chest imaging"],
    [/thirst|urinat|glucose|sugar|diabet/, "metabolic"],
    [/creatinine|kidney|renal|egfr/, "renal"],
    [/bilirubin|liver|hepatic|jaundice/, "hepatic"],
    [/heart|cardiac|blood pressure|hypertension|cholesterol/, "cardiovascular"],
    [/fever|cough|sore throat|headache|acidity|reflux/, "symptom intake"],
  ].filter(([pattern]) => (pattern as RegExp).test(text)).map(([, label]) => label as string);
  const detected = signals.length ? signals : ["general concern"];
  if (/x-?ray|radiograph|pneumonia/.test(text)) return { model: "pneumonia", label: "HealthAI PulmoVision 1.0", behavior: "Request image + metadata", contract: "Chest X-ray upload", signals: detected, reason: "Imaging language selects the gated pediatric chest X-ray workflow; text alone never produces an image prediction." };
  if (/thirst|urinat|glucose|sugar|diabet/.test(text)) return { model: "diabetes", label: "HealthAI Glyco 2.0", behavior: "Open structured screening", contract: "16 questionnaire fields", signals: detected, reason: "Metabolic signals make Glyco 2.0 the highest-specificity candidate. The HealthAI Reasoning Model proposes the route; the specialist owns the numerical estimate." };
  if (/creatinine|kidney|renal|egfr/.test(text)) return { model: "kidney", label: "HealthAI Renal 2.0", behavior: "Collect laboratory inputs", contract: "24 clinical fields", signals: detected, reason: "Renal measurements map to the reviewed Renal 2.0 schema instead of asking the language model to estimate disease risk." };
  if (/bilirubin|liver|hepatic|jaundice/.test(text)) return { model: "liver", label: "HealthAI Hepatic 2.0", behavior: "Collect laboratory inputs", contract: "10 laboratory fields", signals: detected, reason: "Hepatic terminology selects the tabular specialist and its explicit laboratory contract." };
  if (/heart|cardiac|blood pressure|hypertension|cholesterol/.test(text)) return { model: "heart", label: "HealthAI Cardio 2.0", behavior: "Open structured screening", contract: "13 clinical fields", signals: detected, reason: "Cardiovascular intent routes to Cardio 2.0. The reasoner organizes the request but does not replace the validated tabular estimator." };
  return { model: "general", label: "Stateful clinical intake", behavior: "Ask one contextual question", contract: "Symptoms + time + severity", signals: detected, reason: "No specialist input contract is satisfied yet, so the reasoning path gathers context rather than forcing an unrelated disease model." };
};

const resetArchitectureSimulation = () => {
  simulationTrace.classList.remove("running", "complete");
  simulationTrace.querySelectorAll<HTMLElement>("[data-sim-stage]").forEach((node) => node.classList.remove("active", "complete"));
  simulationModelNodes.forEach((node) => node.classList.remove("candidate", "selected"));
  simulationRouter.textContent = "—";
  simulationAction.textContent = "—";
  simulationTool.textContent = "—";
  simulationFields.textContent = "—";
  simulationReasonerDetail.textContent = "Intent + candidate tools";
};

const runLandingSimulation = async (automated = false) => {
  const message = simulationMessage.value.trim();
  if (message.length < 2) {
    simulationMessage.focus();
    return;
  }
  const runId = ++architectureRunId;
  resetArchitectureSimulation();
  simulationTrace.classList.add("running");
  simulationStatus.className = "runtime-link-state running";
  simulationStatus.innerHTML = `<i></i> ${automated ? "Autoplay routing" : "Mapping your message"}`;
  simulationRequestState.textContent = "Reading message signals";
  simulationLatency.textContent = automated ? "AUTO / ROUTING" : "MANUAL / ROUTING";
  simulationResponse.textContent = "Following the model path…";
  const route = findArchitectureRoute(message);
  const origin = simulationTrace.querySelector<HTMLElement>('[data-sim-stage="0"]')!;
  const reasoner = simulationTrace.querySelector<HTMLElement>('[data-sim-stage="1"]')!;
  origin.classList.add("active");
  await waitForSimulationFrame(330);
  if (runId !== architectureRunId) return;
  origin.classList.add("complete");
  reasoner.classList.add("active");
  simulationReasonerDetail.textContent = `Candidates: ${route.signals.join(" · ")}`;
  simulationRouter.textContent = route.signals.join(" · ");
  simulationModelNodes.forEach((node) => {
    if (node.dataset.modelNode === route.model || node.dataset.modelNode === "general") node.classList.add("candidate");
  });
  await waitForSimulationFrame(520);
  if (runId !== architectureRunId) return;
  reasoner.classList.add("complete");
  simulationModelNodes.forEach((node) => node.classList.toggle("selected", node.dataset.modelNode === route.model));
  simulationAction.textContent = route.behavior;
  simulationTool.textContent = route.label;
  simulationFields.textContent = route.contract;
  simulationResponse.textContent = route.reason;
  simulationRequestState.textContent = `${route.label} selected`;
  const activePreset = [...simulationPresets].find((button) => button.classList.contains("active"));
  simulationLatency.textContent = automated ? `AUTO / ${activePreset?.textContent?.trim().toUpperCase() ?? "READY"}` : "MANUAL / READY";
  simulationTrace.classList.remove("running");
  simulationTrace.classList.add("complete");
  simulationStatus.className = "runtime-link-state ready";
  simulationStatus.innerHTML = `<i></i> ${automated ? "Autoplay · next path queued" : "Manual path ready"}`;
};

const stopArchitectureAutoplay = () => {
  architectureAutoplay = false;
  if (architectureAutoTimer !== null) window.clearTimeout(architectureAutoTimer);
  architectureAutoTimer = null;
  architectureRunId += 1;
};

const selectArchitecturePreset = (button: HTMLButtonElement) => {
  simulationPresets.forEach((item) => item.classList.toggle("active", item === button));
  simulationMessage.value = button.dataset.simPrompt ?? "";
};

const queueArchitectureAutoplay = (index = 0, delay = 700) => {
  if (!architectureAutoplay || !simulationPresets.length) return;
  architectureAutoTimer = window.setTimeout(async () => {
    if (!architectureAutoplay) return;
    const button = simulationPresets[index % simulationPresets.length];
    selectArchitecturePreset(button);
    await runLandingSimulation(true);
    if (architectureAutoplay) queueArchitectureAutoplay((index + 1) % simulationPresets.length, 3600);
  }, delay);
};

simulationPresets.forEach((button) => button.addEventListener("click", () => {
  stopArchitectureAutoplay();
  selectArchitecturePreset(button);
  void runLandingSimulation(false);
}));
simulationMessage.addEventListener("input", () => {
  if (architectureAutoplay) {
    stopArchitectureAutoplay();
    simulationStatus.className = "runtime-link-state ready";
    simulationStatus.innerHTML = "<i></i> Manual mode";
  }
});
simulationRun.addEventListener("click", () => {
  stopArchitectureAutoplay();
  void runLandingSimulation(false);
});
queueArchitectureAutoplay();

contactForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!contactForm.reportValidity()) return;
  const data = new FormData(contactForm);
  const name = String(data.get("name") ?? "").trim();
  const replyEmail = String(data.get("email") ?? "").trim();
  const topic = String(data.get("topic") ?? "Support");
  const message = String(data.get("message") ?? "").trim();
  const subject = `[HealthAI Agent Lab] ${topic}`;
  const body = `Name: ${name}\nReply email: ${replyEmail}\nTopic: ${topic}\n\n${message}`;
  contactMailto.href = `mailto:SauravMukherjee928@gmail.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  contactReady.hidden = false;
  contactReady.scrollIntoView({ behavior: "smooth", block: "nearest" });
});

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
  messages.querySelector(".starter-prompts")?.remove();
  lastInputChannel = messageInput.dataset.inputChannel === "voice" ? "Voice · HealthAI Voice 1.0" : "Text";
  delete messageInput.dataset.inputChannel;
  addMessage(text, "user");
  messageInput.value = "";
  await submitTriage(text);
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  if (chatForm.classList.contains("busy") || !messageInput.value.trim()) return;
  chatForm.requestSubmit();
});

messages.addEventListener("click", async (event) => {
  const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-starter-prompt]");
  if (!button || chatForm.classList.contains("busy")) return;
  const text = button.dataset.starterPrompt?.trim();
  if (!text) return;
  messages.querySelectorAll<HTMLButtonElement>("[data-starter-prompt]").forEach((item) => { item.disabled = true; });
  messages.querySelector(".starter-prompts")?.remove();
  lastInputChannel = "Starter question";
  addMessage(text, "user");
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
  messages.innerHTML = `<div class="message assistant"><span class="assistant-avatar message-voice-avatar"><span class="material-symbols-outlined">graphic_eq</span></span><div><p>${INITIAL_MESSAGE}</p><small>HealthAI · now</small></div></div>${STARTER_PROMPTS_HTML}`;
  resetWorkspace();
});

const renderAssessment = (condition: string, fields: AssessmentField[], knownFields: Record<string, string | number> = {}) => {
  activeCondition = condition;
  const form = document.createElement("form");
  form.className = "inline-assessment";
  form.innerHTML = `
    <div class="inline-head"><div><span>Tool selected</span><h3>${escapeHtml(conditionLabel(condition))}</h3></div><div class="assessment-head-actions"><small>${fields.length} required inputs</small><button class="sample-data-button" type="button"><span class="material-symbols-outlined">science</span>Load test data</button></div></div>
    <p class="review-copy">Enter reliable information and review every value before running this research model.</p>
    ${Object.keys(knownFields).length ? `<div class="prefill-note"><span class="material-symbols-outlined">auto_awesome</span><span><strong>${Object.keys(knownFields).length} values extracted</strong><small>Review every highlighted value before running the model.</small></span></div>` : ""}
    <div class="dynamic-fields">${fields.map((field) => renderField(field, knownFields[field.name])).join("")}</div>
    <label class="consent-check"><input type="checkbox" required><span>I confirm these values and understand this is not a diagnosis.</span></label>
    <button class="button primary full" type="submit">Run allowlisted tool <span>→</span></button>`;
  form.addEventListener("submit", handlePrediction);
  form.querySelector<HTMLButtonElement>(".sample-data-button")!.addEventListener("click", () => loadTestData(form, fields));
  fieldsHost.replaceChildren(form);
  fieldsHost.hidden = false;
  setTimeout(() => fieldsHost.scrollIntoView({ behavior: "smooth", block: "nearest" }), 50);
};

const LOWER_PATTERN_TEST_VALUES: Record<string, number> = {
  age: 48, sex: 0, gender: 0, chest_pain: 3, resting_bp: 128, serum_cholesterol: 210,
  fasting_blood_sugar: 0, resting_ecg: 0, max_heart_rate: 158, exercise_angina: 0,
  oldpeak: 0.8, st_slope: 1, major_vessels: 0, thal: 3,
  blood_pressure: 78, specific_gravity: 1.02, albumin: 0, sugar: 0, red_blood_cells: 0,
  pus_cell: 0, pus_cell_clumps: 0, bacteria: 0, blood_glucose_random: 105, blood_urea: 32,
  serum_creatinine: 1.0, sodium: 139, potassium: 4.3, hemoglobin: 14.2,
  packed_cell_volume: 43, white_blood_cell_count: 7600, red_blood_cell_count: 4.8,
  hypertension: 0, diabetes_mellitus: 0, coronary_artery_disease: 0, appetite: 0,
  pedal_edema: 0, anemia: 0, total_bilirubin: 0.9, direct_bilirubin: 0.2,
  alkaline_phosphatase: 190, alanine_aminotransferase: 28, aspartate_aminotransferase: 25,
  total_proteins: 7.1, albumin_globulin_ratio: 1.2,
  polyuria: 0, polydipsia: 0, sudden_weight_loss: 0, weakness: 0, polyphagia: 0,
  genital_thrush: 0, visual_blurring: 0, itching: 0, irritability: 0, delayed_healing: 0,
  partial_paresis: 0, muscle_stiffness: 0, alopecia: 0, obesity: 0,
};

const ELEVATED_PATTERN_TEST_VALUES: Record<string, Record<string, number>> = {
  heart: {
    age: 68, sex: 1, chest_pain: 4, resting_bp: 180, serum_cholesterol: 330,
    fasting_blood_sugar: 1, resting_ecg: 2, max_heart_rate: 88, exercise_angina: 1,
    oldpeak: 4.5, st_slope: 3, major_vessels: 3, thal: 7,
  },
  diabetes: {
    age: 58, gender: 1, polyuria: 1, polydipsia: 1, sudden_weight_loss: 1,
    weakness: 1, polyphagia: 1, genital_thrush: 1, visual_blurring: 1, itching: 1,
    irritability: 1, delayed_healing: 1, partial_paresis: 1, muscle_stiffness: 1,
    alopecia: 0, obesity: 1,
  },
  kidney: {
    age: 67, blood_pressure: 160, specific_gravity: 1.005, albumin: 4, sugar: 3,
    red_blood_cells: 1, pus_cell: 1, pus_cell_clumps: 1, bacteria: 1,
    blood_glucose_random: 260, blood_urea: 145, serum_creatinine: 7.2, sodium: 126,
    potassium: 6.1, hemoglobin: 8.4, packed_cell_volume: 27,
    white_blood_cell_count: 13800, red_blood_cell_count: 3.1, hypertension: 1,
    diabetes_mellitus: 1, coronary_artery_disease: 1, appetite: 1, pedal_edema: 1, anemia: 1,
  },
  liver: {
    age: 62, gender: 1, total_bilirubin: 8.4, direct_bilirubin: 4.8,
    alkaline_phosphatase: 610, alanine_aminotransferase: 185,
    aspartate_aminotransferase: 240, total_proteins: 5.2, albumin: 2.1,
    albumin_globulin_ratio: 0.55,
  },
};

const loadTestData = (form: HTMLFormElement, fields: AssessmentField[], condition = activeCondition) => {
  const fixtureKind = Math.random() < 0.5 ? "lower" : "elevated";
  const values = fixtureKind === "elevated" && condition
    ? { ...LOWER_PATTERN_TEST_VALUES, ...(ELEVATED_PATTERN_TEST_VALUES[condition] ?? {}) }
    : LOWER_PATTERN_TEST_VALUES;
  fields.forEach((field) => {
    const control = form.elements.namedItem(field.name) as HTMLInputElement | HTMLSelectElement | null;
    if (!control) return;
    const fallback = field.field_type === "select"
      ? field.options[0]?.value
      : ((field.minimum ?? 0) + (field.maximum ?? 100)) / 2;
    const conditionSpecific = condition === "liver" && fixtureKind === "lower" && field.name === "albumin" ? 4.1 : undefined;
    control.value = String(conditionSpecific ?? values[field.name] ?? fallback ?? "");
    control.classList.add("sample-prefilled");
    control.dispatchEvent(new Event("change", { bubbles: true }));
  });
  const consent = form.querySelector<HTMLInputElement>(".consent-check input");
  if (consent) consent.checked = false;
  const note = form.querySelector<HTMLElement>(".sample-data-note") ?? document.createElement("div");
  note.className = "sample-data-note";
  note.innerHTML = `<span class="material-symbols-outlined">dataset</span><span><strong>${fixtureKind === "elevated" ? "Elevated-pattern" : "Lower-pattern"} test values loaded</strong><small>These are synthetic demonstration values—not your health data. Each load randomly selects one of two test scenarios; review every value before running the research model.</small></span>`;
  form.querySelector(".dynamic-fields")?.before(note);
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
  const probability = result.probability === null
    ? "An estimated probability is not available for this run"
    : `${Math.round(result.probability * 100)}% estimated probability of the model's target pattern`;
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
  triagePanel.innerHTML = `<article class="triage-route result-summary"><span class="material-symbols-outlined">fact_check</span><small>${escapeHtml(result.model_name)} · screening complete</small><h3>${result.band === "elevated" ? "Elevated pattern" : "No elevated pattern"}</h3><p>${probability}. This is a research output, not a diagnosis.</p><ul><li>${escapeHtml(result.model_version)}</li><li>${escapeHtml(result.validation_status)}</li><li>PDF and Excel provenance available</li></ul></article>`;
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
  setBusy(true, "Transcribing privately with HealthAI Voice 1.0…");
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
    lastInputChannel = "Voice · HealthAI Voice 1.0";
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

type ModelExperience = {
  slug: "heart" | "diabetes" | "kidney" | "liver" | "pneumonia" | "qwen" | "moonshine";
  name: string;
  family: string;
  category: "screening" | "language" | "imaging";
  icon: string;
  accent: string;
  version: string;
  summary: string;
  input: string;
  output: string;
  workflow: string[];
};

const modelExperiences: ModelExperience[] = [
  { slug: "heart", name: "HealthAI Cardio 2.0", family: "Cardiovascular research", category: "screening", icon: "cardiology", accent: "coral", version: "healthai-cardio-v2.0.0", summary: "A compact tabular pipeline that evaluates reviewed cardiovascular measurements against the UCI Statlog research baseline.", input: "13 clinical measurements", output: "Bounded pattern score", workflow: ["Validate 13 inputs", "Run ONNX pipeline", "Apply versioned threshold", "Attach provenance"] },
  { slug: "diabetes", name: "HealthAI Glyco 2.0", family: "Metabolic research", category: "screening", icon: "water_drop", accent: "amber", version: "healthai-glyco-v2.0.0", summary: "A symptom-questionnaire model for exploring early-diabetes-associated patterns with explicit human-confirmed evidence.", input: "16 symptom fields", output: "Bounded pattern score", workflow: ["Review symptom evidence", "Encode explicit answers", "Run ONNX pipeline", "Explain limitations"] },
  { slug: "kidney", name: "HealthAI Renal 2.0", family: "Renal research", category: "screening", icon: "nephrology", accent: "blue", version: "healthai-renal-v2.0.0", summary: "A laboratory-heavy CKD research workflow with strict completeness checks and explicit missing-value handling.", input: "24 clinical and lab fields", output: "Bounded pattern score", workflow: ["Confirm lab values", "Validate all 24 fields", "Run ONNX pipeline", "Verify result boundary"] },
  { slug: "liver", name: "HealthAI Hepatic 2.0", family: "Hepatic research", category: "screening", icon: "gastroenterology", accent: "violet", version: "healthai-hepatic-v2.0.0", summary: "A compact ILPD baseline that consumes reviewed demographic and laboratory measurements without free-form inference.", input: "10 demographic and lab fields", output: "Bounded pattern score", workflow: ["Review laboratory panel", "Validate measurement range", "Run ONNX pipeline", "Surface cohort limits"] },
  { slug: "pneumonia", name: "HealthAI PulmoVision 1.0", family: "Experimental imaging", category: "imaging", icon: "radiology", accent: "cyan", version: "healthai-pulmovision-v1.0.0", summary: "A reproducible PneumoniaMNIST image baseline for pediatric benchmark exploration—not a radiology or adult diagnostic tool.", input: "Reviewed pediatric X-ray", output: "Experimental image score", workflow: ["Confirm image boundary", "Crop and reduce to 28×28", "Run ONNX baseline", "Show imaging limits"] },
  { slug: "qwen", name: "HealthAI Reasoner 1.0", family: "Open language reasoner", category: "language", icon: "forum", accent: "mint", version: "Qwen3-0.6B Q8 · LoRA 1.1 candidate", summary: "The private language layer, powered by Qwen3-0.6B, for conversation and constrained tool proposals. LoRA adapters remain evaluation candidates until they beat the hybrid baseline.", input: "Natural language", output: "Policy-checked JSON proposal", workflow: ["Read user language", "Propose bounded action", "Validate JSON contract", "Use deterministic authority"] },
  { slug: "moonshine", name: "HealthAI Voice 1.0", family: "Open speech model", category: "language", icon: "graphic_eq", accent: "rose", version: "Moonshine 34M · streaming", summary: "A small self-hosted English ASR model, powered by Moonshine, that turns a short recording into an editable transcript before the agent sees it.", input: "16 kHz mono audio", output: "Reviewable transcript", workflow: ["Capture short recording", "Transcribe privately", "Review the transcript", "Send confirmed text"] },
];

let runtimeModelCatalog: ModelSummary[] = [];
let runtimeTools: ToolSummary[] = [];
let voiceRuntimeAvailable = false;
let qwenRuntimeAvailable = false;
let selectedModelSlug: ModelExperience["slug"] = "heart";
let activeModelFilter: "all" | ModelExperience["category"] = "all";
let playgroundStateToken: string | null = null;

const modelExperience = (slug: string) => modelExperiences.find((model) => model.slug === slug);
const runtimeModel = (slug: string) => runtimeModelCatalog.find((model) => model.slug === slug);
const runtimeTool = (slug: string) => runtimeTools.find((tool) => tool.slug === `${slug}_risk` || (slug === "pneumonia" && tool.slug === "pneumonia_xray"));

const modelStatus = (model: ModelExperience) => {
  if (model.slug === "qwen") return qwenRuntimeAvailable ? "Reasoner active" : "Rules fallback";
  if (model.slug === "moonshine") return voiceRuntimeAvailable ? "Voice 1.0 ready" : "Voice service offline";
  const tool = runtimeTool(model.slug);
  if (!runtimeTools.length) return "Checking runtime";
  return tool?.callable ? (tool.deployment_status === "experimental" ? "Experimental" : "Callable") : "Unavailable";
};

const renderModelsGallery = () => {
  const visible = modelExperiences.filter((model) => activeModelFilter === "all" || model.category === activeModelFilter);
  modelsGallery.innerHTML = visible.map((model, index) => {
    const evidence = runtimeModel(model.slug);
    const auroc = evidence?.metrics?.auroc;
    const metric = typeof auroc === "number" ? `AUROC ${auroc.toFixed(3)}` : model.slug === "qwen" ? "LoRA candidate gated" : model.slug === "moonshine" ? "Transcript review required" : "Runtime evidence";
    return `<button class="model-experience-card ${model.accent} ${selectedModelSlug === model.slug ? "selected" : ""}" type="button" data-model-select="${model.slug}" style="--delay:${index * 55}ms">
      <span class="model-card-index">${String(modelExperiences.indexOf(model) + 1).padStart(2, "0")}</span>
      <span class="model-card-icon material-symbols-outlined">${model.icon}</span>
      <span class="model-card-status"><i></i>${escapeHtml(modelStatus(model))}</span>
      <span class="model-card-family">${escapeHtml(model.family)}</span>
      <strong>${escapeHtml(model.name)}</strong>
      <p>${escapeHtml(model.summary)}</p>
      <span class="model-card-meta"><b>${escapeHtml(model.version)}</b><b>${escapeHtml(metric)}</b></span>
      <span class="model-card-cta">Explore workflow <i class="material-symbols-outlined">arrow_forward</i></span>
    </button>`;
  }).join("");
};

const renderPlaygroundIdentity = (model: ModelExperience) => {
  const evidence = runtimeModel(model.slug);
  const auroc = evidence?.metrics?.auroc;
  playgroundIdentity.className = `playground-identity ${model.accent}`;
  playgroundIdentity.innerHTML = `<div class="playground-model-mark"><span class="material-symbols-outlined">${model.icon}</span><i></i></div>
    <span class="playground-kicker">Now exploring · ${escapeHtml(model.family)}</span>
    <h2>${escapeHtml(model.name)}</h2><p>${escapeHtml(model.summary)}</p>
    <dl><div><dt>Input</dt><dd>${escapeHtml(model.input)}</dd></div><div><dt>Output</dt><dd>${escapeHtml(model.output)}</dd></div><div><dt>Evidence</dt><dd>${typeof auroc === "number" ? `AUROC ${auroc.toFixed(4)} · frozen test` : escapeHtml(model.version)}</dd></div></dl>
    <div class="mini-workflow">${model.workflow.map((step, index) => `<span><i>${index + 1}</i>${escapeHtml(step)}</span>`).join("")}</div>`;
};

const modelLoading = (label: string) => {
  playgroundStage.innerHTML = `<div class="model-loading"><div class="model-loader-orbit"><span></span><i></i></div><strong>${escapeHtml(label)}</strong><p>Reading the registered schema and model boundary…</p></div>`;
};

const renderModelForm = (model: ModelExperience, fields: AssessmentField[]) => {
  playgroundStage.innerHTML = `<div class="playground-head"><div><span>Interactive model run</span><h3>Complete the evidence deck</h3></div><div class="assessment-head-actions"><button class="sample-data-button" type="button"><span class="material-symbols-outlined">science</span>Load test data</button><div class="form-level"><span id="model-form-count">0 / ${fields.length}</span><i><b id="model-form-progress"></b></i></div></div></div>
    <form class="model-arena-form" id="model-arena-form"><div class="model-arena-fields">${fields.map((field) => renderField(field)).join("")}</div><div class="arena-submit"><label class="consent-check"><input name="consent" type="checkbox" required><span>I reviewed these values and understand this is research—not a diagnosis.</span></label><button class="button models-primary" type="submit">Run ${escapeHtml(model.name)} <span>→</span></button></div></form>`;
  const form = playgroundStage.querySelector<HTMLFormElement>("#model-arena-form")!;
  const count = playgroundStage.querySelector<HTMLElement>("#model-form-count")!;
  const progress = playgroundStage.querySelector<HTMLElement>("#model-form-progress")!;
  const updateProgress = () => {
    const complete = [...form.elements].filter((element) => element instanceof HTMLInputElement || element instanceof HTMLSelectElement).filter((element) => element.name !== "consent" && element.value !== "").length;
    count.textContent = `${complete} / ${fields.length}`;
    progress.style.width = `${Math.round((complete / fields.length) * 100)}%`;
  };
  form.addEventListener("input", updateProgress);
  form.addEventListener("change", updateProgress);
  playgroundStage.querySelector<HTMLButtonElement>(".sample-data-button")!.addEventListener("click", () => {
    loadTestData(form, fields, model.slug);
    updateProgress();
  });
  form.addEventListener("submit", (event) => void runPlaygroundPrediction(event, model));
};

const renderPneumoniaPlayground = (model: ModelExperience) => {
  playgroundStage.innerHTML = `<div class="playground-head"><div><span>Interactive image run</span><h3>Upload a reviewed research image</h3></div><span class="arena-level-chip">Experimental boundary</span></div>
    <form class="image-arena" id="image-arena"><label class="image-drop-zone" for="model-xray"><span class="material-symbols-outlined">add_photo_alternate</span><strong>Choose a pediatric chest X-ray</strong><small>JPEG or PNG · maximum 8 MB · the model reduces it to 28×28</small><input id="model-xray" name="image" type="file" accept="image/jpeg,image/png" required></label><div id="model-image-name" class="model-image-name">No image selected</div><label class="consent-check"><input name="consent" type="checkbox" required><span>I confirm the research population and understand this cannot replace a radiologist.</span></label><button class="button models-primary" type="submit">Run image model <span>→</span></button></form>`;
  const form = playgroundStage.querySelector<HTMLFormElement>("#image-arena")!;
  const input = playgroundStage.querySelector<HTMLInputElement>("#model-xray")!;
  const name = playgroundStage.querySelector<HTMLElement>("#model-image-name")!;
  input.addEventListener("change", () => { name.textContent = input.files?.[0] ? `${input.files[0].name} · ${(input.files[0].size / 1024).toFixed(0)} KB` : "No image selected"; });
  form.addEventListener("submit", (event) => void runPlaygroundImage(event, model));
};

const renderQwenPlayground = (model: ModelExperience) => {
  playgroundStage.innerHTML = `<div class="playground-head"><div><span>HealthAI Reasoner 1.0 · powered by Qwen3-0.6B</span><h3>From natural language to a bounded proposal</h3></div><span class="arena-level-chip ${qwenRuntimeAvailable ? "ready" : ""}">${qwenRuntimeAvailable ? "Reasoner active" : "Deterministic fallback active"}</span></div>
    <div class="reasoner-demo"><div class="reasoner-pipeline"><article><i>01</i><span class="material-symbols-outlined">chat</span><strong>Natural language</strong><small>User describes a concern</small></article><b>→</b><article><i>02</i><span class="material-symbols-outlined">data_object</span><strong>Qwen proposal</strong><small>Constrained JSON only</small></article><b>→</b><article><i>03</i><span class="material-symbols-outlined">policy</span><strong>Policy check</strong><small>Deterministic authority</small></article><b>→</b><article><i>04</i><span class="material-symbols-outlined">route</span><strong>Allowed action</strong><small>Respond, ask or route</small></article></div>
    <div class="adapter-note"><span class="material-symbols-outlined">experiment</span><div><strong>Fine-tuning is visible, but not silently promoted.</strong><p>The LoRA track improves contract learning through versioned examples. Current adapters remain candidates because direct-routing accuracy has not beaten the tested hybrid.</p></div></div>
    <label class="reasoner-prompt"><span>Try a natural-language concern</span><textarea id="qwen-model-prompt" rows="3">I have been unusually thirsty and urinating often. Which research workflow fits?</textarea></label><button class="button models-primary" type="button" id="open-qwen-agent">Continue in live agent <span>→</span></button></div>`;
  playgroundStage.querySelector<HTMLButtonElement>("#open-qwen-agent")!.addEventListener("click", () => {
    const prompt = playgroundStage.querySelector<HTMLTextAreaElement>("#qwen-model-prompt")!.value.trim();
    showView("assessment");
    messageInput.value = prompt;
    messageInput.focus();
  });
};

const renderMoonshinePlayground = (model: ModelExperience) => {
  playgroundStage.innerHTML = `<div class="playground-head"><div><span>HealthAI Voice 1.0 · powered by Moonshine 34M</span><h3>Experience private medical voice AI</h3></div><span class="arena-level-chip ${voiceRuntimeAvailable ? "ready" : ""}">${voiceRuntimeAvailable ? "Voice 1.0 ready" : "Voice runtime offline"}</span></div>
    <div class="voice-model-demo"><div class="voice-demo-orb"><span class="material-symbols-outlined">graphic_eq</span>${Array.from({length: 18}, (_, index) => `<i style="--bar:${index}"></i>`).join("")}</div><h4>34 million parameters. One focused job.</h4><p>Moonshine transcribes a short English recording inside the controlled runtime. The transcript always returns to the composer for human review before orchestration.</p><div class="voice-demo-path"><span><i>1</i>Speak</span><b></b><span><i>2</i>Transcribe privately</span><b></b><span><i>3</i>Review text</span><b></b><span><i>4</i>Send</span></div><button class="button models-primary" type="button" id="open-voice-agent" ${voiceRuntimeAvailable ? "" : "disabled"}>${voiceRuntimeAvailable ? "Open voice experience" : "Voice service is offline"} <span>→</span></button></div>`;
  playgroundStage.querySelector<HTMLButtonElement>("#open-voice-agent")!.addEventListener("click", () => {
    showView("assessment");
    voiceButton.classList.add("spotlight");
    voiceButton.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => voiceButton.classList.remove("spotlight"), 2400);
  });
};

const selectModelExperience = async (slug: string, scroll = true) => {
  const model = modelExperience(slug);
  if (!model) return;
  selectedModelSlug = model.slug;
  renderModelsGallery();
  renderPlaygroundIdentity(model);
  if (scroll) document.querySelector("#model-playground")?.scrollIntoView({ behavior: "smooth", block: "start" });
  if (model.slug === "qwen") { renderQwenPlayground(model); return; }
  if (model.slug === "moonshine") { renderMoonshinePlayground(model); return; }
  if (model.slug === "pneumonia") { renderPneumoniaPlayground(model); return; }
  modelLoading(`Loading ${model.name}`);
  try {
    const response = await fetch(`${apiBase}/api/v1/triage/start`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ message: `I want to run the ${model.slug} research screening.`, locale: "en" }) });
    if (!response.ok) throw new Error(await apiError(response));
    const result = await response.json() as TriageResponse;
    if (selectedModelSlug !== model.slug) return;
    playgroundStateToken = result.state_token;
    if (result.status !== "ready" || !result.required_fields.length) throw new Error("The registered model schema was not returned.");
    renderModelForm(model, result.required_fields);
  } catch (error) {
    playgroundStage.innerHTML = `<div class="arena-error"><span class="material-symbols-outlined">error</span><h3>Model workflow unavailable</h3><p>${escapeHtml(error instanceof Error ? error.message : "The model could not be loaded.")}</p><button class="button secondary" type="button" id="retry-model">Try again</button></div>`;
    playgroundStage.querySelector<HTMLButtonElement>("#retry-model")?.addEventListener("click", () => void selectModelExperience(model.slug, false));
  }
};

const renderModelThinking = (model: ModelExperience) => {
  playgroundStage.innerHTML = `<div class="model-thinking"><div class="inference-core"><span class="material-symbols-outlined">${model.icon}</span><i></i><b></b></div><span class="thinking-kicker">Running ${escapeHtml(model.name)}</span><h3>Following the evidence trail…</h3><div class="inference-steps"><span class="active"><i>✓</i>Inputs validated</span><span><i></i>Model inference</span><span><i></i>Threshold policy</span><span><i></i>Result provenance</span></div><small>No generated clinical values · no external AI API</small></div>`;
};

const renderPlaygroundResult = (model: ModelExperience, result: Prediction) => {
  const score = result.probability === null ? 0 : Math.round(result.probability * 100);
  const elevated = result.band === "elevated";
  playgroundStage.innerHTML = `<div class="arena-result ${result.band}">${Array.from({length: 14}, (_, index) => `<i class="result-spark" style="--spark:${index}"></i>`).join("")}<div class="result-score-ring" style="--score:${score}"><div><strong>${result.probability === null ? "—" : `${score}%`}</strong><small>estimated probability</small></div></div><div class="arena-result-copy"><span class="result-unlocked"><i class="material-symbols-outlined">verified</i> ${escapeHtml(result.model_name)} result unlocked</span><h3>${elevated ? "Elevated pattern identified" : "No elevated pattern identified"}</h3><p>${result.probability === null ? "An estimated probability is not available for this run." : `${score}% estimated probability of the model's target pattern.`} This research estimate can be wrong and does not establish or rule out a condition.</p><div class="result-provenance"><span><small>Model</small><strong>${escapeHtml(result.model_name)}</strong><small>${escapeHtml(result.model_version)}</small></span><span><small>Status</small><strong>${escapeHtml(result.validation_status)}</strong></span><span><small>Pipeline</small><strong>Verified ONNX</strong></span></div><div class="arena-result-actions"><button class="button models-primary" type="button" data-model-export="pdf">Download PDF</button><button class="button secondary" type="button" data-model-export="xlsx">Download Excel</button><button class="model-run-again" type="button">Run again ↻</button></div></div></div>`;
  playgroundStage.querySelectorAll<HTMLButtonElement>("[data-model-export]").forEach((button) => button.addEventListener("click", () => void downloadReport(button.dataset.modelExport!)));
  playgroundStage.querySelector<HTMLButtonElement>(".model-run-again")!.addEventListener("click", () => void selectModelExperience(model.slug, false));
};

async function runPlaygroundPrediction(event: SubmitEvent, model: ModelExperience) {
  event.preventDefault();
  const form = event.currentTarget as HTMLFormElement;
  const inputs: Record<string, number> = {};
  for (const [name, value] of new FormData(form).entries()) if (name !== "consent") inputs[name] = Number(value);
  renderModelThinking(model);
  try {
    const [response] = await Promise.all([fetch(`${apiBase}/api/v1/assessments/${model.slug}/predict`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ inputs, state_token: playgroundStateToken }) }), new Promise((resolve) => window.setTimeout(resolve, 1400))]);
    if (!response.ok) throw new Error(await apiError(response));
    const result = await response.json() as Prediction;
    reportToken = result.report_token;
    renderPlaygroundResult(model, result);
  } catch (error) {
    playgroundStage.innerHTML = `<div class="arena-error"><span class="material-symbols-outlined">error</span><h3>The research model could not run</h3><p>${escapeHtml(error instanceof Error ? error.message : "Please review the inputs and try again.")}</p><button class="button secondary" type="button" id="retry-model">Return to inputs</button></div>`;
    playgroundStage.querySelector<HTMLButtonElement>("#retry-model")!.addEventListener("click", () => void selectModelExperience(model.slug, false));
  }
}

async function runPlaygroundImage(event: SubmitEvent, model: ModelExperience) {
  event.preventDefault();
  const form = event.currentTarget as HTMLFormElement;
  const file = form.querySelector<HTMLInputElement>("input[type=file]")!.files?.[0];
  if (!file) return;
  if (!["image/jpeg", "image/png"].includes(file.type) || file.size > 8 * 1024 * 1024) {
    playgroundStage.querySelector<HTMLElement>(".model-image-name")!.textContent = "Use a JPEG or PNG smaller than 8 MB.";
    return;
  }
  renderModelThinking(model);
  const body = new FormData(); body.append("image", file);
  try {
    const [response] = await Promise.all([fetch(`${apiBase}/api/v1/images/pneumonia/predict`, { method: "POST", body, credentials: "include" }), new Promise((resolve) => window.setTimeout(resolve, 1400))]);
    if (!response.ok) throw new Error(await apiError(response));
    const result = await response.json() as Prediction;
    reportToken = result.report_token;
    renderPlaygroundResult(model, result);
  } catch (error) {
    playgroundStage.innerHTML = `<div class="arena-error"><span class="material-symbols-outlined">error</span><h3>The image model could not run</h3><p>${escapeHtml(error instanceof Error ? error.message : "Please review the image and try again.")}</p><button class="button secondary" type="button" id="retry-model">Return to upload</button></div>`;
    playgroundStage.querySelector<HTMLButtonElement>("#retry-model")!.addEventListener("click", () => renderPneumoniaPlayground(model));
  }
}

modelsGallery.addEventListener("click", (event) => {
  const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-model-select]");
  if (button?.dataset.modelSelect) void selectModelExperience(button.dataset.modelSelect);
});
document.querySelectorAll<HTMLButtonElement>(".model-constellation [data-model-select]").forEach((button) => button.addEventListener("click", () => { showView("models"); void selectModelExperience(button.dataset.modelSelect ?? "heart"); }));
modelFilterButtons.forEach((button) => button.addEventListener("click", () => { activeModelFilter = (button.dataset.modelFilter ?? "all") as typeof activeModelFilter; modelFilterButtons.forEach((item) => item.classList.toggle("active", item === button)); renderModelsGallery(); }));
exploreModels.addEventListener("click", () => document.querySelector("#models-catalog")?.scrollIntoView({ behavior: "smooth" }));

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
  registryBody.innerHTML = `${toolRows}${blockedRows}<tr><td><strong>HealthAI Voice 1.0</strong><small class="table-note">Powered by Moonshine Tiny Streaming English 34M</small></td><td>healthai-voice-v1.0.0</td><td>Reviewed voice transcript</td><td>Local CPU service</td><td><span class="status-chip ${voiceAvailable ? "success" : ""}">${voiceAvailable ? "Available" : "Separate service"}</span></td></tr><tr><td><strong>HealthAI Reasoner 1.0</strong><small class="table-note">Powered by Qwen3-0.6B Q8 · constrained routing</small></td><td>healthai-reasoner-v1.0.0</td><td>Conversation, extraction and tool proposals</td><td>Docker Model Runner</td><td><span class="status-chip ${qwenAvailable ? "success" : ""}">${qwenAvailable ? "Active locally" : "Rules fallback"}</span></td></tr>`;
};

const loadRuntimeEvidence = async () => {
  setRuntimeBadge(modelsRuntime, "loading", "Checking local runtime");
  setRuntimeBadge(registryRuntime, "loading", "Loading registry");
  refreshModels.disabled = true;
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
    runtimeModelCatalog = models;
    runtimeTools = tools;
    voiceRuntimeAvailable = Boolean(health.voice_available);
    qwenRuntimeAvailable = Boolean(health.qwen_available);
    for (const model of models) {
      const badge = document.querySelector<HTMLElement>(`[data-model-status="${model.slug}"]`);
      if (!badge) continue;
      badge.textContent = model.status === "research" ? "Research model" : model.status;
      badge.classList.toggle("available", model.status === "research" || model.status === "validated");
    }
    renderRegistry(models, tools, Boolean(health.voice_available), Boolean(health.qwen_available));
    renderModelsGallery();
    renderPlaygroundIdentity(modelExperience(selectedModelSlug)!);
    if (selectedModelSlug === "qwen") renderQwenPlayground(modelExperience("qwen")!);
    if (selectedModelSlug === "moonshine") renderMoonshinePlayground(modelExperience("moonshine")!);
    setRuntimeBadge(modelsRuntime, "ready", `${callable.length} callable tools · private runtime`);
    setRuntimeBadge(registryRuntime, "ready", `${tools.length} registered · ${callable.length} callable`);
    if (health.voice_available) {
      setVoiceButtonState("ready");
      voiceButton.setAttribute("aria-label", "Record medical symptoms for up to 30 seconds using HealthAI Voice 1.0");
    } else {
      setVoiceButtonState("unavailable");
      voiceButton.setAttribute("aria-label", "Moonshine voice runs as a separate service and is not attached to this local API");
      composerStatus.textContent = `${locale.value === "hi" ? "हिन्दी" : "English"} · text input`;
    }
  } catch {
    setRuntimeBadge(modelsRuntime, "failed", "Local runtime unavailable");
    setRuntimeBadge(registryRuntime, "failed", "Registry unavailable");
    renderModelsGallery();
    setVoiceButtonState("unavailable");
    voiceButton.setAttribute("aria-label", "Medical voice AI is unavailable because the local API did not respond");
  } finally {
    refreshModels.disabled = false;
  }
};

refreshModels.addEventListener("click", loadRuntimeEvidence);
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
renderModelsGallery();
void selectModelExperience("heart", false);
void loadRuntimeEvidence();
