from __future__ import annotations

import locale
import os
from pathlib import Path

from .output_decode import decode_process_bytes


def is_python_command(command: list[str]) -> bool:
    if not command:
        return False
    executable = Path(str(command[0])).name.lower()
    return executable.startswith("python")


def _decode_strict(data: bytes, encoding: str) -> str | None:
    try:
        return data.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        return None


def _looks_utf16(data: bytes) -> str | None:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    sample = data[:4096]
    if len(sample) < 8:
        return None
    even = sample[0::2]
    odd = sample[1::2]
    if not even or not odd:
        return None
    even_nulls = even.count(0) / len(even)
    odd_nulls = odd.count(0) / len(odd)
    if odd_nulls > 0.28 and even_nulls < 0.08:
        return "utf-16-le"
    if even_nulls > 0.28 and odd_nulls < 0.08:
        return "utf-16-be"
    return None


def _candidate_encodings() -> list[str]:
    encodings = ["cp866"]
    preferred = locale.getpreferredencoding(False)
    if preferred:
        encodings.append(preferred)
    if os.name == "nt":
        encodings.append("mbcs")
    encodings.append("cp1251")

    unique: list[str] = []
    seen: set[str] = set()
    for encoding in encodings:
        key = encoding.lower()
        if key not in seen:
            seen.add(key)
            unique.append(encoding)
    return unique


def _score_decoded_text(text: str) -> int:
    replacement = text.count("\ufffd")
    controls = sum(1 for char in text if ord(char) < 32 and char not in "\r\n\t")
    cyrillic = sum(1 for char in text if "\u0400" <= char <= "\u052f")
    cjk_mojibake = sum(1 for char in text if "\u3400" <= char <= "\u9fff")
    box_drawing = sum(1 for char in text if "\u2500" <= char <= "\u257f")
    suspicious_cyrillic = sum(1 for char in text if char in "ЃѓЄєЅѕІіЇїЈјЉљЊњЋћЌќЎўЏџ")
    common_russian = sum(1 for char in text.lower() if char in "аоеинтсрвлкмдпуяызьбгчйхжюшцщэфъё")
    return (
        common_russian * 3
        + cyrillic
        - replacement * 200
        - controls * 20
        - cjk_mojibake * 15
        - box_drawing * 8
        - suspicious_cyrillic * 6
    )


def decode_subprocess_output(data: bytes) -> str:
    return decode_process_bytes(data)


SPINNER_FRAME_CHARS = set("-\\|/ \t")


def _is_spinner_only_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and all(char in SPINNER_FRAME_CHARS for char in line)


def decoded_process_lines(raw_line: bytes | str) -> list[str]:
    text = str(raw_line) if isinstance(raw_line, str) else decode_process_bytes(raw_line)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for part in text.split("\n"):
        line = part.rstrip()
        if not line or _is_spinner_only_line(line):
            continue
        lines.append(line)
    return lines
