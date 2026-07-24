"""Optional local ``stock_data`` A-share loader."""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from backtest.loaders.base import validate_date_range, validate_ohlc
from backtest.loaders.registry import register
from src.config.accessor import get_env_config

logger = logging.getLogger(__name__)

_INTERVALS = {"1D": "d", "1m": "1", "5m": "5", "15m": "15", "30m": "30", "1H": "60"}
_REQUIRED = ("open", "high", "low", "close", "volume")


def _is_a_share_index(code: str) -> bool:
    """Detect A-share index symbols (000xxx.SH, 399xxx.SZ)."""
    upper = code.upper()
    if upper.endswith(".SH"):
        digits = upper.split(".")[0]
        return len(digits) == 6 and digits.isdigit() and digits.startswith("000")
    if upper.endswith(".SZ"):
        digits = upper.split(".")[0]
        return len(digits) == 6 and digits.isdigit() and digits.startswith("399")
    return False


def _project_root() -> Path | None:
    configured = get_env_config().data.stock_data_path.strip()
    if not configured:
        return None
    root = Path(configured).expanduser()
    if not root.is_dir() or not (root / "stock_data" / "__init__.py").is_file():
        return None
    return root


def _manager_factory() -> Any | None:
    root = _project_root()
    if root is None:
        return None
    root_text = str(root)
    inserted = root_text not in sys.path
    if inserted:
        sys.path.insert(0, root_text)
    try:
        module = importlib.import_module("stock_data.data_provider.manager")
        module_file = getattr(module, "__file__", None)
        if module_file is None or root not in Path(module_file).resolve().parents:
            return None
        return getattr(module, "create_default_manager", None)
    except (ImportError, ModuleNotFoundError, AttributeError) as exc:
        logger.debug("stock_data import failed: %s", exc)
        return None
    finally:
        if inserted:
            try:
                sys.path.remove(root_text)
            except ValueError:
                pass


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame | None:
    result = frame.copy()
    if "trade_date" not in result.columns:
        for candidate in ("date", "datetime", "time"):
            if candidate in result.columns:
                result = result.rename(columns={candidate: "trade_date"})
                break
    if "trade_date" not in result.columns:
        if isinstance(result.index, pd.DatetimeIndex) or result.index.name in {"date", "trade_date", "datetime"}:
            result.index.name = "trade_date"
            result = result.reset_index()
        else:
            return None
    result = result.rename(columns={"vol": "volume"})
    if any(column not in result.columns for column in _REQUIRED):
        return None
    result["trade_date"] = pd.to_datetime(result["trade_date"], errors="coerce")
    for column in _REQUIRED:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=["trade_date", *_REQUIRED])
    result = result.set_index("trade_date")[list(_REQUIRED)].sort_index()
    result.index.name = "trade_date"
    result = validate_ohlc(result, strategy="drop")
    return result if not result.empty else None


@register
class DataLoader:
    """A-share loader backed by an optionally configured local stock_data project."""

    name = "stock_data"
    markets = {"a_share"}
    # stock_data's manager routes optional credentials internally; this loader's
    # availability is determined by the configured local project path.
    requires_auth = False

    def is_available(self) -> bool:
        factory = _manager_factory()
        if factory is None:
            return False
        try:
            factory()
        except Exception as exc:
            logger.debug("stock_data manager unavailable: %s", exc)
            return False
        return True

    def fetch(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: list[str] | None = None,
    ) -> dict[str, pd.DataFrame]:
        validate_date_range(start_date, end_date)
        del fields
        token = interval.strip()
        frequency = _INTERVALS.get(token) or _INTERVALS.get(token.upper())
        if frequency is None:
            raise ValueError(f"stock_data does not support interval={interval!r}")
        manager_factory = _manager_factory()
        if manager_factory is None:
            return {}
        manager = manager_factory()
        result: dict[str, pd.DataFrame] = {}
        for code in codes:
            try:
                asset = "index" if _is_a_share_index(code) else "stock"
                frame, _source = manager.get_kline_data(
                    code,
                    start_date=start_date,
                    end_date=end_date,
                    frequency=frequency,
                    adjust="",
                    asset=asset,
                )
                normalized = _normalize_frame(frame)
                if normalized is not None:
                    result[code] = normalized
            except Exception as exc:
                logger.warning("stock_data failed for %s: %s", code, exc)
        return result
