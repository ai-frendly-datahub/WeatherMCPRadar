from __future__ import annotations

import sys

import pytest

from radar.collector import _collect_single, collect_sources
from radar.exceptions import NetworkError, SourceError
from radar.mcp_source import collect_mcp_server_source
from radar.models import Source


HANGING_MCP_SERVER = "import time; time.sleep(30)"


def test_mcp_server_source_invokes_allowlisted_tool(monkeypatch) -> None:
    source = Source(
        name="Example MCP",
        type="mcp_server",
        url="mcp://example",
        config={
            "transport": "stdio",
            "command": "example-mcp",
            "tools": [{"name": "search", "arguments": {"query": "radar"}}],
            "timeout_seconds": 3,
            "max_items": 5,
        },
    )
    observed = {}

    def fake_payloads(_source, config):
        observed["transport"] = config.transport
        observed["tool"] = config.tools[0].name
        observed["arguments"] = config.tools[0].arguments
        return [
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"title": "Example MCP result", '
                            '"url": "https://example.com/result", '
                            '"summary": "normalized from MCP tool"}'
                        ),
                    }
                ]
            }
        ]

    monkeypatch.setattr("radar.mcp_source.collect_mcp_payloads", fake_payloads)

    articles = _collect_single(source, category="mcp", limit=5, timeout=10)

    assert observed == {
        "transport": "stdio",
        "tool": "search",
        "arguments": {"query": "radar"},
    }
    assert len(articles) == 1
    assert articles[0].title == "Example MCP result"
    assert articles[0].link == "https://example.com/result"
    assert articles[0].summary == "normalized from MCP tool"
    assert articles[0].source == "Example MCP"
    assert articles[0].category == "mcp"


def test_disabled_mcp_server_source_is_not_executed(monkeypatch) -> None:
    source = Source(
        name="Disabled MCP",
        type="mcp_server",
        url="mcp://disabled",
        enabled=False,
        config={"transport": "stdio", "command": "should-not-run", "tools": ["search"]},
    )

    def fail_if_called(_source, _config):
        raise AssertionError("disabled MCP source should not be invoked")

    monkeypatch.setattr("radar.mcp_source.collect_mcp_payloads", fail_if_called)

    articles, errors = collect_sources(
        [source],
        category="mcp",
        min_interval_per_host=0.0,
        max_workers=1,
    )

    assert articles == []
    assert errors == []


def test_required_env_missing_fails_before_process_launch(monkeypatch) -> None:
    monkeypatch.delenv("MCP_RADAR_TEST_API_KEY", raising=False)
    source = Source(
        name="Env-gated MCP",
        type="mcp_server",
        url="mcp://env-gated",
        config={
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-c", "raise SystemExit(99)"],
            "tools": ["search"],
            "env": ["MCP_RADAR_TEST_API_KEY"],
            "timeout_seconds": 1,
        },
    )

    with pytest.raises(SourceError, match="Missing required MCP env var"):
        collect_mcp_server_source(source, category="mcp", limit=5, timeout=1)


def test_mcp_payload_without_url_uses_safe_fallback(monkeypatch) -> None:
    source = Source(
        name="Fallback MCP",
        type="mcp_stdio",
        url="",
        id="fallback-mcp",
        config={"command": "example-mcp", "tools": ["list_items"], "max_items": 1},
    )

    def fake_payloads(_source, _config):
        return [{"content": [{"type": "text", "text": "plain text result"}]}]

    monkeypatch.setattr("radar.mcp_source.collect_mcp_payloads", fake_payloads)

    articles = _collect_single(source, category="mcp", limit=5, timeout=10)

    assert len(articles) == 1
    assert articles[0].title == "plain text result"
    assert articles[0].link == "mcp://fallback-mcp"


def test_stdio_runtime_timeout_reports_request_context() -> None:
    source = Source(
        name="Hanging MCP",
        type="mcp_server",
        url="mcp://hanging",
        config={
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-c", HANGING_MCP_SERVER],
            "tools": ["search"],
            "timeout_seconds": 1,
        },
    )

    with pytest.raises(NetworkError, match="response 1 after 1s"):
        collect_mcp_server_source(source, category="mcp", limit=5, timeout=1)


def test_kma_weather_fake_stdio_fixture_collects_tool_results(monkeypatch) -> None:
    monkeypatch.setenv("KMA_API_KEY_DECODED", "fixture-only")
    source = Source(
        name="woongaro/KMA-WEATHER-MCP",
        type="mcp_server",
        url="https://github.com/woongaro/KMA-WEATHER-MCP",
        config={
            "transport": "stdio",
            "command": sys.executable,
            "args": ["fixtures/mcp/fake_kma_weather_mcp.py"],
            "tools": [
                {
                    "name": "get_ultra_short_term_forecast",
                    "arguments": {"latitude": 37.5665, "longitude": 126.978},
                },
                {
                    "name": "get_village_forecast",
                    "arguments": {"latitude": 37.5665, "longitude": 126.978},
                },
            ],
            "env": ["KMA_API_KEY_DECODED"],
            "timeout_seconds": 5,
            "max_items": 5,
        },
    )

    articles = collect_mcp_server_source(source, category="weather_mcp", limit=5, timeout=5)

    assert len(articles) == 2
    assert [article.title for article in articles] == [
        "KMA ultra short term fixture",
        "KMA village forecast fixture",
    ]
    assert [article.link for article in articles] == [
        "https://example.test/weather/kma-ultra-short-term",
        "https://example.test/weather/kma-village-forecast",
    ]
    assert articles[0].summary == "Fixture-only KMA ultra-short-term forecast for Seoul."
    assert articles[1].summary == "Fixture-only KMA village forecast for Seoul."
    assert {article.source for article in articles} == {"woongaro/KMA-WEATHER-MCP"}
    assert {article.category for article in articles} == {"weather_mcp"}


def test_korea_weather_fake_stdio_fixture_collects_tool_results(monkeypatch) -> None:
    monkeypatch.setenv("KOREA_WEATHER_API_KEY", "fixture-only")
    source = Source(
        name="ohhan777/korea_weather",
        type="mcp_server",
        url="https://github.com/ohhan777/korea_weather",
        config={
            "transport": "stdio",
            "command": sys.executable,
            "args": ["fixtures/mcp/fake_korea_weather_mcp.py"],
            "tools": [
                {
                    "name": "get_nowcast_observation",
                    "arguments": {"lon": 126.978, "lat": 37.5665},
                },
                {
                    "name": "get_nowcast_forecast",
                    "arguments": {"lon": 126.978, "lat": 37.5665},
                },
                {
                    "name": "get_short_term_forecast",
                    "arguments": {"lon": 126.978, "lat": 37.5665},
                },
            ],
            "env": ["KOREA_WEATHER_API_KEY"],
            "timeout_seconds": 5,
            "max_items": 5,
        },
    )

    articles = collect_mcp_server_source(source, category="weather_mcp", limit=5, timeout=5)

    assert len(articles) == 3
    assert [article.title for article in articles] == [
        "Korea weather observation fixture",
        "Korea weather nowcast fixture",
        "Korea weather short term fixture",
    ]
    assert [article.link for article in articles] == [
        "https://example.test/weather/korea-observation",
        "https://example.test/weather/korea-nowcast",
        "https://example.test/weather/korea-short-term",
    ]
    assert articles[0].summary == "Fixture-only Korea weather observation for Seoul."
    assert articles[1].summary == "Fixture-only Korea weather nowcast forecast for Seoul."
    assert articles[2].summary == "Fixture-only Korea weather short-term forecast for Seoul."
    assert {article.source for article in articles} == {"ohhan777/korea_weather"}
    assert {article.category for article in articles} == {"weather_mcp"}
