"""
Debug: Check WebSocket initialization and symbol matching
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

async def test_init():
    """Test WebSocket initialization"""
    test_coins = ['BTCUSDT', 'ETHUSDT']

    aggregator = TradeWebSocket(test_coins)

    print(f"Coins passed: {test_coins}")
    print(f"Coins stored: {aggregator.coins}")
    print(f"WS URL: {aggregator.ws_url}")
    print(f"\ncandles_buffer keys: {list(aggregator.candles_buffer.keys())}")
    print(f"current_candle_data keys: {list(aggregator.current_candle_data.keys())}")

    # Check stream URL generation
    streams = [f"{coin.lower()}@trade" for coin in test_coins]
    base = aggregator.ws_url.replace('/ws', '/stream') if '/ws' in aggregator.ws_url else aggregator.ws_url
    stream_url = f"{base}?streams={'/'.join(streams)}"

    print(f"\nGenerated stream URL: {stream_url}")

    # Start connection and check
    print("\nStarting connection for 5 seconds...")
    ws_task = asyncio.create_task(aggregator.start_connection())
    await asyncio.sleep(5)

    print(f"\nAfter 5s:")
    for coin in test_coins:
        candles = aggregator.candles_buffer.get(coin, [])
        print(f"  {coin}: {len(candles)} candles")

        # Check current_candle_data
        current = aggregator.current_candle_data.get(coin, {})
        trades_by_interval = aggregator._trades_by_interval.get(coin, {})
        print(f"    current_candle_data: candle_start_time={current.get('candle_start_time')}")
        print(f"    trades_by_interval intervals: {list(trades_by_interval.keys())[:3]}")

    await aggregator.stop()
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    asyncio.run(test_init())
