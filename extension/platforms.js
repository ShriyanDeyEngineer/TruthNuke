/**
 * Platform detection and DOM selectors for each social media site.
 * Each platform adapter knows how to find posts, extract text/author,
 * and where to inject the trust badge.
 */

// Common selectors for comment sections to exclude from text extraction
const COMMENT_SELECTORS = [
  '[class*="comment"]', '[class*="Comment"]',
  '[id*="comment"]', '[id*="Comment"]',
  '[data-module="comment"]', '[data-component="comment"]',
  '.discussion', '#discussion',
  '.responses', '#responses',
  '[class*="reply"]', '[class*="Reply"]',
].join(", ");

/** Extract article body text, excluding comments */
function extractArticleText(el) {
  const body = el.querySelector("article") || el.querySelector("main") || el;
  const paragraphs = body.querySelectorAll("p");
  if (paragraphs.length > 0) {
    return Array.from(paragraphs)
      .filter((p) => !p.closest(COMMENT_SELECTORS))
      .map((p) => p.textContent)
      .join(" ")
      .slice(0, 5000);
  }
  const headline = document.querySelector("h1")?.textContent || "";
  const desc = document.querySelector('meta[name="description"]')?.content || "";
  return `${headline} ${desc}`.trim();
}

const PLATFORMS = {
  twitter: {
    name: "Twitter/X",
    match: () =>
      location.hostname === "x.com" || location.hostname === "twitter.com",

    getPostElements: () =>
      document.querySelectorAll('article[data-testid="tweet"]'),

    getPostId: (el) => {
      const link = el.querySelector('a[href*="/status/"]');
      return link ? link.href : null;
    },

    getPostText: (el) => {
      // Only get the main tweet text, not replies/comments
      // Replies are nested articles — skip if this is inside another tweet
      if (el.closest('article[data-testid="tweet"]') !== el) return "";
      const textEl = el.querySelector('[data-testid="tweetText"]');
      return textEl ? textEl.textContent : "";
    },

    getAuthor: (el) => {
      const links = el.querySelectorAll('a[role="link"]');
      for (const link of links) {
        const href = link.getAttribute("href");
        if (
          href &&
          href.match(/^\/[a-zA-Z0-9_]+$/) &&
          !href.includes("/status")
        ) {
          return {
            handle: href.replace("/", ""),
            displayName: link.querySelector("span")?.textContent || "",
          };
        }
      }
      return { handle: "", displayName: "" };
    },

    getBadgeTarget: (el) => el.querySelector('[data-testid="User-Name"]'),
  },

  instagram: {
    name: "Instagram",
    match: () => location.hostname === "www.instagram.com",

    getPostElements: () => {
      const elements = new Set();
      const path = location.pathname;

      // 1. Feed posts and post detail pages — always look for <article>
      document.querySelectorAll("article").forEach((el) => elements.add(el));

      // 2. Dialog/modal overlays (clicking a post from grid)
      document.querySelectorAll('div[role="dialog"] article').forEach((el) => elements.add(el));

      // 3. Reels — /reels/ or /reel/ pages
      //    Instagram reels don't use <article>. The whole page IS the reel.
      if (path.includes("/reel")) {
        // Use the page itself as the "post element"
        const main = document.querySelector("main") || document.body;
        elements.add(main);
      }

      // 4. If nothing found yet, try the main content area as a fallback
      if (elements.size === 0) {
        const main = document.querySelector("main");
        if (main) elements.add(main);
      }

      return elements;
    },

    getPostId: () => {
      // Use the URL — it's unique per post/reel and works for SPA navigation
      return location.href;
    },

    getPostText: (el) => {
      const path = location.pathname;

      // For reels: search the whole page for caption text
      // For posts: search within the article element
      const searchRoot = path.includes("/reel") ? document : el;

      // Instagram captions are in spans. We want the longest non-comment text.
      // Comments live inside <ul> elements, so skip those.
      let bestText = "";
      const spans = searchRoot.querySelectorAll("span");
      for (const span of spans) {
        // Skip comment sections
        if (span.closest("ul")) continue;
        // Skip very short UI text
        const text = (span.textContent || "").trim();
        if (text.length > bestText.length && text.length > 15 && text.length < 3000) {
          bestText = text;
        }
      }

      // Also check h1/h2 (some layouts use headings for captions)
      const headings = searchRoot.querySelectorAll("h1, h2");
      for (const h of headings) {
        const text = (h.textContent || "").trim();
        if (text.length > bestText.length) bestText = text;
      }

      // Fallback: meta description (works on direct reel/post URLs)
      if (!bestText || bestText.length < 15) {
        const meta = document.querySelector('meta[name="description"], meta[property="og:description"]');
        if (meta?.content) bestText = meta.content;
      }

      return bestText;
    },

    getAuthor: (el) => {
      // Strategy: find links that look like /<username>/ (not /p/, /reel/, /explore/, etc.)
      const reservedPaths = /^\/(p|reel|reels|explore|accounts|stories|direct|about|developer|legal)\/?$/;
      const usernamePattern = /^\/([a-zA-Z0-9_.]{1,30})\/?$/;

      // Search in the element first, then broaden to main
      const roots = [el, document.querySelector("main"), document].filter(Boolean);

      for (const root of roots) {
        const links = root.querySelectorAll('a[href^="/"]');
        for (const link of links) {
          const href = link.getAttribute("href") || "";
          const match = href.match(usernamePattern);
          if (match && !reservedPaths.test(href)) {
            const handle = match[1];
            return {
              handle,
              displayName: link.textContent?.trim() || handle,
            };
          }
        }
        // If we found nothing in the element, try the next root
      }

      // Fallback: try og:title meta which often has "Author on Instagram"
      const ogTitle = document.querySelector('meta[property="og:title"]')?.content || "";
      const titleMatch = ogTitle.match(/^(.+?)(?:\s+on\s+Instagram|\s*[-|])/i);
      if (titleMatch) {
        return { handle: titleMatch[1].trim(), displayName: titleMatch[1].trim() };
      }

      return { handle: "", displayName: "" };
    },

    getBadgeTarget: (el) => {
      // 1. Post header (feed posts)
      const header = el.querySelector("header");
      if (header) return header;

      // 2. Find the first username link's parent (reels)
      const reservedPaths = /^\/(p|reel|reels|explore|accounts|stories|direct|about)\/?$/;
      const usernamePattern = /^\/[a-zA-Z0-9_.]{1,30}\/?$/;
      const roots = [el, document.querySelector("main")].filter(Boolean);

      for (const root of roots) {
        const links = root.querySelectorAll('a[href^="/"]');
        for (const link of links) {
          const href = link.getAttribute("href") || "";
          if (usernamePattern.test(href) && !reservedPaths.test(href)) {
            return link.parentElement || link;
          }
        }
      }

      // 3. Fallback: first h2 or the element itself
      return el.querySelector("h2")?.parentElement || el.querySelector("header") || null;
    },
  },

  tiktok: {
    name: "TikTok",
    match: () => location.hostname === "www.tiktok.com",

    getPostElements: () => {
      // TikTok feed items (For You page and following page)
      const feedItems = document.querySelectorAll(
        '[data-e2e="recommend-list-item-container"], ' +
          '[class*="DivItemContainer"], ' +
          '[class*="video-feed-item"]'
      );
      // Also check for video detail page
      const detailDesc = document.querySelectorAll(
        '[data-e2e="browse-video-desc"], [data-e2e="video-desc"]'
      );
      const all = new Set([...feedItems]);
      // Wrap detail descriptions in a pseudo-container if on a video page
      if (feedItems.length === 0 && detailDesc.length > 0) {
        detailDesc.forEach((d) => {
          const container = d.closest('[class*="Container"]') || d.parentElement;
          if (container) all.add(container);
        });
      }
      return all;
    },

    getPostId: (el) => {
      const link = el.querySelector('a[href*="/video/"]');
      return link ? link.href : el.textContent?.slice(0, 60);
    },

    getPostText: (el) => {
      // Video description / caption ONLY — skip comment sections
      const descEl =
        el.querySelector(
          '[data-e2e="video-desc"], [data-e2e="browse-video-desc"]'
        ) ||
        el.querySelector('[class*="DivVideoDesc"], [class*="video-meta"]');
      if (descEl) return descEl.textContent || "";
      // Fallback: grab visible text but skip comment containers
      const spans = el.querySelectorAll("span, h1, h2");
      let text = "";
      for (const s of spans) {
        // Skip comment sections
        if (s.closest('[data-e2e="comment-list"], [class*="CommentList"], [class*="comment"]')) continue;
        text += " " + (s.textContent || "");
      }
      return text.trim();
    },

    getAuthor: (el) => {
      const authorLink =
        el.querySelector('[data-e2e="video-author-uniqueid"]') ||
        el.querySelector('a[href*="/@"]');
      if (authorLink) {
        const href = authorLink.getAttribute("href") || "";
        const handle = href.replace(/.*\/@/, "").replace(/\/.*/, "");
        return {
          handle,
          displayName:
            el.querySelector('[data-e2e="video-author-nickname"]')
              ?.textContent || handle,
        };
      }
      return { handle: "", displayName: "" };
    },

    getBadgeTarget: (el) => {
      // Place next to author name
      const authorEl =
        el.querySelector('[data-e2e="video-author-uniqueid"]') ||
        el.querySelector('[data-e2e="video-author-nickname"]') ||
        el.querySelector('a[href*="/@"]');
      return authorEl?.parentElement || null;
    },
  },

  facebook: {
    name: "Facebook",
    match: () => location.hostname === "www.facebook.com",

    getPostElements: () => {
      return document.querySelectorAll(
        'div[role="article"], div[data-pagelet*="FeedUnit"]'
      );
    },

    getPostId: (el) => {
      const link = el.querySelector(
        'a[href*="/posts/"], a[href*="/permalink/"], a[href*="story_fbid"]'
      );
      return link ? link.href : el.textContent?.slice(0, 60);
    },

    getPostText: (el) => {
      // Get the main post text only — exclude comments section
      // Facebook comments are in nested div[role="article"] elements
      const isComment = el.parentElement?.closest('div[role="article"]');
      if (isComment) return "";

      const textDivs = el.querySelectorAll('div[dir="auto"]');
      let longestText = "";
      for (const div of textDivs) {
        // Skip text inside nested articles (comments)
        if (div.closest('div[role="article"]') !== el) continue;
        const text = div.textContent || "";
        if (text.length > longestText.length && text.length > 20 && text.length < 5000) {
          longestText = text;
        }
      }
      return longestText;
    },

    getAuthor: (el) => {
      const authorLink = el.querySelector(
        'h2 a[role="link"], h3 a[role="link"], h4 a[role="link"], strong a'
      );
      if (authorLink) {
        return {
          handle: authorLink.textContent || "",
          displayName: authorLink.textContent || "",
        };
      }
      return { handle: "", displayName: "" };
    },

    getBadgeTarget: (el) => {
      const authorEl = el.querySelector(
        'h2 a[role="link"], h3 a[role="link"], h4 a[role="link"], strong a'
      );
      return authorEl?.parentElement || null;
    },
  },

  // ── News Sites ──

  cnbc: {
    name: "CNBC",
    match: () => location.hostname === "www.cnbc.com",
    isNews: true,

    getPostElements: () => {
      // Article page
      const article = document.querySelector("article, .ArticleBody-articleBody, .PageBuilder-pageWrapper");
      if (article) return [article];
      // Homepage / listing — individual story cards
      return document.querySelectorAll('.Card-titleContainer, .RiverHeadline-headline, a[href*="/202"]');
    },

    getPostId: () => location.href,

    getPostText: (el) => {
      const body = el.querySelector(".ArticleBody-articleBody, .group, article");
      if (body) {
        const paragraphs = body.querySelectorAll("p");
        if (paragraphs.length > 0) {
          return Array.from(paragraphs)
            .filter((p) => !p.closest(COMMENT_SELECTORS))
            .map((p) => p.textContent).join(" ").slice(0, 5000);
        }
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

    getAuthor: () => {
      const byline = document.querySelector('.Author-authorName, .Author-authorNameAndSocial a, [data-testid="Author"] a, a[href*="/author/"]');
      return {
        handle: byline?.textContent?.trim() || "CNBC",
        displayName: byline?.textContent?.trim() || "CNBC",
      };
    },

    getBadgeTarget: () => {
      // Place badge next to the headline
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  fool: {
    name: "Motley Fool",
    match: () => location.hostname === "www.fool.com",
    isNews: true,
    getPostElements: () => {
      const article = document.querySelector("article, .article-body, main");
      if (article) return [article];
      return [];
    },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('.author-name, a[href*="/author/"], [rel="author"]');
      return {
        handle: byline?.textContent?.trim() || "Motley Fool",
        displayName: byline?.textContent?.trim() || "Motley Fool",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  marketwatch: {
    name: "MarketWatch",
    match: () => location.hostname === "www.marketwatch.com",
    isNews: true,
    getPostElements: () => {
      const article = document.querySelector("article, .article__body, main");
      if (article) return [article];
      return [];
    },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('.author, a[href*="/author/"], .article__byline a');
      return {
        handle: byline?.textContent?.trim() || "MarketWatch",
        displayName: byline?.textContent?.trim() || "MarketWatch",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  yahoo_finance: {
    name: "Yahoo Finance",
    match: () => location.hostname === "finance.yahoo.com",
    isNews: true,
    getPostElements: () => {
      const article = document.querySelector("article, .body, .caas-body, main");
      if (article) return [article];
      return [];
    },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('.caas-author-byline-collapse a, .byline-attr-author, a[href*="/author/"]');
      return {
        handle: byline?.textContent?.trim() || "Yahoo Finance",
        displayName: byline?.textContent?.trim() || "Yahoo Finance",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  bloomberg: {
    name: "Bloomberg",
    match: () => location.hostname === "www.bloomberg.com",
    isNews: true,
    getPostElements: () => { const a = document.querySelector("article, main"); return a ? [a] : []; },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('.author, a[href*="/authors/"], [rel="author"]');
      return { handle: byline?.textContent?.trim() || "Bloomberg", displayName: byline?.textContent?.trim() || "Bloomberg" };
    },
    getBadgeTarget: () => document.querySelector("h1")?.parentElement || null,
  },

  reuters: {
    name: "Reuters",
    match: () => location.hostname === "www.reuters.com",
    isNews: true,
    getPostElements: () => { const a = document.querySelector("article, main"); return a ? [a] : []; },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('a[href*="/authors/"], .author-name, [rel="author"]');
      return { handle: byline?.textContent?.trim() || "Reuters", displayName: byline?.textContent?.trim() || "Reuters" };
    },
    getBadgeTarget: () => document.querySelector("h1")?.parentElement || null,
  },

  investopedia: {
    name: "Investopedia",
    match: () => location.hostname === "www.investopedia.com",
    isNews: true,
    getPostElements: () => { const a = document.querySelector("article, .article-body, main"); return a ? [a] : []; },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('.by-author a, a[href*="/contributors/"], a[href*="/author/"]');
      return { handle: byline?.textContent?.trim() || "Investopedia", displayName: byline?.textContent?.trim() || "Investopedia" };
    },
    getBadgeTarget: () => document.querySelector("h1")?.parentElement || null,
  },

  benzinga: {
    name: "Benzinga",
    match: () => location.hostname === "www.benzinga.com",
    isNews: true,
    getPostElements: () => { const a = document.querySelector("article, .article-content-body, main"); return a ? [a] : []; },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('.author-name, a[href*="/author/"], .byline a');
      return { handle: byline?.textContent?.trim() || "Benzinga", displayName: byline?.textContent?.trim() || "Benzinga" };
    },
    getBadgeTarget: () => document.querySelector("h1")?.parentElement || null,
  },

  seekingalpha: {
    name: "Seeking Alpha",
    match: () => location.hostname === "seekingalpha.com",
    isNews: true,
    getPostElements: () => { const a = document.querySelector("article, [data-test-id='article-body'], main"); return a ? [a] : []; },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('[data-test-id="post-author"] a, a[href*="/author/"]');
      return { handle: byline?.textContent?.trim() || "Seeking Alpha", displayName: byline?.textContent?.trim() || "Seeking Alpha" };
    },
    getBadgeTarget: () => document.querySelector("h1")?.parentElement || null,
  },

  barrons: {
    name: "Barron's",
    match: () => location.hostname === "www.barrons.com",
    isNews: true,
    getPostElements: () => { const a = document.querySelector("article, main"); return a ? [a] : []; },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('.byline a, a[href*="/author/"], [rel="author"]');
      return { handle: byline?.textContent?.trim() || "Barron's", displayName: byline?.textContent?.trim() || "Barron's" };
    },
    getBadgeTarget: () => document.querySelector("h1")?.parentElement || null,
  },

  wsj: {
    name: "Wall Street Journal",
    match: () => location.hostname === "www.wsj.com",
    isNews: true,
    getPostElements: () => { const a = document.querySelector("article, main"); return a ? [a] : []; },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('.byline a, a[href*="/author/"], [rel="author"]');
      return { handle: byline?.textContent?.trim() || "WSJ", displayName: byline?.textContent?.trim() || "WSJ" };
    },
    getBadgeTarget: () => document.querySelector("h1")?.parentElement || null,
  },

  ft: {
    name: "Financial Times",
    match: () => location.hostname === "www.ft.com",
    isNews: true,
    getPostElements: () => { const a = document.querySelector("article, main"); return a ? [a] : []; },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('.article__author a, a[href*="/stream/author"], [rel="author"]');
      return { handle: byline?.textContent?.trim() || "Financial Times", displayName: byline?.textContent?.trim() || "Financial Times" };
    },
    getBadgeTarget: () => document.querySelector("h1")?.parentElement || null,
  },

  thestreet: {
    name: "TheStreet",
    match: () => location.hostname === "www.thestreet.com",
    isNews: true,
    getPostElements: () => { const a = document.querySelector("article, main"); return a ? [a] : []; },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('.author-name a, a[href*="/author/"], [rel="author"]');
      return { handle: byline?.textContent?.trim() || "TheStreet", displayName: byline?.textContent?.trim() || "TheStreet" };
    },
    getBadgeTarget: () => document.querySelector("h1")?.parentElement || null,
  },

  forbes: {
    name: "Forbes",
    match: () => location.hostname === "www.forbes.com",
    isNews: true,
    getPostElements: () => { const a = document.querySelector("article, .article-body, main"); return a ? [a] : []; },
    getPostId: () => location.href,
    getPostText: (el) => extractArticleText(el),
    getAuthor: () => {
      const byline = document.querySelector('.author-name a, a[href*="/sites/"], .fs-author-name a');
      return { handle: byline?.textContent?.trim() || "Forbes", displayName: byline?.textContent?.trim() || "Forbes" };
    },
    getBadgeTarget: () => document.querySelector("h1")?.parentElement || null,
  },
};

/**
 * Detect which platform we're currently on.
 * Returns the platform adapter object or null.
 */
function detectPlatform() {
  for (const [key, platform] of Object.entries(PLATFORMS)) {
    if (platform.match()) {
      console.log(`🛡️ TruthNuke: Detected platform — ${platform.name}`);
      return { key, ...platform };
    }
  }
  return null;
}
