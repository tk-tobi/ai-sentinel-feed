"""Tests for NVD and AIID source connectors."""

from sentinel.sources.aiid import fetch as fetch_aiid
from sentinel.sources.aiid import fetch_page
from sentinel.sources.nvd import fetch as fetch_nvd
from sentinel.sources.nvd import fetch_keyword

NVD_FIXTURE = {
    "totalResults": 2,
    "vulnerabilities": [
        {"cve": {"id": "CVE-2021-43811", "descriptions": [{"lang": "en", "value": "A"}]}},
        {"cve": {"id": "CVE-2021-4118", "descriptions": [{"lang": "en", "value": "B"}]}},
    ],
}

AIID_FIXTURE_PAGE_1 = {
    "data": {
        "incidents": [
            {"incident_id": 1, "title": "First", "description": "One"},
            {"incident_id": 2, "title": "Second", "description": "Two"},
        ]
    }
}

AIID_FIXTURE_PAGE_2 = {
    "data": {
        "incidents": [
            {"incident_id": 3, "title": "Third", "description": "Three"},
        ]
    }
}


class FakeNvdClient:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url, params=None, headers=None):
        self.calls.append(params["keywordSearch"])

        class Response:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        return Response(self.responses[params["keywordSearch"]])

    def close(self):
        return None


def test_fetch_keyword_paginates_results(monkeypatch):
    pages = {
        "pytorch": {
            "totalResults": 2,
            "vulnerabilities": [
                {"cve": {"id": "CVE-2021-43811"}},
            ],
        }
    }

    class PagingClient:
        def __init__(self):
            self.calls = 0

        def get(self, url, params=None, headers=None):
            self.calls += 1

            class Response:
                def raise_for_status(self):
                    return None

                def json(self):
                    if params["startIndex"] == 0:
                        return {
                            "totalResults": 2,
                            "vulnerabilities": [{"cve": {"id": "CVE-1"}}],
                        }
                    return {
                        "totalResults": 2,
                        "vulnerabilities": [{"cve": {"id": "CVE-2"}}],
                    }

            return Response()

        def close(self):
            return None

    monkeypatch.setattr("sentinel.sources.nvd.time.sleep", lambda *_: None)
    records = fetch_keyword("pytorch", client=PagingClient())
    assert len(records) == 2
    assert records[0]["search_keyword"] == "pytorch"


def test_fetch_dedupes_cves_across_keywords(monkeypatch):
    fake_client = FakeNvdClient(
        {
            "pytorch": NVD_FIXTURE,
            "tensorflow": {
                "totalResults": 1,
                "vulnerabilities": [
                    {
                        "cve": {
                            "id": "CVE-2021-43811",
                            "descriptions": [{"lang": "en", "value": "A"}],
                        }
                    },
                ],
            },
        }
    )

    class ClientContext:
        def __enter__(self):
            return fake_client

        def __exit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr("sentinel.sources.nvd.httpx.Client", lambda **kwargs: ClientContext())
    monkeypatch.setattr("sentinel.sources.nvd.time.sleep", lambda *_: None)

    records = fetch_nvd(keywords=["pytorch", "tensorflow"], api_key="test-key")
    assert len(records) == 2
    merged = next(item for item in records if item["cve"]["id"] == "CVE-2021-43811")
    assert merged["search_keyword"] == "pytorch,tensorflow"


def test_fetch_aiid_paginates(monkeypatch):
    responses = [AIID_FIXTURE_PAGE_1, AIID_FIXTURE_PAGE_2]

    def fake_fetch_page(*, limit=100, skip=0, graphql_url=None):
        index = skip // limit
        payload = responses[index]
        return payload["data"]["incidents"]

    monkeypatch.setattr("sentinel.sources.aiid.fetch_page", fake_fetch_page)
    incidents = fetch_aiid(page_size=2)
    assert len(incidents) == 3
    assert incidents[-1]["incident_id"] == 3


def test_fetch_page_raises_on_graphql_error(monkeypatch):
    def raise_graphql_error(*args, **kwargs):
        raise RuntimeError("AIID GraphQL error: bad query")

    monkeypatch.setattr("sentinel.sources.aiid.run_graphql_query", raise_graphql_error)

    try:
        fetch_page()
    except RuntimeError as exc:
        assert "bad query" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
