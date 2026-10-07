# ABOUTME: Validates app/src/models.json, the hand-curated model catalog bundled into the page.
# ABOUTME: The catalog is editorial, so these check its shape and that only https links reach the page.
import json
from datetime import date
from pathlib import Path

import pytest

CATALOG = Path(__file__).resolve().parent.parent / "app" / "src" / "models.json"
PROVIDERS = {"anthropic", "openai", "ollama"}
REQUIRED_TEXT = ("id", "name", "provider", "role", "context", "docs")
OPTIONAL_TEXT = ("price", "size")


@pytest.fixture(scope="module")
def catalog():
    return json.loads(CATALOG.read_text())


@pytest.fixture(scope="module")
def models(catalog):
    return catalog["models"]


def test_reviewed_at_is_an_iso_date(catalog):
    assert date.fromisoformat(catalog["reviewedAt"])


def test_catalog_covers_every_provider(models):
    assert {model["provider"] for model in models} == PROVIDERS


def test_ids_are_unique(models):
    ids = [model["id"] for model in models]
    assert len(ids) == len(set(ids))


def test_required_fields_are_present_and_non_empty(models):
    for model in models:
        for field in REQUIRED_TEXT:
            value = model.get(field)
            assert isinstance(value, str) and value.strip(), f"{model.get('id')}: {field}"


def test_optional_specs_are_text_or_explicitly_absent(models):
    """price applies to hosted models and size to local ones; null says "not applicable"."""
    for model in models:
        for field in OPTIONAL_TEXT:
            value = model[field]
            assert value is None or (isinstance(value, str) and value.strip()), (
                f"{model['id']}: {field}"
            )


def test_every_model_states_strengths_and_weaknesses(models):
    for model in models:
        for field in ("strengths", "weaknesses"):
            points = model[field]
            assert isinstance(points, list) and points, f"{model['id']}: {field} is empty"
            for point in points:
                assert isinstance(point, str) and point.strip(), f"{model['id']}: {field}"


def test_providers_are_known(models):
    for model in models:
        assert model["provider"] in PROVIDERS, f"{model['id']}: {model['provider']}"


def test_docs_links_are_https(models):
    """Same rule the feed applies to item urls: nothing but https reaches the page."""
    for model in models:
        assert model["docs"].startswith("https://"), f"{model['id']}: {model['docs']}"


def test_no_unexpected_fields(models):
    """A typo in a key would otherwise be silently ignored by the UI."""
    allowed = set(REQUIRED_TEXT) | set(OPTIONAL_TEXT) | {"strengths", "weaknesses"}
    for model in models:
        assert set(model) == allowed, f"{model['id']}: {set(model) ^ allowed}"
