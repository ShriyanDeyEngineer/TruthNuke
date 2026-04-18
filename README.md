# 🛡️ TruthNuke — Social Media Finance Checker

A browser extension that analyzes financial advice on social media and rates the trustworthiness of sources. Built to protect beginner investors from misleading influencer content.

## How It Works

1. Extension detects finance-related posts on Twitter/X, Instagram, TikTok, and Facebook
2. Sends post content to the backend API
3. AI extracts claims, detects manipulation tactics, and cross-references market data
4. Displays a trust badge (✅ Trustworthy / ⚠️ Caution / 🚩 Unreliable) on the post
5. Click the badge for a detailed breakdown

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Twitter/X | ✅ | Feed posts, replies |
| Instagram | ✅ | Feed posts, reels |
| TikTok | ✅ | For You page, video pages |
| Facebook | ✅ | News feed posts |

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python main.py
```

The API runs at `http://localhost:8000`. Check `http://localhost:8000/health` to verify.

### Extension

1. Open Chrome → `chrome://extensions/`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked" → select the `extension/` folder
4. Navigate to Twitter/X — badges will appear on finance posts

## API Keys Needed

| Key | Where to get it | Required |
|-----|-----------------|----------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Yes |
| `ALPHA_VANTAGE_API_KEY` | [alphavantage.co](https://www.alphavantage.co/support/#api-key) | Optional (free tier) |

## Tech Stack

- **Extension**: Chrome Manifest V3, vanilla JS, multi-platform content scripts
- **Backend**: Python, FastAPI
- **AI**: Claude (claim extraction + manipulation detection)
- **Market Data**: Alpha Vantage API
