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

// ── Initialize ──
async function init() {
  setupTabs();
  await detectPlatformStatus();
  await loadStoredData();
  listenForUpdates();
  setupSettings();
  setupManualAnalyze();
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

  if (match) {
    pill.classList.add("active");
    pill.classList.remove("inactive");
    pill.querySelector(".status-text").textContent = "Active";
    label.textContent = `Monitoring ${match.icon} ${match.name}`;

    // Ping content script to confirm it's running
    try {
      const response = await chrome.tabs.sendMessage(currentTabId, { type: "PING" });
      if (response?.status === "alive") {
        pill.querySelector(".status-text").textContent = "Active";
      }
    } catch {
      pill.querySelector(".status-text").textContent = "Loading...";
    }
  } else {
    pill.classList.add("inactive");
    pill.classList.remove("active");
    pill.querySelector(".status-text").textContent = "Inactive";
    label.textContent = "Visit a supported site to start";
  }
}

// ── Load Stored Analysis Data ──
async function loadStoredData() {
  const data = await chrome.storage.local.get(["analysisResults", "autoAnalyze", "showAll", "apiUrl", "lastResult", "lastStatus"]);
  analysisResults = data.analysisResults || [];
  renderStats();
  renderFeed();
  renderDistribution();

  // Show the most recent result if available
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
    // Clear the transient status
    chrome.storage.local.remove("lastStatus");
  }

  // Settings
  document.getElementById("autoAnalyze").checked = data.autoAnalyze !== false;
  document.getElementById("showAll").checked = data.showAll === true;
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
      // Clear transient status
      chrome.storage.local.remove("lastStatus");
      // Add to front of list
      analysisResults.unshift(msg.data);
      // Keep max 50 results
      if (analysisResults.length > 50) analysisResults.pop();
      // Persist
      chrome.storage.local.set({ analysisResults });
      // Update UI
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

// ── Loading State ──
function showLoadingState(data) {
  const card = document.getElementById("loadingCard");
  card.style.display = "block";
  document.getElementById("loadingHeadline").textContent = data.headline || "Post";
  document.getElementById("loadingAuthor").textContent = data.author ? `by @${data.author}` : "";

  loadingStartTime = Date.now();
  clearInterval(loadingTimerInterval);
  const timerEl = document.getElementById("loadingTimer");
  timerEl.textContent = "0s elapsed";

  loadingTimerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - loadingStartTime) / 1000);
    if (elapsed >= 30) {
      timerEl.textContent = "Taking longer than expected…";
      timerEl.style.color = "#f87171";
    } else {
      timerEl.textContent = `${elapsed}s elapsed`;
      timerEl.style.color = "#4b5563";
    }
  }, 1000);
}

function hideLoadingState() {
  document.getElementById("loadingCard").style.display = "none";
  clearInterval(loadingTimerInterval);
}

function showErrorState(data) {
  hideLoadingState();
  const card = document.getElementById("loadingCard");
  card.style.display = "block";
  const headline = data.headline || "Post";
  document.getElementById("loadingHeadline").textContent = data.isTimeout
    ? `⏱️ Timed out analyzing: ${headline}`
    : `⚡ Error analyzing: ${headline}`;
  document.getElementById("loadingAuthor").textContent = "Click the retry link on the page badge, or try again.";
  document.getElementById("loadingTimer").textContent = "";
  document.querySelector(".loading-spinner-container").style.display = "none";

  // Auto-hide after 5 seconds
  setTimeout(() => {
    card.style.display = "none";
    document.querySelector(".loading-spinner-container").style.display = "flex";
  }, 5000);
}

// ── Manual Analyze ──
async function setupManualAnalyze() {
  const data = await chrome.storage.local.get(["autoAnalyze"]);
  const autoAnalyze = data.autoAnalyze !== false;
  const card = document.getElementById("manualAnalyzeCard");
  const btn = document.getElementById("manualAnalyzeBtn");

  if (autoAnalyze || !currentTabId) {
    card.style.display = "none";
    return;
  }

  // Ask content script for current post info
  try {
    const response = await chrome.tabs.sendMessage(currentTabId, { type: "GET_CURRENT_POST" });
    if (response?.found) {
      card.style.display = "block";
      document.getElementById("manualHeadline").textContent = response.headline || "Current page";
      document.getElementById("manualAuthor").textContent = response.author ? `by @${response.author}` : response.authorName || "";
    } else {
      card.style.display = "none";
    }
  } catch {
    card.style.display = "none";
    return;
  }

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.textContent = "Analyzing…";
    try {
      await chrome.tabs.sendMessage(currentTabId, { type: "MANUAL_ANALYZE" });
    } catch {
      btn.textContent = "⚡ Error — try refreshing the page";
    }
    // Re-enable after a delay
    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = "🔍 Analyze This Page";
    }, 3000);
  });
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
        <p>No posts analyzed yet. Scroll through your feed to see results here.</p>
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

  // Click to view details
  feedList.querySelectorAll(".feed-item").forEach((item) => {
    item.addEventListener("click", () => {
      const idx = parseInt(item.dataset.index);
      showCurrentPost(analysisResults[idx]);
      // Switch to dashboard tab
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

  // Animate score ring
  const circumference = 2 * Math.PI * 52; // r=52
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

  // Flags
  const flagsEl = document.getElementById("currentFlags");
  if (data.flags && data.flags.length > 0) {
    flagsEl.innerHTML = data.flags.map((f) => `<span class="flag-chip">⚠️ ${escapeHtml(f)}</span>`).join("");
  } else {
    flagsEl.innerHTML = "";
  }

  // Claims
  const claimsEl = document.getElementById("currentClaims");
  if (data.claims && data.claims.length > 0) {
    claimsEl.innerHTML = data.claims
      .map(
        (c) => `
      <div class="claim-card ${c.verdict}">
        <div class="claim-text">"${escapeHtml(c.claim)}"</div>
        <div class="claim-verdict ${c.verdict}">${c.verdict}${c.explanation ? " — " + escapeHtml(c.explanation) : ""}</div>
      </div>`
      )
      .join("");
  } else {
    claimsEl.innerHTML = "";
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

  document.getElementById("autoAnalyze").addEventListener("change", (e) => {
    chrome.storage.local.set({ autoAnalyze: e.target.checked });
    // Show/hide manual analyze button
    if (e.target.checked) {
      document.getElementById("manualAnalyzeCard").style.display = "none";
    } else {
      setupManualAnalyze();
    }
  });

  document.getElementById("showAll").addEventListener("change", (e) => {
    chrome.storage.local.set({ showAll: e.target.checked });
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

// ── Start ──
init();
