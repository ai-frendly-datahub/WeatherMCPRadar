#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any


TOOLS = [
    {
        "name": "get_ultra_short_term_forecast",
        "title": "Ultra Short Term Forecast",
        "description": "Return deterministic KMA ultra-short-term forecast fixture data.",
        "inputSchema": {"type": "object", "additionalProperties": True},
    },
    {
        "name": "get_village_forecast",
        "title": "Village Forecast",
        "description": "Return deterministic KMA village forecast fixture data.",
        "inputSchema": {"type": "object", "additionalProperties": True},
    },
]

TOOL_RESULTS = {
    "get_ultra_short_term_forecast": {
        "title": "KMA ultra short term fixture",
        "url": "https://example.test/weather/kma-ultra-short-term",
        "summary": "Fixture-only KMA ultra-short-term forecast for Seoul.",
        "forecast_area": "Seoul",
        "source": "fixture",
    },
    "get_village_forecast": {
        "title": "KMA village forecast fixture",
        "url": "https://example.test/weather/kma-village-forecast",
        "summary": "Fixture-only KMA village forecast for Seoul.",
        "forecast_area": "Seoul",
        "source": "fixture",
    },
}


def write_message(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def response_for(message: dict[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-kma-weather-mcp", "version": "0.0.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        result = TOOL_RESULTS.get(str(params.get("name")))
        if result is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "Unsupported tool"}],
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
            },
        }
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Unsupported method: {method}"},
    }


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict):
            continue
        response = response_for(message)
        if response is not None:
            write_message(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
