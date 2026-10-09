#!/usr/bin/env python3
"""Load only the reviewed Google model; never generate or authorize news.

The workflow owns the daemon on a separate loopback port. Empty-prompt load
and running-model verification consume the child's existing fixed deadline,
not another generation attempt or a renewed lease. No repository credentials,
model response text, source material or exception bodies are logged here.
"""
import argparse
import json
import math
import time
import urllib.request

BASE = "http://127.0.0.1:11435"
MODEL = "gemma3:4b-it-qat"
DIGEST = "b0313423c9448adfab711aacbc9d0b885a390eb31f1145d7f8495d1e6f84f257"
MAX_BYTES = 262144


def timeout_remaining(deadline, clock):
    if not math.isfinite(deadline):
        raise ValueError("invalid-runtime-deadline")
    remaining = deadline - clock()
    if remaining <= 0:
        raise ValueError("runtime-deadline-expired")
    return min(60.0, remaining)


def request_json(path, deadline, clock, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(BASE + path, data=data,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_remaining(deadline, clock)) as response:
        raw = response.read(MAX_BYTES + 1)
    timeout_remaining(deadline, clock)
    if len(raw) > MAX_BYTES:
        raise ValueError("runtime-response-too-large")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("runtime-response-not-object")
    return value


def prepare(deadline, *, clock=time.time, request=request_json):
    # One fixed 60-second infrastructure budget, itself within the child's
    # original shared deadline. No request retries and no new inference calls.
    timeout_remaining(deadline, clock)
    budget = min(deadline, clock() + 60.0)
    timeout_remaining(budget, clock)
    loaded = request("/api/generate", budget, clock, {
        "model": MODEL, "prompt": "", "stream": False,
        "keep_alive": "10m", "options": {"num_ctx": 32768},
    })
    if (loaded.get("model") != MODEL or loaded.get("done") is not True
        or loaded.get("response") != ""
        or type(loaded.get("eval_count", 0)) is not int
        or loaded.get("eval_count", 0) != 0):
        raise ValueError("runtime-load-not-empty-complete")
    running = request("/api/ps", budget, clock)
    models = running.get("models")
    if not isinstance(models, list) or len(models) != 1 or not isinstance(models[0], dict):
        raise ValueError("runtime-model-set-not-reviewed")
    row = models[0]
    if row.get("name") != MODEL or row.get("digest") != DIGEST:
        raise ValueError("runtime-model-identity-not-reviewed")
    if "context_length" in row and (type(row["context_length"]) is not int or row["context_length"] != 32768):
        raise ValueError("runtime-context-not-reviewed")
    # Runtime telemetry is never editorial success or publication permission.
    metadata = {"model": MODEL, "ownedPort": 11435, "emptyPromptLoaded": True}
    for field in ("size", "size_vram", "context_length"):
        value = row.get(field)
        if type(value) is int and 0 <= value <= 10**12:
            metadata[field] = value
    timeout_remaining(budget, clock)
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deadline-unix", type=float, required=True)
    args = parser.parse_args()
    try:
        metadata = prepare(args.deadline_unix)
    except Exception as exc:
        print("LOCAL_MODEL_OWNED_RUNTIME_FAILED type=" + type(exc).__name__, flush=True)
        return 1
    print("LOCAL_MODEL_OWNED_RUNTIME " + json.dumps(metadata), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
