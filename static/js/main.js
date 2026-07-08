/* ═══════════════════════════════════════════════════════════════
   NewsIQ — main.js
   All UI logic: analyse, compare, history, highlights, toasts
   ═══════════════════════════════════════════════════════════════ */

"use strict";

// ── DOM refs ───────────────────────────────────────────────────────────────
const newsText         = document.getElementById("newsText");
const articleUrl       = document.getElementById("articleUrl");
const btnAnalyse       = document.getElementById("btnAnalyse");
const btnAnalyseText   = document.getElementById("btnAnalyseText");
const btnAnalyseSpinner= document.getElementById("btnAnalyseSpinner");
const resultArea       = document.getElementById("resultArea");
const verdictBadge     = document.getElementById("verdictBadge");
const verdictSummary   = document.getElementById("verdictSummary");
const confidenceBar    = document.getElementById("confidenceBar");
const confidenceNum    = document.getElementById("confidenceNum");
const highlightedText  = document.getElementById("highlightedText");
const explanationList  = document.getElementById("explanationList");
const simpleExplanation= document.getElementById("simpleExplanation");
const signalsList      = document.getElementById("signalsList");
const checklistItems   = document.getElementById("checklistItems");
const langBadge        = document.getElementById("langBadge");

const historyList      = document.getElementById("historyList");
const historyEmpty     = document.getElementById("historyEmpty");
const btnClearHistory  = document.getElementById("btnClearHistory");
const btnClearText     = document.getElementById("btnClearText");
const charCount        = document.getElementById("charCount");
const statusDot        = document.getElementById("statusDot");
const btnFetchUrl      = document.getElementById("btnFetchUrl");

const btnCompareMode   = document.getElementById("btnCompareMode");
const singlePanel      = document.getElementById("singlePanel");
const comparePanel     = document.getElementById("comparePanel");
const compareTextA     = document.getElementById("compareTextA");
const compareTextB     = document.getElementById("compareTextB");
const btnCompare       = document.getElementById("btnCompare");
const btnCompareText   = document.getElementById("btnCompareText");
const btnCompareSpinner= document.getElementById("btnCompareSpinner");
const compareResult    = document.getElementById("compareResult");
const compareVerdictA  = document.getElementById("compareVerdictA");
const compareVerdictB  = document.getElementById("compareVerdictB");
const compareBarA      = document.getElementById("compareBarA");
const compareBarB      = document.getElementById("compareBarB");
const compareSummaryA  = document.getElementById("compareSummaryA");
const compareSummaryB  = document.getElementById("compareSummaryB");
const compareText      = document.getElementById("compareText");
const moreCredibleBadge= document.getElementById("moreCredibleBadge");

const toastEl          = document.getElementById("niqToast");
const toastMsg         = document.getElementById("toastMsg");

// ── Toast helper ────────────────────────────────────────────────────────────
const bsToast = new bootstrap.Toast(toastEl, { delay: 3200 });
function showToast(msg, type = "bg-secondary") {
  toastEl.className = `toast align-items-center text-white border-0 ${type}`;
  toastMsg.textContent = msg;
  bsToast.show();
}

// ── Status check ─────────────────────────────────────────────────────────────
async function checkStatus() {
  try {
    const r = await fetch("/api/status");
    const d = await r.json();
    if (d.watsonx_configured) {
      statusDot.className = "status-dot status-ok";
      statusDot.title = "watsonx.ai connected";
    } else {
      statusDot.className = "status-dot status-error";
      statusDot.title = "API not configured — set .env credentials";
      showToast("⚠️ IBM API credentials not configured in .env", "bg-warning text-dark");
    }
  } catch {
    statusDot.className = "status-dot status-error";
    statusDot.title = "Cannot reach server";
  }
}
checkStatus();

// ── Character counter ────────────────────────────────────────────────────────
newsText.addEventListener("input", () => {
  const len = newsText.value.length;
  charCount.textContent = len;
  if (len > 3000) {
    newsText.value = newsText.value.slice(0, 3000);
    charCount.textContent = 3000;
  }
});

// ── Clear text ───────────────────────────────────────────────────────────────
btnClearText.addEventListener("click", () => {
  newsText.value = "";
  articleUrl.value = "";
  charCount.textContent = 0;
  resultArea.classList.add("d-none");
});

// ── Fetch URL preview ─────────────────────────────────────────────────────────
btnFetchUrl.addEventListener("click", async () => {
  const url = articleUrl.value.trim();
  if (!url) { showToast("Please paste a URL first", "bg-warning text-dark"); return; }
  btnFetchUrl.disabled = true;
  btnFetchUrl.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Fetching…';
  try {
    const r    = await fetch("/api/fetch-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    newsText.value = data.text;
    charCount.textContent = data.text.length;
    showToast(`Fetched ${data.length} characters from URL`, "bg-success");
  } catch (e) {
    showToast(`Fetch error: ${e.message}`, "bg-danger");
  } finally {
    btnFetchUrl.disabled = false;
    btnFetchUrl.innerHTML = '<i class="bi bi-cloud-download me-1"></i>Fetch';
  }
});

// ── Verdict colour helpers ────────────────────────────────────────────────────
const LABEL_COLORS = { REAL: "var(--niq-real)", SUSPICIOUS: "var(--niq-suspicious)", FAKE: "var(--niq-fake)" };
const LABEL_BG     = { REAL: "bg-success", SUSPICIOUS: "bg-warning text-dark", FAKE: "bg-danger" };

function applyVerdict(badgeEl, barEl, label, confidence) {
  badgeEl.textContent = label;
  badgeEl.className   = `verdict-badge verdict-${label}`;
  barEl.style.width   = `${confidence}%`;
  barEl.className     = `progress-bar bar-${label}`;
}

// ── Checklist renderer ────────────────────────────────────────────────────────
const CHECKLIST_LABELS = {
  credible_source:    "Credible source",
  verifiable_claims:  "Verifiable claims",
  emotional_language: "Emotional language (flag if true)",
  author_named:       "Author named",
  consistent_facts:   "Consistent facts",
};

function renderChecklist(cl) {
  checklistItems.innerHTML = "";
  Object.entries(cl || {}).forEach(([key, val]) => {
    const li = document.createElement("li");
    let icon, cls;
    if (key === "emotional_language") {
      // Emotional language is BAD if true
      icon = val === true  ? "bi-x-circle-fill" : "bi-check-circle-fill";
      cls  = val === true  ? "check-fail" : "check-pass";
    } else {
      if (val === true)       { icon = "bi-check-circle-fill"; cls = "check-pass"; }
      else if (val === false) { icon = "bi-x-circle-fill";     cls = "check-fail"; }
      else                    { icon = "bi-question-circle";   cls = "check-null"; }
    }
    li.innerHTML = `<i class="bi ${icon} ${cls}"></i><span>${CHECKLIST_LABELS[key] || key}</span>`;
    checklistItems.appendChild(li);
  });
}

// ── Main analyse ──────────────────────────────────────────────────────────────
btnAnalyse.addEventListener("click", async () => {
  const text = newsText.value.trim();
  const url  = articleUrl.value.trim();
  if (!text && !url) {
    showToast("Please enter some text or a URL to analyse.", "bg-warning text-dark");
    return;
  }

  const lang = document.querySelector('input[name="lang"]:checked').value;

  setAnalyseLoading(true);
  try {
    const r = await fetch("/api/analyse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, url, language: lang }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Unknown error");
    renderResult(data);
    loadHistory();
    showToast("Analysis complete!", "bg-success");
  } catch (e) {
    showToast(`Error: ${e.message}`, "bg-danger");
  } finally {
    setAnalyseLoading(false);
  }
});

function setAnalyseLoading(on) {
  btnAnalyse.disabled = on;
  btnAnalyseText.classList.toggle("d-none", on);
  btnAnalyseSpinner.classList.toggle("d-none", !on);
}

function renderResult(data) {
  resultArea.classList.remove("d-none");
  resultArea.scrollIntoView({ behavior: "smooth", block: "start" });

  const label      = (data.label || "SUSPICIOUS").toUpperCase();
  const confidence = data.confidence || 0;

  // Verdict + confidence
  applyVerdict(verdictBadge, confidenceBar, label, confidence);
  verdictSummary.textContent = data.summary || "";
  confidenceNum.textContent  = `${confidence}%`;

  // Language badge
  const lang = (data.language || "en").toUpperCase();
  langBadge.textContent = lang === "HI" ? "हिं" : "EN";

  // Highlighted text
  highlightedText.innerHTML = data.highlighted_text || bleachText(data.input_text || "");

  // Explanation bullets
  explanationList.innerHTML = "";
  (data.explanation || []).forEach(txt => {
    const li = document.createElement("li");
    li.textContent = txt;
    explanationList.appendChild(li);
  });

  // Plain explanation
  simpleExplanation.textContent = data.simple_explanation || "";

  // Signals
  signalsList.innerHTML = "";
  (data.signals || []).forEach(sig => {
    const span = document.createElement("span");
    span.className   = "signal-pill";
    span.textContent = sig;
    signalsList.appendChild(span);
  });
  if (!data.signals || !data.signals.length) {
    signalsList.innerHTML = '<span class="text-muted small">No specific signals detected.</span>';
  }

  // Checklist
  renderChecklist(data.checklist);
}

// Safety helper — strip tags for raw text
function bleachText(txt) {
  const d = document.createElement("div");
  d.textContent = txt;
  return d.innerHTML;
}

// ── Compare mode ──────────────────────────────────────────────────────────────
let compareMode = false;
btnCompareMode.addEventListener("click", () => {
  compareMode = !compareMode;
  singlePanel.classList.toggle("d-none", compareMode);
  comparePanel.classList.toggle("d-none", !compareMode);
  btnCompareMode.innerHTML = compareMode
    ? '<i class="bi bi-arrow-left me-1"></i>Single'
    : '<i class="bi bi-columns-gap me-1"></i>Compare';
});

btnCompare.addEventListener("click", async () => {
  const textA = compareTextA.value.trim();
  const textB = compareTextB.value.trim();
  if (!textA || !textB) {
    showToast("Please fill in both text fields.", "bg-warning text-dark");
    return;
  }
  setCompareLoading(true);
  try {
    const r = await fetch("/api/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text_a: textA, text_b: textB }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Unknown error");
    renderCompare(data);
    showToast("Comparison complete!", "bg-success");
  } catch (e) {
    showToast(`Error: ${e.message}`, "bg-danger");
  } finally {
    setCompareLoading(false);
  }
});

function setCompareLoading(on) {
  btnCompare.disabled = on;
  btnCompareText.classList.toggle("d-none", on);
  btnCompareSpinner.classList.toggle("d-none", !on);
}

function renderCompare(data) {
  compareResult.classList.remove("d-none");
  compareResult.scrollIntoView({ behavior: "smooth", block: "start" });

  const a = data.text_a || {};
  const b = data.text_b || {};

  applyVerdict(compareVerdictA, compareBarA, (a.label || "SUSPICIOUS").toUpperCase(), a.confidence || 0);
  applyVerdict(compareVerdictB, compareBarB, (b.label || "SUSPICIOUS").toUpperCase(), b.confidence || 0);
  compareSummaryA.textContent = a.summary || "";
  compareSummaryB.textContent = b.summary || "";
  compareText.textContent     = data.comparison || "";

  const mc = (data.more_credible || "").toUpperCase();
  if (mc) {
    moreCredibleBadge.innerHTML =
      `<span class="badge ${mc === "EQUAL" ? "bg-secondary" : "bg-success"}">
        <i class="bi bi-trophy me-1"></i>More credible: ${mc}
      </span>`;
  }
}

// ── History ────────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const r    = await fetch("/api/history?limit=20");
    const data = await r.json();
    renderHistory(data);
  } catch {
    /* silent */
  }
}

function renderHistory(items) {
  if (!items || !items.length) {
    historyList.innerHTML = "";
    historyList.appendChild(historyEmpty);
    historyEmpty.classList.remove("d-none");
    return;
  }
  historyEmpty.classList.add("d-none");
  historyList.innerHTML = "";
  items.forEach(item => {
    const div = document.createElement("div");
    div.className = "niq-history-item";
    div.innerHTML = `
      <span class="hist-label hist-${item.label}">${item.label}</span>
      <span class="hist-text">${escHtml(item.input_text.slice(0, 90))}</span>
      <span class="hist-conf">${item.confidence}%</span>
      <button class="btn-del-hist" data-id="${item.id}" title="Remove">
        <i class="bi bi-x"></i>
      </button>`;
    // Click to re-populate input
    div.addEventListener("click", e => {
      if (e.target.closest(".btn-del-hist")) return;
      newsText.value = item.input_text;
      charCount.textContent = item.input_text.length;
      if (compareMode) {
        compareMode = false;
        singlePanel.classList.remove("d-none");
        comparePanel.classList.add("d-none");
        btnCompareMode.innerHTML = '<i class="bi bi-columns-gap me-1"></i>Compare';
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    div.querySelector(".btn-del-hist").addEventListener("click", async e => {
      e.stopPropagation();
      const id = e.currentTarget.dataset.id;
      await fetch(`/api/history/${id}`, { method: "DELETE" });
      loadHistory();
    });
    historyList.appendChild(div);
  });
}

btnClearHistory.addEventListener("click", async () => {
  if (!confirm("Clear all analysis history?")) return;
  await fetch("/api/history", { method: "DELETE" });
  loadHistory();
  showToast("History cleared.", "bg-secondary");
});

function escHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

// ── Init ───────────────────────────────────────────────────────────────────────
loadHistory();
