// TruthNuke Background Service Worker
// Persists analysis results to chrome.storage so the popup always has fresh data,
// even if it was closed when the content script finished analyzing.

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "ANALYSIS_RESULT") {
    // Save to storage so popup can read it on open
    chrome.storage.local.get(["analysisResults"], (data) => {
      const results = data.analysisResults || [];
      results.unshift(msg.data);
      // Keep max 50
      if (results.length > 50) results.length = 50;
      chrome.storage.local.set({
        analysisResults: results,
        lastResult: msg.data,
      });
    });
  }

  if (msg.type === "ANALYSIS_LOADING" || msg.type === "ANALYSIS_ERROR") {
    // Store the latest status so popup can pick it up when opened
    chrome.storage.local.set({ lastStatus: msg });
  }
});
