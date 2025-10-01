"""
Debug: Check candle finalization timer
"""
import sys
import asyncio

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, '../..')

from src.websocket_handler import TradeWebSocket

async def test_timer():
    """Test candle finalization timer"""
    test_coins = ['BTCUSDT']

    aggregator = TradeWebSocket(test_coins)

    print("Starting connection...")
    ws_task = asyncio.create_task(aggregator.start_connection())

    # Wait longer to ensure timer runs
    for i in range(6):
        await asyncio.sleep(5)
        candles = aggregator.candles_buffer.get('BTCUSDT', [])
        trades_intervals = aggregator._trades_by_interval.get('BTCUSDT', {})

        print(f"\n[{(i+1)*5}s] BTCUSDT:")
        print(f"  Candles: {len(candles)}")
        print(f"  Trades intervals: {len(trades_intervals)}")

        if candles:
            last = candles[-1]
            print(f"  Last candle: ts={last['timestamp']} O={last['open']:.2f} C={last['close']:.2f} V={last['volume']:.4f}")

    await aggregator.stop()
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    asyncio.run(test_timer())
