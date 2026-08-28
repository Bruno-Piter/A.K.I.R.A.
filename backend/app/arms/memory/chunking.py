"""Heading/paragraph-aware markdown chunking with overlapping windows."""

from __future__ import annotations

import re

_HEADING_SPLIT = re.compile(r"(?m)(?=^#{1,6}\s+)")
_BLANK = re.compile(r"\n\s*\n")


def split_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[str]:
    """Split text into overlapping chunks of about ``chunk_size`` characters.

    Prefers markdown headings and paragraphs as packing units, then falls
    back to character windows. Never returns empty chunks.
    """
    if not text or not str(text).strip():
        return []
    chunk_size = max(int(chunk_size), 1)
    chunk_overlap = max(int(chunk_overlap), 0)
    if chunk_overlap >= chunk_size:
        chunk_overlap = max(chunk_size // 4, 0)

    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    units = _markdown_units(normalized)
    packed = _pack_units(units, chunk_size, chunk_overlap)
    overlapped = _apply_overlap(packed, chunk_overlap)
    return [chunk for chunk in overlapped if chunk.strip()]


def _markdown_units(text: str) -> list[str]:
    sections = _HEADING_SPLIT.split(text) if text else []
    if not sections:
        sections = [text]
    units: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        paragraphs = [p.strip() for p in _BLANK.split(section) if p.strip()]
        units.extend(paragraphs if paragraphs else [section])
    return units or ([text.strip()] if text.strip() else [])


def _pack_units(units: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    packed: list[str] = []
    buf: list[str] = []
    size = 0
    for unit in units:
        if len(unit) > chunk_size:
            if buf:
                packed.append("\n\n".join(buf))
                buf, size = [], 0
            packed.extend(_char_windows(unit, chunk_size, chunk_overlap))
            continue
        gap = 2 if buf else 0
        if buf and size + gap + len(unit) > chunk_size:
            packed.append("\n\n".join(buf))
            buf, size = [unit], len(unit)
        else:
            buf.append(unit)
            size += gap + len(unit)
    if buf:
        packed.append("\n\n".join(buf))
    return packed


def _char_windows(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    step = max(1, chunk_size - chunk_overlap)
    windows: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            # Prefer breaking on whitespace.
            probe = text.rfind(" ", start + max(chunk_size // 2, 1), end)
            if probe > start:
                end = probe
        piece = text[start:end].strip()
        if piece:
            windows.append(piece)
        if end >= length:
            break
        start = max(end - chunk_overlap, start + 1)
    return windows


def _apply_overlap(chunks: list[str], chunk_overlap: int) -> list[str]:
    if chunk_overlap <= 0 or len(chunks) <= 1:
        return chunks
    result: list[str] = [chunks[0]]
    for chunk in chunks[1:]:
        prev = result[-1]
        prefix = prev[-chunk_overlap:] if len(prev) > chunk_overlap else prev
        prefix = prefix.lstrip()
        head = chunk[: max(chunk_overlap * 2, 32)]
        if prefix and prefix not in head:
            result.append((prefix + "\n" + chunk).strip())
        else:
            result.append(chunk)
    return result
