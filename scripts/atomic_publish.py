#!/usr/bin/env python3
"""Fail-closed atomic file publication helpers.

Writers stage content in the target directory, fsync and validate the staged
bytes, then replace the canonical file atomically.  The existing canonical
file is untouched unless the complete candidate has passed validation.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable


Validator = Callable[[str], None]


def atomic_write_text(path: Path, text: str, *, validator: Validator | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(text, str) or not text:
        raise ValueError(f"refusing empty publication for {path}")

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

        staged = temp_path.read_text(encoding="utf-8")
        if staged != text:
            raise OSError(f"staged publication verification mismatch for {path}")
        if validator is not None:
            validator(staged)

        os.replace(temp_path, path)
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
        except OSError:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def _validate_json_object(raw: str) -> None:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("published JSON root must be an object")


def atomic_write_json(path: Path, value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"refusing non-object JSON publication for {path}")
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(Path(path), payload, validator=_validate_json_object)
