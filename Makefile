.DEFAULT_GOAL := all
pysources = emmett tests

.PHONY: format
format:
	ruff check --fix $(pysources)
	ruff format $(pysources)

.PHONY: lint
lint:
	ruff check $(pysources)
	ruff format --check $(pysources)

.PHONY: test
test:
	pytest -v tests

.PHONY: all
all: format lint test
