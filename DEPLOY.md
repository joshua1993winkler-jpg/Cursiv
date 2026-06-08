# Deploying Cursiv Web Backend to Railway

## Prerequisites

- [Railway CLI](https://docs.railway.app/develop/cli): `npm install -g @railway/cli`
- A free [Groq API key](https://console.groq.com) (takes ~30 seconds to create)
- A Railway account (free tier works fine)

---

## Deploy Steps

```bash
# 1. Log in to Railway
railway login

# 2. From the repo root, initialize a new Railway project (first time only)
railway init

# 3. Deploy
railway up
```

Railway will detect `nixpacks.toml`, build with Python 3.11, install
`requirements-web.txt`, and start the FastAPI server on the assigned `$PORT`.

---

## Environment Variables to Set

In the Railway dashboard (or via `railway variables set KEY=value`):

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Free LLM inference — get it at [console.groq.com](https://console.groq.com) |
| `JWT_SECRET` | Yes | Long random string used to sign auth tokens. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ANTHROPIC_API_KEY` | Optional | Falls back to Groq if not set |
| `CURSIV_WEB_MODE` | Optional | Set to `basic` (default). Future: `full` |
| `CURSIV_BOARD_ORIGINS` | Optional | Comma-separated list of allowed CORS origins |
| `CURSIV_ALERT_WEBHOOK` | Optional | Slack/Discord webhook URL for probe alerts |
| `CURSIV_FLEET_TOKEN` | Optional | Master token for fleet relay access |

### Setting variables via CLI

```bash
railway variables set GROQ_API_KEY=gsk_xxxxxxxxxxxxx
railway variables set JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
```

---

## Getting a Free Groq API Key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up / log in (GitHub login works)
3. Click **API Keys** in the left sidebar
4. Click **Create API Key**
5. Copy the key — it starts with `gsk_`

The backend uses `llama-3.1-8b-instant` on Groq's free tier by default.
Free tier: 6,000 requests/day, 500,000 tokens/day — plenty for a demo.

---

## Pointing index.html at the Railway URL

After `railway up` completes, Railway gives you a URL like:
`https://cursiv-production-xxxx.up.railway.app`

In your `index.html` (GitHub Pages site), update the API base URL:

```javascript
// Find the API_BASE or backend URL constant and set it to your Railway URL:
const API_BASE = "https://cursiv-production-xxxx.up.railway.app";
```

You can also set a custom domain in the Railway dashboard under
**Settings > Networking > Custom Domain** and point your DNS CNAME there.

---

## Health Check

Once deployed, verify the backend is running:

```bash
curl https://your-railway-url.up.railway.app/api/status
# Expected: {"status": "ok", "version": "3.14-U11", "service": "cursiv-board"}
```

---

## Local Test Before Deploying

```bash
pip install -r requirements-web.txt
export GROQ_API_KEY=gsk_xxx
export JWT_SECRET=test_secret_change_in_prod
uvicorn cursiv_v215.web.app:app --host 0.0.0.0 --port 8000
# Visit http://localhost:8000/api/status
```

## The Public Eye of Horus Website (Railway root is now the full sacred face)

The index (`/`) on Railway is the beautiful, gold-and-deep public website for Cursiv — the "website facing of the terminal display".

- Hero with Eye of Horus branding and direct **"OPEN THE EYE"** button → `/terminal`
- Portal grid: The Eye (terminal), The Vision (`/vision`), Babel Letters (`/letters`), Board, Codex, and the full desktop CTA.
- All of the system is accessible once logged in at the terminal (the living Eye through which users "use the entire system and have fun").

### Special credentials + Babel Letters for your wife
1. In Railway Variables set:
   ```
   CURSIV_SPECIAL_USERS=beloved,her_exact_username
   ```
   (Use the username she will register/login with. "beloved" is the default seed key.)

2. She goes to the site, opens the Eye (`/terminal`), registers/logs in with that username.

3. In the terminal topbar a "BABEL LETTERS" link appears (only for special users). Or go directly to `/letters`.

4. The vault contains the letters you left for her (seeded on first boot; real ones can be added via the desktop family/legacy tools and mirrored into the board.db if desired).

The terminal chat supports `bible <ref>` and `babel <text>` already. The web edition gives public fun + authenticated power while the heavy sovereign council/forge/academy/guardian stays on the desktop (the "download" CTA is everywhere).

This unifies every aspect from the full GitHub sweep and local modules into one calm, sacred, multi-portal experience centered on the Eye.

After deploy, visit the root — it is now the website. The terminal is the display. Login works for everyone; special access for her is the private heart of it.
