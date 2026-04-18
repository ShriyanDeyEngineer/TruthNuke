// TruthNuke - Content Script
// Detects finance-related posts on supported platforms and injects trust badges
// Analysis triggers when the user stops scrolling for a few seconds
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

// Scroll-idle detection
let scrollIdleTimer = null;
const SCROLL_IDLE_DELAY = 3000; // 3 seconds of no scrolling
let isAnalyzing = false;

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
    posts.forEach((post) => {
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

const ANALYSIS_TIMEOUT_MS = 30000; // 30 seconds

async function analyzePost(postElement) {
  const postText = platform.getPostText(postElement);
  if (!postText) return;

  // News sites always analyze; social media needs finance keyword match
  if (!platform.isNews && !isFinanceRelated(postText)) return;

  const postId = platform.getPostId(postElement) || postText.slice(0, 80);
  if (processedPosts.has(postId)) return;
  processedPosts.add(postId);

  const authorInfo = platform.getAuthor(postElement);
  const badgeTarget = platform.getBadgeTarget(postElement);
  if (!badgeTarget) return;

  const headline = document.querySelector("h1")?.textContent?.slice(0, 60) || postText.slice(0, 60);

  // Notify popup that analysis is in progress (progress shows in popup, not on page)
  chrome.runtime.sendMessage({
    type: "ANALYSIS_LOADING",
    data: {
      headline,
      author: authorInfo.handle,
      platform: platform.key,
    },
  }).catch(() => {});

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), ANALYSIS_TIMEOUT_MS);

  try {
    isAnalyzing = true;
    const response = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: postText.slice(0, 3000), // Truncate to keep requests fast
        author: authorInfo.handle,
        author_name: authorInfo.displayName,
        platform: platform.key,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) throw new Error(`API error: ${response.status}`);

    const data = await response.json();

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
    }).catch(() => {});

    const badge = createBadge(data.trust_score, {
      ...data,
      author: authorInfo.handle,
    });
    badgeTarget.appendChild(badge);
  } catch (err) {
    clearTimeout(timeoutId);
    console.error("TruthNuke analysis failed:", err);

    const isTimeout = err.name === "AbortError";
    const errorBadge = document.createElement("span");
    errorBadge.className = "fintrust-badge trust-error";

    if (isTimeout) {
      errorBadge.innerHTML = `<span class="badge-icon">⏱️</span> Timed out — <span class="fintrust-retry">Retry</span>`;
    } else {
      errorBadge.innerHTML = `<span class="badge-icon">⚡</span> Offline — <span class="fintrust-retry">Retry</span>`;
    }

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
      data: {
        headline,
        author: authorInfo.handle,
        platform: platform.key,
        isTimeout,
      },
    }).catch(() => {});
  } finally {
    isAnalyzing = false;
  }
}

function scanVisiblePosts() {
  const posts = platform.getPostElements();
  posts.forEach((post) => analyzePost(post));
}

function onScrollIdle() {
  // User stopped scrolling — analyze visible posts
  if (!isAnalyzing) {
    scanVisiblePosts();
  }
}

function init() {
  // Set up scroll-idle detection: analyze when user stops scrolling for 3 seconds
  const resetIdleTimer = () => {
    clearTimeout(scrollIdleTimer);
    scrollIdleTimer = setTimeout(onScrollIdle, SCROLL_IDLE_DELAY);
  };

  window.addEventListener("scroll", resetIdleTimer, { passive: true });
  window.addEventListener("mousemove", resetIdleTimer, { passive: true });
  window.addEventListener("touchmove", resetIdleTimer, { passive: true });

  // Also trigger on initial page load after a short delay
  setTimeout(onScrollIdle, 2000);

  // Watch for new posts loaded via infinite scroll / SPA navigation
  const observer = new MutationObserver((mutations) => {
    let hasNew = false;
    for (const mutation of mutations) {
      if (mutation.addedNodes.length > 0) {
        hasNew = true;
        break;
      }
    }
    if (hasNew) {
      // Reset idle timer when new content loads
      resetIdleTimer();
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });

  // Re-scan on URL changes (SPA navigation)
  let lastUrl = location.href;
  const urlObserver = new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      setTimeout(onScrollIdle, 2000);
    }
  });
  urlObserver.observe(document.body, { childList: true, subtree: true });

  console.log(
    `🛡️ TruthNuke loaded — monitoring ${platform.name}. Stop scrolling for 3 seconds to analyze posts.`
  );
}
