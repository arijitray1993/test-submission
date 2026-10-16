"""Serve-protocol plumbing for a harness (docs/protocol.md): the websocket server, one Session per task, a Relay
that gives an agent running as a subprocess the same access to the task container over local HTTP, and an MCPClient
for the task's MCP servers.

    import taskbridge

    async def solve(session):
        result = await session.exec("ls -la")
        ...
        return "Wrote /app/output/report.md: ..."     # the final message

    taskbridge.run(solve)                             # listens on $PORT

Standard library plus `websockets`. Copy this file into your submission.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import itertools
import json
import math
import os
import re
import secrets
import signal
import sys
import time
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from websockets.asyncio.server import serve as _ws_serve
from websockets.exceptions import ConnectionClosed

# Limits the evaluator enforces (docs/protocol.md). It counts a message past one of them as malformed, or closes the
# connection.
MAX_FRAME = 16 << 20            # one message, in either direction
MAX_HTTP_BYTES = 10_000_000     # an http request's body
MAX_WRITE_BYTES = 10_000_000    # one write_file's data
MAX_TIMEOUT_SEC = 600           # limits.exec_timeout_sec: a longer exec or http timeout is cut to this
HTTP_METHODS = ("GET", "POST", "DELETE", "PUT", "PATCH", "HEAD", "OPTIONS")

# This file's own limits.
MAX_FINAL_CHARS = 1_000_000     # a longer final message is cut, so that done fits in one message
WRITE_CHUNK = 4 << 20           # write_file sends a larger file in parts of this size, under MAX_WRITE_BYTES
MAX_LINE = 32 << 20             # run_process skips a longer line of subprocess output
MAX_HEAD = 64 << 10             # the Relay's limit on a request line and headers
MAX_BODY = 64 << 20             # and on a body (a write_file body holds a whole file as base64 JSON)


class Cancelled(Exception):
    """The task is over: the evaluator cancelled it (time is up) or the connection closed. Stop and return what you
    have."""


class TaskError(Exception):
    """A request the evaluator answered with ok: false, or one taskbridge refused before sending because the evaluator
    would count it as malformed."""


class Session:
    """One task. Requests may run concurrently; each awaits its own result."""

    def __init__(self, ws, task: dict):
        self.ws = ws
        self.task = task
        self.instruction: str = task["instruction"]
        self.workdir: str = task.get("workdir") or "/"
        limits, servers = task.get("limits"), task.get("mcp_servers")
        self.limits: dict = limits if isinstance(limits, dict) else {}
        self.mcp_servers: list[dict] = [s for s in servers if isinstance(s, dict)] if isinstance(servers, list) else []
        budget = self.limits.get("agent_timeout_sec")
        self.deadline = time.monotonic() + budget if isinstance(budget, (int, float)) and budget > 0 else None
        self.final_message = ""
        self.cancelled = asyncio.Event()
        self._ids = itertools.count(1)
        self._waiting: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    def time_left(self) -> float | None:
        return None if self.deadline is None else self.deadline - time.monotonic()

    async def send(self, message: dict) -> None:
        await self._send(_frame(message))

    async def _send(self, frame: str) -> None:
        async with self._lock:
            await self.ws.send(frame)

    async def _read(self) -> None:
        """Hand each result to the request waiting for it, until the evaluator cancels or closes the socket. A frame
        that is not a JSON object is skipped. When reading stops for any reason, the session is cancelled and every
        waiting request raises Cancelled."""
        try:
            async for frame in self.ws:
                try:
                    msg = json.loads(frame)
                except ValueError:
                    msg = None
                if not isinstance(msg, dict):
                    print(f"taskbridge: skipped a frame that is not a JSON object: {str(frame)[:200]!r}",
                          file=sys.stderr, flush=True)
                    continue
                rid = msg.get("id")
                if msg.get("type") == "result" and isinstance(rid, str) and rid in self._waiting:
                    future = self._waiting.pop(rid)
                    if not future.done():
                        future.set_result(msg)
                elif msg.get("type") == "cancel":
                    break
        except ConnectionClosed:
            pass
        except Exception as exc:  # noqa: BLE001 - logged, and the waiting requests are still released below
            print(f"taskbridge: stopped reading the evaluator's messages: {type(exc).__name__}: {exc}",
                  file=sys.stderr, flush=True)
        finally:
            self.cancelled.set()
            for future in self._waiting.values():
                if not future.done():
                    future.set_exception(Cancelled())
            self._waiting.clear()

    async def request(self, kind: str, **fields) -> dict:
        """Send one request and wait for its result. Fields set to None are left out. Raises Cancelled when the task
        is cancelled or the socket closes, including during the send."""
        if self.cancelled.is_set():
            raise Cancelled()
        rid = str(next(self._ids))
        message = {"type": kind, "id": rid, **{k: v for k, v in fields.items() if v is not None}}
        frame = _frame(message)                                  # a message over MAX_FRAME raises here
        future = asyncio.get_running_loop().create_future()
        self._waiting[rid] = future
        try:
            try:
                await self._send(frame)
            except ConnectionClosed:
                self.cancelled.set()
                if future.done() and not future.cancelled():
                    # the reader may have failed it already: read its exception, or asyncio logs it as never retrieved
                    future.exception()
                raise Cancelled() from None
            return await future
        finally:
            self._waiting.pop(rid, None)

    async def exec(self, command: str, timeout_sec: int = 120) -> dict:
        """Run `bash -c command` in the task container, in workdir. Returns exit_code, output, truncated, timed_out."""
        result = await self.request("exec", command=_text("exec: the command", command),
                                    timeout_sec=_seconds(timeout_sec))
        if result.get("ok") is False:
            raise TaskError(result.get("error"))
        return result

    async def read_file(self, path: str) -> bytes:
        """The whole file. Raises TaskError for a file over 10 MB, the most one read returns (read it in parts with
        exec)."""
        result = await self.read_result(path)
        if not result.get("ok"):
            raise TaskError(result.get("error"))
        if result.get("truncated"):
            raise TaskError(f"{path} is {result.get('size')} bytes, over the 10 MB a read returns; read it in parts")
        return base64.b64decode(result["content_b64"])

    async def read_result(self, path: str) -> dict:
        """read_file's result as the evaluator sends it: ok, content_b64, size, truncated (or error)."""
        return await self.request("read_file", path=_text("read_file: the path", path))

    async def write_file(self, path: str, data: bytes | str, append: bool = False) -> int:
        path = _text("write_file: the path", path)
        if not isinstance(data, (bytes, bytearray, str)):
            raise TaskError("write_file: the data is bytes or text")
        data = data.encode() if isinstance(data, str) else bytes(data)
        size = 0
        for start in range(0, max(len(data), 1), WRITE_CHUNK):
            chunk = data[start:start + WRITE_CHUNK]
            result = await self.request("write_file", path=path, append=bool(append) or start > 0,
                                        content_b64=base64.b64encode(chunk).decode())
            if not result.get("ok"):
                raise TaskError(result.get("error"))
            size = result.get("size", size)
        return size

    async def http(self, url: str, method: str = "POST", headers: dict | None = None, body: bytes = b"",
                   timeout_sec: int = 120) -> dict:
        """Make an HTTP request from inside the task container to one of its mcp_servers. Returns status, headers,
        body and truncated. A request the evaluator would count as malformed raises TaskError here instead."""
        url = _text("http: the url", url)
        if not mcp_allows(url, self.mcp_servers):
            raise TaskError(f"http: {url} is not one of the task's MCP servers, nor a path under one")
        method = str(method or "GET").upper()
        if method not in HTTP_METHODS:
            raise TaskError(f"http: the method is one of {', '.join(HTTP_METHODS)}")
        headers = headers or {}
        if not isinstance(headers, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                    for k, v in headers.items()):
            raise TaskError("http: the headers are names and values, as text")
        for k, v in headers.items():
            _text("http: a header", f"{k}:{v}")
        if not isinstance(body, (bytes, bytearray)):
            raise TaskError("http: the body is bytes")
        if len(body) > MAX_HTTP_BYTES:
            raise TaskError(f"http: the body is {len(body)} bytes, over the {MAX_HTTP_BYTES} an http request carries")
        result = await self.request("http", url=url, method=method, headers=headers, timeout_sec=_seconds(timeout_sec),
                                    body_b64=base64.b64encode(body).decode())
        if result.get("ok") is False:
            raise TaskError(result.get("error"))
        return {"status": result["status"], "headers": result.get("headers") or {},
                "body": base64.b64decode(result.get("body_b64") or ""), "truncated": bool(result.get("truncated"))}

    async def log(self, text: str) -> None:
        with contextlib.suppress(ConnectionClosed):
            await self.send({"type": "log", "text": text[:20000]})

    async def usage(self, model: str, input_tokens: int = 0, output_tokens: int = 0, cache_read_tokens: int = 0):
        with contextlib.suppress(ConnectionClosed):
            await self.send({"type": "usage", "model": model, "input_tokens": positive_int(input_tokens, 0),
                             "output_tokens": positive_int(output_tokens, 0),
                             "cache_read_tokens": positive_int(cache_read_tokens, 0)})


def _frame(message: dict) -> str:
    """`message` as JSON text. Raises TaskError when it is over MAX_FRAME, since the evaluator closes the connection
    on a larger message."""
    frame = json.dumps(message)                 # ASCII (non-ASCII is escaped), so its length is its size in bytes
    if len(frame) > MAX_FRAME:
        hint = "write a long script with write_file and run that" if message.get("type") == "exec" else "send less"
        raise TaskError(f"{message.get('type')}: the message is {len(frame)} bytes, over the protocol's "
                        f"{MAX_FRAME >> 20} MiB; {hint}")
    return frame


def _final(text: str) -> str:
    """`text` cut to MAX_FINAL_CHARS, which stays under MAX_FRAME even if every character is escaped."""
    if len(text) <= MAX_FINAL_CHARS:
        return text
    return text[:MAX_FINAL_CHARS] + "\n[... the rest of this message was cut]"


def _text(what: str, value) -> str:
    """Check a command, path, url or header. The evaluator counts anything other than non-empty text without a NUL
    byte or an unpaired surrogate as a malformed frame."""
    if not isinstance(value, str) or not value:
        raise TaskError(f"{what} is empty or not text")
    if "\x00" in value:
        raise TaskError(f"{what} holds a NUL byte")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise TaskError(f"{what} is not valid UTF-8 (an unpaired surrogate)") from None
    return value


def _seconds(value) -> int:
    """A timeout_sec clamped to 1..MAX_TIMEOUT_SEC, or 120 for None. An int is compared as an int, so 10**400 is
    clamped instead of overflowing float(). Anything else that is not a finite number raises TaskError."""
    if value is None:
        return 120
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value or abs(value) == float("inf"):
        raise TaskError("timeout_sec is a number of seconds")
    return min(max(1, int(value)), MAX_TIMEOUT_SEC)


def mcp_allows(url: str, servers: list[dict]) -> bool:
    """The evaluator's rule for http: the URL is one of the task's MCP server URLs, optionally followed by a query, or
    a path under one. A path with a '.' or '..' segment (before or after percent-decoding), an encoded slash, a
    backslash or a ';' is refused, because a server that normalises it could answer for a route outside the MCP URL
    (some servers drop path parameters such as '..;' before normalising)."""
    try:
        path = urlsplit(url).path
    except ValueError:
        return False
    decoded = unquote(path)
    if "%2f" in path.lower() or "%5c" in path.lower() or "\\" in path or ";" in decoded \
            or {".", ".."} & set(decoded.split("/")):
        return False
    for server in servers:
        base = str(server.get("url") or "")
        if base and (url == base or ("?" not in base and url.startswith(base + "?"))
                     or url.startswith(base.rstrip("/") + "/")):
            return True
    return False


async def _session(ws, handler) -> None:
    try:
        task = json.loads(await ws.recv())
    except ConnectionClosed:
        return
    except ValueError:
        task = None
    if not isinstance(task, dict) or task.get("type") != "task" or not isinstance(task.get("instruction"), str):
        with contextlib.suppress(ConnectionClosed):
            await ws.send(json.dumps({"type": "error", "message": "expected a task message first"}))
        return
    session = Session(ws, task)
    reader = asyncio.create_task(session._read())
    work = asyncio.create_task(handler(session))
    stop = asyncio.create_task(session.cancelled.wait())
    try:
        done, _ = await asyncio.wait({work, stop}, return_when=asyncio.FIRST_COMPLETED)
        exc = work.exception() if work in done and not work.cancelled() else Cancelled()
        if exc is None:
            answer = work.result()
            await session.send({"type": "done", "final_message": _final(answer if isinstance(answer, str) and answer
                                                                       else session.final_message)})
        elif not isinstance(exc, Cancelled):
            print(f"harness error: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            if session.final_message:
                # a summary written before the failure still reaches the graders, who read the final message
                await session.log(f"harness error after its summary: {type(exc).__name__}: {exc}"[:2000])
                await session.send({"type": "done", "final_message": _final(session.final_message)})
            else:
                await session.send({"type": "error", "message": f"{type(exc).__name__}: {exc}"[:2000]})
        else:
            # The evaluator closes the socket 10 s after cancel: give the handler 2 s to return its answer, then
            # cancel it and wait up to 6 s more.
            await asyncio.wait({work}, timeout=2)
            if not work.done():
                work.cancel()
                await asyncio.wait({work}, timeout=6)
            answer = work.result() if work.done() and not work.cancelled() and work.exception() is None else None
            final = answer if isinstance(answer, str) and answer else session.final_message
            await session.send({"type": "done", "final_message": _final(final or "(stopped: time is up)")})
    except ConnectionClosed:
        pass
    finally:
        for t in (work, stop, reader):
            t.cancel()


async def serve_forever(handler, port: int | None = None) -> None:
    port = int(port or os.environ.get("PORT", 8765))

    async def on_connect(ws):
        await _session(ws, handler)

    async with _ws_serve(on_connect, "0.0.0.0", port, max_size=MAX_FRAME, ping_interval=None):
        print(f"listening on {port}", flush=True)
        await asyncio.Future()


def run(handler, port: int | None = None) -> None:
    """Serve `handler(session) -> final message` on $PORT until the process is stopped."""
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve_forever(handler, port))


class Relay:
    """Local HTTP access to the task container for an agent that runs as a subprocess.

        POST {url}/exec        {"command", "timeout_sec"}          -> the exec result
        POST {url}/read_file   {"path"}                             -> {"ok", "content_b64", "size", ...}
        POST {url}/write_file  {"path", "content_b64", "append"}   -> {"ok", "size"}
        ANY  {url}/mcp/<name>/...                                   -> the task's MCP server <name>, proxied

    `url` holds a random token. Give the subprocess `env()`: it sets TASK_RELAY_URL and keeps local traffic off the
    egress proxy. The relay answers one request per connection and refuses a request with unclear framing
    (_read_request). The evaluator's limits apply here too: an MCP request's body is at most MAX_HTTP_BYTES, an exec
    fits one message, and write_file takes up to MAX_BODY of base64 JSON, which it sends on in protocol-sized parts."""

    def __init__(self, session: Session):
        self.session = session
        self.token = secrets.token_hex(16)
        self.url = ""
        self._server = None

    async def __aenter__(self) -> Relay:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0, limit=MAX_HEAD)
        port = self._server.sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}/{self.token}"
        return self

    async def __aexit__(self, *exc) -> None:
        self._server.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self._server.wait_closed(), 2)

    def mcp_url(self, name: str) -> str:
        return f"{self.url}/mcp/{quote(name, safe='')}/"

    def env(self, base: dict | None = None) -> dict:
        env = dict(os.environ if base is None else base)
        env["TASK_RELAY_URL"] = self.url
        local = "127.0.0.1,localhost"
        env["NO_PROXY"] = env["no_proxy"] = f"{local},{env['NO_PROXY']}" if env.get("NO_PROXY") else local
        return env

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            method, path, query, headers, body = await _read_request(reader, writer)
            status, out_headers, payload = await self._route(method, path, query, headers, body)
        except BadRequest as exc:
            status, out_headers = exc.status, {"Content-Type": "application/json"}
            payload = json.dumps({"error": str(exc)}).encode()
        except asyncio.IncompleteReadError:
            status, out_headers = 400, {"Content-Type": "application/json"}
            payload = b'{"error": "the request ended before its body did"}'
        except Cancelled:
            status, out_headers, payload = 503, {"Content-Type": "application/json"}, b'{"error": "cancelled"}'
        except Exception as exc:  # one bad request never stops the relay
            status, out_headers = 500, {"Content-Type": "application/json"}
            payload = json.dumps({"error": f"{type(exc).__name__}: {exc}"}).encode()
        head = f"HTTP/1.1 {status} {_REASONS.get(status, 'OK')}\r\n"
        out_headers = {**out_headers, "Content-Length": str(len(payload)), "Connection": "close"}
        head += "".join(f"{k}: {v}\r\n" for k, v in out_headers.items()) + "\r\n"
        with contextlib.suppress(Exception):
            writer.write(head.encode("latin-1") + payload)
            await writer.drain()
        writer.close()

    async def _route(self, method: str, path: str, query: str, headers: dict, body: bytes):
        prefix = f"/{self.token}/"
        if not path.startswith(prefix):
            return 404, {}, b""
        route = path[len(prefix):]
        if route.startswith("mcp/"):
            return await self._mcp(method, route[4:], query, headers, body)
        if method != "POST" or route not in ("exec", "read_file", "write_file"):
            return 404, {}, b""
        try:
            fields = json.loads(body or b"{}")
        except ValueError:
            fields = None
        if not isinstance(fields, dict):
            return 400, {"Content-Type": "application/json"}, b'{"error": "the body is a JSON object"}'
        # Only the known fields go on, through the Session's own methods. A request they refuse gets a result with ok
        # false here and never reaches the evaluator as a malformed frame.
        try:
            if route == "exec":
                result = await self.session.exec(fields.get("command"), fields.get("timeout_sec", 120))
            elif route == "read_file":
                result = await self.session.read_result(fields.get("path"))
            else:
                encoded = fields.get("content_b64")     # the evaluator requires it too; "" writes an empty file
                if not isinstance(encoded, str):
                    raise TaskError('write_file: content_b64 is required, as base64 text ("" writes an empty file)')
                try:
                    data = base64.b64decode(encoded, validate=True)
                except ValueError:
                    raise TaskError("write_file: content_b64 is not base64 text") from None
                result = {"ok": True, "size": await self.session.write_file(fields.get("path"), data,
                                                                            bool(fields.get("append")))}
        except TaskError as exc:
            result = {"ok": False, "error": str(exc)}
        result = {k: v for k, v in result.items() if k not in ("type", "id")}
        return 200, {"Content-Type": "application/json"}, json.dumps(result).encode()

    async def _mcp(self, method: str, rest: str, query: str, headers: dict, body: bytes):
        name, _, tail = rest.partition("/")
        server = next((s for s in self.session.mcp_servers if s.get("name") == unquote(name)), None)
        if server is None:
            return 404, {}, b"no such MCP server"
        if method == "GET" or method not in HTTP_METHODS:
            # a GET opens a stream of server-sent events, which one http request and its single response cannot carry
            return 405, {"Allow": ", ".join(m for m in HTTP_METHODS if m != "GET")}, b""
        if len(body) > MAX_HTTP_BYTES:
            return 413, {"Content-Type": "application/json"}, json.dumps(
                {"error": f"the body is over the {MAX_HTTP_BYTES} bytes an http request carries"}).encode()
        keep = ("content-type", "accept", "mcp-session-id", "mcp-protocol-version", "authorization", "last-event-id")
        forward = {k: v for k, v in headers.items() if k.lower() in keep}
        try:
            reply = await self.session.http(mcp_target(str(server.get("url") or ""), tail, query), method=method,
                                            headers=forward, body=body, timeout_sec=MAX_TIMEOUT_SEC)
        except TaskError as exc:            # refused here (a path outside the server, a bad header) or by the evaluator
            return 400, {"Content-Type": "application/json"}, json.dumps({"error": str(exc)}).encode()
        if reply["truncated"]:
            return 502, {}, b"the MCP server's response is larger than the protocol carries"
        back = {k: v for k, v in reply["headers"].items()
                if k.lower() in ("content-type", "mcp-session-id", "mcp-protocol-version")}
        return reply["status"], back, reply["body"]


def mcp_target(server_url: str, tail: str, query: str) -> str:
    """The URL the relay forwards a request to: `tail`, a path below the MCP server, goes on the end of the server
    URL's path, then `query`. The evaluator takes a server URL that has a query of its own only as it is."""
    if not tail and not query:
        return server_url
    parts = urlsplit(server_url)
    if parts.query:
        raise TaskError(f"{server_url} has a query of its own, so the evaluator accepts it only without a path or "
                        "query added")
    path = f"{parts.path.rstrip('/')}/{tail}" if tail else parts.path
    return urlunsplit(parts._replace(path=path, query=query))


class MCPError(RuntimeError):
    """An MCP server answered with an HTTP or JSON-RPC error, with too large an answer, or with no answer to the
    request."""


class MCPClient:
    """One of the task's MCP servers (streamable HTTP: JSON-RPC posts, answered with JSON or with server-sent events),
    called from inside the task container through Session.http. An MCP failure raises MCPError, and a request
    Session.http refuses raises TaskError."""
    VERSION = "2025-06-18"                      # the MCP protocol version asked for

    def __init__(self, session: Session, url: str, *, client: str = "harness", timeout_sec: int = 300):
        self.session, self.url, self.client, self.timeout_sec = session, url, client, timeout_sec
        self.headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        self._ids = itertools.count(1)

    async def rpc(self, method: str, params: dict | None = None, notify: bool = False) -> dict | None:
        """Call `method` and return its result as a dict, or None for a notification (its answer is not read)."""
        message = {"jsonrpc": "2.0", "method": method, **({"params": params} if params is not None else {})}
        if not notify:
            message["id"] = next(self._ids)
        reply = await self.session.http(self.url, "POST", dict(self.headers), json.dumps(message).encode(),
                                        timeout_sec=self.timeout_sec)
        if reply.get("truncated"):
            raise MCPError(f"{method}: the answer is larger than the protocol carries")
        for key, value in reply["headers"].items():
            if key.lower() == "mcp-session-id":
                self.headers["Mcp-Session-Id"] = value
        if notify:
            return None
        body = reply["body"].decode("utf-8", "replace")
        if reply["status"] >= 400:
            raise MCPError(f"{method}: HTTP {reply['status']}: {body[:300]!r}")
        for answer in self.messages(body):
            if answer.get("id") == message["id"]:
                if "error" in answer:
                    raise MCPError(f"{method}: {answer['error']}")
                return answer["result"] if isinstance(answer.get("result"), dict) else {}
        raise MCPError(f"{method}: no answer in {body[:300]!r}")

    @staticmethod
    def messages(body: str) -> list[dict]:
        """The JSON-RPC messages in an answer body: JSON (one message or a batch), or server-sent events with each
        event's `data:` lines joined. Anything that is not a JSON object is skipped."""
        text = body.strip()
        if text.startswith(("{", "[")):
            chunks = [text]
        else:
            chunks = ["\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:"))
                      for block in re.split(r"\r?\n\r?\n", text)]
        found = []
        for chunk in filter(None, chunks):
            try:
                data = json.loads(chunk)
            except ValueError:
                continue
            found += [m for m in (data if isinstance(data, list) else [data]) if isinstance(m, dict)]
        return found

    async def initialize(self) -> dict:
        """Open the session. Every later request names the protocol version the server chose, as MCP's HTTP transport
        asks."""
        result = await self.rpc("initialize", {"protocolVersion": self.VERSION, "capabilities": {},
                                               "clientInfo": {"name": self.client, "version": "1.0"}})
        version = result.get("protocolVersion")
        self.headers["MCP-Protocol-Version"] = version if isinstance(version, str) and version else self.VERSION
        await self.rpc("notifications/initialized", notify=True)
        return result

    async def list_tools(self, max_pages: int = 100) -> list[dict]:
        """The server's tools that have a name, from at most `max_pages` pages of tools/list, with each description
        made text and each inputSchema an object."""
        tools, cursor = [], None
        for _ in range(max_pages):
            page = await self.rpc("tools/list", {"cursor": cursor} if cursor else {})
            found = page.get("tools") if isinstance(page.get("tools"), list) else []
            tools += [{**t, "description": str(t.get("description") or ""),
                       "inputSchema": t["inputSchema"] if isinstance(t.get("inputSchema"), dict) else {}}
                      for t in found if isinstance(t, dict) and isinstance(t.get("name"), str) and t["name"]]
            cursor = page.get("nextCursor")
            if not cursor:
                break
        return tools

    async def call_tool(self, name: str, arguments: dict) -> dict:
        return await self.rpc("tools/call", {"name": name, "arguments": arguments})


_REASONS = {200: "OK", 202: "Accepted", 400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed",
            413: "Content Too Large", 417: "Expectation Failed", 500: "Internal Server Error", 502: "Bad Gateway",
            503: "Service Unavailable"}
_TOKEN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
_CTL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")                 # control characters; a tab is allowed in a value
_TARGET = re.compile(r"/[!-~]*")                                 # a path (and query), printable ASCII
_CHUNK_LINE = re.compile(rb"([0-9A-Fa-f]{1,16})(;[\t\x20-\x7e]*)?\r\n")


class BadRequest(Exception):
    """A request the relay will not read: answered with `status`, and the connection closed."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _fields(lines: list[str]) -> list[tuple[str, str]]:
    """Header (or trailer) lines as (name, value) pairs. A folded line, a line without a name, or a control character
    other than a tab (a bare CR or LF included) raises BadRequest."""
    out = []
    for line in lines:
        name, sep, value = line.partition(":")
        if not sep or not _TOKEN.fullmatch(name) or _CTL.search(value):
            raise BadRequest(400, "a malformed or folded header line")
        out.append((name, value.strip(" \t")))
    return out


async def _read_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) \
        -> tuple[str, str, str, dict, bytes]:
    """Read one HTTP/1.x request, framed by Content-Length or by Transfer-Encoding: chunked (a request with both is
    refused). An HTTP/1.1 `Expect: 100-continue` is answered before the body is read."""
    try:
        head = await reader.readuntil(b"\r\n\r\n")
    except asyncio.LimitOverrunError:
        raise BadRequest(400, f"the request head is larger than {MAX_HEAD >> 10} KiB") from None
    line, *lines = head[:-4].decode("latin-1").split("\r\n")
    parts = line.split(" ")
    if len(parts) != 3 or not _TOKEN.fullmatch(parts[0]) or parts[2] not in ("HTTP/1.0", "HTTP/1.1") \
            or not _TARGET.fullmatch(parts[1]):
        raise BadRequest(400, "not an HTTP/1.x request line")
    method, target, version = parts
    fields = _fields(lines)
    lengths, codings, expect = ([v for k, v in fields if k.lower() == key]
                                for key in ("content-length", "transfer-encoding", "expect"))
    if lengths and codings:
        raise BadRequest(400, "both Content-Length and Transfer-Encoding")
    if codings and (len(codings) > 1 or codings[0].lower() != "chunked"):
        raise BadRequest(400, "Transfer-Encoding other than chunked")
    if lengths and (len(set(lengths)) > 1 or not (lengths[0].isascii() and lengths[0].isdigit())):
        raise BadRequest(400, "a malformed Content-Length")
    length = int(lengths[0]) if lengths else 0
    too_large = f"the body is larger than {MAX_BODY >> 20} MiB"
    if expect and version == "HTTP/1.1":
        if len(expect) > 1 or expect[0].lower() != "100-continue" or length > MAX_BODY:
            raise BadRequest(417, too_large if length > MAX_BODY else "only Expect: 100-continue")
        writer.write(b"HTTP/1.1 100 Continue\r\n\r\n")
        await writer.drain()
    if length > MAX_BODY:
        raise BadRequest(413, too_large)
    body = await _chunked(reader) if codings else await reader.readexactly(length)
    target = urlsplit(target)
    return method.upper(), target.path, target.query, dict(fields), body


async def _chunked(reader: asyncio.StreamReader) -> bytes:
    """Read a chunked body. Chunk extensions are ignored, and the trailers are read up to the empty line and dropped."""
    body = bytearray()
    while True:
        try:
            m = _CHUNK_LINE.fullmatch(await reader.readuntil(b"\r\n"))
        except asyncio.LimitOverrunError:
            m = None
        if m is None:
            raise BadRequest(400, "a malformed chunk-size line")
        size = int(m.group(1), 16)
        if size == 0:
            break
        if len(body) + size > MAX_BODY:
            raise BadRequest(413, f"the body is larger than {MAX_BODY >> 20} MiB")
        body += await reader.readexactly(size)
        if await reader.readexactly(2) != b"\r\n":
            raise BadRequest(400, "chunk data that does not end where its size says")
    trailers = []
    while True:
        try:
            line = await reader.readuntil(b"\r\n")
        except asyncio.LimitOverrunError:
            raise BadRequest(400, "a trailer line that is too long") from None
        if line == b"\r\n":
            break
        trailers.append(line[:-2].decode("latin-1"))
        if len(trailers) > 100:
            raise BadRequest(400, "too many trailer lines")
    _fields(trailers)
    return bytes(body)


@dataclass
class Finished:
    code: int                   # the exit code; -1 when it was stopped before it exited
    stderr: str                 # the last lines of stderr
    stopped: bool = False       # stopped before the deadline (stop_before_sec)


async def lines(stream: asyncio.StreamReader, max_line: int = MAX_LINE):
    """The stream's lines, without their line breaks; a line longer than `max_line` is skipped. Each chunk is split
    by offset and trimmed once, so a chunk of many short lines costs time linear in its size."""
    buf, skipping = bytearray(), False
    while chunk := await stream.read(1 << 20):
        buf += chunk
        start = 0
        while (end := buf.find(b"\n", start)) >= 0:
            if not skipping and end - start <= max_line:
                yield bytes(buf[start:end])
            skipping, start = False, end + 1
        del buf[:start]
        if len(buf) > max_line:
            buf.clear()
            skipping = True
    if buf and not skipping:
        yield bytes(buf)


def positive_int(value, default: int, cap: int | None = None) -> int:
    """A positive whole number from a tool argument (a number or numeric text, rounded up), at most `cap`. Zero, a
    negative number, None or anything else gives `default`, also capped: models pass 0 to mean "no limit", and that
    must not become a 1-second timeout."""
    number = 0.0
    if isinstance(value, int) and not isinstance(value, bool):
        number = value                  # an int stays an int: float() overflows past about 1e308
    elif not isinstance(value, bool):
        with contextlib.suppress(TypeError, ValueError, OverflowError):
            number = float(value)
    limit = math.ceil(number) if 0 < number < math.inf else default
    return limit if cap is None else min(limit, cap)


def time_share(left: float | None, reserve: float, fraction: float = 0.25) -> float | None:
    """How much of `left` seconds to spend while keeping `reserve` back for the end. With little time left the
    reserve shrinks to `fraction` of it, so a short task still gets most of its time. None when there is no
    deadline."""
    if left is None:
        return None
    left = max(left, 0.0)
    return left - min(reserve, left * fraction)


async def run_process(argv: list[str], session: Session, *, env: dict | None = None, cwd: str | None = None,
                      stdin: bytes | None = None, on_line=None, stop_before_sec: float = 60,
                      log_prefix: str = "") -> Finished:
    """Run an agent subprocess until it exits, the task is cancelled, or `stop_before_sec` before the deadline (less on
    a short task, see time_share), then stop what is left of its process group (_stop). `stdin` is written to its
    standard input. `on_line(line)`, a coroutine, gets each line of stdout as it arrives; without it stdout is
    discarded. Lines of stderr go to the task log."""
    pipe, devnull = asyncio.subprocess.PIPE, asyncio.subprocess.DEVNULL
    proc = await asyncio.create_subprocess_exec(*argv, env=env, cwd=cwd, start_new_session=True,
                                                stdin=devnull if stdin is None else pipe,
                                                stdout=devnull if on_line is None else pipe, stderr=pipe)
    err: list[str] = []

    async def feed():
        with contextlib.suppress(ConnectionError):
            proc.stdin.write(stdin)
            await proc.stdin.drain()
            proc.stdin.close()

    async def pump_out():
        async for line in lines(proc.stdout):
            with contextlib.suppress(Exception):
                await on_line(line)

    async def pump_err():
        async for line in lines(proc.stderr):
            text = line.decode("utf-8", "replace").rstrip()
            err.append(text)
            del err[:-50]
            print(f"{log_prefix}{text}", file=sys.stderr, flush=True)
            if text:
                await session.log(f"{log_prefix}{text}"[:2000])

    pumps = asyncio.gather(pump_err(), *([pump_out()] if on_line else []), *([feed()] if stdin is not None else []))
    left = session.time_left()
    run_for = time_share(left, stop_before_sec)
    stopped = False
    try:
        await asyncio.wait_for(asyncio.shield(proc.wait()), run_for)
    except asyncio.TimeoutError:
        stopped = True
        await session.log(f"{log_prefix}stopped {max(left, 0) - run_for:.0f} s before the time limit")
    finally:
        await asyncio.shield(_stop(proc))
        with contextlib.suppress(Exception):
            await asyncio.wait_for(pumps, 10)
    code = proc.returncode if proc.returncode is not None and not stopped else -1
    return Finished(code, "\n".join(err), stopped)


async def _stop(proc) -> None:
    """SIGTERM to the process group, then SIGKILL to whatever is left of it once the leader is done or 5 s have
    passed, so a child that outlives the leader or ignores SIGTERM is stopped too."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGTERM)
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(proc.wait(), 5)
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)
    await proc.wait()
