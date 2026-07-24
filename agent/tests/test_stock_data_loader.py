from __future__ import annotations

import importlib
import sys

import pandas as pd
import pytest

from src.config.accessor import reset_env_config


def test_stock_data_path_reads_from_env(monkeypatch):
    monkeypatch.setenv("VIBE_TRADING_STOCK_DATA_PATH", r"D:\GitRepo\skills\stock_data")
    reset_env_config()
    from src.config.env_schema import EnvConfig

    assert EnvConfig().data.stock_data_path.endswith("stock_data")


def test_unconfigured_path_is_unavailable(monkeypatch):
    monkeypatch.delenv("VIBE_TRADING_STOCK_DATA_PATH", raising=False)
    reset_env_config()
    from backtest.loaders.stock_data_loader import DataLoader

    assert DataLoader().is_available() is False


def test_invalid_path_does_not_import_or_raise(monkeypatch, tmp_path):
    monkeypatch.setenv("VIBE_TRADING_STOCK_DATA_PATH", str(tmp_path))
    reset_env_config()
    from backtest.loaders.stock_data_loader import DataLoader

    assert DataLoader().is_available() is False


def test_normalize_frame():
    loader_module = importlib.import_module("backtest.loaders.stock_data_loader")
    frame = pd.DataFrame({
        "date": ["2024-01-02", "2024-01-01"],
        "open": [10, 9], "high": [11, 10], "low": [9, 8],
        "close": [10.5, 9.5], "vol": [200, 100],
    })
    result = loader_module._normalize_frame(frame)
    assert result is not None
    assert result.index.name == "trade_date"
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]
    assert result.index.is_monotonic_increasing
    assert result["volume"].tolist() == [100.0, 200.0]


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("000001.SH", True),
        ("000300.sh", True),
        ("399001.SZ", True),
        ("399006.sz", True),
        ("600519.SH", False),
        ("000001.SZ", False),
        ("510300.SH", False),
        ("920001.BJ", False),
        ("000001", False),
        ("00001.SH", False),
        ("NOT-A-SYMBOL", False),
    ],
)
def test_is_a_share_index(code, expected):
    from backtest.loaders.stock_data_loader import _is_a_share_index

    assert _is_a_share_index(code) is expected


def test_fetch_delegates_per_symbol_with_asset_and_empty_adjust(monkeypatch, tmp_path):
    package = tmp_path / "stock_data"
    (package / "data_provider").mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "data_provider" / "__init__.py").write_text("")
    (package / "data_provider" / "manager.py").write_text(
        "class Manager:\n"
        "    def __init__(self): self.calls = []\n"
        "    def get_kline_data(self, code, **kwargs):\n"
        "        self.calls.append((code, kwargs))\n"
        "        import pandas as pd\n"
        "        return pd.DataFrame({'date':['2024-01-01'], 'open':[1], 'high':[2], 'low':[1], 'close':[1.5], 'vol':[3]}), 'fake'\n"
        "manager = Manager()\n"
        "def create_default_manager(): return manager\n"
    )
    monkeypatch.setenv("VIBE_TRADING_STOCK_DATA_PATH", str(tmp_path))
    reset_env_config()
    sys.modules.pop("stock_data.data_provider.manager", None)
    sys.modules.pop("stock_data.data_provider", None)
    sys.modules.pop("stock_data", None)
    module = importlib.import_module("backtest.loaders.stock_data_loader")
    loader = module.DataLoader()
    codes = ["600519.SH", "000300.SH", "399001.SZ", "920001.BJ"]
    result = loader.fetch(codes, "2024-01-01", "2024-01-02", interval="1m")
    manager = importlib.import_module("stock_data.data_provider.manager").manager

    assert list(result) == codes
    assert manager.calls == [
        (
            code,
            {
                "start_date": "2024-01-01",
                "end_date": "2024-01-02",
                "frequency": "1",
                "adjust": "",
                "asset": asset,
            },
        )
        for code, asset in zip(codes, ["stock", "index", "index", "stock"])
    ]


def test_stock_data_is_registered_and_in_a_share_chain():
    from backtest.loaders.registry import FALLBACK_CHAINS, LOADER_REGISTRY, VALID_SOURCES, _ensure_registered

    _ensure_registered()
    assert "stock_data" in VALID_SOURCES
    assert "stock_data" in LOADER_REGISTRY
    assert FALLBACK_CHAINS["a_share"][2] == "stock_data"


def test_unsupported_interval_raises(monkeypatch):
    monkeypatch.delenv("VIBE_TRADING_STOCK_DATA_PATH", raising=False)
    reset_env_config()
    from backtest.loaders.stock_data_loader import DataLoader

    with pytest.raises(ValueError, match="interval"):
        DataLoader().fetch([], "2024-01-01", "2024-01-02", interval="4H")


def test_market_data_tool_lists_source():
    from src.tools.market_data_tool import MarketDataTool

    assert "stock_data" in MarketDataTool.parameters["properties"]["source"]["enum"]


def test_explicit_stock_data_does_not_fallback():
    from backtest.loaders.registry import _NO_NETWORK_FALLBACK_SOURCES

    assert "stock_data" in _NO_NETWORK_FALLBACK_SOURCES


def test_supported_intervals_are_mapped():
    from backtest.loaders.stock_data_loader import _INTERVALS

    assert _INTERVALS == {"1D": "d", "1m": "1", "5m": "5", "15m": "15", "30m": "30", "1H": "60"}


def test_invalid_ohlc_is_dropped():
    module = importlib.import_module("backtest.loaders.stock_data_loader")
    frame = pd.DataFrame({
        "date": ["2024-01-01"], "open": [10], "high": [5], "low": [9],
        "close": [10], "vol": [1],
    })
    assert module._normalize_frame(frame) is None


def test_no_path_does_not_change_sys_path(monkeypatch):
    monkeypatch.delenv("VIBE_TRADING_STOCK_DATA_PATH", raising=False)
    reset_env_config()
    before = list(sys.path)
    importlib.import_module("backtest.loaders.stock_data_loader").DataLoader().is_available()
    assert sys.path == before


@pytest.fixture(autouse=True)
def _reset_after_test():
    yield
    reset_env_config()
    for name in ("stock_data.data_provider.manager", "stock_data.data_provider", "stock_data"):
        sys.modules.pop(name, None)
