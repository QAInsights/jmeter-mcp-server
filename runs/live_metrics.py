"""
Cheap live metrics from a growing JTL file.

Reads only a tail window of the file so it works on very large JTLs
without loading them into memory.
"""

import csv
import io
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Union

_CHUNK = 1024 * 1024       # 1 MB chunks for the newline count
_TAIL_BLOCK = 64 * 1024    # 64 KB blocks when seeking from the end


def _percentile(sorted_values, percentile):
    """Same formula as MetricsCalculator._calculate_percentile."""
    if not sorted_values:
        return 0
    index = (percentile / 100) * (len(sorted_values) - 1)
    if index == int(index):
        return sorted_values[int(index)]
    lower = math.floor(index)
    upper = math.ceil(index)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (index - lower)


def _read_tail_lines(path: Path, max_lines: int):
    """Return (lines, from_start) — the last max_lines lines of the file.
    from_start is True when the read reached the beginning of the file,
    meaning the first returned line is complete."""
    size = os.path.getsize(path)
    data = b""
    with open(path, 'rb') as f:
        pos = size
        while pos > 0 and data.count(b"\n") <= max_lines:
            read_size = min(_TAIL_BLOCK, pos)
            pos -= read_size
            f.seek(pos)
            data = f.read(read_size) + data
    return data.decode('utf-8', errors='replace').splitlines(), pos == 0


def read_live_metrics(jtl_path: Union[str, Path], window_lines: int = 2000) -> Dict:
    """Compute cheap live metrics from a (possibly still-growing) CSV JTL.

    Returns {"supported": False, "reason": ...} for non-CSV JTLs.
    """
    path = Path(jtl_path)
    unsupported = {"supported": False, "reason": "live metrics require CSV JTL"}
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            first_line = f.readline()
    except OSError as e:
        return {"supported": False, "reason": str(e)}

    if 'timeStamp' not in first_line and 'elapsed' not in first_line:
        return dict(unsupported)
    header = next(csv.reader([first_line]))

    file_size = os.path.getsize(path)

    # Count total lines in 1 MB chunks
    total_lines = 0
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(_CHUNK)
            if not chunk:
                break
            total_lines += chunk.count(b"\n")
    ends_with_newline = file_size > 0
    if ends_with_newline:
        with open(path, 'rb') as f:
            f.seek(file_size - 1)
            ends_with_newline = f.read(1) == b"\n"
    total_samples = total_lines - 1  # minus header
    if not ends_with_newline and total_lines > 0:
        total_samples += 1  # last line without trailing newline still counts
    if total_samples < 0:
        total_samples = 0

    # Parse the tail window
    tail, from_start = _read_tail_lines(path, window_lines + 2)
    if tail and tail[0] == first_line.rstrip('\n'):
        tail = tail[1:]
    # Drop a possibly-partial first tail line (only when the read started
    # mid-file) and a possibly-partial last line
    if tail and not from_start:
        tail = tail[1:]
    if tail and (not ends_with_newline):
        tail = tail[:-1]
    # Keep only the requested window
    tail = tail[-window_lines:]

    idx = {name: i for i, name in enumerate(header)}
    recent = 0
    errors = 0
    rts = []
    last_ts = None
    active_threads = None
    for line in tail:
        if not line.strip():
            continue
        try:
            row = next(csv.reader(io.StringIO(line)))
        except Exception:
            continue
        try:
            rt = int(row[idx['elapsed']])
            success = row[idx['success']].strip().lower() in ("true", "1")
        except (KeyError, IndexError, ValueError):
            continue  # skip malformed/partial lines
        recent += 1
        rts.append(rt)
        if not success:
            errors += 1
        if 'timeStamp' in idx and idx['timeStamp'] < len(row):
            try:
                last_ts = int(row[idx['timeStamp']])
            except ValueError:
                pass
        if 'allThreads' in idx and idx['allThreads'] < len(row):
            try:
                active_threads = int(row[idx['allThreads']])
            except ValueError:
                pass

    rts_sorted = sorted(rts)
    return {
        "supported": True,
        "total_samples": total_samples,
        "recent_samples": recent,
        "recent_error_rate_pct": (errors / recent) * 100 if recent else 0.0,
        "recent_avg_response_ms": sum(rts) / recent if recent else 0.0,
        "recent_p95_response_ms": _percentile(rts_sorted, 95),
        "active_threads": active_threads,
        "last_sample_time": datetime.fromtimestamp(last_ts / 1000).isoformat() if last_ts else None,
        "file_size_bytes": file_size,
    }
