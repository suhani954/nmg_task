PYTHON ?= $(if $(wildcard .venv/Scripts/python.exe),.venv/Scripts/python.exe,$(if $(wildcard .venv/bin/python),.venv/bin/python,python3))
.PHONY: demo run eval test
demo:
	$(PYTHON) scripts/demo.py
run:
	$(PYTHON) -m relay run --inbox "$(INBOX)"
eval:
	$(PYTHON) -m relay eval --runs $(or $(RUNS),5)
test:
	$(PYTHON) -m pytest -q
