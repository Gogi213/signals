# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a real-time trading signals system that monitors cryptocurrency markets via WebSocket connections to Bybit, processes trade data into candles, applies technical analysis, and sends trading signals to remote strategy servers.

## Development Commands

### Running the Application
```bash
python main.py
```

### Testing
```bash
pytest
pytest-asyncio  # For async tests
```

### Code Quality
```bash
# Type checking
mypy .

# Linting
flake8

# Code formatting
black .
```

### Dependencies
```bash
pip install -r requirements.txt
```

## Architecture

### Core Components

1. **main.py** - Application entry point and main event loop
   - Orchestrates WebSocket connections, signal processing, and strategy communication
   - Handles warmup period (70 intervals) before sending signals
   - Filters coins by volume (MIN_DAILY_VOLUME = 60M) and blacklist

2. **src/websocket_handler.py** - WebSocket connection management
   - `TradeWebSocket` class handles multiple connections to Bybit streams
   - Distributes symbols across connections (max 20 coins per connection, 12 max connections)
   - Buffers trade data into 10-second candles with rolling 100-candle limit

3. **src/candle_aggregator.py** - Trade data aggregation
   - Converts individual trades into OHLCV candles
   - Calculates scaled average candle size for volume analysis

4. **src/signal_processor.py** - Technical analysis and signal generation
   - Implements multiple technical indicators (ATR, NATR, volume analysis)
   - Processes candles to generate buy/sell signals based on configurable criteria

5. **src/strategy_client.py** - External strategy communication
   - Sends trading signals to remote strategy servers via HTTP
   - Handles multiple servers and strategies simultaneously

6. **src/trading_api.py** - Market data API integration
   - Fetches symbol information and historical data from Bybit REST API
   - Volume-based filtering of trading pairs

7. **src/config.py** - Configuration management
   - Direct configuration without environment variables
   - Structured JSON logging with separate log files (system.json, signals.json, websocket.json)

### Key Configuration

- **Strategy Names**: Configured in `DEFAULT_STRATEGY_NAMES` (currently: ['xxx'])
- **Server URLs**: Listed in `DEFAULT_SERVER_URLS` (localhost, 192.168.1.100)
- **Volume Filter**: `MIN_DAILY_VOLUME = 60000000` (60M)
- **Blacklisted Coins**: Major pairs excluded from trading (BTC, ETH, SOL, etc.)
- **Warmup Period**: 70 intervals before signals activate
- **Candle Interval**: 10 seconds per candle
- **WebSocket URL**: `wss://stream.bybit.com/v5/public/linear`

### Signal Processing Flow

1. WebSocket receives trade data from Bybit
2. Trades aggregated into 10-second candles
3. Technical analysis applied to candle data
4. Signals generated based on multiple criteria:
   - Volume analysis (low_vol, narrow_rng)
   - Volatility (high_natr)
   - Growth filters
5. Valid signals sent to all configured strategy servers
6. All activity logged in structured JSON format

### Logging Structure

The system uses structured JSON logging with three separate log files:
- `logs/system.json` - Application lifecycle and errors
- `logs/signals.json` - Trading signals and analysis results
- `logs/websocket.json` - Connection events and data flow

### Important Notes

- The system requires a 70-interval warmup period before generating signals
- Coins with no trading data for 10+ minutes are automatically excluded
- All signals are sent to multiple strategy servers simultaneously
- The application runs continuously with 0.3-second processing intervals
- Code follows strict anti-overengineering principles as outlined in code-expert.md
- All changes must be logged in docs/backlog.md

### File Structure

```
src/
├── __init__.py
├── candle_aggregator.py     # Trade data aggregation
├── config.py                # Configuration and logging
├── signal_processor.py      # Technical analysis
├── strategy_client.py       # External API communication
├── trading_api.py          # Market data fetching
└── websocket_handler.py    # WebSocket management

docs/
└── backlog.md              # Change tracking (mandatory updates)

logs/                       # JSON log files (auto-created)
```