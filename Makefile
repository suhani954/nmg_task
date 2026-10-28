PYTHON ?= python3
.PHONY: demo run eval test
demo:
	$(PYTHON) scripts/demo.py
run:
	$(PYTHON) -m relay run --inbox "$(INBOX)"
eval:
	$(PYTHON) -m relay eval --runs $(or $(RUNS),5)
test:
	$(PYTHON) -m pytest -q
