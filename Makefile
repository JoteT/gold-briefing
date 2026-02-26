# Africa Gold Intelligence — Makefile
# =====================================
# Single-command shortcuts for the AGI pipeline.
#
# USAGE:
#   make run         — live run (creates Beehiiv draft for review)
#   make publish     — live run (publishes immediately to site)
#   make preview     — dry run with today's scheduled post type
#   make <weekday>   — dry run forcing that day's edition + opens browser
#   make logs        — show last 10 pipeline run entries
#   make update      — upgrade all Python dependencies
#   make sync        — pull latest code changes (git pull)
#   make clean       — remove __pycache__ and .pyc files

PYTHON  := python3
SCRIPT  := orchestrator.py
OPEN    := open /tmp/agi_preview_free.html && open /tmp/agi_preview_premium.html

.PHONY: run publish preview monday tuesday wednesday thursday friday saturday sunday \
        logs update sync clean check

# ── Pipeline ──────────────────────────────────────────────────────────────────

run:
	$(PYTHON) $(SCRIPT)

publish:
	$(PYTHON) $(SCRIPT) --publish

preview:
	$(PYTHON) $(SCRIPT) --dry-run
	$(OPEN)

# ── Day-specific previews ─────────────────────────────────────────────────────

monday:
	$(PYTHON) $(SCRIPT) --dry-run --post-type monday_deep_dive
	$(OPEN)

tuesday:
	$(PYTHON) $(SCRIPT) --dry-run --post-type africa_regional
	$(OPEN)

wednesday:
	$(PYTHON) $(SCRIPT) --dry-run --post-type aggregator
	$(OPEN)

thursday:
	$(PYTHON) $(SCRIPT) --dry-run --post-type africa_premium
	$(OPEN)

friday:
	$(PYTHON) $(SCRIPT) --dry-run --post-type trader_intel
	$(OPEN)

saturday:
	$(PYTHON) $(SCRIPT) --dry-run --post-type analysis
	$(OPEN)

sunday:
	$(PYTHON) $(SCRIPT) --dry-run --post-type week_review
	$(OPEN)

# ── Ops ───────────────────────────────────────────────────────────────────────

logs:
	$(PYTHON) $(SCRIPT) --log

update:
	pip3 install -r requirements.txt --upgrade --break-system-packages

sync:
	git pull

check:
	$(PYTHON) distribution/beehiiv_api_check.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
	@echo "  ✅ Cleaned up __pycache__ and .pyc files"
