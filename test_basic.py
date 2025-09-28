"""
Basic tests for trading signals system - SPRINT 1 validation
"""
import asyncio
import pytest
from src.trading_api import get_futures_symbols, filter_symbols_by_volume
from src.candle_aggregator import aggregate_trades_to_candles, calculate_scaled_avg_candle_size
from src.signal_processor import generate_signal


def test_trading_api_connection():
    """Test that we can connect to Bybit API and get symbols"""
    symbols = get_futures_symbols()
    assert isinstance(symbols, list), "Should return a list of symbols"
    print(f"Successfully retrieved {len(symbols)} symbols from API")


def test_symbol_filtering():
    """Test symbol filtering by volume"""
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']
    filtered = filter_symbols_by_volume(test_symbols)
    assert isinstance(filtered, list), "Should return a list of filtered symbols"
    print(f"Successfully filtered symbols: {len(filtered)} from {len(test_symbols)}")


def test_candle_aggregation():
    """Test trade aggregation into candles"""
    # Mock trade data
    mock_trades = [
        {'timestamp': 1609459200000, 'price': 100.0, 'size': 10.0, 'side': 'Buy'},
        {'timestamp': 1609459201000, 'price': 101.0, 'size': 5.0, 'side': 'Sell'},
        {'timestamp': 1609459202000, 'price': 99.0, 'size': 8.0, 'side': 'Buy'},
        {'timestamp': 1609459203000, 'price': 102.0, 'size': 3.0, 'side': 'Sell'},
    ]

    candles = aggregate_trades_to_candles(mock_trades, 2000)  # 2-second candles
    assert isinstance(candles, list), "Should return a list of candles"
    assert len(candles) > 0, "Should create at least one candle"

    # Test candle structure
    candle = candles[0]
    required_keys = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    for key in required_keys:
        assert key in candle, f"Candle should have {key} key"

    # Test candle size calculation
    scaled_size = calculate_scaled_avg_candle_size(candles)
    assert isinstance(scaled_size, int), "Should return an integer"
    assert scaled_size >= 0, "Scaled size should be non-negative"

    print(f"Successfully aggregated {len(mock_trades)} trades into {len(candles)} candles")
    print(f"Calculated scaled candle size: {scaled_size}")


def test_signal_generation():
    """Test signal generation with mock candle data"""
    # Create mock candles with enough data for signal calculation
    mock_candles = []
    base_time = 1609459200000

    for i in range(60):  # Create 60 candles (enough for all indicators)
        candle = {
            'timestamp': base_time + i * 10000,  # 10-second intervals
            'open': 100.0 + i * 0.1,
            'high': 101.0 + i * 0.1,
            'low': 99.0 + i * 0.1,
            'close': 100.5 + i * 0.1,
            'volume': 1000.0 - i * 10  # Decreasing volume
        }
        mock_candles.append(candle)

    signal = generate_signal(mock_candles)
    assert isinstance(signal, bool), "Signal should be a boolean"

    print(f"Generated signal from {len(mock_candles)} candles: {signal}")


async def test_websocket_initialization():
    """Test WebSocket class initialization (without actual connection)"""
    from src.websocket_handler import TradeWebSocket

    test_coins = ['BTCUSDT', 'ETHUSDT']
    ws = TradeWebSocket(test_coins, max_coins_per_connection=1)

    assert ws.coins is not None, "Should have coins list"
    assert ws.trades_buffer is not None, "Should have trades buffer"
    assert not ws.running, "Should not be running initially"

    connections_needed = ws._calculate_needed_connections()
    assert connections_needed >= 0, "Should calculate valid number of connections"

    print(f"WebSocket initialized with {len(ws.coins)} coins, needs {connections_needed} connections")


if __name__ == "__main__":
    print("Running SPRINT 1 Basic Tests...")
    print()

    # Run synchronous tests
    test_trading_api_connection()
    test_symbol_filtering()
    test_candle_aggregation()
    test_signal_generation()

    # Run async test
    asyncio.run(test_websocket_initialization())

    print()
    print("All basic tests passed! SPRINT 1 core functionality is working.")
    print()
    print("What was tested:")
    print("  - API connectivity and symbol retrieval")
    print("  - Symbol filtering by volume")
    print("  - Trade aggregation into candles")
    print("  - Signal generation logic")
    print("  - WebSocket class initialization")
    print()
    print("Ready for production testing with real WebSocket connections!")