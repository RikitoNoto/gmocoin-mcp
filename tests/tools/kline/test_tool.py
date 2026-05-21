from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastmcp import Client, FastMCP
from gmo_fx.api.klines import KlinesApi

from tools.kline import register_kline_tools
import tools.kline.tool as kline_tool


@dataclass
class FakeKline:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float


def create_test_server():
    mcp = FastMCP("test")
    register_kline_tools(mcp)
    return mcp


@pytest.mark.anyio
async def test_registers_kline_api_tool():
    mcp = create_test_server()
    tool = await mcp.get_tool("kline_api")

    assert tool is not None
    assert tool.name == "kline_api"
    assert set(tool.parameters["required"]) == {
        "symbol",
        "price_type",
        "interval",
        "date",
    }
    description = tool.description or ""
    assert "price_typeは必須" in description
    assert "ローソク足" in description
    assert "OHLC" in description
    assert "dateはYYYY-MM-DD形式" in description


@pytest.mark.anyio
async def test_kline_api_calls_api_with_parsed_date_and_formats_klines(monkeypatch):
    calls = []

    class FakeKlinesApi:
        def __call__(self, *, symbol, price_type, interval, date):
            calls.append(
                {
                    "symbol": symbol,
                    "price_type": price_type,
                    "interval": interval,
                    "date": date,
                }
            )
            return SimpleNamespace(
                klines=[
                    FakeKline(
                        open_time=datetime(2026, 5, 5, 0, 0, tzinfo=timezone.utc),
                        open=151.1,
                        high=152.2,
                        low=150.3,
                        close=151.8,
                    ),
                    FakeKline(
                        open_time=datetime(2026, 5, 5, 0, 5, tzinfo=timezone.utc),
                        open=151.8,
                        high=153.0,
                        low=151.0,
                        close=152.4,
                    ),
                ]
            )

    mcp = create_test_server()
    monkeypatch.setattr(kline_tool, "KlinesApi", FakeKlinesApi)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "kline_api",
            {
                "symbol": "USD_JPY",
                "price_type": "BID",
                "interval": "5min",
                "date": "2026-05-05",
            },
        )

    assert calls == [
        {
            "symbol": KlinesApi.Symbol.USD_JPY,
            "price_type": "BID",
            "interval": KlinesApi.KlineInterval.Min5,
            "date": datetime(2026, 5, 5),
        }
    ]
    assert result.data == [
        {
            "open_time": "2026-05-05T00:00:00+00:00",
            "open": 151.1,
            "high": 152.2,
            "low": 150.3,
            "close": 151.8,
        },
        {
            "open_time": "2026-05-05T00:05:00+00:00",
            "open": 151.8,
            "high": 153.0,
            "low": 151.0,
            "close": 152.4,
        },
    ]


@pytest.mark.anyio
async def test_kline_api_rejects_non_iso_date(monkeypatch):
    class FakeKlinesApi:
        def __call__(self, **kwargs):
            raise AssertionError("API should not be called when date parsing fails")

    mcp = create_test_server()
    monkeypatch.setattr(kline_tool, "KlinesApi", FakeKlinesApi)

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="time data"):
            await client.call_tool(
                "kline_api",
                {
                    "symbol": "USD_JPY",
                    "price_type": "BID",
                    "interval": "5min",
                    "date": "2026/05/05",
                },
            )
