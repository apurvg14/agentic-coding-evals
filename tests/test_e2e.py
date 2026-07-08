"""Browser-based end-to-end tests for the dashboard UI (Playwright).

These drive a real Chromium instance against a live dashboard and assert the
things a human actually does: the page loads, the Advanced panel toggles, task
selection works, the task inspector opens, and a full keyless `reference` run
streams a log and populates the scorecard.

Skipped automatically if Playwright / the browser binaries aren't installed, so
the stdlib API tests can still run standalone.
"""
from __future__ import annotations

import re

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

pytestmark = pytest.mark.e2e


def test_page_loads_core_controls(page, base_url):
    page.goto(base_url)
    expect(page.get_by_test_id("run-card")).to_be_visible()
    expect(page.get_by_test_id("model-select")).to_be_visible()
    expect(page.get_by_test_id("task-list")).to_be_visible()
    expect(page.get_by_test_id("run-btn")).to_be_enabled()
    expect(page.get_by_test_id("suite-tag")).to_contain_text("tasks")


def test_advanced_settings_hidden_until_toggled(page, base_url):
    page.goto(base_url)
    # Advanced knobs live inside a collapsed <details>, so they start hidden.
    expect(page.get_by_test_id("budget-input")).to_be_hidden()
    page.get_by_test_id("advanced-toggle").click()
    expect(page.get_by_test_id("budget-input")).to_be_visible()
    expect(page.get_by_test_id("maxsize-input")).to_be_visible()


def test_select_all_and_none(page, base_url):
    page.goto(base_url)
    checkboxes = page.locator('[data-task]')
    total = checkboxes.count()
    assert total > 0
    page.get_by_test_id("select-none").click()
    assert checkboxes.evaluate_all("els => els.filter(e => e.checked).length") == 0
    page.get_by_test_id("select-all").click()
    assert checkboxes.evaluate_all("els => els.filter(e => e.checked).length") == total


def test_custom_model_input_reveals(page, base_url):
    page.goto(base_url)
    expect(page.get_by_test_id("custom-model-input")).to_be_hidden()
    page.get_by_test_id("model-select").select_option("__custom__")
    expect(page.get_by_test_id("custom-model-input")).to_be_visible()


def test_task_inspector_opens_and_closes(page, base_url):
    page.goto(base_url)
    page.locator('#tasklist .name').first.click()
    overlay = page.get_by_test_id("overlay")
    expect(overlay).to_be_visible()
    expect(page.get_by_test_id("modal")).to_contain_text("Prompt")
    page.keyboard.press("Escape")
    expect(overlay).to_be_hidden()


def test_full_reference_run_populates_scorecard(page, base_url):
    """The end-to-end happy path: configure a keyless run and watch it finish."""
    page.goto(base_url)
    page.get_by_test_id("model-select").select_option("reference")

    # One task keeps the run fast; shallow search keeps it faster still.
    page.get_by_test_id("select-none").click()
    page.locator('[data-testid^="task-cb-"]').first.check()
    page.get_by_test_id("advanced-toggle").click()
    page.get_by_test_id("maxsize-input").fill("1")
    page.get_by_test_id("budget-input").fill("8")

    page.get_by_test_id("run-btn").click()

    # Pill reaches a terminal, successful state.
    expect(page.get_by_test_id("run-pill")).to_contain_text(
        re.compile(r"exit 0"), timeout=120_000)
    # Log streamed something.
    expect(page.get_by_test_id("log")).not_to_be_empty()
    # Scorecard rendered with the reference backend.
    expect(page.get_by_test_id("headline")).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("results")).to_contain_text("reference")
