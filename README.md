# SwiftGet

> 灵感来源 / Inspired by [aria2-next](https://github.com/AnInsomniacy/aria2-next) — aria2 的活跃维护分支

一个简化的多连接命令行下载工具，用 Python 实现。借鉴 aria2 的多连接下载理念，提供轻量、易用的 HTTP/HTTPS 文件下载功能。

A simplified multi-connection CLI download tool written in Python. Drawing inspiration from aria2's multi-segment download concept, it provides lightweight and easy-to-use HTTP/HTTPS file downloading.

## 功能特性 / Features

- **多连接下载** — 将文件分成多个块并行下载，加速大文件获取
- **断点续传** — 中断后可从已下载位置继续，无需重新开始
- **批量下载** — 从文本文件读取 URL 列表，批量下载
- **进度显示** — 实时显示下载进度、速度和已下载大小
- **速度限制** — 可选的下载限速，避免占满带宽
- **自动文件名** — 从 URL 或 `Content-Disposition` 头自动提取文件名

| Feature | Description |
|---------|-------------|
| Multi-connection | Split files into segments for parallel download |
| Resume support | Continue interrupted downloads from where they left off |
| Batch download | Download multiple URLs from a text file |
| Progress bar | Real-time progress, speed, and size display |
| Speed limit | Optional throttling to preserve bandwidth |
| Auto filename | Derive filenames from URL or response headers |

## 安装 / Installation

```bash
pip install swiftget
```

从源码安装 / From source:

```bash
git clone https://github.com/dcz6360/swiftget.git
cd swiftget
pip install -e .
```

## 使用示例 / Usage

### 下载单个文件

```bash
# 基本下载 / Basic download
swiftget https://example.com/file.zip

# 指定输出路径 / Specify output path
swiftget -o /path/to/output.zip https://example.com/file.zip

# 使用 8 个连接 / Use 8 connections
swiftget -c 8 https://example.com/largefile.iso

# 禁用断点续传 / Disable resume
swiftget --no-resume https://example.com/file.zip

# 限制速度为 1MB/s / Limit speed to 1MB/s
swiftget --limit 1M https://example.com/file.zip
```

### 批量下载 / Batch Download

创建一个包含 URL 的文本文件（每行一个 URL，`#` 开头为注释）：

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

### 命令行选项 / CLI Options

```
usage: swiftget [-h] [-o OUTPUT] [-c CONNECTIONS] [-f FILE] [--no-resume] [--limit SPEED] [-V] [url]

A simplified multi-connection CLI download tool.

positional arguments:
  url                   URL to download

options:
  -o, --output          输出文件或目录路径 (output file or directory path)
  -c, --connections      并行连接数 / number of parallel connections (default: 4)
  -f, --file            从文件读取URL列表批量下载 / batch download URLs from file
  --no-resume           禁用断点续传 / disable resume support
  --limit SPEED         限速 (如 500K, 1M) / speed limit (e.g. 500K, 1M)
  -V, --version         显示版本号 / show version
  -h, --help            显示帮助 / show help
```

## 与原项目的区别 / Differences from Original

| 方面 / Aspect | aria2-next | SwiftGet |
|------|-----------|----------|
| 语言 / Language | C++ | Python |
| 协议 / Protocols | HTTP, FTP, SFTP, BitTorrent, Metalink, ED2K | HTTP/HTTPS |
| 架构 / Architecture | 完整下载引擎 + JSON-RPC | 轻量 CLI 工具 |
| 依赖 / Dependencies | C++ 工具链, 多个系统库 | Python 3.10+, requests |
| 体积 / Size | 大型项目 | 单包, ~500 行代码 |

SwiftGet 是一个**原创实现**，不包含 aria2 或 aria2-next 的任何代码。仅借鉴了"多连接分块下载"的功能思路，用 Python 标准库和 `requests` 重新实现了一个简化版本。

SwiftGet is an **original implementation** that does not contain any code from aria2 or aria2-next. It only borrows the concept of "multi-connection segmented downloading" and reimplements a simplified version using Python's standard library and `requests`.

## 开发 / Development

```bash
# 安装开发依赖 / Install dev dependencies
pip install -e ".[dev]"

# 运行测试 / Run tests
pytest tests/ -v

# 运行覆盖率 / Run with coverage
pytest tests/ --cov=swiftget
```

## 许可证 / License

MIT License — see [LICENSE](LICENSE).
