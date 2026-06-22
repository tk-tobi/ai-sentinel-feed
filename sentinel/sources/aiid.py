"""AI Incident Database (AIID) source connector via Playwright GraphQL."""

from __future__ import annotations

from typing import Any

from sentinel.config import AIID_GRAPHQL_URL

INCIDENTS_QUERY = """
query Incidents($pagination: PaginationType) {
  incidents(pagination: $pagination) {
    incident_id
    title
    description
    date
    AllegedDeployerOfAISystem { name }
    AllegedDeveloperOfAISystem { name }
    reports {
      report_number
      title
      date_published
      source_domain
      url
    }
  }
}
"""

DEFAULT_PAGE_SIZE = 100


def run_graphql_query(
    query: str,
    variables: dict[str, Any],
    *,
    graphql_url: str = AIID_GRAPHQL_URL,
) -> dict[str, Any]:
    """Execute a GraphQL query through a headless browser session."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://incidentdatabase.ai/", wait_until="networkidle", timeout=120_000)
        result = page.evaluate(
            """async ({ graphqlUrl, query, variables }) => {
                const response = await fetch(graphqlUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ query, variables }),
                });
                return await response.json();
            }""",
            {
                "graphqlUrl": graphql_url,
                "query": query,
                "variables": variables,
            },
        )
        browser.close()

    if "errors" in result:
        messages = "; ".join(error.get("message", "unknown") for error in result["errors"])
        raise RuntimeError(f"AIID GraphQL error: {messages}")

    return result


def fetch_page(
    *,
    limit: int = DEFAULT_PAGE_SIZE,
    skip: int = 0,
    graphql_url: str = AIID_GRAPHQL_URL,
) -> list[dict[str, Any]]:
    """Fetch a single page of AIID incidents."""
    result = run_graphql_query(
        INCIDENTS_QUERY,
        {"pagination": {"limit": limit, "skip": skip}},
        graphql_url=graphql_url,
    )
    return result.get("data", {}).get("incidents", [])


def fetch(
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    graphql_url: str = AIID_GRAPHQL_URL,
) -> list[dict[str, Any]]:
    """Fetch all AIID incidents via paginated GraphQL requests."""
    incidents: list[dict[str, Any]] = []
    skip = 0

    while True:
        batch = fetch_page(limit=page_size, skip=skip, graphql_url=graphql_url)
        if not batch:
            break
        incidents.extend(batch)
        if len(batch) < page_size:
            break
        skip += page_size

    return incidents
