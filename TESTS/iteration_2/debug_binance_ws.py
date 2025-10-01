"""
Debug test: Check Binance WebSocket URL and message format
"""
import sys
import asyncio
import websockets
import json

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

async def test_raw_websocket():
    """Test raw WebSocket connection to Binance"""
    # Test URL
    url = "wss://fstream.binance.com/stream?streams=btcusdt@trade"

    print(f"Connecting to: {url}")

    try:
        async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
            print("✅ Connected successfully!")
            print("Waiting for messages (10 seconds)...\n")

            message_count = 0
            start = asyncio.get_event_loop().time()

            while asyncio.get_event_loop().time() - start < 10:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(msg)
                    message_count += 1

                    if message_count <= 3:
                        print(f"Message {message_count}:")
                        print(json.dumps(data, indent=2))
                        print()

                except asyncio.TimeoutError:
                    continue

            print(f"\n✅ Received {message_count} messages total")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_raw_websocket())
