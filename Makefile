.PHONY: setup precommit lint format test unit integ cov

setup:
	python3 -m pip install --upgrade pip
	python3 -m pip install -r requirements.txt

precommit:
	python3 -m pre_commit run --files $(git diff --name-only --cached)

lint:
	python3 -m ruff .

format:
	python3 -m isort .
	python3 -m black . --extend-exclude "app/core/config.py"

test:
	python3 -m pytest

unit:
	python3 -m pytest tests/test_overlay_draw.py tests/test_image_utils.py

integ:
	python3 -m pytest tests/integration

cov:
	python3 -m pytest --cov=.
