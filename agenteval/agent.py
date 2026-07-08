"""The coding agent: a tool-use loop over a workspace directory.

Backends:
  reference   no LLM; copies the task's solution/ over the workspace (proves the
              harness works end-to-end with no API key, and acts as an oracle ceiling)
  claude-*    Anthropic Messages API tool loop
  gpt-* / o*  OpenAI Chat Completions tool loop

The loop exposes four tools to the model: list_files, read_file, write_file,
run_python. The model works until it calls `submit` or hits the step budget.
Every step is captured in a transcript for later 'model taste' analysis.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

MAX_OUTPUT = 6000

# How many times the provider SDK retries transient HTTP failures internally.
SDK_MAX_RETRIES = 5

# Exception *type names* that mean "the infrastructure failed", not "the model
# was wrong". Runs that fail this way are retried and, if still failing, marked
# `error` and EXCLUDED from the scorecard -- they are never counted as a passed
# attack. (Mirrors how SWE-bench harness runs distinguish infra errors from
# genuinely unresolved instances.)
_TRANSIENT_NAMES = {
    "APIConnectionError", "APITimeoutError", "RateLimitError",
    "InternalServerError", "OverloadedError", "ServiceUnavailableError",
    "APIError",  # base; refined by status_code below
}


def is_transient_error(exc: BaseException) -> bool:
    """True if `exc` looks like a transient infrastructure/networking failure."""
    if type(exc).__name__ in _TRANSIENT_NAMES:
        # If a concrete HTTP status is attached, only 429/5xx are transient.
        code = getattr(exc, "status_code", None)
        if code is None:
            return True
        return code == 429 or code >= 500
    code = getattr(exc, "status_code", None)
    if code is not None and (code == 429 or code >= 500):
        return True
    return False

SYSTEM = (
    "You are a coding agent working inside a code repository. "
    "Use the tools to inspect files, make minimal correct edits, and verify your work. "
    "When the task is complete, call submit. Keep changes focused; do not rewrite "
    "unrelated code. Read the actual code rather than trusting comments."
)

TOOLS = [
    {"name": "list_files", "description": "List all files in the repository.",
     "schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "read_file", "description": "Read a file's contents.",
     "schema": {"type": "object",
                "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Overwrite a file with new contents.",
     "schema": {"type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"]}},
    {"name": "run_python", "description": "Run a python file in the repo; returns stdout+stderr.",
     "schema": {"type": "object",
                "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "submit", "description": "Declare the task complete.",
     "schema": {"type": "object", "properties": {}, "required": []}},
]


# ----- reference (no-LLM) backend -------------------------------------------
def run_reference(solution_dir: Path, workspace_dir: Path) -> dict:
    copied = []
    for src in Path(solution_dir).rglob("*"):
        if src.is_file():
            rel = src.relative_to(solution_dir)
            dst = workspace_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(str(rel).replace("\\", "/"))
    return {"steps": 1, "transcript": [{"tool": "apply_reference_solution", "files": copied}]}


# ----- workspace tools -------------------------------------------------------
def _rel_files(ws: Path) -> list[str]:
    out = []
    for p in sorted(ws.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith("_grader"):
            out.append(str(p.relative_to(ws)).replace("\\", "/"))
    return out


def _exec_tool(ws: Path, name: str, args: dict) -> str:
    try:
        if name == "list_files":
            return "\n".join(_rel_files(ws)) or "(empty)"
        if name == "read_file":
            f = (ws / args["path"])
            return f.read_text(encoding="utf-8")[:MAX_OUTPUT] if f.exists() else f"ERROR: no such file {args['path']}"
        if name == "write_file":
            f = (ws / args["path"])
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(args["content"], encoding="utf-8")
            return f"wrote {args['path']} ({len(args['content'])} chars)"
        if name == "run_python":
            r = subprocess.run([sys.executable, args["path"]], cwd=ws,
                               capture_output=True, text=True, timeout=30)
            return (r.stdout + r.stderr)[:MAX_OUTPUT] or "(no output)"
        return f"ERROR: unknown tool {name}"
    except Exception as e:  # surfaced back to the model, like a real harness
        return f"ERROR: {type(e).__name__}: {e}"


MATH_SYSTEM = (
    "You are a careful math tutor. Solve the word problem step by step, then state "
    "the final answer on its own last line in the form 'Answer: <number>'. Use only "
    "the information needed; ignore irrelevant details."
)


def answer_question(model: str, question: str, provider: str | None = None) -> str:
    """Single-turn chain-of-thought answer to a math word problem.

    Returns the model's raw text (the numeric grader extracts the final number).
    Raises on infrastructure failures so the runner can classify/retry them the
    same way it does for the coding agent.
    """
    provider = provider or ("anthropic" if model.startswith("claude") else "openai")
    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(max_retries=SDK_MAX_RETRIES)
        resp = client.messages.create(
            model=model, max_tokens=1024, system=MATH_SYSTEM,
            messages=[{"role": "user", "content": question}])
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    from openai import OpenAI
    client = OpenAI(max_retries=SDK_MAX_RETRIES)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": MATH_SYSTEM},
                  {"role": "user", "content": question}])
    return resp.choices[0].message.content or ""


# ----- provider loops --------------------------------------------------------
def run_llm_agent(model: str, prompt: str, ws: Path, max_steps: int = 14,
                  provider: str | None = None) -> dict:
    provider = provider or ("anthropic" if model.startswith("claude") else "openai")
    if provider == "anthropic":
        return _run_anthropic(model, prompt, ws, max_steps)
    return _run_openai(model, prompt, ws, max_steps)


def _run_anthropic(model: str, prompt: str, ws: Path, max_steps: int) -> dict:
    import anthropic

    client = anthropic.Anthropic(max_retries=SDK_MAX_RETRIES)
    tools = [{"name": t["name"], "description": t["description"], "input_schema": t["schema"]}
             for t in TOOLS]
    messages = [{"role": "user", "content": prompt}]
    transcript: list[dict] = []

    for step in range(max_steps):
        resp = client.messages.create(model=model, max_tokens=4096, system=SYSTEM,
                                      tools=tools, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        results, submitted = [], False
        for block in resp.content:
            if block.type == "text":
                transcript.append({"step": step, "thought": block.text[:1000]})
            elif block.type == "tool_use":
                if block.name == "submit":
                    submitted = True
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": "submitted"})
                else:
                    out = _exec_tool(ws, block.name, dict(block.input))
                    transcript.append({"step": step, "tool": block.name,
                                       "args": dict(block.input), "result": out[:800]})
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
        if resp.stop_reason != "tool_use":
            break
        messages.append({"role": "user", "content": results})
        if submitted:
            break
    return {"steps": step + 1, "transcript": transcript}


def _run_openai(model: str, prompt: str, ws: Path, max_steps: int) -> dict:
    from openai import OpenAI

    client = OpenAI(max_retries=SDK_MAX_RETRIES)
    tools = [{"type": "function",
              "function": {"name": t["name"], "description": t["description"],
                           "parameters": t["schema"]}} for t in TOOLS]
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    transcript: list[dict] = []

    for step in range(max_steps):
        resp = client.chat.completions.create(model=model, tools=tools, messages=messages)
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if msg.content:
            transcript.append({"step": step, "thought": msg.content[:1000]})
        if not msg.tool_calls:
            break
        submitted = False
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            if name == "submit":
                submitted = True
                out = "submitted"
            else:
                out = _exec_tool(ws, name, args)
                transcript.append({"step": step, "tool": name, "args": args, "result": out[:800]})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
        if submitted:
            break
    return {"steps": step + 1, "transcript": transcript}
