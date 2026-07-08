"""A zero-dependency local web dashboard for the eval harness.

Run it with `python -m agenteval dashboard`. It serves a single HTML page on
localhost where a non-coder can pick a model, choose tasks, tune the worst-case
search, launch a run, watch live progress, and read the scorecard -- all the CLI
flags, but point-and-click.

Design notes:
- Pure standard library (http.server + threading + subprocess). No web framework,
  no build step, nothing to install beyond what a real-model run already needs.
- A run is just the existing CLI (`python -m agenteval run ...`) spawned as a
  subprocess; we stream its stdout to the browser and read results.json when done.
  That means the dashboard and the command line always agree.
- Binds to 127.0.0.1 only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import report
from .perturb import ATOMS
from .tasks import discover_tasks

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "tasks"
# Results dir is overridable so tests (and CI) can point at a throwaway location
# instead of the developer's real results/.
OUT = Path(os.environ.get("AGENTEVAL_RESULTS_DIR") or (ROOT / "results"))
HTML = Path(__file__).resolve().parent / "dashboard.html"

PRESET_MODELS = ["reference", "brittle-a", "brittle-b"]

# Single active run, guarded by a lock. The dashboard runs one experiment at a time.
_LOCK = threading.Lock()
RUN: dict = {"active": False, "log": [], "done": True, "returncode": None,
             "config": None, "proc": None}


def load_dotenv() -> None:
    """Load KEY=VALUE pairs from .env into the process env (so spawned runs see
    the API key). Never logged, never echoed."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _meta() -> dict:
    tasks = [{"id": t.id, "title": t.title} for t in discover_tasks(SUITE)]
    return {
        "tasks": tasks,
        "preset_models": PRESET_MODELS,
        "atoms": list(ATOMS),
        "defaults": {"search": "greedy", "budget": 24, "max_size": 2,
                     "max_steps": 14, "grader": "local"},
        "has_anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "has_openai_key": bool(os.environ.get("OPENAI_API_KEY")),
    }


def _task_detail(task_id: str) -> dict | None:
    tdir = SUITE / task_id
    if not (tdir / "task.json").exists():
        return None
    meta = json.loads((tdir / "task.json").read_text(encoding="utf-8"))

    def _files(sub: str) -> list[dict]:
        d = tdir / sub
        if not d.exists():
            return []
        return [{"name": f.name, "content": f.read_text(encoding="utf-8")}
                for f in sorted(d.iterdir()) if f.is_file()]

    check = ""
    if (tdir / "check.py").exists():
        check = (tdir / "check.py").read_text(encoding="utf-8")
    return {
        "id": task_id,
        "title": meta.get("title", task_id),
        "prompt": meta.get("prompt", ""),
        "prompt_vague": meta.get("prompt_vague", ""),
        "prompt_paraphrase": meta.get("prompt_paraphrase", ""),
        "workspace": _files("workspace"),
        "solution": _files("solution"),
        "check": check,
    }


def _results_summary() -> dict:
    rp = OUT / "results.json"
    if not rp.exists():
        return {"models": [], "failure_classes": [], "transfer": {"models": [], "matrix": {}},
                "per_task": [], "atoms": list(ATOMS)}
    results = json.loads(rp.read_text(encoding="utf-8"))
    return report.summarize(results)


def _reader_thread(proc: subprocess.Popen) -> None:
    assert proc.stdout is not None
    for line in iter(proc.stdout.readline, ""):
        RUN["log"].append(line.rstrip("\n"))
    proc.stdout.close()
    proc.wait()
    RUN["returncode"] = proc.returncode
    RUN["done"] = True
    RUN["active"] = False


def _clamp(v, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def _start_run(cfg: dict) -> dict:
    with _LOCK:
        if RUN["active"]:
            return {"ok": False, "error": "a run is already in progress"}

        # Validate / clamp everything from the browser before it reaches argv.
        model = (str(cfg.get("model") or "reference")).strip() or "reference"
        search = cfg.get("search", "greedy")
        if search not in ("greedy", "random", "none"):
            search = "greedy"
        grader = cfg.get("grader", "local")
        if grader not in ("local", "docker"):
            grader = "local"
        budget = _clamp(cfg.get("budget"), 1, 200, 24)
        max_size = _clamp(cfg.get("max_size"), 1, 4, 2)
        max_steps = _clamp(cfg.get("max_steps"), 1, 60, 14)
        valid_ids = {t.id for t in discover_tasks(SUITE)}
        tasks = [t for t in (cfg.get("tasks") or [])
                 if isinstance(t, str) and t in valid_ids]
        if not tasks:
            return {"ok": False, "error": "select at least one valid task"}

        cmd = [sys.executable, "-u", "-m", "agenteval", "run",
               "--model", model, "--out", str(OUT), "--search", search,
               "--budget", str(budget), "--max-size", str(max_size),
               "--max-steps", str(max_steps), "--grader", grader,
               "--tasks", ",".join(tasks)]

        RUN.update({"active": True, "log": [f"$ {' '.join(cmd[2:])}"],
                    "done": False, "returncode": None, "config": cfg, "proc": None})
        try:
            proc = subprocess.Popen(cmd, cwd=str(ROOT), env=os.environ.copy(),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1)
        except Exception as e:  # noqa: BLE001 - surface a clean failure to the UI
            RUN.update({"active": False, "done": True, "returncode": -1})
            RUN["log"].append(f"failed to start run: {type(e).__name__}: {e}")
            return {"ok": False, "error": f"could not launch: {e}"}

        RUN["proc"] = proc
        threading.Thread(target=_reader_thread, args=(proc,), daemon=True).start()
        return {"ok": True}


def _stop_run() -> dict:
    proc = RUN.get("proc")
    if proc and proc.poll() is None:
        proc.terminate()
        RUN["log"].append("-- stop requested --")
        return {"ok": True}
    return {"ok": False, "error": "no active run"}


def _clear_results() -> dict:
    if RUN["active"]:
        return {"ok": False, "error": "stop the active run before clearing"}
    import shutil
    for p in (OUT / "results.json", OUT / "report.md"):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    shutil.rmtree(OUT / "transcripts", ignore_errors=True)
    return {"ok": True}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet the default per-request logging
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
        elif u.path == "/api/meta":
            self._json(_meta())
        elif u.path == "/api/task":
            d = _task_detail((q.get("id") or [""])[0])
            self._json(d) if d else self._json({"error": "not found"}, 404)
        elif u.path == "/api/status":
            since = int((q.get("since") or ["0"])[0])
            self._json({"lines": RUN["log"][since:], "total": len(RUN["log"]),
                        "active": RUN["active"], "done": RUN["done"],
                        "returncode": RUN["returncode"]})
        elif u.path == "/api/results":
            self._json(_results_summary())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            body = {}
        if u.path == "/api/run":
            self._json(_start_run(body))
        elif u.path == "/api/stop":
            self._json(_stop_run())
        elif u.path == "/api/clear":
            self._json(_clear_results())
        else:
            self._json({"error": "not found"}, 404)


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    load_dotenv()
    OUT.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((host, port), Handler)
    # When bound to all interfaces (e.g. inside Docker) there's no local browser
    # to open and "0.0.0.0" isn't a navigable URL, so point users at localhost.
    display_host = "localhost" if host in ("0.0.0.0", "::") else host
    url = f"http://{display_host}:{port}/"
    print(f"agenteval dashboard -> {url}  (bound to {host}:{port})")
    print("Pick a model, choose tasks, hit Run. Ctrl+C to stop the server.")
    if open_browser and host not in ("0.0.0.0", "::"):
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        httpd.shutdown()
