# Backlog

## 2025-10-01: Migration from Bybit to Binance Futures

### Sprint 1+2 Completed 

**Changes:**
- Migrated `src/trading_api.py` from Bybit to Binance Futures API
- Updated all HTTP endpoints:
  - `get_futures_symbols()`: `/v5/market/tickers` ’ `/fapi/v1/exchangeInfo`
  - `get_all_symbols_by_volume()`: `turnover24h` ’ `quoteVolume`
  - `get_recent_trades()`: `/v5/market/recent-trade` ’ `/fapi/v1/trades`
- Removed Bybit API wrapper structure (`retCode`, `result.list`)
- Simplified error handling (removed unused exception variables)
- Added `BINANCE_FUTURES_BASE` constant for DRY

**Field Mappings:**
- Timestamp: microseconds ’ milliseconds (removed `// 1000`)
- Trade size: `v` ’ `qty`
- Trade side: `S` ’ inverted `isBuyerMaker` logic

**Tests:**
- Created `TESTS/iteration_2/test_binance_api.py`
- All tests passed: 547 symbols, 124 filtered by volume, trades validated

**Code metrics:**
- Lines changed: ~40 lines in trading_api.py (159’121, -38 lines)
- Complexity reduced: Removed nested response wrappers
- No new dependencies added

**Justification:**
- Exchange migration requirement (Bybit ’ Binance)
- Preserved all business logic (signal_processor, candle_aggregator unchanged)
- Minimal surface area change following YAGNI/KISS

---
