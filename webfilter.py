#!/usr/bin/env python3
"""Bulk FortiGuard Web Filter category lookup utility.

This project is an unofficial community tool. It automates repeated lookups
against FortiGuard's public web-filter lookup page and is not a Fortinet API.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover - exercised by runtime environment
    curl_requests = None

LOOKUP_URL = "https://www.fortiguard.com/webfilter"
DEFAULT_INPUT = Path("addresses.txt")
DEFAULT_DELAY = 2.0
DEFAULT_TIMEOUT = 15.0
DEFAULT_RETRIES = 2


@dataclass(frozen=True)
class LookupResult:
    target: str
    category: str | None
    status: str
    error: str | None = None


def _clean_category(value: str | None) -> str | None:
    if not value:
        return None

    value = re.sub(r"\s+", " ", value).strip(" \t\r\n:-")
    value = re.sub(r"^category\s*:\s*", "", value, flags=re.IGNORECASE).strip()

    if not value or len(value) > 160:
        return None

    generic = {
        "category",
        "categories",
        "web filter category",
        "web filter categories",
    }
    if value.lower() in generic:
        return None

    return value


def parse_category(html: str) -> str | None:
    """Extract a FortiGuard category from a lookup response.

    FortiGuard's HTML has changed over time. The parser intentionally supports
    several observed layouts so a small front-end change is less likely to
    break every lookup.
    """

    soup = BeautifulSoup(html, "html.parser")

    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        text = heading.get_text(" ", strip=True)
        if not re.search(r"\bcategory\b", text, flags=re.IGNORECASE):
            continue

        anchor = heading.find("a")
        if anchor:
            candidate = _clean_category(anchor.get_text(" ", strip=True))
            if candidate:
                return candidate

        match = re.search(r"\bcategory\s*:\s*(.+)$", text, flags=re.IGNORECASE)
        if match:
            candidate = _clean_category(match.group(1))
            if candidate:
                return candidate

    info = soup.find(class_=re.compile(r"info[_-]?title", flags=re.IGNORECASE))
    if info:
        candidate = _clean_category(info.get_text(" ", strip=True))
        if candidate:
            return candidate

    page_text = soup.get_text(" ", strip=True)
    match = re.search(
        r"The address has been found as\s+(.+?)(?:\s{2,}|$)",
        page_text,
        flags=re.IGNORECASE,
    )
    if match:
        candidate = _clean_category(match.group(1))
        if candidate:
            return candidate

    match = re.search(
        r"Category\s*:\s*</?[^>]*>\s*<[^>]+>([^<]+)<",
        html,
        flags=re.IGNORECASE,
    )
    if match:
        return _clean_category(match.group(1))

    return None


def read_targets(path: Path) -> list[str]:
    """Read targets, ignoring blank lines and comment lines."""

    targets: list[str] = []
    seen: set[str] = set()

    with path.open("r", encoding="utf-8-sig") as handle:
        for raw_line in handle:
            target = raw_line.strip()
            if not target or target.startswith("#"):
                continue
            if target not in seen:
                targets.append(target)
                seen.add(target)

    return targets


def default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path(f"categories-{timestamp}.csv")


def lookup_target(
    session: Any,
    target: str,
    *,
    timeout: float,
    retries: int,
    impersonate: str,
) -> LookupResult:
    """Lookup one target with bounded retries for transient failures."""

    last_error: str | None = None

    for attempt in range(retries + 1):
        try:
            response = session.get(
                LOOKUP_URL,
                params={"q": target},
                timeout=timeout,
                impersonate=impersonate,
                allow_redirects=True,
            )

            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"HTTP {response.status_code}"
            elif response.status_code != 200:
                return LookupResult(
                    target=target,
                    category=None,
                    status="error",
                    error=f"HTTP {response.status_code}",
                )
            else:
                category = parse_category(response.text)
                if category:
                    return LookupResult(
                        target=target,
                        category=category,
                        status="ok",
                    )
                return LookupResult(
                    target=target,
                    category=None,
                    status="error",
                    error="category not found in response",
                )
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"

        if attempt < retries:
            time.sleep(min(2**attempt, 5))

    return LookupResult(
        target=target,
        category=None,
        status="error",
        error=last_error or "lookup failed",
    )


def write_results(path: Path, results: Iterable[LookupResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["target", "category", "status", "error"],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "target": result.target,
                    "category": result.category or "",
                    "status": result.status,
                    "error": result.error or "",
                }
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bulk-check URL/domain categories using FortiGuard Web Filter Lookup.",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input text file, one URL/domain per line (default: {DEFAULT_INPUT}).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output CSV path. Default: timestamped categories-*.csv file.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Seconds between targets (default: {DEFAULT_DELAY}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Per-request timeout in seconds (default: {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Retries for transient HTTP/network failures (default: {DEFAULT_RETRIES}).",
    )
    parser.add_argument(
        "--impersonate",
        default="chrome",
        help="curl_cffi browser profile to impersonate (default: chrome).",
    )
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.delay < 0:
        parser.error("--delay must be 0 or greater")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if args.retries < 0:
        parser.error("--retries must be 0 or greater")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args, parser)

    if curl_requests is None:
        print(
            "Missing dependency: curl_cffi. Install dependencies with "
            "'python -m pip install -r requirements.txt'.",
            file=sys.stderr,
        )
        return 2

    if not args.input.is_file():
        print(
            f"Input file not found: {args.input}\n"
            "Copy addresses.example.txt to addresses.txt or pass --input <file>.",
            file=sys.stderr,
        )
        return 2

    targets = read_targets(args.input)
    if not targets:
        print(f"No targets found in {args.input}.", file=sys.stderr)
        return 2

    output = args.output or default_output_path()
    results: list[LookupResult] = []
    interrupted = False

    session = curl_requests.Session()
    try:
        for index, target in enumerate(targets, start=1):
            print(f"[{index}/{len(targets)}] {target}", end=" ... ", flush=True)
            result = lookup_target(
                session,
                target,
                timeout=args.timeout,
                retries=args.retries,
                impersonate=args.impersonate,
            )
            results.append(result)

            if result.status == "ok":
                print(result.category)
            else:
                print(f"ERROR: {result.error}")

            if index < len(targets) and args.delay:
                time.sleep(args.delay)
    except KeyboardInterrupt:
        interrupted = True
        print("\nInterrupted by user. Writing partial results...", file=sys.stderr)
    finally:
        close = getattr(session, "close", None)
        if callable(close):
            close()

    write_results(output, results)

    failures = sum(1 for result in results if result.status != "ok")
    print(f"\nWrote {len(results)} result(s) to {output}")
    if interrupted:
        return 1
    if failures:
        print(f"Completed with {failures} failed lookup(s).", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
