# stock_data DataLoader Asset Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and test-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Add explicit stock/index K-line routing to the new `stock_data` loader without modifying upstream loaders.

**Architecture:** Keep the Tushare-compatible A-share index predicate private to `stock_data_loader.py`. Convert the predicate result into the `asset` argument expected by `stock_data.DataFetcherManager`.

**Tech Stack:** Python, pandas, pytest, Vibe-Trading DataLoaderProtocol, stock_data DataFetcherManager.

---

### Task 1: Add stock_data-local routing tests

**Files:**
- Test: `agent/tests/test_stock_data_loader.py`

- [x] Add predicate cases for `000xxx.SH`, `399xxx.SZ`, lowercase suffixes, ordinary stocks, ETF, BJ, bare and malformed codes.
- [x] Extend the fake Manager test with an ordered mixed batch and assert `asset` values.
- [x] Run `python -m pytest tests/test_stock_data_loader.py -q` before implementation and verify failure from the missing local predicate/asset routing.

### Task 2: Implement local asset routing

**Files:**
- Modify: `agent/backtest/loaders/stock_data_loader.py`

- [x] Add private `_is_a_share_index(code)` using the established Tushare rule.
- [x] Derive `asset = "index" if _is_a_share_index(code) else "stock"` per input code.
- [x] Pass `asset=asset` to `manager.get_kline_data` and preserve `result[code]`.
- [x] Run `python -m pytest tests/test_stock_data_loader.py -q`; expect all tests to pass.

### Task 3: Verify scope and quality

**Files:**
- Verify: `agent/backtest/loaders/stock_data_loader.py`
- Verify: `agent/tests/test_stock_data_loader.py`

- [ ] Run focused stock_data and existing Tushare tests together.
- [ ] Run Ruff on the two changed Python files.
- [ ] Inspect Git diff and confirm no upstream loader/shared utility is modified.
- [ ] Do not commit unless separately requested.
