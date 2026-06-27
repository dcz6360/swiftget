# SwiftGet

> Inspired by [aria2-next](https://github.com/AnInsomniacy/aria2-next) — an actively maintained fork of aria2

A simplified multi-connection CLI download tool written in Python. Drawing inspiration from aria2's multi-segment download concept, it provides lightweight and easy-to-use HTTP/HTTPS file downloading.

## Features

- **Multi-connection download** — Split files into segments and download in parallel
- **Resume support** — Continue interrupted downloads from where they left off
- **Batch download** — Read a list of URLs from a text file and download them all
- **Progress display** — Real-time progress bar with speed and size info
- **Speed limiting** — Optional download throttling to preserve bandwidth
- **Auto filename** — Automatically extract filenames from URLs or `Content-Disposition` headers

## Installation

```bash
pip install swiftget
```

From source:

```bash
git clone https://github.com/dcz6360/swiftget.git
cd swiftget
pip install -e .
```

## Usage

### Download a single file

```bash
# Basic download
swiftget https://example.com/file.zip

# Specify output path
swiftget -o /path/to/output.zip https://example.com/file.zip

# Use 8 connections
swiftget -c 8 https://example.com/largefile.iso

# Disable resume
swiftget --no-resume https://example.com/file.zip

# Limit speed to 1MB/s
swiftget --limit 1M https://example.com/file.zip
```

### Batch download

Create a text file with URLs (one per line, `#` for comments):

```text
# urls.txt
https://example.com/file1.zip
https://example.com/file2.zip
https://example.com/file3.zip
```

```bash
swiftget -f urls.txt -o ./downloads/
```

### CLI Options

```
usage: swiftget [-h] [-o OUTPUT] [-c CONNECTIONS] [-f FILE] [--no-resume] [--limit SPEED] [-V] [url]

A simplified multi-connection CLI download tool.

positional arguments:
  url                   URL to download

options:
  -o, --output          Output file or directory path
  -c, --connections      Number of parallel connections (default: 4)
  -f, --file            Batch download URLs from file
  --no-resume           Disable resume support
  --limit SPEED         Speed limit (e.g. 500K, 1M)
  -V, --version         Show version
  -h, --help            Show help
```

## Differences from the Original

| Aspect | aria2-next | SwiftGet |
|--------|-----------|----------|
| Language | C++ | Python |
| Protocols | HTTP, FTP, SFTP, BitTorrent, Metalink, ED2K | HTTP/HTTPS |
| Architecture | Full download engine + JSON-RPC | Lightweight CLI tool |
| Dependencies | C++ toolchain, multiple system libraries | Python 3.10+, requests |
| Size | Large project | Single package, ~500 lines |

SwiftGet is an **original implementation** that does not contain any code from aria2 or aria2-next. It only borrows the concept of "multi-connection segmented downloading" and reimplements a simplified version using Python's standard library and `requests`.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=swiftget
```

## License

MIT License — see [LICENSE](LICENSE).
