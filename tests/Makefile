# 5G K3s KubeEdge Testbed - Test Suite
# Simple Makefile wrapper for the Textual CLI and run_tests.py

.PHONY: help all cli e2e protocols performance resilience clean clean-all

VENVDIR := venv
REQS    := requirements.txt
STAMP   := $(VENVDIR)/.installed

all: $(STAMP)
	@echo "🚀 Launching Interactive CLI..."
	@if [ -d "$(VENVDIR)" ]; then \
		. $(VENVDIR)/bin/activate && python interactive_cli.py; \
	else \
		python3 interactive_cli.py; \
	fi

cli: all

$(STAMP): $(REQS)
	@echo "🔍 Ensuring virtualenv and dependencies..."
	@python3 -m venv $(VENVDIR) >/dev/null 2>&1 || true
	@$(VENVDIR)/bin/pip install -q --disable-pip-version-check -r $(REQS) || $(VENVDIR)/bin/pip install -r $(REQS)
	@touch $(STAMP)
	@echo "✅ Environment ready!"

e2e:
	@python3 run_tests.py -s e2e

protocols:
	@python3 run_tests.py -s protocols

performance:
	@python3 run_tests.py -s performance

resilience:
	@python3 run_tests.py -s resilience

verbose:
	@python3 run_tests.py -v

list:
	@python3 run_tests.py --list

clean:
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.log" -delete 2>/dev/null || true
	@find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true

clean-all: clean
	@rm -rf $(VENVDIR)/

help:
	@echo "5G K3s KubeEdge Testbed - Test Suite"
	@echo "====================================="
	@echo "Targets:"
	@echo "  make / make cli   - Launch Interactive CLI"
	@echo "  e2e|protocols|performance|resilience - Run specific suites"
	@echo "  verbose           - Run all tests verbosely"
	@echo "  list              - List available tests"
	@echo "  clean             - Remove caches/logs"
	@echo "  clean-all         - Remove venv too"
