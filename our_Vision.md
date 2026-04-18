🏦 Project: AI Financial Misinformation Detector
Working name: “TruthNuke”

🎯 Core Problem (Refined)
AI-generated financial misinformation is spreading fast and can:
Trigger panic (e.g., bank runs)
Mislead retail investors
Amplify scams
A Reuters report highlighted how AI-generated content could accelerate bank runs by spreading false financial signals.
👉 The gap:
Tools exist for fact-checking politics
Almost nothing exists for real-time financial misinformation detection for everyday users

💡 Solution Overview
A real-time AI system that:
Detects financial claims in content
Verifies them against trusted sources
Assigns a trust score
Explains why something may be misleading

🧩 Key Features (MVP → Advanced)
✅ 1. Financial Claim Detection
Input:
Tweet, Reddit post, article, or text
Output:
Extracted claims like:
“Bank X is going bankrupt”
“Stock Y will crash tomorrow”
Tech
NLP classification (LLM or fine-tuned model)

✅ 2. Misinformation Classification
Classifies content into:
✅ Verified / likely true
⚠️ Misleading
❌ Likely false
🚨 Potentially harmful (panic-inducing)
Tech
LLM + retrieval (RAG)
Prompting with financial context

✅ 3. Trust Score (Core Feature)
A 0–100 score based on:
Source credibility
Evidence availability
Language signals (sensational tone)
Cross-source agreement

✅ 4. Explanation Engine (THIS is what makes it stand out)
Instead of just saying “false,” it explains:
“This claim lacks supporting evidence from major financial outlets and uses emotionally charged language (‘collapse imminent’), which is common in misinformation.”

✅ 5. Source Verification
Cross-check against:
Major financial news (e.g., Bloomberg, CNBC)
Official sources (SEC filings, company statements)

🚀 Advanced Features (if we have time)
🔔 Real-Time Alerts
Detect trending misinformation spikes
🌐 Browser Extension
Highlights suspicious content directly on:
Twitter/X
Reddit
News sites
🧠 “What Happens If This Is Believed?”
Simulates potential impact:
“If widely believed, this could trigger sell-offs”

🏗️ System Architecture
🔹 Frontend
React / Next.js
UI Components:
Input box (paste content or URL)
Trust score meter
Explanation panel
Highlighted text (flagged phrases)

🔹 Backend
Node.js / FastAPI
Handles:
API routing
Model calls
Data aggregation

🔹 AI Layer
1. Claim Extraction
Use LLM (OpenAI API)
Prompt:
“Extract financial claims from this text”

2. Retrieval-Augmented Generation (RAG)
Query:
News APIs
Financial datasets
Compare claim vs reality

3. Classification Model
Options:
Simple: Prompt-based LLM classification
Advanced: Fine-tuned classifier

4. Scoring Engine
Custom heuristic:
Trust Score =
 (Source Credibility * 0.3) +
 (Evidence Strength * 0.3) +
 (Language Neutrality * 0.2) +
 (Cross-Source Agreement * 0.2)

🧠 AI Techniques Used
NLP (claim extraction)
LLM reasoning
Retrieval (RAG)
Text classification
Sentiment / tone analysis

📊 Example User Flow
Input:
“Breaking: XYZ Bank is collapsing—withdraw your money now!”
Output:
🚨 Trust Score: 18/100
⚠️ Classification: Likely misinformation
📌 Explanation:
No confirmation from major outlets
Uses panic-inducing language
Similar patterns seen in past false rumors

🧪 Datasets / APIs
News APIs
NewsAPI
GDELT
Financial Data
Yahoo Finance API
Optional
Reddit / Twitter scraping (for demo)

🎨 UI Design Ideas
Color-coded trust meter:
Green (safe)
Yellow (uncertain)
Red (danger)
Highlight:
“collapse imminent” → flagged as emotional trigger

⚠️ Challenges (Judges will care about this)
1. Hallucination risk
👉 Mitigation:
Always show sources
Add confidence scores

2. False positives
👉 Solution:
Show uncertainty instead of binary labels

3. Real-time accuracy
👉 Keep scope:
Focus on analysis, not perfect truth detection

Potential strengths of this software/tool
🔥 Extremely relevant (AI + finance risk)
🧠 Shows real AI understanding (not just API calls)
⚖️ Ethical + societal impact
🎯 Clear user value

🧩 MVP Scope (What we should ACTUALLY build)
If time is limited:
Build THIS:
Text input
Claim extraction (LLM)
Simple trust score
Explanation output
Skip (initially):
Browser extension
Real-time scraping
Complex ML training

