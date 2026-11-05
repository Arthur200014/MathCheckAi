"""Create genuine safe HTTP requests to populate live FastAPI metrics."""
from __future__ import annotations

import argparse
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ENDPOINTS = ("/api/task-types", "/health", "/docs")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Populate real HTTP traffic, without Ollama.")
    parser.add_argument("--requests", type=int, default=120)
    parser.add_argument("--interval", type=float, default=0.18, help="Seconds between requests")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args(argv)
    if not 1 <= args.requests <= 1000:
        parser.error("--requests must be from 1 to 1000")
    if not 0 <= args.interval <= 5:
        parser.error("--interval must be between 0 and 5 seconds")

    success = 0
    failed = 0
    for i in range(args.requests):
        path = ENDPOINTS[i % len(ENDPOINTS)]
        try:
            with urlopen(args.base_url.rstrip("/") + path, timeout=10) as response:
                response.read(128)
                if response.status != 200:
                    raise RuntimeError(f"unexpected HTTP response: {response.status}")
            success += 1
        except (HTTPError, URLError, OSError, RuntimeError) as exc:
            failed += 1
            if failed <= 3:
                print(f"Request failed ({path}): {type(exc).__name__}", flush=True)
        if i < args.requests - 1:
            time.sleep(args.interval)

    print(f"HTTP traffic: {success}/{args.requests} succeeded; {failed} failed", flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
