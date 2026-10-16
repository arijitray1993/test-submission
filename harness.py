"""The harness: Pi (the pi coding agent, @earendil-works/pi-coding-agent), one headless run per task.

Pi runs in this server's container, and the task's files are in another one. task-tools.ts replaces Pi's read,
write, edit and bash tools with versions that act on the task's container through taskbridge's local relay, and the
task's MCP servers reach Pi through the same relay. Pi's own loop does the rest: it calls the model, runs the tools,
retries failed model calls and compacts a long conversation. Its last answer is the final message.

The model is the one model_api names in submission.yaml. Pi's models.json, written for each task, reads the variables
the evaluator sets. Claude and Gemini models use their native APIs under Pi's own provider names (anthropic with
ANTHROPIC_BASE_URL and ANTHROPIC_API_KEY, google with GOOGLE_GEMINI_BASE_URL and GEMINI_API_KEY), so Pi's catalog
gives their limits, thinking and image input. Any other model uses the OpenAI-compatible MODEL_BASE_URL and
MODEL_API_KEY under a provider named "model", which the catalog does not know, so it gets UNKNOWN_MODEL.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import taskbridge

HERE = Path(__file__).resolve().parent
PI = shutil.which("pi") or str(HERE / "node_modules" / ".bin" / "pi")   # npm ci, from package-lock.json
THINKING = "max"                     # pi's --thinking level: off, minimal, low, medium, high, xhigh or max
STOP_BEFORE_SEC = 90                 # stop pi this long before the deadline (less on short tasks) so its answer arrives
CATALOG_TIMEOUT_SEC = 30
# Request features the Google Cloud route for Claude refuses. pi leaves them out, and the Anthropic API works without
# them too.
COMPAT = {"supportsStrictTools": False, "supportsMidConvoEffort": False,
          "supportsMidConvoSystemMessages": False, "supportsMidConvoToolChanges": False}
# A model pi's catalog does not know gets these limits; tune them for yours.
UNKNOWN_MODEL = {"input": ["text"], "contextWindow": 128000, "maxTokens": 16384}
NOTE = ("You are working on an engineering task. Your tools act on the task's Linux container, whose working "
        "directory is {workdir}; it has no internet access. Read the whole instruction and the files it points to, "
        "put every deliverable exactly where and in the format the instruction asks, and check what you wrote. "
        "When you are done, reply with a short summary of what you delivered and where.")


def provider() -> tuple[str, dict]:
    """Pi's provider for the model: its name and its models.json entry."""
    if os.environ.get("ANTHROPIC_BASE_URL"):
        return "anthropic", {"baseUrl": os.environ["ANTHROPIC_BASE_URL"], "api": "anthropic-messages",
                             "apiKey": "$ANTHROPIC_API_KEY", "compat": COMPAT}
    if os.environ.get("GOOGLE_GEMINI_BASE_URL"):
        return "google", {"baseUrl": os.environ["GOOGLE_GEMINI_BASE_URL"] + "/v1beta", "api": "google-generative-ai",
                          "apiKey": "$GEMINI_API_KEY"}
    return "model", {"baseUrl": os.environ["MODEL_BASE_URL"], "api": "openai-completions", "apiKey": "$MODEL_API_KEY"}


def in_catalog(name: str, model: str, env: dict) -> bool:
    """Whether pi's own catalog knows the model. A probe that hangs is killed after CATALOG_TIMEOUT_SEC and counts
    as no, and the model is then configured explicitly with UNKNOWN_MODEL's limits."""
    try:
        out = subprocess.run([PI, "--offline", "--list-models", model], env=env, capture_output=True, text=True,
                             timeout=CATALOG_TIMEOUT_SEC).stdout
    except (subprocess.TimeoutExpired, OSError):
        return False
    return any(line.split()[:2] == [name, model] for line in out.splitlines())


def configure(agent_dir: Path, relay: taskbridge.Relay, session: taskbridge.Session, env: dict) -> tuple[str, str]:
    """Pi's configuration for one task, in its agent directory: the model, quiet settings and the task's MCP
    servers (through the relay)."""
    model = os.environ["MODEL_NAME"]
    name, config = provider()
    models = agent_dir / "models.json"
    models.write_text(json.dumps({"providers": {name: config}}))         # `pi --list-models` reads the provider here
    if not in_catalog(name, model, env):
        config["models"] = [{"id": model, "name": model, **UNKNOWN_MODEL}]
        models.write_text(json.dumps({"providers": {name: config}}))
    settings = {"defaultProjectTrust": "never", "quietStartup": True, "cacheWarming": "off",
                "retry": {"maxRetries": 6, "maxAgentDelayMs": 60000}}
    (agent_dir / "settings.json").write_text(json.dumps(settings))
    servers = {s["name"]: {"url": relay.mcp_url(s["name"]), "timeout": 300} for s in session.mcp_servers}
    (agent_dir / "mcp.json").write_text(json.dumps({"mcpServers": servers}))
    return name, model


class Run:
    """One pi process: its JSON events become the final message, usage notes and log lines."""

    def __init__(self, session: taskbridge.Session, model: str):
        self.session, self.model, self.replies = session, model, 0

    async def on_event(self, event: dict) -> None:
        kind, message = event.get("type"), event.get("message") or {}
        if kind == "message_end" and message.get("role") == "assistant":
            self.replies += 1
            text = "\n".join(b.get("text", "") for b in message.get("content") or [] if b.get("type") == "text")
            if text.strip():
                self.session.final_message = text.strip()
            if message.get("stopReason") == "error":
                await self.session.log(f"pi: model error: {message.get('errorMessage')}")
            u = message.get("usage") or {}             # input_tokens counts cached prompt tokens too
            await self.session.usage(self.model, input_tokens=u.get("input", 0) + u.get("cacheRead", 0)
                                     + u.get("cacheWrite", 0), output_tokens=u.get("output", 0),
                                     cache_read_tokens=u.get("cacheRead", 0))
        elif kind == "tool_execution_start":
            await self.session.log(f"pi: {event.get('toolName')} {json.dumps(event.get('args'))[:300]}")
        elif kind in ("auto_retry_start", "compaction_start"):
            await self.session.log(f"pi: {kind} {json.dumps(event)[:300]}")

    async def on_line(self, line: bytes) -> None:
        try:
            event = json.loads(line)
        except ValueError:
            return
        if isinstance(event, dict):
            await self.on_event(event)


async def solve(session: taskbridge.Session) -> str:
    """Work one task: pi in a scratch home, its tools on the task's container, the instruction on stdin."""
    with tempfile.TemporaryDirectory(prefix="pi-", dir=os.environ.get("HOME") or None,
                                     ignore_cleanup_errors=True) as scratch:
        agent_dir, work = Path(scratch) / "agent", Path(scratch) / "work"
        agent_dir.mkdir()
        work.mkdir()
        async with taskbridge.Relay(session) as relay:
            env = relay.env()
            env.update(PI_CODING_AGENT_DIR=str(agent_dir), PI_OFFLINE="1", PI_SKIP_VERSION_CHECK="1",
                       PI_TELEMETRY="0", NODE_NO_WARNINGS="1", TASK_WORKDIR=session.workdir)
            name, model = await asyncio.to_thread(configure, agent_dir, relay, session, env)
            argv = [PI, "--print", "--mode", "json", "--no-session", "-nc", "-ns", "-np", "-na",
                    "-e", str(HERE / "task-tools.ts"), "--provider", name, "--model", model, "--thinking", THINKING,
                    "--append-system-prompt", NOTE.format(workdir=session.workdir)]
            run = Run(session, model)
            done = await taskbridge.run_process(argv, session, env=env, cwd=str(work), on_line=run.on_line,
                                                stdin=session.instruction.encode(), stop_before_sec=STOP_BEFORE_SEC,
                                                log_prefix="pi: ")
    if not run.replies:
        raise RuntimeError(f"pi exited with {done.code} before the model answered: {done.stderr[-2000:]}")
    return session.final_message or "(pi stopped without a final message)"
