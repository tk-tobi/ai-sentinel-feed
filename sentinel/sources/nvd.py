"""NVD / CVE source connector."""

from __future__ import annotations

import time
from typing import Any

import httpx

from sentinel.config import NVD_API_KEY, NVD_API_URL, NVD_KEYWORDS

DEFAULT_RESULTS_PER_PAGE = 100
UNAUTHENTICATED_DELAY_SECONDS = 6.0
AUTHENTICATED_DELAY_SECONDS = 0.6
MAX_RETRIES = 6
INITIAL_BACKOFF_SECONDS = 5.0
MAX_BACKOFF_SECONDS = 120.0
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


def _request_params(
    keyword: str,
    *,
    start_index: int,
    results_per_page: int,
) -> dict[str, Any]:
    return {
        "keywordSearch": keyword,
        "startIndex": start_index,
        "resultsPerPage": results_per_page,
    }


def _request_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["apiKey"] = api_key
    return headers


def _get_json_with_retry(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    """GET JSON from NVD, retrying transient upstream failures."""
    backoff = INITIAL_BACKOFF_SECONDS
    for attempt in range(1, MAX_RETRIES + 1):
        response = client.get(url, params=params, headers=headers)
        status_code = getattr(response, "status_code", 200)
        if status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
            print(
                f"[nvd] {response.status_code} for {params.get('keywordSearch')} "
                f"startIndex={params.get('startIndex')}; "
                f"retry {attempt}/{MAX_RETRIES - 1} in {backoff:.0f}s"
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
            continue
        response.raise_for_status()
        return response.json()
    response.raise_for_status()
    raise RuntimeError("NVD request failed after retries")


def fetch_keyword(
    keyword: str,
    *,
    api_key: str | None = NVD_API_KEY,
    api_url: str = NVD_API_URL,
    results_per_page: int = DEFAULT_RESULTS_PER_PAGE,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Fetch all CVE vulnerability records for a single keyword search."""
    headers = _request_headers(api_key)
    delay = AUTHENTICATED_DELAY_SECONDS if api_key else UNAUTHENTICATED_DELAY_SECONDS
    records: list[dict[str, Any]] = []
    start_index = 0
    total_results: int | None = None

    owns_client = client is None
    client = client or httpx.Client(timeout=120.0)

    try:
        while total_results is None or start_index < total_results:
            payload = _get_json_with_retry(
                client,
                api_url,
                params=_request_params(
                    keyword,
                    start_index=start_index,
                    results_per_page=results_per_page,
                ),
                headers=headers,
            )

            if total_results is None:
                total_results = int(payload.get("totalResults", 0))

            batch = payload.get("vulnerabilities", [])
            if not batch:
                break

            for item in batch:
                record = dict(item)
                record["search_keyword"] = keyword
                records.append(record)

            start_index += len(batch)
            if start_index < total_results:
                time.sleep(delay)
    finally:
        if owns_client:
            client.close()

    return records


def fetch(
    keywords: list[str] | None = None,
    *,
    api_key: str | None = NVD_API_KEY,
) -> list[dict[str, Any]]:
    """Fetch CVE records for all configured ML keywords, deduped by CVE id."""
    keywords = keywords or NVD_KEYWORDS
    by_cve_id: dict[str, dict[str, Any]] = {}

    with httpx.Client(timeout=120.0) as client:
        for keyword in keywords:
            for record in fetch_keyword(keyword, api_key=api_key, client=client):
                cve_id = record.get("cve", {}).get("id")
                if not cve_id:
                    continue

                existing = by_cve_id.get(cve_id)
                if existing is None:
                    by_cve_id[cve_id] = record
                    continue

                existing_keywords = {
                    existing.get("search_keyword"),
                    record.get("search_keyword"),
                }
                existing["search_keyword"] = ",".join(
                    sorted(k for k in existing_keywords if k)
                )

    return list(by_cve_id.values())
