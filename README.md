# News → Telegram → X Bot

Pulls news articles, sends them to a Telegram group for human approval, then posts approved ones to X automatically.

## How it works

```
News API → Dedup check → Telegram group
                              ↓
                    [✅ Post to X] [❌ Skip]
                              ↓
                         X (Twitter)
```

1. Bot polls your news API every N minutes (default: 15)
2. Deduplication filters out articles that are too similar to recent ones
3. New articles are sent to your Telegram group with **Post** / **Skip** buttons
4. Click **Post** → published to X immediately
5. Click **Skip** → discarded quietly

---

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the **Bot Token** you receive
4. Create or open your group, then add the bot as a member
5. Promote the bot to **Admin** (it needs permission to send messages)
6. Get your group's chat ID:
   - Send any message in the group
   - Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find `"chat": {"id": -XXXXXXXXX}` — that negative number is your group ID

### 2. Get X API Keys

1. Go to [developer.x.com](https://developer.x.com) and create an account
2. Create a new **Project** and **App**
3. Under **App settings → User authentication settings**, set permissions to **Read and Write**
4. Go to **Keys and Tokens** and generate:
   - API Key & Secret
   - Access Token & Secret
5. Copy all four values

### 3. Deploy to Railway

1. Push this repo to GitHub
2. Sign in at [railway.app](https://railway.app) and create a **New Project**
3. Choose **Deploy from GitHub repo** and select your repo
4. Go to **Variables** and add all the env vars from `.env.example`
5. Railway will build and deploy automatically — that's it

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | From @BotFather |
| `TELEGRAM_GROUP_ID` | ✅ | Your group's chat ID (negative number) |
| `X_API_KEY` | ✅ | X consumer key |
| `X_API_SECRET` | ✅ | X consumer secret |
| `X_ACCESS_TOKEN` | ✅ | X access token |
| `X_ACCESS_TOKEN_SECRET` | ✅ | X access token secret |
| `NEWS_API_KEY` | ⚠️ | newsapi.org key (if using default client) |
| `NEWS_COUNTRY` | ❌ | Default: `us` |
| `NEWS_CATEGORY` | ❌ | Default: `technology` |
| `NEWS_PAGE_SIZE` | ❌ | Articles per poll (default: `10`) |
| `SIMILARITY_THRESHOLD` | ❌ | Dedup sensitivity 0–1 (default: `0.80`) |
| `DEDUP_WINDOW_HOURS` | ❌ | Hours to look back for duplicates (default: `24`) |
| `POLL_INTERVAL_MINUTES` | ❌ | How often to fetch news (default: `15`) |

---

## Using Your Own News API

Open `news_client.py` and add your own client class:

```python
class MyNewsClient(NewsClient):
    def fetch_articles(self) -> list[dict]:
        resp = requests.get(
            "https://your-api.com/articles",
            headers={"Authorization": f"Bearer {os.getenv('MY_API_KEY')}"},
            timeout=10,
        )
        resp.raise_for_status()
        return [
            {
                "title":        a["headline"],
                "description":  a.get("summary", ""),
                "url":          a["link"],
                "published_at": a.get("date", ""),
                "source":       a.get("publisher", ""),
            }
            for a in resp.json().get("results", [])
        ]
```

Then in `bot.py`, change:
```python
news_client = NewsAPIClient()   # ← before
news_client = MyNewsClient()    # ← after
```

---

## Tuning Deduplication

If you're getting too many duplicates slipping through → lower `SIMILARITY_THRESHOLD` (e.g. `0.70`).  
If unrelated articles are being blocked → raise it (e.g. `0.90`).

The bot compares incoming article titles against everything seen in the last `DEDUP_WINDOW_HOURS` hours using fuzzy token matching, so reworded headlines of the same story are caught automatically.

---

## File Structure

```
main.py          — Entry point, starts the bot
config.py        — All environment variables
database.py      — SQLite: seen articles + pending approvals
deduplicator.py  — Fuzzy similarity checking
news_client.py   — News API integration (swap in your own here)
x_poster.py      — Posts to X via Tweepy
bot.py           — Telegram handlers, message formatting, scheduler
requirements.txt
railway.toml
.env.example
```
