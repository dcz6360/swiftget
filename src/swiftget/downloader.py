"""Core download engine for SwiftGet.

Implements multi-connection HTTP downloads with resume support,
progress reporting, and optional speed limiting.
"""

from __future__ import annotations

import os
import sys
import time
import threading
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .utils import (
    format_size,
    format_speed,
    format_time,
    get_filename,
    calculate_chunks,
    sanitize_filename,
)


@dataclass
class DownloadResult:
    """Result of a download operation."""

    url: str
    filepath: str
    total_size: int
    elapsed: float
    success: bool
    error: str | None = None

    @property
    def average_speed(self) -> float:
        """Average download speed in bytes per second."""
        if self.elapsed <= 0:
            return 0.0
        return self.total_size / self.elapsed


@dataclass
class ChunkProgress:
    """Progress tracker for a single download chunk."""

    chunk_id: int
    start: int
    end: int
    downloaded: int = 0
    done: bool = False
    error: str | None = None

    @property
    def size(self) -> int:
        """Total size of this chunk in bytes."""
        return self.end - self.start + 1


class Downloader:
    """Multi-connection HTTP downloader with resume support.

    Args:
        url: The URL to download.
        output: Output file path or directory.  If ``None``, the filename
            is derived from the URL.
        connections: Number of parallel connections (default 4).
        resume: Whether to attempt resuming a partial download (default True).
        speed_limit: Maximum speed in bytes/sec, or ``None`` for unlimited.
        chunk_size: Buffer size for reading data (default 64 KB).
        timeout: Request timeout in seconds (default 30).
    """

    def __init__(
        self,
        url: str,
        output: str | None = None,
        connections: int = 4,
        resume: bool = True,
        speed_limit: float | None = None,
        chunk_size: int = 65536,
        timeout: int = 30,
    ) -> None:
        self.url = url
        self.output = output
        self.connections = max(1, connections)
        self.resume = resume
        self.speed_limit = speed_limit
        self.chunk_size = chunk_size
        self.timeout = timeout
        self._stop = threading.Event()
        self._progress_callbacks: list = []

    def add_progress_callback(self, callback) -> None:
        """Register a callback called periodically with progress info.

        The callback receives ``(downloaded_bytes, total_bytes, speed)``.
        """
        self._progress_callbacks.append(callback)

    def _notify_progress(
        self, downloaded: int, total: int, speed: float
    ) -> None:
        for cb in self._progress_callbacks:
            try:
                cb(downloaded, total, speed)
            except Exception:
                pass

    def _head(self) -> requests.Response:
        """Send a HEAD request to get metadata."""
        resp = requests.head(
            self.url, allow_redirects=True, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp

    def get_remote_info(self) -> dict:
        """Fetch remote file metadata via HEAD request.

        Returns:
            Dict with keys ``size``, ``filename``, ``accept_ranges``,
            and ``status_code``.
        """
        resp = self._head()
        size = int(resp.headers.get("Content-Length", 0))
        accept_ranges = resp.headers.get("Accept-Ranges", "").lower()
        return {
            "size": size,
            "filename": get_filename(self.url, dict(resp.headers)),
            "accept_ranges": accept_ranges == "bytes",
            "status_code": resp.status_code,
        }

    def _resolve_output(self, info: dict) -> str:
        """Determine the final output file path."""
        if self.output:
            if os.path.isdir(self.output):
                name = sanitize_filename(info["filename"])
                return os.path.join(self.output, name)
            return self.output
        return sanitize_filename(info["filename"])

    def _download_chunk(
        self,
        chunk: ChunkProgress,
        filepath: str,
    ) -> ChunkProgress:
        """Download a single byte-range chunk and write to ``filepath``.

        Uses a temporary ``.partN`` file so that interrupted downloads
        can be resumed.
        """
        part_file = f"{filepath}.part{chunk.chunk_id}"

        # Determine resume offset within this chunk
        resume_offset = 0
        if self.resume and os.path.exists(part_file):
            resume_offset = os.path.getsize(part_file)
            if resume_offset >= chunk.size:
                chunk.downloaded = chunk.size
                chunk.done = True
                return chunk

        actual_start = chunk.start + resume_offset
        headers = {"Range": f"bytes={actual_start}-{chunk.end}"}

        mode = "ab" if resume_offset > 0 else "wb"
        try:
            resp = requests.get(
                self.url,
                headers=headers,
                stream=True,
                timeout=self.timeout,
            )
            resp.raise_for_status()

            with open(part_file, mode) as f:
                for data in resp.iter_content(self.chunk_size):
                    if self._stop.is_set():
                        chunk.error = "Cancelled"
                        return chunk
                    f.write(data)
                    chunk.downloaded += len(data)

                    # Speed limiting
                    if self.speed_limit and self.speed_limit > 0:
                        time.sleep(len(data) / self.speed_limit)

            chunk.done = True
        except requests.RequestException as exc:
            chunk.error = str(exc)
        except OSError as exc:
            chunk.error = str(exc)

        return chunk

    def _merge_chunks(
        self, chunks: list[ChunkProgress], filepath: str
    ) -> None:
        """Merge all ``.partN`` files into the final output file."""
        with open(filepath, "wb") as out:
            for chunk in sorted(chunks, key=lambda c: c.chunk_id):
                part_file = f"{filepath}.part{chunk.chunk_id}"
                if not os.path.exists(part_file):
                    raise FileNotFoundError(
                        f"Missing chunk file: {part_file}"
                    )
                with open(part_file, "rb") as part:
                    while True:
                        data = part.read(self.chunk_size)
                        if not data:
                            break
                        out.write(data)

    def _cleanup_parts(self, filepath: str, num_chunks: int) -> None:
        """Remove temporary ``.partN`` files after a successful merge."""
        for i in range(num_chunks):
            part_file = f"{filepath}.part{i}"
            try:
                if os.path.exists(part_file):
                    os.remove(part_file)
            except OSError:
                pass

    def _has_partial(self, filepath: str, num_chunks: int) -> bool:
        """Check whether any ``.partN`` file exists for resuming."""
        return any(
            os.path.exists(f"{filepath}.part{i}") for i in range(num_chunks)
        )

    def download(self) -> DownloadResult:
        """Execute the download.

        Returns:
            A :class:`DownloadResult` describing the outcome.
        """
        start_time = time.time()

        try:
            info = self.get_remote_info()
        except requests.RequestException as exc:
            return DownloadResult(
                url=self.url,
                filepath="",
                total_size=0,
                elapsed=0,
                success=False,
                error=f"Failed to get file info: {exc}",
            )

        total_size = info["size"]
        filepath = self._resolve_output(info)

        # If server doesn't report size or doesn't support ranges,
        # fall back to single-connection download
        use_multi = (
            total_size > 0
            and info["accept_ranges"]
            and self.connections > 1
        )

        if not use_multi:
            num_chunks = 1
            if total_size > 0:
                ranges = calculate_chunks(total_size, 1)
            else:
                ranges = [(0, 0)]
        else:
            num_chunks = min(self.connections, total_size)
            ranges = calculate_chunks(total_size, num_chunks)

        # Build chunk progress objects
        chunks = [
            ChunkProgress(
                chunk_id=i,
                start=ranges[i][0],
                end=ranges[i][1],
            )
            for i in range(num_chunks)
        ]

        # Track total downloaded for progress reporting
        progress_state = {"last_report": time.time(), "last_bytes": 0}

        def make_callback(chunk: ChunkProgress):
            def _cb():
                downloaded = sum(c.downloaded for c in chunks)
                now = time.time()
                if now - progress_state["last_report"] >= 0.5:
                    dt = now - progress_state["last_report"]
                    speed = (
                        (downloaded - progress_state["last_bytes"]) / dt
                        if dt > 0
                        else 0
                    )
                    self._notify_progress(downloaded, total_size, speed)
                    progress_state["last_report"] = now
                    progress_state["last_bytes"] = downloaded
            return _cb

        # Download chunks in parallel
        if num_chunks == 1 and not use_multi:
            # Simple single-stream download
            single_chunk = chunks[0]
            if total_size == 0:
                # Unknown size - download everything
                try:
                    resp = requests.get(
                        self.url, stream=True, timeout=self.timeout
                    )
                    resp.raise_for_status()
                    with open(filepath, "wb") as f:
                        for data in resp.iter_content(self.chunk_size):
                            if self._stop.is_set():
                                break
                            f.write(data)
                            single_chunk.downloaded += len(data)
                    single_chunk.done = True
                    total_size = single_chunk.downloaded
                except (requests.RequestException, OSError) as exc:
                    single_chunk.error = str(exc)
            else:
                self._download_chunk(single_chunk, filepath)
                if single_chunk.done:
                    # Rename part file to final
                    part_file = f"{filepath}.part0"
                    if os.path.exists(part_file):
                        os.rename(part_file, filepath)
        else:
            with ThreadPoolExecutor(max_workers=num_chunks) as pool:
                futures = {}
                for chunk in chunks:
                    cb = make_callback(chunk)
                    future = pool.submit(self._download_chunk, chunk, filepath)
                    future.add_done_callback(lambda f, c=cb: c())
                    futures[future] = chunk

                # Periodically report progress while waiting
                while futures:
                    done_set = set()
                    for future in as_completed(futures, timeout=None):
                        done_set.add(future)
                    for future in done_set:
                        del futures[future]
                    break  # as_completed already handles the wait

            # Check for errors
            errors = [c for c in chunks if c.error]
            if errors:
                # Still try to merge what we have if all are done
                if all(c.done or c.error for c in chunks):
                    pass

            # Merge chunks
            all_done = all(c.done for c in chunks)
            if all_done:
                self._merge_chunks(chunks, filepath)
                self._cleanup_parts(filepath, num_chunks)
            else:
                err_msgs = "; ".join(
                    f"chunk {c.chunk_id}: {c.error}" for c in errors
                )
                elapsed = time.time() - start_time
                return DownloadResult(
                    url=self.url,
                    filepath=filepath,
                    total_size=sum(c.downloaded for c in chunks),
                    elapsed=elapsed,
                    success=False,
                    error=f"Download incomplete: {err_msgs}",
                )

        elapsed = time.time() - start_time
        self._notify_progress(total_size, total_size, 0)

        return DownloadResult(
            url=self.url,
            filepath=filepath,
            total_size=total_size,
            elapsed=elapsed,
            success=True,
        )

    def cancel(self) -> None:
        """Signal all download threads to stop."""
        self._stop.set()


def download_url(
    url: str,
    output: str | None = None,
    connections: int = 4,
    resume: bool = True,
    speed_limit: float | None = None,
) -> DownloadResult:
    """Convenience function to download a single URL.

    Args:
        url: URL to download.
        output: Output path (file or directory).
        connections: Number of parallel connections.
        resume: Whether to resume partial downloads.
        speed_limit: Max speed in bytes/sec.

    Returns:
        A :class:`DownloadResult`.
    """
    dl = Downloader(
        url=url,
        output=output,
        connections=connections,
        resume=resume,
        speed_limit=speed_limit,
    )
    return dl.download()
