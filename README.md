# Africa Gold Intelligence (AGI) — Daily Briefing Pipeline

Automated daily gold market briefing for African investors and traders.
Publishes to Beehiiv. Runs every morning via macOS LaunchAgent.

---

## Quick Start

```bash
cd ~/Documents/GoldBriefing

make tuesday     # preview Tuesday's Africa Regional edition
make preview     # preview today's scheduled edition
make run         # live run → creates Beehiiv draft for review
make publish     # live run → publishes immediately
make logs        # show last 10 pipeline runs
```

---

## Project Structure

```
GoldBriefing/
├── orchestrator.py          ← entry point — runs the full pipeline
├── Makefile                 ← single-command shortcuts (make run, make tuesday…)
├── requirements.txt         ← Python dependencies
│
├── agents/                  ← all pipeline intelligence modules
│   ├── beehiiv_daily_post.py       Agent 2  · Content Synthesis & Market Data
│   ├── africa_data_agent.py        Agent 1.5· Africa Miner Intelligence
│   ├── contract_transparency_agent.py  Agent 1.6· Mining Contracts & Shadow Economy
│   ├── seo_agent.py                Agent 4  · SEO & Discoverability
│   ├── social_agent.py             Agent 5  · Social Amplification
│   ├── partnership_agent.py        Agent 6  · Partnership Outreach
│   ├── monetization_agent.py       Agent 7  · Monetization Optimizer
│   ├── analytics_agent.py          Agent 8  · Analytics & Reporting
│   └── gold_market_briefing.py     Legacy market data utilities
│
├── distribution/            ← Beehiiv delivery layer
│   ├── beehiiv_browser.py          Browser automation (works on any plan)
│   └── beehiiv_api_check.py        API connectivity diagnostic
│
├── data/                    ← persistent data (gitignored sensitive files)
│   ├── partners.json               Partnership outreach contacts
│   └── .beehiiv_session.json       Browser login session (auto-generated)
│
├── logs/                    ← run logs (gitignored — regenerated each run)
│   ├── run_log.jsonl               Full pipeline run history
│   ├── seo_log.jsonl               SEO metadata per post
│   ├── social_log.jsonl            Social posts generated/posted
│   ├── monetization_log.jsonl      Upsell scores and strategies
│   └── outreach_log.jsonl          Partnership email drafts
│
├── setup/                   ← one-time setup scripts (run once)
│   ├── setup_gold_briefing.sh      Install Python deps + Playwright
│   ├── setup_browser.sh            Configure browser automation
│   ├── setup_beehiiv_login.py      Save Beehiiv login session
│   ├── install_scheduler.sh        Install macOS LaunchAgent
│   └── *.plist                     LaunchAgent config files
│
├── tests/                   ← diagnostic and preview tools
│   └── test_email.py               Email delivery test
│
└── docs/                    ← reference documents
    ├── AGI Autonomous Agent Team Framework.docx
    ├── AGI Gold Trader Currency Cheat Sheet.pdf
    ├── AGI_Community_Post_Templates.md
    └── GOLD_BRIEFING_SETUP.md
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

| Variable           | Description                                      |
|--------------------|--------------------------------------------------|
| `NOTIFY_PASSWORD`  | Gmail App Password for operator alerts           |
| `BEEHIIV_EMAIL`    | Beehiiv login email (browser automation)         |
| `BEEHIIV_PASSWORD` | Beehiiv login password                           |
| `BEEHIIV_API_KEY`  | Beehiiv V2 API key (Enterprise plan only)        |
| `NOTIFY_EMAIL`     | Operator email (default: jote.taddese@gmail.com) |

---

## Agent Pipeline

```
Agent 1   · Market Intelligence      prices, FX rates, RSI, news
Agent 1.5 · Africa Intelligence      miner margins, AISC, seasonal signals
Agent 1.6 · Contract Transparency    mining contracts, shadow economy, nationalism
Agent 2   · Content Synthesis        builds HTML for free + premium tiers
Agent 3   · Distribution             posts to Beehiiv (API or browser)
Agent 4   · SEO & Discoverability    slug, tags, JSON-LD, meta
Agent 5   · Social Amplification     Twitter/X, LinkedIn, WhatsApp drafts
Agent 6   · Partnership Outreach     auto-draft partnership emails
Agent 7   · Monetization Optimizer   upsell scoring and CTA injection
Agent 8   · Analytics & Reporting    pipeline health and trend analysis
```

---

## Sync

```bash
make sync    # git pull — fetch latest code updates
make update  # pip install --upgrade — update Python packages
make clean   # remove __pycache__ files
```

---

## Troubleshooting

```bash
make check   # run Beehiiv API connectivity diagnostic
make logs    # see recent pipeline run history
```

Full setup guide: `docs/GOLD_BRIEFING_SETUP.md`
