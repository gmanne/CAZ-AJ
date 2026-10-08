# CareAtZero

A free web app that helps uninsured and low-income North Carolinians find
genuinely free, very-low-cost, or sliding-scale medical, dental, and
behavioral healthcare they can realistically access soon. Built for the
Congressional App Challenge.

CareAtZero does not diagnose, give medical advice, or store medical records.

## Status

This repo has **two parallel builds** of the same idea:

1. **`app.py` (Streamlit / Python)** — real data only, no samples. Talks to
   its own local **MCP server** (`mcp_server/server.py`) to search, which in
   turn pulls from three real official sources: **HRSA** (medical), **SAMHSA**
   (behavioral health), and **NC DHHS** (dental + other facility types).
2. **`webapp/index.html` (standalone web app)** — a self-contained
   HTML/CSS/JS build matching the homepage design mockup, currently still on
   sample data. Runs directly in any browser — no Python required.

Pick one to move forward as the actual CAC submission — see "Which one do
I submit?" below.

## Quick start — Streamlit version (real data)

Requires **Python 3.10+** (the MCP SDK's minimum — see "Upgrading Python"
below if you're on an older version).

```bash
pip install -r requirements.txt
streamlit run app.py
```

No separate step needed to start the MCP server — `app.py` spawns it
automatically as a subprocess for each search, detail lookup, and referral
summary. See "MCP architecture" below for why.

## Deploying publicly (Streamlit Community Cloud)

This makes the app reachable by anyone with a link, not just on your own
computer — free, and it uses the GitHub repo you've already been pushing to.

1. Make sure this whole repo (including `runtime.txt` and
   `requirements.txt`) is pushed to your GitHub repo.
2. Go to **share.streamlit.io** and sign in with GitHub.
3. Click **"New app"**, pick your repo and branch, and set the main file
   path to `app.py`.
4. Deploy. First boot takes a minute or two while it installs dependencies.
5. You'll get a public URL like `https://your-app-name.streamlit.app` —
   that's the real, shareable link.

**Why this works without changes:** the app spawns its own MCP server as a
subprocess for every search (see `utils/mcp_client.py`), using
`sys.executable` rather than a bare `python` command — which is exactly
the pattern
[Streamlit's own docs](https://docs.streamlit.io/knowledge-base/deploy/invoking-python-subprocess-deployed-streamlit-app)
recommend for subprocesses on Community Cloud, so no special configuration
is needed there.

**What's different once it's public, on purpose:**
- **Saved items are session-only**, not written to a shared file. Community
  Cloud runs one container for *every* visitor, so a shared file would mix
  everyone's saved items together — a real privacy problem. Session state
  is private per browser session instead; saved items just won't survive
  closing the tab. (This is why the earlier local-file version was changed
  — see `app.py`'s comment above `toggle_save`.)
- Each search calls three live government APIs plus spawns a subprocess,
  so it's a bit slower than the old sample-data version — a few seconds per
  search is normal and expected.

## Quick start — standalone web app

No install needed — just open `webapp/index.html` directly in a browser
(double-click it, or drag it into a browser window).

## Architecture

```
                    ┌─────────────────────────┐
  Streamlit UI  <-->│   MCP Server (stdio)     │
   (app.py)         │   mcp_server/server.py   │
                    └───────────┬──────────────┘
                                │
                    ┌───────────┴──────────────┐
                    │   connectors/combined.py  │
                    └─────┬───────────┬─────────┘
                          │           │
              ┌───────────┼───────────┼────────────┐
              ▼           ▼           ▼             ▼
         HRSAConnector SAMHSAConnector NCSafetyNetConnector  (each a real,
         (medical)     (behavioral)    (dental + more)        live source)
```

The Streamlit app is an **MCP client** — the same role an app like Claude
Desktop plays. It never imports `connectors/` or `scoring/` directly;
every search, detail lookup, and referral summary is a real
Model Context Protocol tool call to `mcp_server/server.py`, spawned as a
subprocess over stdio. Anything that can speak MCP (Claude Desktop, Claude
Code, another app) can talk to the exact same server.

| Component | Location | Purpose |
|---|---|---|
| Streamlit UI (MCP client) | `app.py` | Search form, results, detail view, saved list — talks to the MCP server |
| MCP server | `mcp_server/server.py` | Exposes `search_care`, `get_care_detail`, `get_referral_summary`, `list_upcoming_events` as tools |
| Source connectors | `connectors/hrsa_connector.py`, `samhsa_connector.py`, `nc_safety_net_connector.py` | Each pulls from one real, official source |
| Combiner | `connectors/combined.py` | Merges all sources; one source failing never takes down the others |
| ZIP-centroid geocoding | `connectors/zip_centroids.py` | Real Census Bureau data, cached locally — no live geocoding API needed |
| Care Access Engine | `scoring/care_access_score.py` | Transparent, weighted scoring — no ML |
| Local cache | `database/` | SQLite schema (reserved for future caching of live results) |

## What's covered — real data, by category

| Category | Source | Type | What it really tells you |
|---|---|---|---|
| **Medical** | HRSA Health Care Service Delivery Sites | Live federal API, no key | Real, active, HRSA-funded health centers in NC — name, address, phone, coordinates, facility type |
| **Behavioral** | SAMHSA FindTreatment.gov | Live federal API, no key | Real mental health & substance use treatment facilities near NC — with real payment/eligibility info where the facility reports it |
| **Dental** (+ hospitals, FQHCs, school clinics, etc.) | NC DHHS Safety Net Sites List | NC state data (periodically-updated file) | Real facility names, addresses, and **facility type** across NC — see the note on ZIP-centroid coordinates below |
| **Vision** | — | *Not covered* | No verified, freely-available public data source was found. Vision searches return real results (empty, with a note) rather than fabricated ones. |

**Coordinates**: HRSA and SAMHSA both provide exact coordinates directly.
The NC DHHS list doesn't include coordinates, so that connector resolves
each site's ZIP code to a real Census Bureau ZIP-centroid — accurate
enough for the 10%-weighted distance signal, not exact-address precision.

**Cost labels**: never marked `"Free"` unless the source itself says so
(HRSA/NC DHHS facility categories are legally required to use a sliding
fee scale, so they're marked `"Sliding Scale"`; SAMHSA facilities are
marked `"Free"` only when their own reported payment-assistance text says
so). Anything not covered by the source is marked `"Unknown"` rather than
guessed.

**If a source goes down**: `connectors/combined.py` catches it, logs a
warning, and keeps going with whatever other sources succeeded — a search
never crashes just because one federal API had a bad moment.

## Care Access Score

No machine learning — a transparent weighted formula (`scoring/care_access_score.py`):

| Signal | Weight |
|---|---|
| Cost fit | 35% |
| Time to care / availability | 25% |
| Service match | 15% |
| Eligibility confidence | 10% |
| Distance | 10% |
| Information freshness | 5% |

The Streamlit detail page shows this as a real per-category breakdown with
progress bars (via the MCP server's `get_care_detail` tool, which includes
`score_breakdown` when a `service` is passed).

## MCP server — for AI assistants too

`mcp_server/server.py` also works standalone with any MCP client, not just
the Streamlit app — e.g. Claude Desktop. Add this to its config (Settings →
Developer → Edit Config), replacing the path with this project's actual
location:

```json
{
  "mcpServers": {
    "careatzero": {
      "command": "python",
      "args": ["/absolute/path/to/care-at-zero/mcp_server/server.py"]
    }
  }
}
```

Tools exposed: `search_care`, `get_care_detail`, `get_referral_summary`,
`list_upcoming_events` (currently always empty — none of the connected
sources publish mobile/pop-up event schedules yet).

## Which one do I submit?

|  | Streamlit (`app.py`) | Web app (`webapp/index.html`) |
|---|---|---|
| Data | **Real** — HRSA, SAMHSA, NC DHHS | Sample/placeholder |
| Runs | Needs Python 3.10+ | Any browser, no install |
| Shows real architecture (MCP server, live connectors) | Yes | No |
| Matches the homepage mockup design | Approximated, not pixel-exact | Yes |
| Hosting for CAC | Needs Streamlit Community Cloud | Any static host (GitHub Pages) |

Given the Streamlit version is now backed by real data and a real MCP
server, it's the stronger technical submission. The web app is easier to
host publicly with zero setup for judges.

## Upgrading Python (if you're below 3.10)

The MCP SDK requires Python 3.10+. If `python --version` shows something
older:
1. Download a 3.11 or 3.12 installer from python.org
2. Run it, checking **"Add python.exe to PATH"** (Windows) during install
3. Restart your terminal/VS Code
4. Re-run `pip install -r requirements.txt`

## UI notes

The Streamlit app's picker cards, colored score bars, and cost/facility
badges are custom-styled (see the CSS block near the top of `app.py`) to
get closer to the web app's visual language within Streamlit's own
component model. Saved items persist to `data/saved_items.json` on
disk — they survive closing and reopening the app, not just the current
session — and the nav bar shows a live count (e.g. "Saved (3)").

Researched but not included: a real per-hospital financial-assistance
data source (none found), and Remote Area Medical's real NC mobile
clinic schedule (the public page renders its event list via JavaScript
with no accessible API — scraping it would be fragile and could break
without warning, so it was left out rather than built unreliably).

## Tests

`tests/test_app_navigation.py` and `tests/test_app_search_flow.py` use
Streamlit's `AppTest` framework to click through the app headlessly (no
browser needed) — navigation between all five pages, and a full
search → view details → save flow with a mocked MCP response. Run with:

```bash
python tests/test_app_navigation.py
python tests/test_app_search_flow.py
```

## Adding a real connector

1. Subclass `BaseConnector` in `connectors/` (see `hrsa_connector.py` or
   `nc_safety_net_connector.py` for real examples).
2. Implement `fetch_records() -> List[CareRecord]`.
3. Only set `cost_class="Free"` when the source explicitly says so.
4. Raise `ConnectorUnavailableError` on failure — never fabricate data
   when a source can't be reached.
5. Stamp `last_checked` with the real fetch time.
6. Add it to `connectors/combined.py`'s `fetch_all_records()`.

## Repository structure

```
care-at-zero/
  app.py                     Streamlit entry point (MCP client)
  mcp_server/server.py       MCP server exposing search to any MCP client
  utils/mcp_client.py        Streamlit's MCP client helper
  connectors/
    hrsa_connector.py         Real: HRSA medical data (live federal API)
    samhsa_connector.py       Real: SAMHSA behavioral health (live federal API)
    nc_safety_net_connector.py Real: NC DHHS dental + other facility types
    zip_centroids.py          Real: Census Bureau ZIP-centroid geocoding
    combined.py                Merges all real sources
    base_connector.py          CareRecord model + connector interface
    sample_connector.py        Sample data (used only by the web app now)
  scoring/care_access_score.py Care Access scoring engine
  database/                   SQLite schema + init script (reserved)
  webapp/                     Standalone HTML/CSS/JS web app (sample data)
  tests/                       AppTest-based regression tests
  data/                        Local saved-items file (created at runtime)
  requirements.txt
```

## AI use disclosure

Per Congressional App Challenge rules, all AI usage must be disclosed.
Note here which parts of this codebase were AI-assisted and describe your
own contributions and understanding of how each part works before you
submit.
