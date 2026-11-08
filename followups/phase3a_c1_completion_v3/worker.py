"""Owned SDK worker. No journal, audit paths or persistence capability is passed in."""
from __future__ import annotations

import asyncio
import base64
import json
import os
import struct
import threading
import time
from multiprocessing.connection import Connection
from typing import Any

MAX_FRAME = 16_777_216


def fixture_http_frame_limit(request: dict) -> int:
    """Only fixture HTTP RPCs echo the whole SDK request as base64 to the parent."""
    size = len(json.dumps(request, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode())
    if size > 128_000_000:
        raise ValueError("fixture request exceeds the provider wire ceiling")
    # Match the initial-frame SDK/envelope allowance; base64 requires four
    # bytes for each three source bytes, plus the small HTTP RPC metadata.
    return max(MAX_FRAME, 4 * ((size + 1_048_576 + 2) // 3) + 65_536)


def main(connection: Connection, fixture_behavior: dict | None = None,
         request_frame_limit: int = MAX_FRAME) -> None:
    if type(request_frame_limit) is not int or not MAX_FRAME <= request_frame_limit <= 130_000_000:
        connection.close()
        return
    behavior = fixture_behavior or {}
    if behavior.get("ipc") == "never_read":
        while True:
            time.sleep(1)
    if behavior.get("ipc") == "partial_frame":
        os.write(connection.fileno(), struct.pack("!i", 1_000_000) + b"partial")
        while True:
            time.sleep(1)
    try:
        init = json.loads(connection.recv_bytes(request_frame_limit).decode("utf-8"))
        asyncio.run(_operation(connection, init, behavior))
    except BaseException:
        return  # Parent treats absent complete receipt as unknown; no raw exception crosses IPC.
    finally:
        connection.close()


async def _operation(connection: Connection, init: dict, behavior: dict) -> None:
    import anthropic
    import httpx
    import httpx2
    import openai

    fixture = init["fixture"]
    fixture_frame = fixture_http_frame_limit(init["request"]) if fixture else MAX_FRAME
    if behavior and not fixture:
        raise ValueError("fixture behavior in live worker")
    if fixture and set(init["keys"].values()) != {"fixture-not-a-secret"}:
        raise ValueError("fixture keys differ")
    loop = asyncio.get_running_loop()
    go = asyncio.Event()
    futures: dict[int, asyncio.Future] = {}
    send_lock = threading.Lock()
    task: asyncio.Task | None = None

    def send(value: dict) -> None:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
        limit = fixture_frame if fixture and value.get("type") == "http" else MAX_FRAME
        if len(encoded) > limit:
            raise ValueError("oversized worker frame")
        with send_lock:
            connection.send_bytes(encoded)

    def deliver(value: dict) -> None:
        if value.get("type") == "go":
            go.set()
        elif value.get("type") == "cancel":
            if task is not None:
                task.cancel()
        elif value.get("type") == "http_result":
            ident = value.get("id")
            future = futures.get(ident) if isinstance(ident, int) else None
            if future is not None and not future.done():
                future.set_result(value)

    def reader() -> None:
        try:
            while True:
                value = json.loads(connection.recv_bytes(MAX_FRAME).decode("utf-8"))
                loop.call_soon_threadsafe(deliver, value)
        except BaseException:
            if not loop.is_closed():
                loop.call_soon_threadsafe(deliver, {"type": "cancel"})

    threading.Thread(target=reader, daemon=True).start()

    async def pause(seconds: float) -> None:
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            if not behavior.get("ignore_cancel"):
                raise
            await asyncio.sleep(behavior.get("cancel_delay", 0))

    async def mocked(request: Any, provider: str, module: Any) -> Any:
        if behavior.get("block_loop"):
            while True:
                time.sleep(1)
        await pause(behavior.get("response_delay", 0))
        failure = behavior.get("failure")
        if failure:
            kinds = {"connect": module.ConnectTimeout, "read": module.ReadTimeout,
                     "write": module.WriteTimeout, "pool": module.PoolTimeout}
            raise kinds[failure]("synthetic timeout", request=request)
        ident = len(futures) + 1
        future = loop.create_future()
        futures[ident] = future
        send({"type": "http", "id": ident, "provider": provider, "method": request.method,
              "url": str(request.url), "body": base64.b64encode(request.content).decode("ascii"),
              "timeouts": request.extensions.get("timeout")})
        value = await future
        body = base64.b64decode(value["body"])
        if behavior.get("body_delay"):
            class DelayedBody(module.AsyncByteStream):
                async def __aiter__(self):
                    await pause(behavior["body_delay"])
                    yield body
            return module.Response(value["status"], headers=value["headers"], stream=DelayedBody(), request=request)
        return module.Response(value["status"], headers=value["headers"], content=body, request=request)

    async def call() -> None:
        clients: list[Any] = []
        response: Any
        try:
            await go.wait()
            io = init["io"]
            if init["role"] == "group":
                group_timeout = httpx.Timeout(**io)
                group_extra: dict[str, Any] = {"transport": httpx.MockTransport(lambda r: mocked(r, "openai", httpx))} if fixture else {}
                group_http = openai.DefaultAsyncHttpxClient(trust_env=False, follow_redirects=False, timeout=group_timeout, **group_extra)
                group_client = openai.AsyncOpenAI(api_key=init["keys"]["openai_api_key"], base_url="https://api.openai.com/v1",
                    max_retries=0, timeout=group_timeout, http_client=group_http)
                clients.append(group_client)
                send({"type": "invoked"})
                response = await group_client.chat.completions.create(**init["request"])
            else:
                message_timeout = httpx2.Timeout(**io)
                message_extra: dict[str, Any] = {"transport": httpx2.MockTransport(lambda r: mocked(r, "anthropic", httpx2))} if fixture else {}
                message_http = anthropic.DefaultAsyncHttpxClient(trust_env=False, follow_redirects=False, timeout=message_timeout, **message_extra)
                message_client = anthropic.AsyncAnthropic(api_key=init["keys"]["anthropic_api_key"], base_url="https://api.anthropic.com",
                    max_retries=0, timeout=message_timeout, http_client=message_http)
                clients.append(message_client)
                send({"type": "invoked"})
                response = await message_client.messages.create(**init["request"])
            send({"type": "receipt", "raw": response.model_dump(mode="json", exclude_none=True),
                  "request_id": getattr(response, "_request_id", None)})
        except BaseException as exc:
            chain = []
            item: BaseException | None = exc
            for _ in range(5):
                if item is None:
                    break
                chain.append(type(item).__name__)
                item = item.__cause__
            subtype = next((n for n in ("ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout") if n in chain), None)
            category = ("timeout" if isinstance(exc, (anthropic.APITimeoutError, openai.APITimeoutError, asyncio.CancelledError))
                        else "connection" if isinstance(exc, (anthropic.APIConnectionError, openai.APIConnectionError))
                        else "provider_status" if isinstance(exc, (anthropic.APIStatusError, openai.APIStatusError)) else "transport_error")
            status = getattr(exc, "status_code", None) if category == "provider_status" else None
            send({"type": "failure", "category": category, "status_code": status,
                  "request_id": getattr(exc, "request_id", None), "timeout_subtype": subtype})
        finally:
            if behavior.get("cleanup_delay"):
                await asyncio.sleep(behavior["cleanup_delay"])
            for client in clients:
                await client.close()
            for key in init["keys"]:
                init["keys"][key] = ""
            send({"type": "done"})

    task = asyncio.create_task(call())
    send({"type": "ready"})
    await task
