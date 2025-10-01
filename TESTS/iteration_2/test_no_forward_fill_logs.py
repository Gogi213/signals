"""
Test: Forward-fill signals should NOT be logged to signals.json
"""
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.config import log_signal


def test_forward_fill_not_logged():
    """Test that forward-fill signals are NOT logged"""
    print("=" * 70)
    print("TEST: Forward-Fill Signals NOT Logged")
    print("=" * 70)

    # Mock file handler to capture logs
    logged_signals = []

    class MockFileHandler:
        def __init__(self, filename):
            pass

        def emit(self, record):
            logged_signals.append(record)

    # Patch JSONFileHandler
    import src.config
    original_handler = src.config.JSONFileHandler
    src.config.JSONFileHandler = MockFileHandler

    # Test case 1: Forward-fill signal (should NOT log)
    print("\n[Test 1] Forward-fill signal (validation_error)...")
    signal_data_ff = {
        'validation_error': 'No trades in last candle (forward-fill)',
        'candle_count': 50,
        'criteria': {}
    }
    log_signal('TESTCOIN', False, signal_data_ff, warmup_complete=True)

    if len(logged_signals) == 0:
        print("✅ PASS: Forward-fill NOT logged")
    else:
        print("❌ FAIL: Forward-fill WAS logged!")
        return False

    # Test case 2: Invalid candle (should NOT log)
    print("\n[Test 2] Invalid candle signal...")
    signal_data_invalid = {
        'validation_error': 'Invalid candle 45: high < low',
        'candle_count': 50,
        'criteria': {}
    }
    log_signal('TESTCOIN', False, signal_data_invalid, warmup_complete=True)

    if len(logged_signals) == 0:
        print("✅ PASS: Invalid candle NOT logged")
    else:
        print("❌ FAIL: Invalid candle WAS logged!")
        return False

    # Test case 3: Valid signal (SHOULD log)
    print("\n[Test 3] Valid signal (no validation_error)...")
    signal_data_valid = {
        'candle_count': 50,
        'criteria': {
            'low_vol': True,
            'narrow_rng': False,
            'high_natr': True,
            'growth_filter': True
        }
    }
    log_signal('TESTCOIN', False, signal_data_valid, warmup_complete=True)

    if len(logged_signals) == 1:
        print("✅ PASS: Valid signal WAS logged")
    else:
        print(f"❌ FAIL: Valid signal NOT logged (count: {len(logged_signals)})")
        return False

    # Restore original handler
    src.config.JSONFileHandler = original_handler

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = test_forward_fill_not_logged()
    sys.exit(0 if success else 1)
