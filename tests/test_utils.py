"""Tests for swiftget.utils."""

import pytest
from swiftget.utils import (
    format_size,
    format_speed,
    format_time,
    parse_url,
    get_filename,
    calculate_chunks,
    sanitize_filename,
)


class TestFormatSize:
    """Tests for format_size()."""

    def test_zero_bytes(self):
        assert format_size(0) == "0.00 B"

    def test_bytes(self):
        assert format_size(512) == "512.00 B"

    def test_kilobytes(self):
        assert format_size(1536) == "1.50 KB"

    def test_megabytes(self):
        assert format_size(1048576) == "1.00 MB"

    def test_gigabytes(self):
        assert format_size(1073741824) == "1.00 GB"

    def test_negative_returns_zero(self):
        assert format_size(-100) == "0.00 B"

    def test_large_value(self):
        # 1 TB
        result = format_size(1099511627776)
        assert "TB" in result


class TestFormatSpeed:
    """Tests for format_speed()."""

    def test_zero_speed(self):
        assert format_speed(0) == "0.00 B/s"

    def test_negative_speed(self):
        assert format_speed(-10) == "0.00 B/s"

    def test_megabytes_per_sec(self):
        result = format_speed(1048576)
        assert "MB/s" in result


class TestFormatTime:
    """Tests for format_time()."""

    def test_zero_seconds(self):
        assert format_time(0) == "00:00:00"

    def test_seconds(self):
        assert format_time(45) == "00:00:45"

    def test_minutes(self):
        assert format_time(125) == "00:02:05"

    def test_hours(self):
        assert format_time(3661) == "01:01:01"

    def test_infinite(self):
        assert format_time(float("inf")) == "--:--:--"


class TestParseUrl:
    """Tests for parse_url()."""

    def test_valid_https(self):
        assert parse_url("https://example.com/file.zip") is True

    def test_valid_http(self):
        assert parse_url("http://example.com/path/to/file") is True

    def test_valid_with_port(self):
        assert parse_url("https://example.com:8080/file") is True

    def test_valid_with_query(self):
        assert parse_url("https://example.com/file?token=abc123") is True

    def test_invalid_ftp(self):
        assert parse_url("ftp://example.com/file") is False

    def test_invalid_no_scheme(self):
        assert parse_url("example.com/file") is False

    def test_invalid_empty(self):
        assert parse_url("") is False

    def test_invalid_none(self):
        assert parse_url(None) is False  # type: ignore[arg-type]

    def test_invalid_plain_text(self):
        assert parse_url("just some text") is False


class TestGetFilename:
    """Tests for get_filename()."""

    def test_from_url_path(self):
        url = "https://example.com/path/to/file.zip"
        assert get_filename(url) == "file.zip"

    def test_from_url_with_query(self):
        url = "https://example.com/download?file=data.csv"
        # Query is stripped, uses path
        assert get_filename(url) == "download"

    def test_from_content_disposition(self):
        url = "https://example.com/download"
        headers = {"Content-Disposition": 'attachment; filename="report.pdf"'}
        assert get_filename(url, headers) == "report.pdf"

    def test_from_content_disposition_encoded(self):
        url = "https://example.com/download"
        headers = {
            "Content-Disposition": "attachment; filename*=UTF-8''hello%20world.txt"
        }
        result = get_filename(url, headers)
        assert "hello" in result

    def test_url_without_path(self):
        url = "https://example.com"
        assert get_filename(url) == "download.bin"

    def test_empty_url(self):
        assert get_filename("") == "download.bin"


class TestCalculateChunks:
    """Tests for calculate_chunks()."""

    def test_even_split(self):
        chunks = calculate_chunks(100, 4)
        assert len(chunks) == 4
        assert chunks == [(0, 24), (25, 49), (50, 74), (75, 99)]

    def test_uneven_split(self):
        chunks = calculate_chunks(10, 3)
        assert len(chunks) == 3
        # Last chunk gets the remainder
        assert chunks[-1][1] == 9
        # No gaps or overlaps
        for i in range(len(chunks) - 1):
            assert chunks[i][1] + 1 == chunks[i + 1][0]

    def test_single_chunk(self):
        chunks = calculate_chunks(500, 1)
        assert chunks == [(0, 499)]

    def test_more_chunks_than_bytes(self):
        chunks = calculate_chunks(3, 10)
        # Should be capped to 3 chunks
        assert len(chunks) == 3

    def test_contiguous(self):
        """Verify chunks cover the full range without gaps."""
        total = 997
        num = 7
        chunks = calculate_chunks(total, num)
        assert chunks[0][0] == 0
        assert chunks[-1][1] == total - 1
        for i in range(len(chunks) - 1):
            assert chunks[i][1] + 1 == chunks[i + 1][0]

    def test_invalid_total(self):
        with pytest.raises(ValueError):
            calculate_chunks(0, 4)

    def test_invalid_num_chunks(self):
        with pytest.raises(ValueError):
            calculate_chunks(100, 0)


class TestSanitizeFilename:
    """Tests for sanitize_filename()."""

    def test_clean_name(self):
        assert sanitize_filename("file.zip") == "file.zip"

    def test_removes_slashes(self):
        result = sanitize_filename("path/to/file.zip")
        assert "/" not in result

    def test_removes_special_chars(self):
        result = sanitize_filename('file<>:"|?*.zip')
        for ch in '<>:"|?*':
            assert ch not in result

    def test_strips_dots(self):
        assert sanitize_filename("..file..") == "file"

    def test_empty_returns_default(self):
        assert sanitize_filename("") == "download.bin"

    def test_only_special_chars(self):
        result = sanitize_filename("***")
        assert result == "download.bin"
