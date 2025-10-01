"""
Test script for Binance Futures API migration (Sprint 1+2)
Tests get_futures_symbols, get_all_symbols_by_volume, get_recent_trades
"""
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.trading_api import get_futures_symbols, get_all_symbols_by_volume, get_recent_trades

def test_get_futures_symbols():
    """Test getting all futures symbols from Binance"""
    print("=" * 60)
    print("TEST 1: get_futures_symbols()")
    print("=" * 60)

    symbols = get_futures_symbols()

    if symbols:
        print(f"✅ SUCCESS: Retrieved {len(symbols)} symbols")
        print(f"First 10 symbols: {symbols[:10]}")

        # Check for common symbols
        common_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        found = [s for s in common_symbols if s in symbols]
        print(f"Common symbols found: {found}")
        return True
    else:
        print("❌ FAIL: No symbols retrieved")
        return False

def test_get_all_symbols_by_volume():
    """Test filtering symbols by volume"""
    print("\n" + "=" * 60)
    print("TEST 2: get_all_symbols_by_volume()")
    print("=" * 60)

    # Test with default MIN_DAILY_VOLUME = 30M
    symbols = get_all_symbols_by_volume()

    if symbols:
        print(f"✅ SUCCESS: Retrieved {len(symbols)} symbols with volume >= 30M")
        print(f"First 10 filtered symbols: {symbols[:10]}")
        return True
    else:
        print("❌ FAIL: No symbols retrieved")
        return False

def test_get_recent_trades():
    """Test getting recent trades for a symbol"""
    print("\n" + "=" * 60)
    print("TEST 3: get_recent_trades('BTCUSDT')")
    print("=" * 60)

    trades = get_recent_trades('BTCUSDT', limit=5)

    if trades:
        print(f"✅ SUCCESS: Retrieved {len(trades)} trades")
        print("\nSample trades:")
        for i, trade in enumerate(trades[:3]):
            print(f"  Trade {i+1}: price={trade['price']}, size={trade['size']}, "
                  f"side={trade['side']}, timestamp={trade['timestamp']}")

        # Validate structure
        required_fields = ['timestamp', 'price', 'size', 'side']
        valid = all(field in trades[0] for field in required_fields)
        if valid:
            print("✅ Trade structure valid (timestamp, price, size, side)")
        else:
            print("❌ Trade structure invalid")
            return False

        return True
    else:
        print("❌ FAIL: No trades retrieved")
        return False

def main():
    """Run all tests"""
    print("\nStarting Binance API Tests (Sprint 1+2)\n")

    results = []
    results.append(("get_futures_symbols", test_get_futures_symbols()))
    results.append(("get_all_symbols_by_volume", test_get_all_symbols_by_volume()))
    results.append(("get_recent_trades", test_get_recent_trades()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED - Sprint 1+2 Complete!")
    else:
        print("SOME TESTS FAILED - Review errors above")
    print("=" * 60)

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
