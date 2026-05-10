// Predict + feedback + retrain UI logic.

const NUMERIC_FIELDS = ["age", "trestbps", "chol", "thalach", "oldpeak"];
const INT_FIELDS = ["sex", "cp", "fbs", "restecg", "exang", "slope", "ca", "thal"];

const EXAMPLE = {
  age: 63, sex: 1, cp: 1, trestbps: 145, chol: 233,
  fbs: 1, restecg: 2, thalach: 150, exang: 0,
  oldpeak: 2.3, slope: 3, ca: 0, thal: 6,
};

const form = document.getElementById("predict-form");
const resultCard = document.getElementById("result-card");
const summaryEl = document.getElementById("prediction-summary");
const probFill = document.getElementById("probability-fill");
const probText = document.getElementById("probability-text");
const feedbackStatus = document.getElementById("feedback-status");
const retrainStatus = document.getElementById("retrain-status");
const modelInfoEl = document.getElementById("model-info");

let lastFeatures = null;
let lastPrediction = null;

function readForm() {
  const data = new FormData(form);
  const out = {};
  for (const [k, v] of data.entries()) {
    if (NUMERIC_FIELDS.includes(k)) out[k] = Number(v);
    else if (INT_FIELDS.includes(k)) out[k] = parseInt(v, 10);
    else out[k] = v;
  }
  return out;
}

function applyExample() {
  for (const [k, v] of Object.entries(EXAMPLE)) {
    const el = form.elements[k];
    if (el) el.value = v;
  }
}

function setStatus(el, msg, kind = "info") {
  el.textContent = msg;
  el.className = `status ${kind}`;
}

async function loadModelInfo() {
  try {
    const res = await fetch("/model-info");
    const info = await res.json();
    if (!info.model_loaded) {
      modelInfoEl.textContent = "⚠ Model not loaded. Run training first.";
      return;
    }
    const auc = info.test_metrics?.roc_auc?.toFixed(3) ?? "—";
    const ts = info.trained_at ? new Date(info.trained_at).toLocaleString() : "unknown";
    modelInfoEl.textContent = `Model: ${info.best_model} · ROC-AUC ${auc} · trained ${ts}`;
  } catch (e) {
    modelInfoEl.textContent = "Could not fetch model info.";
  }
}

async function predict(ev) {
  ev.preventDefault();
  const features = readForm();
  lastFeatures = features;
  setStatus(feedbackStatus, "");
  try {
    const res = await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(features),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const body = await res.json();
    lastPrediction = body;
    renderPrediction(body);
  } catch (e) {
    resultCard.hidden = false;
    summaryEl.textContent = "Prediction failed";
    probText.textContent = e.message;
  }
}

function renderPrediction(body) {
  resultCard.hidden = false;
  resultCard.classList.remove("disease", "no-disease");
  resultCard.classList.add(body.label === "disease" ? "disease" : "no-disease");
  summaryEl.textContent =
    body.label === "disease" ? "Likely Heart Disease" : "Likely No Disease";
  const pct = (body.probability * 100).toFixed(1);
  probFill.style.width = `${pct}%`;
  probText.textContent = `${pct}% (label = ${body.label}, class = ${body.prediction})`;
}

async function submitFeedback(actualLabel) {
  if (!lastFeatures || lastPrediction === null) {
    setStatus(feedbackStatus, "Make a prediction first.", "err");
    return;
  }
  setStatus(feedbackStatus, "Saving feedback…", "info");
  try {
    const payload = {
      features: lastFeatures,
      true_label: actualLabel,
      predicted_label: lastPrediction.prediction,
      probability: lastPrediction.probability,
    };
    const res = await fetch("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const body = await res.json();
    setStatus(
      feedbackStatus,
      `Feedback saved (total feedback rows: ${body.total_feedback_rows}). Retraining triggered in the background…`,
      "ok",
    );
    await triggerRetrain({ silent: true });
  } catch (e) {
    setStatus(feedbackStatus, `Failed: ${e.message}`, "err");
  }
}

async function triggerRetrain(opts = {}) {
  const silent = !!opts.silent;
  if (!silent) setStatus(retrainStatus, "Starting retraining run…", "info");
  try {
    const res = await fetch("/retrain", { method: "POST" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const body = await res.json();
    setStatus(
      retrainStatus,
      `Retraining started (job #${body.job_id}). The model will reload automatically when finished. Refresh model info in ~60s.`,
      "info",
    );
    setTimeout(loadModelInfo, 60000);
  } catch (e) {
    setStatus(retrainStatus, `Retrain failed: ${e.message}`, "err");
  }
}

form.addEventListener("submit", predict);
document.getElementById("example-btn").addEventListener("click", applyExample);
document
  .getElementById("feedback-correct")
  .addEventListener("click", () => submitFeedback(lastPrediction?.prediction));
document
  .getElementById("feedback-wrong")
  .addEventListener("click", () => submitFeedback(1 - (lastPrediction?.prediction ?? 0)));
document.getElementById("retrain-btn").addEventListener("click", () => triggerRetrain());

loadModelInfo();
