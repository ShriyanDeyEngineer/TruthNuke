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
      // Instagram feed posts and reels comments
      const posts = document.querySelectorAll("article");
      // Also grab explore/reel overlay text
      const reelItems = document.querySelectorAll(
        'div[role="presentation"] article, div[role="dialog"] article'
      );
      return new Set([...posts, ...reelItems]);
    },

    getPostId: (el) => {
      const link = el.querySelector('a[href*="/p/"], a[href*="/reel/"]');
      return link ? link.href : el.textContent?.slice(0, 60);
    },

    getPostText: (el) => {
      // Instagram caption is usually in a span inside the first list item or a div with specific structure
      const captionSpans = el.querySelectorAll("span");
      let longestText = "";
      for (const span of captionSpans) {
        const text = span.textContent || "";
        if (text.length > longestText.length && text.length > 20) {
          longestText = text;
        }
      }
      return longestText;
    },

    getAuthor: (el) => {
      // Author handle is typically in a header link
      const headerLink = el.querySelector(
        'header a[href*="/"], span a[href*="/"]'
      );
      if (headerLink) {
        const href = headerLink.getAttribute("href") || "";
        const handle = href.replace(/\//g, "");
        return {
          handle,
          displayName: headerLink.textContent || handle,
        };
      }
      return { handle: "", displayName: "" };
    },

    getBadgeTarget: (el) => {
      // Place badge next to the username in the post header
      const header = el.querySelector("header");
      if (header) {
        const nameContainer = header.querySelector(
          'span a, div[role="button"]'
        );
        return nameContainer?.parentElement || header;
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
      // Facebook feed posts — they use role="article" or data-pagelet
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
      // Facebook post text is in a div with dir="auto" inside the post
      const textDivs = el.querySelectorAll('div[dir="auto"]');
      let longestText = "";
      for (const div of textDivs) {
        const text = div.textContent || "";
        // Skip very short strings (likely UI elements) and very long ones (comments section)
        if (text.length > longestText.length && text.length > 20 && text.length < 5000) {
          longestText = text;
        }
      }
      return longestText;
    },

    getAuthor: (el) => {
      // Author is usually the first strong tag or h2/h3 link in the post
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
      // Place next to the author name
      const authorEl = el.querySelector(
        'h2 a[role="link"], h3 a[role="link"], h4 a[role="link"], strong a'
      );
      return authorEl?.parentElement || null;
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
      console.log(`🛡️ FinTrust: Detected platform — ${platform.name}`);
      return { key, ...platform };
    }
  }
  return null;
}
