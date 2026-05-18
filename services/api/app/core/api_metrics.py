from __future__ import annotations

from collections import Counter
from threading import Lock

_request_counts: Counter[tuple[str, str, int]] = Counter()
_request_lock = Lock()


def record_api_request(*, method: str, path: str, status_code: int) -> None:
    with _request_lock:
        _request_counts[(method.upper(), path, status_code)] += 1


def get_api_request_metrics() -> list[dict[str, object]]:
    with _request_lock:
        items = list(_request_counts.items())
    return [
        {
            "method": method,
            "path": path,
            "status_code": status_code,
            "count": count,
        }
        for (method, path, status_code), count in sorted(items)
    ]
