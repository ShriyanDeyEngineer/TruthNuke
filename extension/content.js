// TruthNuke - Content Script
// Detects finance-related posts on any supported platform and injects trust badges
// Platform adapters are loaded from platforms.js

const API_BASE = "http://localhost:8000"; // Change to deployed URL in production

// Finance-related keywords to detect relevant posts
const FINANCE_KEYWORDS = [
  "stock", "stocks", "invest", "investing", "investment", "trader", "trading",
  "crypto", "bitcoin", "btc", "eth", "ethereum", "altcoin", "defi",
  "buy", "sell", "short", "long", "bull", "bear", "moon", "pump", "dump",
  "portfolio", "dividend", "earnings", "ipo", "etf", "mutual fund",
  "forex", "options", "calls", "puts", "strike", "expiry",
  "sp500", "s&p", "nasdaq", "dow", "nyse",
  "passive income", "financial freedom", "retire early", "fire",
  "roi", "yield", "apy", "apr", "market cap",
  "$tsla", "$aapl", "$amzn", "$goog", "$msft", "$nvda", "$spy", "$btc",
  "nfa", "dyor", "not financial advice", "to the moon",
  "10x", "100x", "guaranteed returns", "free money"
];

// Track which posts we've already processed
const processedPosts = new Set();

// Settings (loaded from chrome.storage, updated via listener)
let settings = {
  autoAnalyze: true,
  showAll: false,
};

// Load settings from storage, then initialize
async function loadSettings() {
  const data = await chrome.storage.local.get(["autoAnalyze", "showAll"]);
  settings.autoAnalyze = data.autoAnalyze !== false; // default true
  settings.showAll = data.showAll === true;           // default false
}

// Keep settings in sync when changed from the popup
chrome.storage.onChanged.addListener((changes) => {
  if (changes.autoAnalyze) settings.autoAnalyze = changes.autoAnalyze.newValue !== false;
  if (changes.showAll) settings.showAll = changes.showAll.newValue === true;
});

// Detect current platform
const platform = detectPlatform();

if (!platform) {
  console.log("🛡️ TruthNuke: No supported platform detected on this page.");
} else {
  loadSettings().then(() => init());
}

// Respond to popup messages
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "PING") {
    sendResponse({ status: "alive", platform: platform?.key || null });
  }
  if (msg.type === "GET_CURRENT_POST") {
    // Return info about the current page/post for the manual analyze button
    if (!platform) {
      sendResponse({ found: false });
      return;
    }
    const posts = platform.getPostElements();
    const firstPost = posts instanceof Set ? [...posts][0] : posts[0];
    if (!firstPost) {
      sendResponse({ found: false });
      return;
    }
    const text = platform.getPostText(firstPost);
    const author = platform.getAuthor(firstPost);
    const headline = document.querySelector("h1")?.textContent?.slice(0, 80) || text?.slice(0, 80) || "";
    sendResponse({
      found: true,
      headline,
      author: author.handle,
      authorName: author.displayName,
      platform: platform.key,
    });
  }
  if (msg.type === "MANUAL_ANALYZE") {
    // Triggered from popup — analyze the current page
    if (!platform) return;
    const posts = platform.getPostElements();
    posts.forEach((post) => {
      const postId = platform.getPostId(post) || "";
      processedPosts.delete(postId); // Allow re-analysis
      analyzePost(post);
    });
  }
});

function isFinanceRelated(text) {
  const lower = text.toLowerCase();
  if (/\$[a-zA-Z]{1,5}\b/.test(text)) return true;
  return FINANCE_KEYWORDS.some((kw) => lower.includes(kw));
}

function createBadge(score, data) {
  const badge = document.createElement("span");
  badge.className = "fintrust-badge";

  let level, icon, label;
  if (score >= 70) {
    level = "high";
    icon = "✅";
    label = "Trustworthy";
  } else if (score >= 40) {
    level = "medium";
    icon = "⚠️";
    label = "Caution";
  } else {
    level = "low";
    icon = "🚩";
    label = "Unreliable";
  }

  badge.classList.add(`trust-${level}`);
  badge.innerHTML = `<span class="badge-icon">${icon}</span> ${label} (${score}/100)`;

  // Build tooltip
  const tooltip = document.createElement("div");
  tooltip.className = "fintrust-tooltip";

  let flagsHtml = "";
  if (data.flags && data.flags.length > 0) {
    flagsHtml = `
      <ul class="tooltip-flags">
        ${data.flags.map((f) => `<li>${f}</li>`).join("")}
      </ul>`;
  }

  let claimsHtml = "";
  if (data.claims && data.claims.length > 0) {
    claimsHtml = `
      <div class="tooltip-claims">
        <strong>Claims detected:</strong>
        ${data.claims
          .map(
            (c) => `
          <div class="claim-item">
            <div class="claim-text">"${c.claim}"</div>
            <div class="claim-verdict ${c.verdict}">${c.verdict}: ${c.explanation}</div>
          </div>`
          )
          .join("")}
      </div>`;
  }

  tooltip.innerHTML = `
    <div class="tooltip-header">
      <div>
        <div class="tooltip-label">Trust Score</div>
        <div class="tooltip-score" style="color: ${
          level === "high" ? "#6ee7b7" : level === "medium" ? "#fcd34d" : "#fca5a5"
        }">${score}/100</div>
      </div>
      <div style="text-align: right;">
        <div class="tooltip-label">Source</div>
        <div>@${data.author || "unknown"}</div>
      </div>
    </div>
    ${flagsHtml}
    ${claimsHtml}
    <div class="tooltip-explanation">
      ${data.explanation || "Analysis based on content patterns and source credibility."}
    </div>
    <div style="margin-top: 8px; font-size: 11px; color: #6b7280;">
      Powered by TruthNuke · ${platform.name} · Not financial advice
    </div>
  `;

  badge.appendChild(tooltip);

  badge.addEventListener("click", (e) => {
    e.stopPropagation();
    e.preventDefault();
    document.querySelectorAll(".fintrust-tooltip.visible").forEach((t) => {
      if (t !== tooltip) t.classList.remove("visible");
    });
    tooltip.classList.toggle("visible");
  });

  document.addEventListener("click", () => {
    tooltip.classList.remove("visible");
  });

  return badge;
}

function createLoadingBadge(headline) {
  const badge = document.createElement("span");
  badge.className = "fintrust-badge trust-loading";
  const shortTitle = headline ? headline.slice(0, 40) + (headline.length > 40 ? "…" : "") : "";
  badge.innerHTML = `<span class="fintrust-spinner"></span> Analyzing${shortTitle ? ": " + shortTitle : "..."}`;
  return badge;
}

const ANALYSIS_TIMEOUT_MS = 30000; // 30 seconds

async function analyzePost(postElement) {
  const postText = platform.getPostText(postElement);
  if (!postText) return;

  // Skip non-finance posts unless "showAll" is enabled
  // News sites are always finance-related regardless of setting
  if (!platform.isNews && !settings.showAll && !isFinanceRelated(postText)) return;

  const postId = platform.getPostId(postElement) || postText.slice(0, 80);
  if (processedPosts.has(postId)) return;
  processedPosts.add(postId);

  const authorInfo = platform.getAuthor(postElement);
  const badgeTarget = platform.getBadgeTarget(postElement);
  if (!badgeTarget) return;

  const headline = document.querySelector("h1")?.textContent?.slice(0, 60) || postText.slice(0, 60);
  const loadingBadge = createLoadingBadge(headline);
  badgeTarget.appendChild(loadingBadge);

  // Notify popup that analysis is in progress
  chrome.runtime.sendMessage({
    type: "ANALYSIS_LOADING",
    data: {
      headline,
      author: authorInfo.handle,
      platform: platform.key,
    },
  }).catch(() => {});

  // Create an AbortController for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), ANALYSIS_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: postText,
        author: authorInfo.handle,
        author_name: authorInfo.displayName,
        platform: platform.key,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) throw new Error(`API error: ${response.status}`);

    const data = await response.json();
    loadingBadge.remove();

    // Send result to popup dashboard
    chrome.runtime.sendMessage({
      type: "ANALYSIS_RESULT",
      data: {
        ...data,
        author: authorInfo.handle,
        author_name: authorInfo.displayName,
        text: postText.slice(0, 200),
        platform: platform.key,
        timestamp: Date.now(),
      },
    }).catch(() => {}); // Popup may not be open

    const badge = createBadge(data.trust_score, {
      ...data,
      author: authorInfo.handle,
    });
    badgeTarget.appendChild(badge);
  } catch (err) {
<<<<<<< HEAD
=======
    clearTimeout(timeoutId);
>>>>>>> 094d948 (Added progress bar + pop up for user to wait for analyze)
    console.error("TruthNuke analysis failed:", err);
    loadingBadge.remove();

    const isTimeout = err.name === "AbortError";
    const errorBadge = document.createElement("span");
    errorBadge.className = "fintrust-badge trust-error";

    if (isTimeout) {
      errorBadge.innerHTML = `<span class="badge-icon">⏱️</span> Timed out — <span class="fintrust-retry">Retry</span>`;
    } else {
      errorBadge.innerHTML = `<span class="badge-icon">⚡</span> Offline — <span class="fintrust-retry">Retry</span>`;
    }

    // Allow retry on click
    errorBadge.querySelector(".fintrust-retry").addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      errorBadge.remove();
      processedPosts.delete(postId);
      analyzePost(postElement);
    });

    badgeTarget.appendChild(errorBadge);

    // Notify popup of the error
    chrome.runtime.sendMessage({
      type: "ANALYSIS_ERROR",
      data: {
        headline,
        author: authorInfo.handle,
        platform: platform.key,
        isTimeout,
      },
    }).catch(() => {});
  }
}

function scanForPosts() {
  // Only scan if auto-analyze is enabled
  if (!settings.autoAnalyze) return;

  const posts = platform.getPostElements();
  posts.forEach((post) => analyzePost(post));
}

function init() {
  // Initial scan
  scanForPosts();

  // Watch for new posts loaded via infinite scroll / SPA navigation
  const observer = new MutationObserver((mutations) => {
    let shouldScan = false;
    for (const mutation of mutations) {
      if (mutation.addedNodes.length > 0) {
        shouldScan = true;
        break;
      }
    }
    if (shouldScan) {
      clearTimeout(observer._timeout);
      observer._timeout = setTimeout(scanForPosts, 500);
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });

  // Also re-scan on URL changes (SPA navigation for reels, stories, etc.)
  let lastUrl = location.href;
  const urlObserver = new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      setTimeout(scanForPosts, 1000);
    }
  });
  urlObserver.observe(document.body, { childList: true, subtree: true });

  console.log(
    `🛡️ TruthNuke loaded — monitoring ${platform.name} for financial posts`
  );
}
