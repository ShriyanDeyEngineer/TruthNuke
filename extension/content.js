// TruthNuke - Content Script
// Detects finance-related posts on supported platforms and injects trust badges
// Analysis triggers when the user stops scrolling for a few seconds
// Platform adapters are loaded from platforms.js

const API_BASE_DEFAULT = "http://localhost:8000";
let API_BASE = API_BASE_DEFAULT;

// Load custom API URL from storage if set
chrome.storage?.local?.get(["apiUrl"], (data) => {
  if (data?.apiUrl) API_BASE = data.apiUrl;
});

// Finance-related keywords to detect relevant posts
const FINANCE_KEYWORDS = [
  // Market terms
  "stock", "stocks", "equity", "shares", "market", "portfolio", "dividend",
  "earnings", "ipo", "etf", "mutual fund", "sp500", "s&p", "nasdaq", "dow", "nyse",
  // Trading actions
  "buy", "sell", "short", "long", "trade", "trading", "calls", "puts",
  "options", "strike", "expiry", "forex", "leverage",
  // Crypto
  "crypto", "bitcoin", "btc", "eth", "ethereum", "altcoin", "defi",
  "nft", "blockchain", "token", "staking",
  // Hype (high signal)
  "guaranteed returns", "risk-free", "free money", "easy money",
  "moon", "to the moon", "100x", "10x", "pump", "dump",
  "passive income", "financial freedom", "retire early",
  "nfa", "dyor", "not financial advice",
  // Tickers
  "$tsla", "$aapl", "$amzn", "$goog", "$msft", "$nvda", "$spy", "$btc",
  // General
  "invest", "investing", "investment", "trader", "bull", "bear",
  "roi", "yield", "apy", "apr", "market cap",
  "get rich", "guaranteed", "sure thing"
];

// Track which posts we've already processed
const processedPosts = new Set();

// Detect current platform
const platform = detectPlatform();

if (!platform) {
  console.log("🛡️ TruthNuke: No supported platform detected on this page.");
} else {
  init();
}

// Respond to popup messages
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "PING") {
    sendResponse({ status: "alive", platform: platform?.key || null });
  }
  if (msg.type === "GET_CURRENT_POST") {
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
    if (!platform) return;
    const posts = platform.getPostElements();
    const postArray = posts instanceof Set ? [...posts] : Array.from(posts);
    postArray.forEach((post) => {
      const postId = platform.getPostId(post) || "";
      processedPosts.delete(postId);
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
            ${c.sources && c.sources.length > 0 ? `<div class="claim-sources">${c.sources.map((s) => `<span class="claim-source">📰 ${s}</span>`).join("")}</div>` : ""}
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
    ${data.sources && data.sources.length > 0 ? `
    <div class="tooltip-sources">
      <strong>📰 Cross-reference:</strong>
      <ul>${data.sources.map((s) => `<li>${s}</li>`).join("")}</ul>
    </div>` : ""}
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

const ANALYSIS_TIMEOUT_MS = 50000; // 50 seconds

// Active request controller — abort when user navigates to a new post
let activeController = null;

function cancelActiveAnalysis() {
  if (activeController) {
    activeController.abort();
    activeController = null;
  }
}

async function analyzePost(postElement) {
  const postText = platform.getPostText(postElement);
  if (!postText) {
    console.log("🛡️ TruthNuke: Skipped post — no text found");
    return;
  }

  if (!platform.isNews && postText.length < 30 && !isFinanceRelated(postText)) {
    console.log("🛡️ TruthNuke: Skipped short non-finance post");
    return;
  }

  const postId = platform.getPostId(postElement) || postText.slice(0, 80);
  if (processedPosts.has(postId)) return;
  processedPosts.add(postId);

  const authorInfo = platform.getAuthor(postElement);
  const badgeTarget = platform.getBadgeTarget(postElement);
  if (!badgeTarget) {
    console.log("🛡️ TruthNuke: Skipped post — no badge target found for @" + authorInfo.handle);
    return;
  }

  // Cancel any in-flight analysis (user moved on)
  cancelActiveAnalysis();

  console.log(`🛡️ TruthNuke: Analyzing post by @${authorInfo.handle} (${postText.length} chars)`);
  const headline = document.querySelector("h1")?.textContent?.slice(0, 60) || postText.slice(0, 60);

  chrome.runtime.sendMessage({
    type: "ANALYSIS_LOADING",
    data: { headline, author: authorInfo.handle, platform: platform.key },
  }).catch(() => {});

  const controller = new AbortController();
  activeController = controller;
  const timeoutId = setTimeout(() => controller.abort(), ANALYSIS_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: postText.slice(0, 3000),
        author: authorInfo.handle,
        author_name: authorInfo.displayName,
        platform: platform.key,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    if (activeController !== controller) return; // User already moved on

    if (!response.ok) throw new Error(`API error: ${response.status}`);

    const data = await response.json();
    activeController = null;

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
    }).catch(() => {});

    const badge = createBadge(data.trust_score, { ...data, author: authorInfo.handle });
    badgeTarget.appendChild(badge);
  } catch (err) {
    clearTimeout(timeoutId);

    // If aborted because user moved on, silently skip — don't show error badge
    if (err.name === "AbortError" && activeController !== controller) {
      console.log("🛡️ TruthNuke: Cancelled stale analysis for @" + authorInfo.handle);
      processedPosts.delete(postId); // Allow re-analysis if user comes back
      return;
    }

    activeController = null;
    console.error("TruthNuke analysis failed:", err);

    const isTimeout = err.name === "AbortError";
    const errorBadge = document.createElement("span");
    errorBadge.className = "fintrust-badge trust-error";
    errorBadge.innerHTML = isTimeout
      ? `<span class="badge-icon">⏱️</span> Timed out — <span class="fintrust-retry">Retry</span>`
      : `<span class="badge-icon">⚡</span> Offline — <span class="fintrust-retry">Retry</span>`;

    errorBadge.querySelector(".fintrust-retry").addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      errorBadge.remove();
      processedPosts.delete(postId);
      analyzePost(postElement);
    });

    badgeTarget.appendChild(errorBadge);

    chrome.runtime.sendMessage({
      type: "ANALYSIS_ERROR",
      data: { headline, author: authorInfo.handle, platform: platform.key, isTimeout },
    }).catch(() => {});
  }
}

function scanVisiblePosts() {
  const posts = platform.getPostElements();
  const postArray = posts instanceof Set ? [...posts] : Array.from(posts);
  console.log(`🛡️ TruthNuke: Scanning — found ${postArray.length} post element(s)`);
  postArray.forEach((post) => analyzePost(post));
}

function init() {
  // Scan immediately, then keep retrying until we find something
  // This handles slow-loading SPAs where content appears after initial load
  let retryCount = 0;
  const maxRetries = 10;

  function tryScan() {
    const posts = platform.getPostElements();
    const postArray = posts instanceof Set ? [...posts] : Array.from(posts);

    if (postArray.length > 0) {
      scanVisiblePosts();
      retryCount = 0; // Reset for next navigation
    } else if (retryCount < maxRetries) {
      retryCount++;
      setTimeout(tryScan, 1000); // Retry every second
    }
  }

  // Initial scan with retries
  setTimeout(tryScan, 1000);

  // Watch for new content (infinite scroll, lazy loading)
  let scanDebounce = null;
  const observer = new MutationObserver(() => {
    clearTimeout(scanDebounce);
    scanDebounce = setTimeout(scanVisiblePosts, 1500);
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });

  // Re-scan on URL changes (SPA navigation — Twitter, TikTok, etc.)
  let lastUrl = location.href;
  setInterval(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      // Cancel any in-flight analysis and clear for new page
      cancelActiveAnalysis();
      processedPosts.clear();
      document.querySelectorAll(".fintrust-badge, .fintrust-tooltip").forEach((el) => el.remove());
      // Retry scan with delays to catch late-loading content
      retryCount = 0;
      setTimeout(tryScan, 1000);
      setTimeout(tryScan, 2500);
      setTimeout(tryScan, 5000);
    }
  }, 500);

  // Also scan on scroll stop (catches content that loads as you scroll)
  let scrollTimer = null;
  window.addEventListener("scroll", () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(scanVisiblePosts, 2000);
  }, { passive: true });

  // TikTok-specific: detect video swipes (URL doesn't change on For You page)
  // Poll for the currently visible video changing
  if (platform.key === "tiktok") {
    let lastVideoId = null;
    setInterval(() => {
      const posts = platform.getPostElements();
      const postArray = posts instanceof Set ? [...posts] : Array.from(posts);
      if (postArray.length === 0) return;
      const currentId = platform.getPostId(postArray[0]);
      if (currentId && currentId !== lastVideoId) {
        lastVideoId = currentId;
        console.log(`🛡️ TruthNuke: TikTok video changed — ${currentId.slice(0, 60)}`);
        cancelActiveAnalysis();
        scanVisiblePosts();
      }
    }, 1500);
  }

  console.log(`🛡️ TruthNuke loaded — monitoring ${platform.name}`);
}
