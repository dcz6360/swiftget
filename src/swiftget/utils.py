"""Utility functions for SwiftGet.

Provides helpers for formatting, URL parsing, filename extraction,
and chunk-range calculation used by the downloader.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse, unquote


def format_size(num_bytes: float) -> str:
    """Format a byte count into a human-readable string.

    Args:
        num_bytes: Number of bytes (can be fractional).

    Returns:
        Human-readable size string, e.g. ``"1.50 MB"``.

    Examples:
        >>> format_size(0)
        '0.00 B'
        >>> format_size(1536)
        '1.50 KB'
        >>> format_size(1048576)
        '1.00 MB'
    """
    if num_bytes < 0:
        return "0.00 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} {units[-1]}"


def format_speed(bytes_per_sec: float) -> str:
    """Format a download speed into a human-readable string.

    Args:
        bytes_per_sec: Speed in bytes per second.

    Returns:
        Human-readable speed string, e.g. ``"1.50 MB/s"``.
    """
    if bytes_per_sec <= 0:
        return "0.00 B/s"
    return f"{format_size(bytes_per_sec)}/s"


def format_time(seconds: float) -> str:
    """Format seconds into a ``HH:MM:SS`` string.

    Args:
        seconds: Number of seconds.

    Returns:
        Formatted time string.
    """
    if seconds < 0 or seconds == float("inf"):
        return "--:--:--"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_url(url: str) -> bool:
    """Validate that a string is a well-formed HTTP(S) URL.

    Args:
        url: The URL string to validate.

    Returns:
        ``True`` if the URL is valid, ``False`` otherwise.

    Examples:
        >>> parse_url("https://example.com/file.zip")
        True
        >>> parse_url("not a url")
        False
        >>> parse_url("ftp://example.com/file")
        False
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except (ValueError, AttributeError):
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def get_filename(url: str, headers: dict | None = None) -> str:
    """Extract a filename from a URL or response headers.

    Tries the ``Content-Disposition`` header first, then falls back to
    the last path segment of the URL.  Returns ``"download.bin"`` if
    nothing usable is found.

    Args:
        url: The download URL.
        headers: Optional response headers dict.

    Returns:
        A filename string.
    """
    # Try Content-Disposition header first
    if headers:
        cd = headers.get("Content-Disposition") or headers.get(
            "content-disposition"
        )
        if cd:
            match = re.search(r'filename\*?=["\']?(?:UTF-\d\'\')?([^"\';\s]+)', cd)
            if match:
                return unquote(match.group(1))

    # Fall back to URL path
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if path:
        name = os.path.basename(path.rstrip("/"))
        if name:
            return name

    return "download.bin"


def calculate_chunks(total_size: int, num_chunks: int) -> list[tuple[int, int]]:
    """Split a byte range into ``num_chunks`` contiguous segments.

    Args:
        total_size: Total number of bytes.
        num_chunks: Number of chunks to create.

    Returns:
        List of ``(start, end)`` byte offsets (inclusive).

    Raises:
        ValueError: If ``total_size`` or ``num_chunks`` is not positive.

    Examples:
        >>> calculate_chunks(100, 4)
        [(0, 24), (25, 49), (50, 74), (75, 99)]
        >>> calculate_chunks(10, 3)
        [(0, 2), (3, 5), (6, 9)]
    """
    if total_size <= 0:
        raise ValueError("total_size must be positive")
    if num_chunks <= 0:
        raise ValueError("num_chunks must be positive")

    num_chunks = min(num_chunks, total_size)
    chunk_size = total_size // num_chunks
    chunks: list[tuple[int, int]] = []
    start = 0
    for i in range(num_chunks):
        if i == num_chunks - 1:
            # Last chunk gets the remainder
            end = total_size - 1
        else:
            end = start + chunk_size - 1
        chunks.append((start, end))
        start = end + 1
    return chunks


def sanitize_filename(name: str) -> str:
    """Remove characters that are unsafe in filenames.

    Args:
        name: The original filename.

    Returns:
        A sanitized filename safe for the local filesystem.
    """
    # Remove or replace unsafe characters
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)
    # Strip leading/trailing dots, spaces, and underscores
    name = name.strip(". _")
    return name if name else "download.bin"
