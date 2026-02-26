# Africa Gold Intelligence — Gold Briefing Pipeline

**Also called:** AGI, the briefing, the pipeline
**Status:** Active — running daily on Jote's Mac
**GitHub:** https://github.com/JoteT/gold-briefing (private repo)

## What It Is
Automated daily gold market briefing for African investors and traders.
Fetches live market data, builds free + premium HTML editions, posts to Beehiiv.

## Mac Setup
- **Project path:** `~/Documents/GoldBriefing`
- **Entry point:** `python3 orchestrator.py`
- **Shortcuts:** `make run`, `make tuesday`, `make sync`, etc.
- **Scheduler:** macOS LaunchAgent runs it every morning automatically
- **Python:** system python3 with `--break-system-packages`

## Key Files
| File | Purpose |
|------|---------|
| `orchestrator.py` | Pipeline entry point — runs all agents |
| `agents/beehiiv_daily_post.py` | Agent 2: content synthesis + market data |
| `agents/africa_data_agent.py` | Agent 1.5: Africa miner intelligence |
| `agents/contract_transparency_agent.py` | Agent 1.6: mining contracts + shadow economy |
| `distribution/beehiiv_browser.py` | Browser automation for posting |
| `data/partners.json` | Partnership outreach contacts |
| `logs/run_log.jsonl` | Full pipeline run history |
| `.env` | Secrets (API keys, passwords) — gitignored |

## Agent Pipeline
```
Agent 1   · Market Intelligence       prices, FX, RSI, news (Yahoo Finance + RSS)
Agent 1.5 · Africa Intelligence       miner AISC margins, pan-African composite
Agent 1.6 · Contract Transparency     mining contracts DB, shadow economy, nationalism
Agent 2   · Content Synthesis         builds HTML free + premium tiers
Agent 3   · Distribution              posts to Beehiiv (browser automation)
Agent 4   · SEO                       slug, tags, JSON-LD
Agent 5   · Social Amplification      Twitter/X, LinkedIn, WhatsApp drafts
Agent 6   · Partnership Outreach      auto-draft partnership emails
Agent 7   · Monetization Optimizer    upsell scoring + CTA injection
Agent 8   · Analytics & Reporting     pipeline health
```

## Post Types (by weekday)
| Day | Post Type | make command |
|-----|-----------|-------------|
| Monday | monday_deep_dive | `make monday` |
| Tuesday | africa_regional | `make tuesday` |
| Wednesday | aggregator | `make wednesday` |
| Thursday | africa_premium | `make thursday` |
| Friday | trader_intel | `make friday` |
| Saturday | analysis | `make saturday` |
| Sunday | week_review | `make sunday` |

## Folder Structure
```
GoldBriefing/
├── orchestrator.py        entry point
├── Makefile               shortcuts
├── agents/                all 9 intelligence modules
├── distribution/          Beehiiv browser + API checker
├── data/                  partners.json, session cookie
├── logs/                  JSONL run logs (gitignored)
├── setup/                 one-time scripts + plists
├── tests/                 test scripts
├── docs/                  reference documents
└── memory/                Claude's persistent memory (this file)
```

## Beehiiv Setup
- Posts via browser automation (Playwright) — works on any Beehiiv plan
- API key needed only for Enterprise plan auto-posting
- Credentials: BEEHIIV_EMAIL + BEEHIIV_PASSWORD in .env

## Key Data Points (as of Feb 2026)
- Gold price: ~$5,193/oz (at ATH levels)
- Africa miners tracked: 5 (Barrick, AngloGold, Gold Fields, Kinross, B2Gold)
- Mining contracts in DB: 11 (across DRC, Mali, Ghana, Tanzania, etc.)
- Illicit gold estimate: 321–474 tonnes/yr ($23–35B) — Swissaid 2024
- Dubai undeclared gap: 2,569 tonnes / $115.3B (2012–2022)

## GitHub
- Repo: https://github.com/JoteT/gold-briefing
- Branch: main
- Sync: `make sync` (= `git pull`)
- Push: `git add -A && git commit -m "message" && git push`
- Secrets (.env, session cookies, logs) are gitignored — never committed

## Common Commands
```bash
cd ~/Documents/GoldBriefing
make tuesday    # preview Tuesday's Africa Regional edition
make run        # live run → Beehiiv draft
make publish    # live run → publish immediately
make sync       # git pull — fetch latest code
make logs       # last 10 pipeline runs
make update     # pip install --upgrade
make clean      # remove __pycache__
```
