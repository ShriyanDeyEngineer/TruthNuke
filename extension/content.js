// TruthNuke - Content Script
// Detects finance-related posts on supported platforms and injects trust badges
// Analysis triggers when the user stops scrolling for a few seconds

const API_BASE = "http://localhost:8000";

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

const processedPosts = new Set();
let scrollIdleTimer = null;
const SCROLL_IDLE_DELAY = 3000;
let isAnalyzing = false;

const platform = detectPlatform();

if (!platform) {
  console.log("🛡️ TruthNuke: No supported platform detected.");
} else {
  init();
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "PING") {
    sendResponse({ status: "alive", platform: platform?.key || null });
  }
  if (msg.type === "GET_CURRENT_POST") {
    if (!platform) { sendResponse({ found: false }); return; }
    const posts = platform.getPostElements();
    const firstPost = posts instanceof Set ? [...posts][0] : posts[0];
    if (!firstPost) { sendResponse({ found: false }); return; }
    const text = platform.getPostText(firstPost);
    const author = platform.getAuthor(firstPost);
    const headline = document.querySelector("h1")?.textContent?.slice(0, 80) || text?.slice(0, 80) || "";
    sendResponse({ found: true, headline, author: author.handle, authorName: author.displayName, platform: platform.key });
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

/**
 * Transform our backend response into the format the badge/tooltip expects.
 */
function transformResponse(data) {
  const claims = (data.claims || []).map((ca) => ({
    claim: ca.claim?.text || "",
    verdict: (ca.classification?.label || "").toLowerCase().replace("_", " "),
    explanation: ca.classification?.reasoning?.slice(0, 150) || "",
  }));

  const flags = [];
  if (data.trust_score !== null && data.trust_score < 40) flags.push("Low trust score");
  if (data.trust_score_breakdown) {
    if (data.trust_score_breakdown.source_credibility < 40) flags.push("Low source credibility");
    if (data.trust_score_breakdown.language_neutrality < 40) flags.push("Emotional/manipulative language detected");
    if (data.trust_score_breakdown.cross_source_agreement < 40) flags.push("Sources disagree");
  }
  for (const ca of data.claims || []) {
    if (ca.classification?.label === "HARMFUL") flags.push("Potentially harmful content");
    if (ca.classification?.label === "LIKELY_FALSE") flags.push("Likely false claim detected");
  }

  // Surface risk assessment signals
  const risk = data.risk_assessment;
  if (risk) {
    if (risk.risk_level === "high") flags.push(`⚠️ High risk score (${risk.risk_score})`);
    else if (risk.risk_level === "medium") flags.push(`Risk score: ${risk.risk_score} (medium)`);
    if (risk.signals?.phrases?.length > 0) {
      flags.push(`Risky phrases: ${risk.signals.phrases.slice(0, 3).join(", ")}`);
    }
    if (risk.signals?.keywords?.hype?.length > 0) {
      flags.push(`Hype language: ${risk.signals.keywords.hype.slice(0, 3).join(", ")}`);
    }
  }

  return {
    trust_score: data.trust_score ?? 50,
    explanation: data.explanation || "",
    risk_explanation: risk?.explanation || "",
    claims,
    flags: [...new Set(flags)],
  };
}

function createBadge(score, data) {
  const badge = document.createElement("span");
  badge.className = "fintrust-badge";

  let level, icon, label;
  if (score >= 70) { level = "high"; icon = "✅"; label = "Trustworthy"; }
  else if (score >= 40) { level = "medium"; icon = "⚠️"; label = "Caution"; }
  else { level = "low"; icon = "🚩"; label = "Unreliable"; }

  badge.classList.add(`trust-${level}`);
  badge.innerHTML = `<span class="badge-icon">${icon}</span> ${label} (${score}/100)`;

  const tooltip = document.createElement("div");
  tooltip.className = "fintrust-tooltip";

  let flagsHtml = "";
  if (data.flags && data.flags.length > 0) {
    flagsHtml = `<ul class="tooltip-flags">${data.flags.map((f) => `<li>${f}</li>`).join("")}</ul>`;
  }

  let claimsHtml = "";
  if (data.claims && data.claims.length > 0) {
    claimsHtml = `<div class="tooltip-claims"><strong>Claims detected:</strong>${data.claims.map((c) => `
      <div class="claim-item">
        <div class="claim-text">"${c.claim}"</div>
        <div class="claim-verdict ${c.verdict}">${c.verdict}: ${c.explanation}</div>
      </div>`).join("")}</div>`;
  }

  tooltip.innerHTML = `
    <div class="tooltip-header">
      <div><div class="tooltip-label">Trust Score</div>
        <div class="tooltip-score" style="color: ${level === "high" ? "#6ee7b7" : level === "medium" ? "#fcd34d" : "#fca5a5"}">${score}/100</div></div>
      <div style="text-align: right;"><div class="tooltip-label">Source</div><div>@${data.author || "unknown"}</div></div>
    </div>
    ${flagsHtml}${claimsHtml}
    <div class="tooltip-explanation">${data.explanation || "Analysis based on content patterns and source credibility."}</div>
    <div style="margin-top: 8px; font-size: 11px; color: #6b7280;">Powered by TruthNuke · ${platform.name} · Not financial advice</div>`;

  badge.appendChild(tooltip);
  badge.addEventListener("click", (e) => {
    e.stopPropagation(); e.preventDefault();
    document.querySelectorAll(".fintrust-tooltip.visible").forEach((t) => { if (t !== tooltip) t.classList.remove("visible"); });
    tooltip.classList.toggle("visible");
  });
  document.addEventListener("click", () => tooltip.classList.remove("visible"));
  return badge;
}

const ANALYSIS_TIMEOUT_MS = 120000;

async function analyzePost(postElement) {
  const postText = platform.getPostText(postElement);
  if (!postText) return;
  if (!platform.isNews && !isFinanceRelated(postText)) return;

  const postId = platform.getPostId(postElement) || postText.slice(0, 80);
  if (processedPosts.has(postId)) return;
  processedPosts.add(postId);

  const authorInfo = platform.getAuthor(postElement);
  const badgeTarget = platform.getBadgeTarget(postElement);
  if (!badgeTarget) return;

  const headline = document.querySelector("h1")?.textContent?.slice(0, 60) || postText.slice(0, 60);

  chrome.runtime.sendMessage({ type: "ANALYSIS_LOADING", data: { headline, author: authorInfo.handle, platform: platform.key } }).catch(() => {});

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), ANALYSIS_TIMEOUT_MS);

  try {
    isAnalyzing = true;
    const response = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: postText.slice(0, 3000) }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!response.ok) throw new Error(`API error: ${response.status}`);

    const rawData = await response.json();
    const data = transformResponse(rawData);

    chrome.runtime.sendMessage({
      type: "ANALYSIS_RESULT",
      data: { ...data, author: authorInfo.handle, author_name: authorInfo.displayName, text: postText.slice(0, 200), platform: platform.key, timestamp: Date.now() },
    }).catch(() => {});

    const badge = createBadge(data.trust_score, { ...data, author: authorInfo.handle });
    badgeTarget.appendChild(badge);
  } catch (err) {
    clearTimeout(timeoutId);
    console.error("TruthNuke analysis failed:", err);
    const isTimeout = err.name === "AbortError";
    const errorBadge = document.createElement("span");
    errorBadge.className = "fintrust-badge trust-error";
    errorBadge.innerHTML = isTimeout
      ? `<span class="badge-icon">⏱️</span> Timed out — <span class="fintrust-retry">Retry</span>`
      : `<span class="badge-icon">⚡</span> Offline — <span class="fintrust-retry">Retry</span>`;
    errorBadge.querySelector(".fintrust-retry").addEventListener("click", (e) => {
      e.stopPropagation(); e.preventDefault(); errorBadge.remove(); processedPosts.delete(postId); analyzePost(postElement);
    });
    badgeTarget.appendChild(errorBadge);
    chrome.runtime.sendMessage({ type: "ANALYSIS_ERROR", data: { headline, author: authorInfo.handle, platform: platform.key, isTimeout } }).catch(() => {});
  } finally {
    isAnalyzing = false;
  }
}

function scanVisiblePosts() { platform.getPostElements().forEach((post) => analyzePost(post)); }

function init() {
  const resetIdleTimer = () => { clearTimeout(scrollIdleTimer); scrollIdleTimer = setTimeout(() => { if (!isAnalyzing) scanVisiblePosts(); }, SCROLL_IDLE_DELAY); };
  window.addEventListener("scroll", resetIdleTimer, { passive: true });
  window.addEventListener("mousemove", resetIdleTimer, { passive: true });
  setTimeout(() => { if (!isAnalyzing) scanVisiblePosts(); }, 2000);

  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) { if (m.addedNodes.length > 0) { resetIdleTimer(); break; } }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  let lastUrl = location.href;
  new MutationObserver(() => { if (location.href !== lastUrl) { lastUrl = location.href; setTimeout(() => { if (!isAnalyzing) scanVisiblePosts(); }, 2000); } }).observe(document.body, { childList: true, subtree: true });

  console.log(`🛡️ TruthNuke loaded — monitoring ${platform.name}`);
}
