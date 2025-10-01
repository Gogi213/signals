"""
Iteration 2 - Audit #1: Collect fresh logs for hypothesis generation
Run main application with 4-minute timeout (longer than warmup)
"""
import asyncio
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from main import main

async def run_with_timeout():
    """Run main() with 4-minute timeout"""
    print("Starting application for 4-minute log collection...")
    print("Warmup period: ~100 seconds (10 candles * 10s)")
    print("Will run for 240 seconds total")
    print()

    start_time = time.time()

    try:
        # Run main() with 4-minute (240 second) timeout
        await asyncio.wait_for(main(), timeout=240.0)
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        print(f"\nTimeout reached after {elapsed:.1f}s - logs collected")
        print(f"Logs saved to: logs/system.json, logs/signals.json, logs/websocket.json")
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f"\nStopped after {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\nError after {elapsed:.1f}s: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(run_with_timeout())
