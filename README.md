# Ingredient Lens

A Streamlit app that reads the ingredient label on a food product photo and explains what's actually in it — in plain, friendly language, not a chemistry lecture.

**Live app:** https://multi-modal-ingredient-analyzer-using-vision-and-text-based-in.streamlit.app/

## What It Does

Upload a photo of a product's ingredient list (or snap one with your camera), and the app:

1. Reads the ingredients straight off the label using a vision-capable LLM (Google Gemini).
2. Translates anything technical into plain English — no jargon without a plain-words explanation.
3. Breaks the analysis into a few clear, skimmable sections.
4. Lets you ask follow-up questions about the specific product (e.g. *"Is this safe for someone with a gluten allergy?"*).

The goal is a friend standing next to you in the grocery aisle, not a lab report.

## Features

- **Two ways to capture a label** — drag-and-drop file upload or live camera capture, right in the browser.
- **Plain-language analysis**, structured into:
  - 🧾 **What's In It** — a quick, grouped rundown of the ingredients
  - ⚠️ **Things To Watch For** — additives/preservatives worth knowing about, explained simply
  - 🥗 **Diet Fit** — a quick vegan / halal / kosher read
  - ⭐ **Health Score** — a 1–5 star rating with one plain-English reason
  - 💡 **Better Options** — a healthier alternative, only when genuinely relevant
- **Follow-up Q&A** — ask anything else about the analyzed product; the conversation keeps the ingredient context.
- **Fast by design** — images are downscaled/compressed before analysis, and the model is instructed to only reach for a web search when it's genuinely unsure of something, instead of by default.
- **Graceful failure** — a hard timeout and explicit error handling mean a slow or failed AI/network call surfaces a clear message instead of an endless spinner.

## Tech Stack

| Piece | Choice |
|---|---|
| UI | [Streamlit](https://streamlit.io/) |
| Agent framework | [phidata](https://github.com/phidatahq/phidata) (`Agent`) |
| Vision + language model | Google **Gemini 3.6 Flash** via `google-generativeai` |
| Optional web verification | [Tavily](https://tavily.com/) search API (`search_depth="basic"`, used sparingly) |
| Image handling | Pillow |
| Hosting | [Streamlit Community Cloud](https://streamlit.io/cloud) |

## How It Works

```
 upload / camera photo
          │
          ▼
  downscale + compress (≤1600px longest side, JPEG q85)
          │
          ▼
  phidata Agent  ──►  Gemini 3.6 Flash (vision)
          │                  │
          │        (only if genuinely unsure)
          │                  ▼
          │           Tavily web search
          │                  │
          └──────────◄───────┘
          ▼
  Markdown response, styled + rendered in Streamlit
```

The system prompt and structure instructions live in [`constants.py`](constants.py) — that's the file to edit to change the analysis tone, sections, or depth. All UI/layout/styling logic lives in [`app.py`](app.py).

## Project Structure

```
app.py            # Streamlit UI, image handling, agent orchestration
constants.py       # System prompt + instructions that shape the AI's analysis style
requirements.txt   # Runtime dependencies (kept minimal — only what app.py imports)
.python-version     # Pins Python 3.12 for the deploy target
.streamlit/
  secrets.toml      # Local-only API keys (never committed — see below)
Images/             # Sample product photos for manual testing
```

## Running It Locally

**Requirements:** Python 3.12, a [Google AI Studio](https://aistudio.google.com/app/apikey) API key, and a [Tavily](https://tavily.com/) API key (free tier is fine for both).

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` (this file is git-ignored — never commit real keys):

```toml
GEMINI_KEY = "your-gemini-api-key"
TAVILY_KEY = "your-tavily-api-key"
```

Then run:

```bash
streamlit run app.py
```

This opens the app at `http://localhost:8501`.

## Deploying

The live app is hosted on **Streamlit Community Cloud**, deployed straight from this repo's `main` branch:

1. [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub → **Create app**.
2. Point it at this repo, branch `main`, main file `app.py`.
3. Under **Advanced settings → Secrets**, paste the same two keys as above (`GEMINI_KEY`, `TAVILY_KEY`).
4. Deploy. Any push to `main` auto-redeploys.

## A Note on Rate Limits

This project runs on Google's **free tier** for the Gemini API, which caps out at:

- 5 requests per minute
- **20 requests per day**, total

That's easy to exhaust during active testing/demoing — each analysis and each follow-up question counts as one request. If you see *"Google's Free Tier quota is temporarily exhausted,"* it resets daily (~midnight Pacific), or you can raise the limit substantially by enabling billing on the associated Google Cloud project (Tier 1 raises it to 1,000/min and 10,000/day).

## Known Limitations

- Free-tier daily quota (see above) — not meant for high-traffic use as-is.
- Analysis quality depends on how legible the label photo is; blurry or angled shots may need a retake.
- Search-tool verification is intentionally used sparingly to keep response times reasonable, so very obscure or newly-reformulated products may lean more on the model's own knowledge than live web data.

## License

Built as a course project. No license specified — treat as all-rights-reserved by default unless the repo owner adds one.
