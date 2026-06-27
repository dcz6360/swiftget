"""Command-line interface for SwiftGet.

Usage examples::

    swiftget https://example.com/file.zip
    swiftget -o myfile.zip https://example.com/file.zip
    swiftget -c 8 https://example.com/largefile.iso
    swiftget -f urls.txt -o ./downloads/
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from . import __version__
from .downloader import Downloader, DownloadResult
from .utils import format_size, format_speed, format_time, parse_url


def _print_progress(downloaded: int, total: int, speed: float) -> None:
    """Print a simple progress bar to stderr."""
    if total > 0:
        pct = downloaded / total * 100
        bar_len = 30
        filled = int(bar_len * downloaded / total)
        bar = "=" * filled + "-" * (bar_len - filled)
        sys.stderr.write(
            f"\r  [{bar}] {pct:5.1f}%  "
            f"{format_size(downloaded)}/{format_size(total)}  "
            f"{format_speed(speed)}"
        )
        sys.stderr.flush()
    else:
        sys.stderr.write(f"\r  {format_size(downloaded)}  {format_speed(speed)}")
        sys.stderr.flush()


def download_single(
    url: str,
    output: str | None,
    connections: int,
    resume: bool,
    speed_limit: float | None,
) -> int:
    """Download a single URL.  Returns exit code."""
    if not parse_url(url):
        print(f"Error: invalid URL: {url}", file=sys.stderr)
        return 1

    print(f"URL:      {url}")
    if output:
        print(f"Output:   {output}")
    print(f"Threads:  {connections}")
    print(f"Resume:   {'on' if resume else 'off'}")
    if speed_limit:
        print(f"Limit:    {format_speed(speed_limit)}")
    print()

    dl = Downloader(
        url=url,
        output=output,
        connections=connections,
        resume=resume,
        speed_limit=speed_limit,
    )
    dl.add_progress_callback(_print_progress)

    result = dl.download()

    sys.stderr.write("\n")
    if result.success:
        print(f"Done: {result.filepath}")
        print(f"  Size:     {format_size(result.total_size)}")
        print(f"  Time:     {format_time(result.elapsed)}")
        print(f"  Avg speed:{format_speed(result.average_speed)}")
        return 0
    else:
        print(f"Failed: {result.error}", file=sys.stderr)
        return 1


def download_batch(
    file_path: str,
    output: str | None,
    connections: int,
    resume: bool,
    speed_limit: float | None,
) -> int:
    """Download multiple URLs from a text file.  Returns exit code."""
    if not os.path.isfile(file_path):
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return 1

    with open(file_path, "r", encoding="utf-8") as f:
        urls = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]

    if not urls:
        print("Error: no URLs found in file", file=sys.stderr)
        return 1

    print(f"Batch download: {len(urls)} URL(s)")
    if output:
        print(f"Output dir: {output}")
        os.makedirs(output, exist_ok=True)
    print()

    success_count = 0
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        code = download_single(url, output, connections, resume, speed_limit)
        if code == 0:
            success_count += 1
        print()

    print(f"Completed: {success_count}/{len(urls)}")
    return 0 if success_count == len(urls) else 1


def parse_speed_limit(value: str) -> float:
    """Parse a speed limit string like ``"1M"`` into bytes/sec.

    Supports suffixes: B, K, M, G (case-insensitive).

    Args:
        value: Speed string, e.g. ``"500K"`` or ``"1M"``.

    Returns:
        Speed in bytes per second.

    Raises:
        argparse.ArgumentTypeError: If the value cannot be parsed.
    """
    value = value.strip()
    if not value:
        raise argparse.ArgumentTypeError("empty speed value")
    units = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3}
    suffix = value[-1].upper()
    if suffix in units:
        num_str = value[:-1]
    else:
        num_str = value
        suffix = "B"
    try:
        num = float(num_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid speed: {value}")
    return num * units[suffix]


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="swiftget",
        description=(
            "SwiftGet - A simplified multi-connection CLI download tool.\n"
            "快速多连接命令行下载工具。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  swiftget https://example.com/file.zip\n"
            "  swiftget -c 8 -o data.iso https://example.com/big.iso\n"
            "  swiftget -f urls.txt -o ./downloads/\n"
            "  swiftget --no-resume --limit 1M https://example.com/file\n"
        ),
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="URL to download (除非使用 -f 批量模式 / unless using -f batch mode)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="输出文件或目录路径 (output file or directory path)",
    )
    parser.add_argument(
        "-c",
        "--connections",
        type=int,
        default=4,
        help="并行连接数 / number of parallel connections (default: 4)",
    )
    parser.add_argument(
        "-f",
        "--file",
        default=None,
        help="从文件读取URL列表批量下载 / batch download URLs from file",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="禁用断点续传 / disable resume support",
    )
    parser.add_argument(
        "--limit",
        type=parse_speed_limit,
        default=None,
        metavar="SPEED",
        help="限速 (如 500K, 1M) / speed limit (e.g. 500K, 1M)",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"swiftget {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI.

    Args:
        argv: Command-line arguments.  If ``None``, uses ``sys.argv``.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Validate: need either a URL or a batch file
    if not args.url and not args.file:
        parser.print_help(sys.stderr)
        return 2

    if args.file:
        return download_batch(
            args.file,
            args.output,
            args.connections,
            resume=not args.no_resume,
            speed_limit=args.limit,
        )
    else:
        return download_single(
            args.url,
            args.output,
            args.connections,
            resume=not args.no_resume,
            speed_limit=args.limit,
        )


if __name__ == "__main__":
    sys.exit(main())
