# OTASEC — OT Asset Security

A bilingual news aggregator for OT/ICS security: **otasec.com** (English) and
**otasec.nl** (Dutch). The site has two parts:

- **Live feed**: every OT/ICS-relevant story from dedicated OT outlets, vendor and
  government advisories, the broader security press and X. It's updated
  hourly, tagged by type, sector, vendor and CVE, and filterable.
- **Daily briefing**: each morning, the day's most-covered stories clustered
  into one post. Each story gets a summary, a takeaway for asset owners and links
  to every source.

The site is fully static, so there's no PHP, database or server cron. A scheduled
GitHub Action does all the work and uploads plain HTML to the existing host.

```
config/sources.yaml ─┐
  RSS / Atom feeds   ├─► ingest ─► classify ─► data/items.json ─┐
  X recent search  ──┘   (hourly)  (Claude Haiku)               ├─► build ─► dist/en ─► otasec.com
                                                                │           dist/nl ─► otasec.nl
                         briefing (07:00 NL) ─► data/briefings/ ┘
                         (Claude Sonnet, EN + NL in one call)
```

## How it decides what's relevant and what's "popular"

- **Relevance.** Sources marked `focus: ot` are always kept. Items from broad sources
  (The Hacker News, BleepingComputer, NCSC-NL, Security.NL…) are published only when
  Claude judges them to have a real OT/ICS or critical-infrastructure angle.
- **Popularity.** RSS has no view counts, so the briefing ranks stories by
  **how many independent sources cover the same event**, then by X shares, then by impact.
- **No invented links.** The briefing model refers to items by id. Links are then
  attached from the real fetched items, so it can't add or alter a URL. Every link
  is also restricted to http(s), and all text is HTML-escaped.

## Repository layout

```
config/site.yaml        domains, languages, models, briefing time, retention
config/sources.yaml     feeds + X queries (edit this to add/remove sources)
otasec/                 Python package (feeds, xsource, classify, briefing, build, pipeline)
templates/              Jinja2 templates (about_en / about_nl hold the About text)
static/                 style.css, app.js (client-side filters), favicon
data/                   items.json, briefings/*.json, health.json (committed by the bot)
.github/workflows/      pipeline.yml (hourly), tests.yml
tests/                  pytest suite
```

## Setup

### 1. Repository secrets and variables

In GitHub, go to **Settings → Secrets and variables → Actions**.

| Kind | Name | Value |
|---|---|---|
| Secret | `ANTHROPIC_API_KEY` | Anthropic API key |
| Secret | `X_BEARER_TOKEN` | X API v2 bearer token (optional) |
| Secret | `FTP_HOST` | e.g. `ftp.yourhost.nl` (leave unset to skip deploy) |
| Secret | `FTP_USER` | FTP/SFTP user |
| Secret | `FTP_PASSWORD` | FTP/SFTP password |
| Variable | `FTP_PROTOCOL` | `ftp` (default, uses TLS when offered) or `sftp` |
| Variable | `FTP_DIR_EN` | remote folder for otasec.com, e.g. `/domains/otasec.com/public_html` |
| Variable | `FTP_DIR_NL` | remote folder for otasec.nl, e.g. `/domains/otasec.nl/public_html` |
| Variable | `FTP_DELETE` | `true` to remove remote files that aren't in the build (off by default) |

The two domains need **separate document roots**. If both currently point to the
same folder (as the old PHP site did), create a separate root for one of them
in your hosting panel first. `otasec.eu` can point at the English root.

### 2. First run

Go to **Actions → OTASEC pipeline → Run workflow**, and tick *Regenerate
today's briefing* so you get a briefing straight away. After that it runs
hourly at :17. The first run that's both after 07:00 (Amsterdam) and has
relevant news publishes the day's briefing.

The old PHP files left on the host are blocked by the new `.htaccess`, and
`index.html` takes precedence. Once you've confirmed the new site works, you
can delete them, or set `FTP_DELETE=true` for one run.

### 3. Check source health

`/about/` on the site, and `data/health.json`, show which feeds answered on the
last run. Some outlets sit behind bot protection. If a feed keeps failing,
check the URL in a browser, or replace it with an RSS proxy URL in
`config/sources.yaml`.

## Local development

```bash
pip install -r requirements.txt
cp .env.example .env            # add your keys (optional)
python -m otasec run            # fetch + classify + briefing if due + build
python -m otasec build          # rebuild HTML from data/ only
python -m otasec briefing --force
python -m otasec serve en       # http://localhost:8000 (or: serve nl)
python -m pytest -q
```

Without an `ANTHROPIC_API_KEY`, the site still builds: a keyword filter stands
in for Claude, and items get no summaries or briefing.

## Running costs (estimate, Oct 2026 list prices)

| Part | Volume | Approx. |
|---|---|---|
| Classification (Haiku 5.5) | ~100–200 new items/day | cents per day |
| Briefing (Sonnet 5.5) | 1 call/day, EN + NL | ≈ $0.10/day |
| X recent search | 50 posts × 4 runs/day at ~$0.005/post | ≈ $1/day |
| GitHub Actions | ~24 short runs/day | free on public repos; ~5 min/day on private |

X is the main cost driver. Tune `x.max_posts_per_run` and `x.min_interval_hours`
in `config/sources.yaml`, or set `x.enabled: false`.

## Adding a source

Add an entry to `config/sources.yaml`:

```yaml
  - id: my-source
    name: My Source
    url: https://example.com/feed/
    focus: ot        # ot = keep everything, broad = keep only OT-relevant items
    kind: news       # news | advisory | vendor
    lang: en         # en | nl
```

## Ideas for next iterations

- An email newsletter of the daily briefing (e.g. via Buttondown or MailerLite)
- Posting each briefing to an OTASEC account on X or LinkedIn
- Matching advisories to an asset inventory (vendor/product watch-lists)
- A weekly digest, plus tags for IEC 62443 zones and conduits and the Purdue level each item affects
