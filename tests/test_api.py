"""API smoke tests for the dashboard HTTP server.

Pure stdlib (urllib + json) driven through pytest's `base_url` fixture. These
verify the JSON contract the front-end depends on and the request-validation
that guards the run endpoint -- without ever launching a real evaluation.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


def _get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        # The server returns a JSON body with error codes (e.g. 404); surface it.
        return e.code, e.read().decode("utf-8")


def _get_json(base, path):
    status, body = _get(base, path)
    return status, json.loads(body)


def _post_json(base, path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + path, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def test_index_serves_html_with_test_hooks(base_url):
    status, body = _get(base_url, "/")
    assert status == 200
    for hook in ('data-testid="run-btn"', 'data-testid="model-select"',
                 'data-testid="task-list"', 'data-testid="advanced-toggle"',
                 'data-testid="results"'):
        assert hook in body, f"missing UI hook {hook}"


def test_meta_contract(base_url):
    status, meta = _get_json(base_url, "/api/meta")
    assert status == 200
    assert isinstance(meta["tasks"], list) and meta["tasks"], "expected tasks"
    assert all("id" in t and "title" in t for t in meta["tasks"])
    assert isinstance(meta["atoms"], list) and meta["atoms"]
    assert "reference" in meta["preset_models"]
    for key in ("search", "budget", "max_size", "max_steps", "grader"):
        assert key in meta["defaults"], f"defaults missing {key}"
    assert isinstance(meta["has_anthropic_key"], bool)


def test_results_contract(base_url):
    status, res = _get_json(base_url, "/api/results")
    assert status == 200
    for key in ("models", "failure_classes", "transfer", "per_task", "atoms"):
        assert key in res, f"results missing {key}"
    assert "models" in res["transfer"] and "matrix" in res["transfer"]


def test_task_detail_ok(base_url):
    _, meta = _get_json(base_url, "/api/meta")
    tid = meta["tasks"][0]["id"]
    status, task = _get_json(base_url, "/api/task?id=" + tid)
    assert status == 200
    assert task["id"] == tid
    assert "prompt" in task and "workspace" in task and "check" in task


def test_task_detail_missing_is_404(base_url):
    status, task = _get_json(base_url, "/api/task?id=__does_not_exist__")
    assert status == 404
    assert "error" in task


def test_status_contract(base_url):
    status, s = _get_json(base_url, "/api/status?since=0")
    assert status == 200
    for key in ("lines", "total", "active", "done", "returncode"):
        assert key in s, f"status missing {key}"


def test_run_rejects_empty_task_selection(base_url):
    status, res = _post_json(base_url, "/api/run", {"model": "reference", "tasks": []})
    assert status == 200
    assert res["ok"] is False
    assert "task" in res["error"].lower()


def test_run_rejects_unknown_task(base_url):
    status, res = _post_json(base_url, "/api/run",
                             {"model": "reference", "tasks": ["__nope__"]})
    assert status == 200
    assert res["ok"] is False


def test_unknown_endpoint_is_404(base_url):
    status, res = _get_json(base_url, "/api/does-not-exist")
    assert status == 404
    assert "error" in res
