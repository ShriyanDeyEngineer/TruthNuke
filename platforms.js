/**
 * Platform detection and DOM selectors for each social media site.
 * Each platform adapter knows how to find posts, extract text/author,
 * and where to inject the trust badge.
 */

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

      // 1. Standard feed posts (articles)
      document.querySelectorAll("article").forEach((el) => elements.add(el));

      // 2. Dialog/modal posts and reels
      document
        .querySelectorAll(
          'div[role="presentation"] article, div[role="dialog"] article'
        )
        .forEach((el) => elements.add(el));

      // 3. Reels page — full-screen reel containers
      //    Instagram reels live in sections/divs on /reels/ URLs
      if (location.pathname.includes("/reel")) {
        // Single reel page: grab the main content area
        const mainContent = document.querySelector("main section") || document.querySelector("main");
        if (mainContent) {
          // Look for the reel video container with caption nearby
          const reelSections = mainContent.querySelectorAll("section");
          reelSections.forEach((s) => {
            if (s.querySelector("video") || s.querySelector("span")) {
              elements.add(s);
            }
          });
          // Fallback: if no sections found, use main itself
          if (reelSections.length === 0) elements.add(mainContent);
        }
      }

      // 4. Reels tab / scrollable reels feed
      //    Each reel in the feed is typically inside a div with a video element
      document
        .querySelectorAll(
          'div[style*="height: 100vh"], div[style*="height:100vh"], div[role="presentation"]'
        )
        .forEach((el) => {
          if (el.querySelector("video") && !elements.has(el)) {
            elements.add(el);
          }
        });

      return elements;
    },

    getPostId: (el) => {
      // Check for reel/post links within the element
      const link = el.querySelector('a[href*="/p/"], a[href*="/reel/"]');
      if (link) return link.href;
      // On a /reel/ page, use the URL itself
      if (location.pathname.includes("/reel")) return location.href;
      return el.textContent?.slice(0, 60);
    },

    getPostText: (el) => {
      // Strategy: collect text from multiple possible caption locations

      // 1. Look for spans with substantial text (captions)
      const captionSpans = el.querySelectorAll("span");
      let longestText = "";
      for (const span of captionSpans) {
        const text = span.textContent || "";
        if (text.length > longestText.length && text.length > 20) {
          longestText = text;
        }
      }

      // 2. On reel pages, also check for h1 elements (reel titles/captions)
      if (!longestText || longestText.length < 20) {
        const headings = el.querySelectorAll("h1, h2");
        for (const h of headings) {
          const text = h.textContent || "";
          if (text.length > longestText.length) longestText = text;
        }
      }

      // 3. On reel pages, captions can be in a sibling/nearby container
      if ((!longestText || longestText.length < 20) && location.pathname.includes("/reel")) {
        // Search the broader page for caption text
        const allSpans = document.querySelectorAll("main span");
        for (const span of allSpans) {
          const text = span.textContent || "";
          // Skip very short UI labels and very long comment sections
          if (text.length > longestText.length && text.length > 20 && text.length < 3000) {
            longestText = text;
          }
        }
      }

      return longestText;
    },

    getAuthor: (el) => {
      // 1. Standard post header link
      const headerLink = el.querySelector(
        'header a[href*="/"], span a[href*="/"]'
      );
      if (headerLink) {
        const href = headerLink.getAttribute("href") || "";
        const handle = href.replace(/\//g, "");
        if (handle && handle.length > 0 && handle.length < 40) {
          return {
            handle,
            displayName: headerLink.textContent || handle,
          };
        }
      }

      // 2. Reel page — author is often in a link near the video
      const authorLinks = (el.closest("main") || el).querySelectorAll('a[href^="/"]');
      for (const link of authorLinks) {
        const href = link.getAttribute("href") || "";
        // Match simple username paths like /username/ but not /p/ /reel/ /explore/ etc.
        if (
          href.match(/^\/[a-zA-Z0-9_.]+\/?$/) &&
          !href.match(/^\/(p|reel|reels|explore|accounts|stories|direct)\/?$/)
        ) {
          const handle = href.replace(/\//g, "");
          return {
            handle,
            displayName: link.textContent || handle,
          };
        }
      }

      return { handle: "", displayName: "" };
    },

    getBadgeTarget: (el) => {
      // 1. Standard post header
      const header = el.querySelector("header");
      if (header) {
        const nameContainer = header.querySelector(
          'span a, div[role="button"]'
        );
        return nameContainer?.parentElement || header;
      }

      // 2. Reel page — find the author name area to attach badge
      const authorLinks = (el.closest("main") || el).querySelectorAll('a[href^="/"]');
      for (const link of authorLinks) {
        const href = link.getAttribute("href") || "";
        if (
          href.match(/^\/[a-zA-Z0-9_.]+\/?$/) &&
          !href.match(/^\/(p|reel|reels|explore|accounts|stories|direct)\/?$/)
        ) {
          return link.parentElement || link;
        }
      }

      return null;
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
      // Video description / caption
      const descEl =
        el.querySelector(
          '[data-e2e="video-desc"], [data-e2e="browse-video-desc"]'
        ) ||
        el.querySelector('[class*="DivVideoDesc"], [class*="video-meta"]');
      if (descEl) return descEl.textContent || "";
      // Fallback: grab all visible text
      const spans = el.querySelectorAll("span, h1, h2");
      let text = "";
      for (const s of spans) {
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
      const textDivs = el.querySelectorAll('div[dir="auto"]');
      let longestText = "";
      for (const div of textDivs) {
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
      // Full article body
      const body = el.querySelector(".ArticleBody-articleBody, .group, article");
      if (body) {
        const paragraphs = body.querySelectorAll("p");
        if (paragraphs.length > 0) {
          return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
        }
      }
      // Headline + description fallback
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

    getPostText: (el) => {
      const body = el.querySelector(".article-body, .tailwind-article-body, article");
      if (body) {
        const paragraphs = body.querySelectorAll("p");
        if (paragraphs.length > 0) {
          return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
        }
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

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

    getPostText: (el) => {
      const body = el.querySelector(".article__body, .body, article");
      if (body) {
        const paragraphs = body.querySelectorAll("p");
        if (paragraphs.length > 0) {
          return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
        }
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

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

    getPostText: (el) => {
      const body = el.querySelector(".caas-body, .body, article");
      if (body) {
        const paragraphs = body.querySelectorAll("p");
        if (paragraphs.length > 0) {
          return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
        }
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

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

    getPostElements: () => {
      const article = document.querySelector("article, main");
      if (article) return [article];
      return [];
    },

    getPostId: () => location.href,

    getPostText: (el) => {
      const paragraphs = el.querySelectorAll("p");
      if (paragraphs.length > 0) {
        return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

    getAuthor: () => {
      const byline = document.querySelector('.author, a[href*="/authors/"], [rel="author"]');
      return {
        handle: byline?.textContent?.trim() || "Bloomberg",
        displayName: byline?.textContent?.trim() || "Bloomberg",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  reuters: {
    name: "Reuters",
    match: () => location.hostname === "www.reuters.com",
    isNews: true,

    getPostElements: () => {
      const article = document.querySelector("article, main");
      if (article) return [article];
      return [];
    },

    getPostId: () => location.href,

    getPostText: (el) => {
      const paragraphs = el.querySelectorAll("p");
      if (paragraphs.length > 0) {
        return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

    getAuthor: () => {
      const byline = document.querySelector('a[href*="/authors/"], .author-name, [rel="author"]');
      return {
        handle: byline?.textContent?.trim() || "Reuters",
        displayName: byline?.textContent?.trim() || "Reuters",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  investopedia: {
    name: "Investopedia",
    match: () => location.hostname === "www.investopedia.com",
    isNews: true,

    getPostElements: () => {
      const article = document.querySelector("article, .article-body, main");
      if (article) return [article];
      return [];
    },

    getPostId: () => location.href,

    getPostText: (el) => {
      const body = el.querySelector(".article-body, .article-body-content, article");
      if (body) {
        const paragraphs = body.querySelectorAll("p");
        if (paragraphs.length > 0) {
          return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
        }
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

    getAuthor: () => {
      const byline = document.querySelector('.by-author a, a[href*="/contributors/"], a[href*="/author/"]');
      return {
        handle: byline?.textContent?.trim() || "Investopedia",
        displayName: byline?.textContent?.trim() || "Investopedia",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  benzinga: {
    name: "Benzinga",
    match: () => location.hostname === "www.benzinga.com",
    isNews: true,

    getPostElements: () => {
      const article = document.querySelector("article, .article-content-body, main");
      if (article) return [article];
      return [];
    },

    getPostId: () => location.href,

    getPostText: (el) => {
      const body = el.querySelector(".article-content-body, .body-content, article");
      if (body) {
        const paragraphs = body.querySelectorAll("p");
        if (paragraphs.length > 0) {
          return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
        }
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

    getAuthor: () => {
      const byline = document.querySelector('.author-name, a[href*="/author/"], .byline a');
      return {
        handle: byline?.textContent?.trim() || "Benzinga",
        displayName: byline?.textContent?.trim() || "Benzinga",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  seekingalpha: {
    name: "Seeking Alpha",
    match: () => location.hostname === "seekingalpha.com",
    isNews: true,

    getPostElements: () => {
      const article = document.querySelector("article, [data-test-id='article-body'], main");
      if (article) return [article];
      return [];
    },

    getPostId: () => location.href,

    getPostText: (el) => {
      const body = el.querySelector("[data-test-id='article-body'], .paywall-full-content, article");
      if (body) {
        const paragraphs = body.querySelectorAll("p");
        if (paragraphs.length > 0) {
          return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
        }
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

    getAuthor: () => {
      const byline = document.querySelector('[data-test-id="post-author"] a, a[href*="/author/"]');
      return {
        handle: byline?.textContent?.trim() || "Seeking Alpha",
        displayName: byline?.textContent?.trim() || "Seeking Alpha",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  barrons: {
    name: "Barron's",
    match: () => location.hostname === "www.barrons.com",
    isNews: true,

    getPostElements: () => {
      const article = document.querySelector("article, main");
      if (article) return [article];
      return [];
    },

    getPostId: () => location.href,

    getPostText: (el) => {
      const paragraphs = el.querySelectorAll("p");
      if (paragraphs.length > 0) {
        return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

    getAuthor: () => {
      const byline = document.querySelector('.byline a, a[href*="/author/"], [rel="author"]');
      return {
        handle: byline?.textContent?.trim() || "Barron's",
        displayName: byline?.textContent?.trim() || "Barron's",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  wsj: {
    name: "Wall Street Journal",
    match: () => location.hostname === "www.wsj.com",
    isNews: true,

    getPostElements: () => {
      const article = document.querySelector("article, main");
      if (article) return [article];
      return [];
    },

    getPostId: () => location.href,

    getPostText: (el) => {
      const paragraphs = el.querySelectorAll("p");
      if (paragraphs.length > 0) {
        return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

    getAuthor: () => {
      const byline = document.querySelector('.byline a, a[href*="/author/"], [rel="author"]');
      return {
        handle: byline?.textContent?.trim() || "WSJ",
        displayName: byline?.textContent?.trim() || "WSJ",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  ft: {
    name: "Financial Times",
    match: () => location.hostname === "www.ft.com",
    isNews: true,

    getPostElements: () => {
      const article = document.querySelector("article, main");
      if (article) return [article];
      return [];
    },

    getPostId: () => location.href,

    getPostText: (el) => {
      const body = el.querySelector(".article__body, .body, article");
      if (body) {
        const paragraphs = body.querySelectorAll("p");
        if (paragraphs.length > 0) {
          return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
        }
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

    getAuthor: () => {
      const byline = document.querySelector('.article__author a, a[href*="/stream/author"], [rel="author"]');
      return {
        handle: byline?.textContent?.trim() || "Financial Times",
        displayName: byline?.textContent?.trim() || "Financial Times",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  thestreet: {
    name: "TheStreet",
    match: () => location.hostname === "www.thestreet.com",
    isNews: true,

    getPostElements: () => {
      const article = document.querySelector("article, main");
      if (article) return [article];
      return [];
    },

    getPostId: () => location.href,

    getPostText: (el) => {
      const paragraphs = el.querySelectorAll("p");
      if (paragraphs.length > 0) {
        return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

    getAuthor: () => {
      const byline = document.querySelector('.author-name a, a[href*="/author/"], [rel="author"]');
      return {
        handle: byline?.textContent?.trim() || "TheStreet",
        displayName: byline?.textContent?.trim() || "TheStreet",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
  },

  forbes: {
    name: "Forbes",
    match: () => location.hostname === "www.forbes.com",
    isNews: true,

    getPostElements: () => {
      const article = document.querySelector("article, .article-body, main");
      if (article) return [article];
      return [];
    },

    getPostId: () => location.href,

    getPostText: (el) => {
      const body = el.querySelector(".article-body, .body-container, article");
      if (body) {
        const paragraphs = body.querySelectorAll("p");
        if (paragraphs.length > 0) {
          return Array.from(paragraphs).map((p) => p.textContent).join(" ").slice(0, 5000);
        }
      }
      const headline = document.querySelector("h1")?.textContent || "";
      const desc = document.querySelector('meta[name="description"]')?.content || "";
      return `${headline} ${desc}`.trim();
    },

    getAuthor: () => {
      const byline = document.querySelector('.author-name a, a[href*="/sites/"], .fs-author-name a');
      return {
        handle: byline?.textContent?.trim() || "Forbes",
        displayName: byline?.textContent?.trim() || "Forbes",
      };
    },

    getBadgeTarget: () => {
      return document.querySelector("h1")?.parentElement || null;
    },
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
