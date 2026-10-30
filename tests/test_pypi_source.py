"""PyPI source tests: synthetic fixtures, no live requests."""

from unittest.mock import patch
from urllib.parse import urlsplit

import pytest

from openleads.models import Query
from openleads.sources.pypi import PyPISource, parse_results


def test_parse_package_with_public_email():
    data = {
        "info": {
            "name": "sample-package",
            "author": "Alice Example",
            "author_email": "alice@example.com",
            "summary": "A sample package",
            "project_url": "https://pypi.org/project/sample-package/",
            "home_page": "https://example.com",
            "project_urls": {},
        }
    }

    results = parse_results(data)

    assert len(results) == 1
    assert results[0].full_name == "Alice Example"
    assert results[0].domain == "example.com"
    assert results[0].extra["public_email"] == "alice@example.com"


def test_skip_package_without_maintainer_name():
    assert parse_results({
        "info": {
            "name": "sample-package",
            "author": "",
            "maintainer": "",
        }
    }) == []


@pytest.mark.parametrize(
    "data",
    [None, "bad", 42, {}, {"info": None}, {"info": "bad"}],
)
def test_malformed_responses_are_empty(data):
    assert parse_results(data) == []


def test_shared_host_is_not_used_as_domain():
    results = parse_results({
        "info": {
            "name": "sample-package",
            "author": "Alice Example",
            "home_page": "https://github.com/alice/project",
            "project_url": "https://pypi.org/project/sample-package/",
        }
    })

    assert len(results) == 1
    assert results[0].domain == ""


def test_topic_search_fetches_multiple_packages_and_respects_count():
    source = PyPISource()
    source.cache = object()

    def response(url, **kwargs):
        assert kwargs["cache"] is source.cache
        assert kwargs["ttl_ns"] == "dataset"

        path = urlsplit(url).path
        package = path.split("/")[-2]

        return {
            "info": {
                "name": package,
                "author": "Alice Example",
                "author_email": "alice@example.com",
                "summary": "Synthetic test package",
                "project_url": "https://pypi.org/project/{}/".format(package),
            }
        }

    with patch(
        "openleads.sources.pypi.get_json",
        side_effect=response,
    ) as fetch:
        results = list(
            source.search(Query(keyword="django", count=2))
        )

    assert len(results) == 2
    assert fetch.call_count == 2


@pytest.mark.parametrize(
    "query",
    [Query(), Query(keyword="django", count=0)],
)
def test_empty_query_does_not_fetch(query):
    with patch("openleads.sources.pypi.get_json") as fetch:
        assert list(PyPISource().search(query)) == []
        fetch.assert_not_called()


def test_http_failure_returns_empty_results():
    with patch(
        "openleads.sources.pypi.get_json",
        return_value=None,
    ):
        assert list(
            PyPISource().search(Query(keyword="django"))
        ) == []
