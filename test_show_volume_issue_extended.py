"""
Extended test to demonstrate the volume issue with real trades
Runs for 3 minutes to increase chances of catching the issue
"""
import asyncio
import sys
import os
from datetime import datetime
from src.websocket_handler import TradeWebSocket
from src.config import setup_logging, start_candle_logging

# Redirect all output to file AND console
output_file = open('test_show_volume_issue_extended_output.txt', 'w', encoding='utf-8', buffering=1)

class TeeOutput:
    def __init__(self, file):
        self.file = file
        self.stdout = sys.stdout
        
    def write(self, text):
        self.stdout.write(text)
        self.stdout.flush()
        self.file.write(text)
        self.file.flush()
        
    def flush(self):
        self.stdout.flush()
        self.file.flush()

sys.stdout = TeeOutput(output_file)
sys.stderr = TeeOutput(output_file)

async def main():
    setup_logging()
    start_candle_logging()
    
    # Use coins that had L=0 issues in previous tests
    test_coins = [
        'ALPINEUSDT',  # Known to have L=0 issues
        'ASTERUSDT',
        'BIOUSDT',
        'TRUTHUSDT',
        'SOMIUSDT',
        'DASHUSDT',
        'ZECUSDT',
        'EDENUSDT',
        'STBLUSDT',
        'XPLUSDT',
        'EIGENUSDT',
        'AVNTUSDT',
        'FARTCOINUSDT',
        'BARDUSDT' # Known to have L=0 issues
    ]
    
    print(f"\n{'='*80}")
    print(f"EXTENDED VOLUME ISSUE DEMONSTRATION TEST")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Coins: {test_coins}")
    print(f"Duration: 180 seconds (18 candles per coin)")
    print(f"{'='*80}\n")
    print("📌 WATCH FOR: Candles with L=0 but non-zero volume")
    print("This indicates a bug in the candle aggregation process\n")
    print("Starting WebSocket connections...\n", flush=True)
    
    aggregator = TradeWebSocket(test_coins)
    ws_task = asyncio.create_task(aggregator.start_connection())
    
    # Wait 180 seconds (3 minutes)
    print("Waiting 180 seconds for data collection...\n", flush=True)
    await asyncio.sleep(180)
    
    # Analyze
    print(f"\n{'='*80}")
    print(f"VOLUME ISSUE ANALYSIS")
    print(f"{'='*80}\n")
    
    total_issues = 0
    total_candles = 0
    
    for coin in test_coins:
        print(f"\n{coin}:")
        print(f"{'-'*60}")
        
        if coin in aggregator.candles_buffer:
            candles = aggregator.candles_buffer[coin]
            print(f"  Candles: {len(candles)} candles")
            total_candles += len(candles)
            
            issue_found = False
            zero_low_count = 0
            zero_vol_count = 0
            
            for i, candle in enumerate(candles):
                # Check for the issue: L=0 but volume > 0
                if candle['low'] == 0 and candle['volume'] > 0:
                    issue_found = True
                    total_issues += 1
                    print(f"    ❌ ISSUE FOUND in Candle {i+1}:")
                    print(f"       O={candle['open']:.6f}, H={candle['high']:.6f}, L={candle['low']:.6f}, C={candle['close']:.6f}, V={candle['volume']:.6f}")
                    print(f"       ⚠️  Low is 0 but volume is non-zero! This is a bug!")
                elif candle['low'] == 0:
                    zero_low_count += 1
                    print(f"    ⚠️  Candle {i+1}: L=0 (forward-fill), V={candle['volume']:.6f}")
                elif candle['volume'] == 0:
                    zero_vol_count += 1
                    print(f"    ⚠️  Candle {i+1}: V=0 (forward-fill), L={candle['low']:.6f}")
            
            if not issue_found:
                print(f"    ✅ No volume issues detected")
            
            if zero_low_count > 0:
                print(f"    📊 Summary: {zero_low_count} candles with L=0")
            if zero_vol_count > 0:
                print(f"    📊 Summary: {zero_vol_count} candles with V=0")
        else:
            print(f"  No candles data")
    
    print(f"\n{'='*80}")
    print(f"EXTENDED TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Total candles analyzed: {total_candles}")
    print(f"Total issues found: {total_issues}")
    print(f"Issue rate: {(total_issues/total_candles*100):.2f}%" if total_candles > 0 else "N/A")
    print(f"{'='*80}")
    print(f"TEST COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output saved to: test_show_volume_issue_extended_output.txt")
    print(f"{'='*80}\n")
    
    output_file.flush()
    output_file.close()
    
    # Force exit
    os._exit(0)

if __name__ == "__main__":
    asyncio.run(main())