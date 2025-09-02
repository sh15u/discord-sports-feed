# JP Sports Enriched RSS (TrustDice-linked)

This minimal script aggregates **Japanese sports news** (NPB / Jリーグ / 競馬 / MLB) and **automatically appends a stable TrustDice sports page link** for each item. You can point the generated RSS to **MEE6 RSS** to auto-post into your Discord.

> This version **does not** attempt per-match deep linking. Instead, it links to the stable league/sport page you provided:
>
> - Jリーグ: `https://trustdice.win/ja/sports/soccer/japan/jleague-cup-1714283915738488832`
> - NPB: `https://trustdice.win/ja/sports/baseball/japan/npb-1723217780884512768`
> - MLB: `https://trustdice.win/ja/sports/baseball/usa/mlb-1671175995522211840`
> - 競馬: `https://trustdice.win/ja/sports/horse-racing-55`

---

## 1) Quick Start (local)

```bash
# (optional) create venv
python3 -m venv .venv && source .venv/bin/activate

pip install -r requirements.txt

python enrich.py
# => writes dist/feed.xml
```

Open `dist/feed.xml` in a browser to verify.

---

## 2) Configure feeds / target links

Edit **config.json** to adjust:
- `feeds`: RSS URLs and the *stable* TrustDice page for that sport
- `feed_title`, `feed_link`, `feed_description`

> Tip: You can add or remove feeds any time. If you later want to split output by sport (one RSS per sport), duplicate the script and configs per group.

---

## 3) Hook into Discord (MEE6 RSS)

1. Host `dist/feed.xml` at a public URL (see options below).
2. In MEE6 Dashboard → **RSS** plugin → **Add RSS Feed** → paste your public feed URL.
3. Choose a channel (e.g., `#jp-betting-news`) and customize the message format:
   ```
   📰 {title}
   📎 {link}
   🎲 ベットはこちら: (本文に自動で含まれます)
   ```

MEE6 will post each new entry as it appears in the feed.

---

## 4) Hosting options

### A) GitHub Pages (free)
- Create a public repo and add these files.
- Add a GitHub Action (manual or scheduled) that runs `python enrich.py` and publishes the `dist/` folder to Pages.
- After deployment, your feed will be at `https://<user>.github.io/<repo>/feed.xml`.
- Put that URL into MEE6.

A simple Pages workflow (save as `.github/workflows/pages.yml`) **requires** that you enable Pages in repo settings:

```yaml
name: build-and-deploy-rss

on:
  workflow_dispatch:
  schedule:
    - cron: "*/30 * * * *"  # every 30 minutes

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.x'
      - run: pip install -r requirements.txt
      - run: python enrich.py
      - uses: actions/upload-pages-artifact@v3
        with:
          path: dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

### B) Vercel / Cloudflare (serverless)
- Serve `dist/feed.xml` as a static asset, or write a tiny handler that calls `enrich.py` and returns XML.
- Use a cron (Vercel Cron / Workers Cron) to rebuild periodically and cache the output.

### C) Any VPS
- Run `python enrich.py` by cron (`*/30 * * * *`) and serve `dist/feed.xml` via Nginx.

---

## 5) Next steps (optional improvements)

- **Per-match deep links**: add a background indexer + redirector (`/goto?key=...`) when you’re ready.
- **JP summaries**: call an LLM to produce a 140–220字要約 for `{description}`.
- **Split feeds by channel**: produce multiple XMLs (e.g., `dist/npb.xml`, `dist/jleague.xml`, etc.).
- **Anti-duplication**: store a small `cache.sqlite` to remember what was posted last run.

---

## 6) Troubleshooting

- If your feed isn’t posting, open `dist/feed.xml` in a browser—there should be valid XML with at least one `<item>`.
- Some publishers omit `published`—the script auto-fills with current JST.
- To force-refresh in MEE6, toggle the RSS feed off/on or edit the URL query (e.g., `?v=2`).

---

**Author’s note**: This repo is intentionally minimal and safe for beginners—no headless browser, no AI, just clean Japanese sports feeds enriched with your stable TrustDice league links.

---

## Do I have to keep my computer on? (No.)

You have **three** easy ways to run this without leaving your computer on:

1. **GitHub Pages (free & simple)**  
   - This repo already includes `.github/workflows/pages.yml`.  
   - When you push to GitHub and enable **Pages**, GitHub will run the script **every 30 minutes** on its own and publish `dist/feed.xml`.  
   - Your PC can be off; GitHub’s servers do the work.

2. **Vercel / Cloudflare Workers (free tiers)**  
   - Deploy a tiny serverless endpoint or static hosting for `feed.xml`.  
   - Use Vercel Cron or Workers Cron to run `python enrich.py` on a schedule.  
   - Again, **no need** to keep your computer on.

3. **Any small VPS**  
   - Set up a cron job like `*/30 * * * * python /path/enrich.py` and serve `dist/` with Nginx.  
   - Your VPS runs 24/7, not your laptop.

---

## Splitting per-sport feeds (e.g., `npb.xml`, `jleague.xml`)

Sometimes you want **one Discord channel per sport** (e.g., `#npb-news`, `#jleague-news`) and connect **one RSS per channel**.  
This project can output **5 files** at once:

- `feed.xml` — combined (all sports in one feed)
- `npb.xml` — NPB-only items
- `jleague.xml` — Jリーグ-only items
- `keiba.xml` — 競馬-only items
- `mlb.xml` — MLB-only items

Point each file’s **public URL** to the matching MEE6 RSS in that channel.

---

## Quick test mode (no waiting on real news)

You can instantly generate a test feed using **demo mode**:
```bash
python enrich.py --demo
# -> dist/feed.xml + per-sport XMLs with fake items you can use to test MEE6
```

You can also control how many demo items per sport:
```bash
python enrich.py --demo --per-sport 5
```

---

## GitHub Pages setup (step-by-step)

1. Create a **new public repo** on GitHub (e.g., `jp-sports-enriched-rss`).
2. Upload all files in this folder (or `git init` locally and push).
3. In your repo: **Settings → Pages → Build and deployment**
   - Source: **GitHub Actions**
4. Go to **Actions** tab and enable workflows (if prompted).
5. The included workflow `.github/workflows/pages.yml` will run every 30 minutes and publish `dist/` to Pages.
6. After the first successful run, the Actions log will show your **Pages URL** (e.g., `https://<user>.github.io/<repo>/`).
7. Your feeds will be available like:
   - Combined: `https://<user>.github.io/<repo>/feed.xml`
   - NPB: `https://<user>.github.io/<repo>/npb.xml`
   - Jリーグ: `https://<user>.github.io/<repo>/jleague.xml`
   - 競馬: `https://<user>.github.io/<repo>/keiba.xml`
   - MLB: `https://<user>.github.io/<repo>/mlb.xml`
8. Paste those URLs into **MEE6 → RSS** for the channels you want.

> Tip: you can also run the Action manually from the Actions tab (workflow_dispatch) to publish immediately.
