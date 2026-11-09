"""Model backends. Each returns a dict:
    {"text": final reply, "model": resolved model id, "usage": {...},
     "cost_usd": float | None, "tool_attempts": int, "raw": transport record}

Single-turn, no tools, fresh context per trial.

  anthropic-api  Anthropic Messages API        (ANTHROPIC_API_KEY)
  openai-api     OpenAI Responses API          (OPENAI_API_KEY)
  claude-cli     Claude Code `claude -p`, tools disabled, own system prompt,
                 no settings / CLAUDE.md, run in an empty temp dir
  codex-cli      Codex `codex exec`, shell/exec/web disabled (exec fails closed),
                 throwaway CODEX_HOME holding only auth, empty temp dir
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

SYSTEM_PROMPT = "You are an expert FHIR interoperability engineer. Answer precisely."


def anthropic_api(prompt: str, model: str, max_tokens: int = 64000, effort: str | None = None, **_) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    kwargs = {}
    if effort:
        kwargs["thinking"] = {"type": "adaptive"}
        kwargs["output_config"] = {"effort": effort}
    # Streaming avoids HTTP timeouts on long reasoning replies.
    with client.messages.stream(
        model=model, max_tokens=max_tokens, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}], **kwargs,
    ) as stream:
        msg = stream.get_final_message()
    text = "".join(b.text for b in msg.content if b.type == "text")
    return {"text": text, "model": msg.model, "usage": msg.usage.model_dump(),
            "cost_usd": None, "tool_attempts": 0, "raw": {"stop_reason": msg.stop_reason}}


def openai_api(prompt: str, model: str, effort: str | None = None, **_) -> dict:
    from openai import OpenAI

    client = OpenAI()
    kwargs = {"reasoning": {"effort": effort}} if effort else {}
    resp = client.responses.create(model=model, instructions=SYSTEM_PROMPT, input=prompt, **kwargs)
    return {"text": resp.output_text, "model": resp.model, "usage": resp.usage.model_dump() if resp.usage else {},
            "cost_usd": None, "tool_attempts": 0, "raw": {"status": resp.status}}


def claude_cli(prompt: str, model: str, effort: str | None = None, timeout: int = 1800, **_) -> dict:
    cmd = ["claude", "-p", "--model", model, "--tools", "", "--strict-mcp-config",
           "--setting-sources", "", "--no-session-persistence",
           "--system-prompt", SYSTEM_PROMPT, "--output-format", "json"]
    if effort:
        cmd += ["--effort", effort]
    with tempfile.TemporaryDirectory() as cwd:
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"claude exited {p.returncode}: {p.stderr[-500:] or p.stdout[-500:]}")
    d = json.loads(p.stdout)
    if d.get("is_error"):
        raise RuntimeError(f"claude error: {d.get('result')}")
    models = list(d.get("modelUsage", {}))
    return {"text": d.get("result", ""), "model": models[0] if len(models) == 1 else models,
            "usage": d.get("usage", {}), "cost_usd": d.get("total_cost_usd"), "tool_attempts": 0,
            "raw": {k: d.get(k) for k in ("duration_ms", "num_turns", "session_id", "modelUsage")}}


# Item types that are real tool use. "error" items are startup warnings Codex emits
# (approval-policy fallback, disabled code-mode host), not model actions.
_TOOL_ITEMS = ("command_execution", "file_change", "mcp_tool_call", "web_search", "collab_tool_call")

_CODEX_DISABLE = ["shell_tool", "unified_exec", "code_mode_host", "apps", "tool_suggest", "sleep_tool"]


def codex_cli(prompt: str, model: str, effort: str | None = None, timeout: int = 1800, **_) -> dict:
    auth = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "auth.json"
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as cwd:
        if auth.exists():
            os.symlink(auth, Path(home) / "auth.json")
        cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
               "--ignore-rules", "-s", "read-only", "-C", cwd, "-m", model, "--json",
               "-c", 'web_search="disabled"']
        for f in _CODEX_DISABLE:
            cmd += ["--disable", f]
        if effort:
            cmd += ["-c", f'model_reasoning_effort="{effort}"']
        cmd.append("-")
        env = dict(os.environ, CODEX_HOME=home)
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout)
    events = [json.loads(l) for l in p.stdout.splitlines() if l.startswith("{")]
    messages, tool_attempts, usage, item_types = [], 0, {}, []
    for e in events:
        item = e.get("item", {})
        if e.get("type") == "item.completed":
            item_types.append(item.get("type"))
            if item.get("type") == "agent_message":
                messages.append(item.get("text", ""))
            elif item.get("type") in _TOOL_ITEMS:
                tool_attempts += 1
        if e.get("type") == "turn.completed":
            usage = e.get("usage", {})
        if e.get("type") in ("turn.failed", "error"):
            raise RuntimeError(f"codex error: {json.dumps(e)[:500]}")
    if not messages:
        raise RuntimeError(f"codex produced no message (exit {p.returncode}): {p.stderr[-500:]}")
    return {"text": messages[-1], "model": model, "usage": usage, "cost_usd": None,
            "tool_attempts": tool_attempts, "raw": {"n_events": len(events), "item_types": item_types, "n_messages": len(messages)}}


BACKENDS = {"anthropic-api": anthropic_api, "openai-api": openai_api,
            "claude-cli": claude_cli, "codex-cli": codex_cli}


def available(backend: str) -> bool:
    if backend == "anthropic-api":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if backend == "openai-api":
        return bool(os.environ.get("OPENAI_API_KEY"))
    return shutil.which(backend.split("-")[0]) is not None
