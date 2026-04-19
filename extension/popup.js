// TruthNuke Popup Dashboard
// Communicates with content script via Chrome messaging to show live analysis results

const SUPPORTED_SITES = [
  { pattern: "x.com", name: "Twitter/X", icon: "𝕏" },
  { pattern: "twitter.com", name: "Twitter/X", icon: "𝕏" },
  { pattern: "instagram.com", name: "Instagram", icon: "📷" },
  { pattern: "tiktok.com", name: "TikTok", icon: "🎵" },
  { pattern: "facebook.com", name: "Facebook", icon: "📘" },
  { pattern: "cnbc.com", name: "CNBC", icon: "📺" },
  { pattern: "fool.com", name: "Motley Fool", icon: "🃏" },
  { pattern: "marketwatch.com", name: "MarketWatch", icon: "📈" },
  { pattern: "finance.yahoo.com", name: "Yahoo Finance", icon: "💹" },
  { pattern: "bloomberg.com", name: "Bloomberg", icon: "📊" },
  { pattern: "reuters.com", name: "Reuters", icon: "🗞️" },
  { pattern: "investopedia.com", name: "Investopedia", icon: "📚" },
  { pattern: "benzinga.com", name: "Benzinga", icon: "⚡" },
  { pattern: "seekingalpha.com", name: "Seeking Alpha", icon: "🔍" },
  { pattern: "barrons.com", name: "Barron's", icon: "📰" },
  { pattern: "wsj.com", name: "WSJ", icon: "📰" },
  { pattern: "ft.com", name: "Financial Times", icon: "📰" },
  { pattern: "thestreet.com", name: "TheStreet", icon: "🏛️" },
  { pattern: "forbes.com", name: "Forbes", icon: "💰" },
];

let analysisResults = [];
let currentTabId = null;
let loadingStartTime = null;
let loadingTimerInterval = null;
let loadingProgressInterval = null;

// ── Initialize ──
async function init() {
  setupTabs();
  await detectPlatformStatus();
  await loadStoredData();
  listenForUpdates();
  setupSettings();
  setupFeedSearch();
  setupAdFree();
}

// ── Tab Navigation ──
function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
    });
  });
}

// ── Platform Detection ──
async function detectPlatformStatus() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTabId = tab?.id;
  const url = tab?.url || "";
  const pill = document.getElementById("statusPill");
  const label = document.getElementById("platformLabel");

  const match = SUPPORTED_SITES.find((s) => url.includes(s.pattern));

  // Check if content script is alive on this page
  let contentScriptAlive = false;
  let detectedPlatform = null;
  try {
    const response = await chrome.tabs.sendMessage(currentTabId, { type: "PING" });
    if (response?.status === "alive") {
      contentScriptAlive = true;
      detectedPlatform = response.platform;
    }
  } catch {
    // Content script not loaded
  }

  if (match) {
    pill.classList.add("active");
    pill.classList.remove("inactive");
    pill.querySelector(".status-text").textContent = "Active";
    label.textContent = `Monitoring ${match.icon} ${match.name}`;
  } else if (contentScriptAlive && detectedPlatform) {
    // Generic site detected by content script
    pill.classList.add("active");
    pill.classList.remove("inactive");
    pill.querySelector(".status-text").textContent = "Active";
    const hostname = new URL(url).hostname.replace("www.", "");
    label.textContent = `Monitoring 🌐 ${hostname}`;
  } else if (url.startsWith("http")) {
    pill.classList.add("active");
    pill.classList.remove("inactive");
    pill.querySelector(".status-text").textContent = "Scanning...";
    const hostname = new URL(url).hostname.replace("www.", "");
    label.textContent = `Checking ${hostname} for financial content`;
  } else {
    pill.classList.add("inactive");
    pill.classList.remove("active");
    pill.querySelector(".status-text").textContent = "Inactive";
    label.textContent = "Visit a supported site to start";
  }
}

// ── Load Stored Analysis Data ──
async function loadStoredData() {
  const data = await chrome.storage.local.get(["analysisResults", "apiUrl", "lastResult", "lastStatus"]);
  analysisResults = data.analysisResults || [];
  renderStats();
  renderFeed();
  renderDistribution();

  // Restore the most recent result if popup was closed during analysis
  if (data.lastResult) {
    showCurrentPost(data.lastResult);
  }

  // Restore loading/error state if analysis was in progress
  if (data.lastStatus) {
    if (data.lastStatus.type === "ANALYSIS_LOADING") {
      showLoadingState(data.lastStatus.data);
    } else if (data.lastStatus.type === "ANALYSIS_ERROR") {
      showErrorState(data.lastStatus.data);
    }
    chrome.storage.local.remove("lastStatus");
  }

  document.getElementById("apiUrl").value = data.apiUrl || "http://localhost:8000";
}

// ── Listen for Live Updates from Content Script ──
function listenForUpdates() {
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "ANALYSIS_LOADING") {
      showLoadingState(msg.data);
    }
    if (msg.type === "ANALYSIS_RESULT") {
      hideLoadingState();
      chrome.storage.local.remove("lastStatus");
      // Update local array (background.js handles persisting to storage)
      analysisResults.unshift(msg.data);
      if (analysisResults.length > 50) analysisResults.pop();
      renderStats();
      renderFeed();
      renderDistribution();
      showCurrentPost(msg.data);
    }
    if (msg.type === "ANALYSIS_ERROR") {
      showErrorState(msg.data);
    }
  });
}

// ── Loading State with Progress Bar ──
function showLoadingState(data) {
  const card = document.getElementById("loadingCard");
  const emptyState = document.getElementById("emptyState");
  card.style.display = "block";
  emptyState.style.display = "none";

  const authorText = data.author ? ` by @${data.author}` : "";
  document.getElementById("loadingHeadline").textContent = data.headline || "Post";
  document.getElementById("loadingAuthor").textContent = `Analyzing${authorText} on ${data.platform || "page"}`;

  // Reset progress bar
  const progressFill = document.getElementById("loadingProgressFill");
  progressFill.style.width = "0%";

  loadingStartTime = Date.now();
  clearInterval(loadingTimerInterval);
  clearInterval(loadingProgressInterval);

  const timerEl = document.getElementById("loadingTimer");
  timerEl.textContent = "Starting analysis...";
  timerEl.style.color = "#4b5563";

  // Animate progress bar (estimate ~15s for typical analysis)
  loadingProgressInterval = setInterval(() => {
    const elapsed = (Date.now() - loadingStartTime) / 1000;
    // Asymptotic progress: approaches 90% over ~15s, never reaches 100% until done
    const progress = Math.min(90, (1 - Math.exp(-elapsed / 8)) * 95);
    progressFill.style.width = `${progress}%`;
  }, 200);

  loadingTimerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - loadingStartTime) / 1000);
    if (elapsed >= 25) {
      timerEl.textContent = "Taking longer than expected…";
      timerEl.style.color = "#f87171";
    } else {
      timerEl.textContent = `${elapsed}s elapsed`;
      timerEl.style.color = "#4b5563";
    }
  }, 1000);
}

function hideLoadingState() {
  // Complete the progress bar before hiding
  const progressFill = document.getElementById("loadingProgressFill");
  progressFill.style.width = "100%";

  clearInterval(loadingTimerInterval);
  clearInterval(loadingProgressInterval);

  setTimeout(() => {
    document.getElementById("loadingCard").style.display = "none";
    progressFill.style.width = "0%";
  }, 400);
}

function showErrorState(data) {
  clearInterval(loadingTimerInterval);
  clearInterval(loadingProgressInterval);

  const card = document.getElementById("loadingCard");
  card.style.display = "block";

  const progressFill = document.getElementById("loadingProgressFill");
  progressFill.style.width = "100%";
  progressFill.style.background = "#f87171";

  const headline = data.headline || "Post";
  document.getElementById("loadingHeadline").textContent = data.isTimeout
    ? `⏱️ Timed out: ${headline}`
    : `⚡ Error: ${headline}`;
  document.getElementById("loadingAuthor").textContent = "The post badge on the page has a retry link.";
  document.getElementById("loadingTimer").textContent = "";

  setTimeout(() => {
    card.style.display = "none";
    progressFill.style.width = "0%";
    progressFill.style.background = "";
    // Show empty state if no results
    if (analysisResults.length === 0) {
      document.getElementById("emptyState").style.display = "block";
    }
  }, 5000);
}

// ── Render Stats ──
function renderStats() {
  const total = analysisResults.length;
  const flagged = analysisResults.filter((r) => r.trust_score < 40).length;
  const trusted = analysisResults.filter((r) => r.trust_score >= 70).length;

  document.getElementById("postsAnalyzed").textContent = total;
  document.getElementById("flagsRaised").textContent = flagged;
  document.getElementById("trustworthy").textContent = trusted;
}

// ── Render Live Feed ──
function renderFeed() {
  const feedList = document.getElementById("feedList");

  if (analysisResults.length === 0) {
    feedList.innerHTML = `
      <div class="feed-empty">
        <div class="empty-icon">📡</div>
        <p>No posts analyzed yet. Stop scrolling on a financial post to see results here.</p>
      </div>`;
    return;
  }

  feedList.innerHTML = analysisResults
    .map((r, i) => {
      const level = r.trust_score >= 70 ? "high" : r.trust_score >= 40 ? "medium" : "low";
      const platformName = SUPPORTED_SITES.find((s) => s.pattern.includes(r.platform))?.name || r.platform;
      const timeAgo = getTimeAgo(r.timestamp);
      return `
      <div class="feed-item" data-index="${i}">
        <div class="feed-score-badge ${level}">${r.trust_score}</div>
        <div class="feed-info">
          <div class="feed-author">@${r.author || "unknown"}</div>
          <div class="feed-text">${escapeHtml(r.text?.slice(0, 80) || "")}</div>
          <div class="feed-meta">
            <span class="feed-platform">${platformName}</span>
            <span class="feed-time">${timeAgo}</span>
          </div>
        </div>
      </div>`;
    })
    .join("");

  feedList.querySelectorAll(".feed-item").forEach((item) => {
    item.addEventListener("click", () => {
      const idx = parseInt(item.dataset.index);
      showCurrentPost(analysisResults[idx]);
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
      document.querySelector('[data-tab="dashboard"]').classList.add("active");
      document.getElementById("tab-dashboard").classList.add("active");
    });
  });
}

// ── Show Current Post Detail ──
function showCurrentPost(data) {
  const card = document.getElementById("currentPostCard");
  const empty = document.getElementById("emptyState");
  card.style.display = "block";
  empty.style.display = "none";

  const score = data.trust_score;
  const level = score >= 70 ? "high" : score >= 40 ? "medium" : "low";

  const circumference = 2 * Math.PI * 52;
  const offset = circumference - (score / 100) * circumference;
  const ring = document.getElementById("scoreRingFill");
  ring.style.strokeDashoffset = offset;
  ring.style.stroke = level === "high" ? "#34d399" : level === "medium" ? "#fbbf24" : "#f87171";

  document.getElementById("currentScore").textContent = score;
  const labelEl = document.getElementById("currentLevel");
  labelEl.textContent = level === "high" ? "Trustworthy" : level === "medium" ? "Caution" : "Unreliable";
  labelEl.className = `score-label ${level}`;

  document.getElementById("currentAuthor").textContent = data.author ? `@${data.author}` : "";
  document.getElementById("currentExplanation").textContent =
    data.explanation || "No detailed analysis available.";

  const flagsEl = document.getElementById("currentFlags");
  if (data.flags && data.flags.length > 0) {
    flagsEl.innerHTML = data.flags.map((f) => `<span class="flag-chip">⚠️ ${escapeHtml(f)}</span>`).join("");
  } else {
    flagsEl.innerHTML = "";
  }

  const claimsEl = document.getElementById("currentClaims");
  if (data.claims && data.claims.length > 0) {
    claimsEl.innerHTML = data.claims
      .map(
        (c) => `
      <div class="claim-card ${c.verdict}">
        <div class="claim-text">"${escapeHtml(c.claim)}"</div>
        <div class="claim-verdict ${c.verdict}">${c.verdict}${c.explanation ? " — " + escapeHtml(c.explanation) : ""}</div>
        ${c.sources && c.sources.length > 0 ? `<div class="claim-sources">${c.sources.map((s) => `<div class="claim-source">📰 ${escapeHtml(s)}</div>`).join("")}</div>` : ""}
      </div>`
      )
      .join("");
  } else {
    claimsEl.innerHTML = "";
  }

  // Top-level sources
  const sourcesEl = document.getElementById("currentSources");
  if (sourcesEl) {
    if (data.sources && data.sources.length > 0) {
      sourcesEl.innerHTML = `<div class="card-title">📰 Cross-reference</div>` +
        data.sources.map((s) => `<div class="source-item">${escapeHtml(s)}</div>`).join("");
      sourcesEl.style.display = "block";
    } else {
      sourcesEl.style.display = "none";
    }
  }

  // Affected assets
  const assetsEl = document.getElementById("affectedAssets");
  const assetsListEl = document.getElementById("assetsList");
  if (assetsEl && assetsListEl) {
    const assets = data.affected_assets || [];
    if (assets.length > 0) {
      assetsListEl.innerHTML = assets.map((a) => `
        <div class="asset-item">
          <span class="asset-ticker">${escapeHtml(a.name)}</span>
          <span class="asset-type">${escapeHtml(a.type || "")}</span>
          <span class="asset-impact">${escapeHtml(a.impact || "may be affected")}</span>
        </div>`).join("");
      assetsEl.style.display = "block";
    } else {
      assetsEl.style.display = "none";
    }
  }
}

// ── Trust Distribution ──
function renderDistribution() {
  const card = document.getElementById("distributionCard");
  if (analysisResults.length === 0) {
    card.style.display = "none";
    return;
  }
  card.style.display = "block";

  const total = analysisResults.length;
  const high = analysisResults.filter((r) => r.trust_score >= 70).length;
  const medium = analysisResults.filter((r) => r.trust_score >= 40 && r.trust_score < 70).length;
  const low = analysisResults.filter((r) => r.trust_score < 40).length;

  document.getElementById("distHigh").style.width = `${(high / total) * 100}%`;
  document.getElementById("distMedium").style.width = `${(medium / total) * 100}%`;
  document.getElementById("distLow").style.width = `${(low / total) * 100}%`;
}

// ── Settings ──
function setupSettings() {
  document.getElementById("saveBtn").addEventListener("click", async () => {
    const apiUrl = document.getElementById("apiUrl").value.trim();
    await chrome.storage.local.set({ apiUrl });
    const statusEl = document.getElementById("apiStatus");

    try {
      const resp = await fetch(`${apiUrl}/health`);
      if (resp.ok) {
        statusEl.textContent = "✓ Connected";
        statusEl.className = "api-status ok";
      } else {
        throw new Error();
      }
    } catch {
      statusEl.textContent = "✗ Cannot reach backend";
      statusEl.className = "api-status error";
    }
  });

  document.getElementById("clearDataBtn").addEventListener("click", async () => {
    analysisResults = [];
    await chrome.storage.local.set({ analysisResults: [], lastResult: null, lastStatus: null });
    renderStats();
    renderFeed();
    renderDistribution();
    document.getElementById("currentPostCard").style.display = "none";
    document.getElementById("emptyState").style.display = "block";
  });
}

// ── Helpers ──
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function getTimeAgo(timestamp) {
  if (!timestamp) return "";
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

// ── Feed Search / Chat ──
function setupFeedSearch() {
  const input = document.getElementById("feedSearchInput");
  const btn = document.getElementById("feedSearchBtn");
  const answerEl = document.getElementById("searchAnswer");
  if (!input || !btn) return;

  async function doSearch() {
    const question = input.value.trim();
    if (!question) return;

    btn.disabled = true;
    btn.textContent = "...";
    answerEl.style.display = "block";
    answerEl.textContent = "Thinking...";

    const data = await chrome.storage.local.get(["analysisResults", "apiUrl"]);
    const apiUrl = data.apiUrl || "http://localhost:8000";
    const feed = (data.analysisResults || []).map((r) => ({
      platform: r.platform,
      author: r.author,
      text: r.text,
      trust_score: r.trust_score,
      timestamp: r.timestamp,
    }));

    try {
      const resp = await fetch(`${apiUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, feed }),
      });
      const result = await resp.json();
      answerEl.textContent = result.answer || "No answer available.";
    } catch (err) {
      answerEl.textContent = "Could not reach the backend. Make sure it's running.";
    }

    btn.disabled = false;
    btn.textContent = "Ask";
  }

  btn.addEventListener("click", doSearch);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doSearch();
  });
}

// ── Ad-Free Button ──
function setupAdFree() {
  const btn = document.getElementById("goAdFreeBtn");
  if (!btn) return;
  btn.addEventListener("click", () => {
    btn.textContent = "✓ Thanks for your interest!";
    btn.style.background = "#34d399";
    setTimeout(() => {
      btn.textContent = "Go Ad-Free — only $2.99";
      btn.style.background = "";
    }, 2000);
  });
}

// ── Start ──
init();
