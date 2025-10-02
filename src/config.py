"""
Configuration module - direct settings without environment variables
"""
import os
from typing import List

# Volume filter settings
MIN_DAILY_VOLUME = 100000000

# Blacklist configuration - coins to exclude from trading
BLACKLISTED_COINS = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','LTCUSDT','ADAUSDT','DOGEUSDT','DOTUSDT','TRXUSDT']

# Strategy configuration
DEFAULT_STRATEGY_NAMES = ['xxx']
DEFAULT_SERVER_URLS = ['localhost', '192.168.1.100']

# Signal processing settings
DEFAULT_UPDATE_INTERVAL = 0.3
WARMUP_INTERVALS = 20  # Number of intervals to warm up before signals (matches signal_processor requirement)
CANDLE_INTERVAL_SECONDS = 10  # Each candle represents 10 seconds
# NOTE: TRADES_BUFFER_SECONDS removed - now using incremental candle building with rolling 100-candle limit

# WebSocket configuration
WS_URL = 'wss://fstream.binance.com/ws'
MAX_CONNECTIONS = 20
MAX_COINS_PER_CONNECTION = 10  # Binance allows 200 streams per connection

# HTTP request timeouts
HTTP_TIMEOUT = 30
CONNECT_TIMEOUT = 10

# Strategy server configuration
SERVER_PROTOCOL = 'http'
SERVER_PORT = 3001
SERVER_ENDPOINT = 'update_settings'

def build_strategy_url(server_ip: str) -> str:
    """Build complete strategy server URL from configuration"""
    return f"{SERVER_PROTOCOL}://{server_ip}:{SERVER_PORT}/{SERVER_ENDPOINT}"


def _format_number(value) -> str:
    """Format number avoiding scientific notation"""
    if value == 'N/A' or value is None:
        return 'N/A'
    try:
        num = float(value)
        # Use appropriate precision based on magnitude
        if abs(num) < 0.001:
            return f"{num:.8f}".rstrip('0').rstrip('.')
        elif abs(num) < 1:
            return f"{num:.6f}".rstrip('0').rstrip('.')
        elif abs(num) < 1000:
            return f"{num:.4f}".rstrip('0').rstrip('.')
        else:
            return f"{num:.2f}".rstrip('0').rstrip('.')
    except (ValueError, TypeError):
        return str(value)