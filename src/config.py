"""
Configuration module - direct settings without environment variables
"""
import os
import json
import logging
from datetime import datetime
from typing import List

# Volume filter settings
MIN_DAILY_VOLUME = 60000000

# Blacklist configuration - coins to exclude from trading
BLACKLISTED_COINS = ['BTCUSDT','BTCPERP','ETHUSDT','SOLUSDT','XRPUSDT','LTCUSDT','ADAUSDT','DOGEUSDT','DOTUSDT','TRXUSDT']

# Strategy configuration
DEFAULT_STRATEGY_NAMES = ['xxx']
DEFAULT_SERVER_URLS = ['localhost', '192.168.1.100']

# Signal processing settings
DEFAULT_UPDATE_INTERVAL = 0.3
WARMUP_INTERVALS = 1  # Number of intervals to warm up before signals
CANDLE_INTERVAL_SECONDS = 10  # Each candle represents 10 seconds
# NOTE: TRADES_BUFFER_SECONDS removed - now using incremental candle building with rolling 100-candle limit

# WebSocket configuration
WS_URL = 'wss://stream.bybit.com/v5/public/linear'
MAX_CONNECTIONS = 20
MAX_COINS_PER_CONNECTION = 4

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

# Logging configuration
LOG_LEVEL = 'INFO'

# Create logs directory if it doesn't exist
LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for clean structured logging"""

    def format(self, record):
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'message': record.getMessage()
        }

        # Add essential fields only
        if hasattr(record, 'coin'):
            log_entry['coin'] = record.coin
        if hasattr(record, 'signal_type'):
            log_entry['signal_type'] = record.signal_type
        if hasattr(record, 'failed_criteria'):
            log_entry['failed_criteria'] = record.failed_criteria

        return json.dumps(log_entry, ensure_ascii=False)

def setup_logging():
    """Setup separated logging to different files and console"""

    # Create handlers for different log categories
    system_handler = logging.FileHandler(f'{LOGS_DIR}/system.json', encoding='utf-8')
    system_handler.setFormatter(JSONFormatter())
    system_handler.setLevel(logging.INFO)

    signals_handler = logging.FileHandler(f'{LOGS_DIR}/signals.json', encoding='utf-8')
    signals_handler.setFormatter(JSONFormatter())
    signals_handler.setLevel(logging.INFO)

    websocket_handler = logging.FileHandler(f'{LOGS_DIR}/websocket.json', encoding='utf-8')
    websocket_handler.setFormatter(JSONFormatter())
    websocket_handler.setLevel(logging.INFO)

    # Create console handler with simple format
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    console_handler.setLevel(logging.INFO)

    # Configure root logger (system events)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = []  # Clear existing handlers
    root_logger.addHandler(system_handler)
    root_logger.addHandler(console_handler)

    # Configure signals logger
    signals_logger = logging.getLogger('signals')
    signals_logger.setLevel(logging.INFO)
    signals_logger.handlers = []
    signals_logger.addHandler(signals_handler)
    signals_logger.addHandler(console_handler)  # Also to console
    signals_logger.propagate = False  # Don't propagate to root

    # Configure websocket logger
    ws_logger = logging.getLogger('websocket')
    ws_logger.setLevel(logging.INFO)
    ws_logger.handlers = []
    ws_logger.addHandler(websocket_handler)
    ws_logger.addHandler(console_handler)  # Also to console
    ws_logger.propagate = False  # Don't propagate to root

    # Disable debug logs from external libraries
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

def log_signal(coin: str, signal: bool, signal_data: dict = None):
    """Log trading signal in clean structured format"""

    # Skip all warmup and insufficient data logs from signals
    if not signal and signal_data and 'criteria' in signal_data:
        criteria = signal_data['criteria']
        validation_error = criteria.get('validation_error', '')
        if validation_error:  # Skip all validation errors (warmup, insufficient data)
            return

    # Only log actual trading signals (BUY or conditions met)
    logger = logging.getLogger('signals')

    signal_text = "BUY" if signal else "NO SIGNAL"
    message = f"{coin} - {signal_text}"

    # Add detailed criteria for signals
    if signal_data and 'criteria' in signal_data:
        criteria = signal_data['criteria']

        if criteria.get('validation_error'):
            message += f" ({criteria['validation_error']})"
        elif 'criteria_details' in criteria:
            # Show detailed values for all criteria
            details = criteria['criteria_details']
            if details:  # Ensure details is not None
                parts = []

                for name, data in details.items():
                    status = "PASS" if data.get('passed', False) else "FAIL"
                    current = data.get('current', 0)
                    threshold = data.get('threshold', 0)
                    parts.append(f"{name}:{status}({current}/{threshold})")

                if parts:
                    message += f" [{', '.join(parts)}]"

    # Create clean log record with minimal data
    record = logging.LogRecord(
        name=logger.name,
        level=logging.INFO,
        pathname='',
        lineno=0,
        msg=message,
        args=(),
        exc_info=None
    )

    # Add only essential fields for JSON
    record.coin = coin
    record.signal_type = signal_text
    if not signal and signal_data and 'criteria' in signal_data and signal_data['criteria']:
        record.failed_criteria = [k for k, v in signal_data['criteria'].items()
                                 if k in ['low_vol', 'narrow_rng', 'high_natr', 'growth_filter'] and not v]

    # Use the signals logger instead of handle
    signals_logger = logging.getLogger('signals')
    signals_logger.info(message)

def log_connection_info(coin_count: int):
    """Log connection information"""
    logger = logging.getLogger()  # System logger
    logger.info(f"WebSocket connections established for {coin_count} coins")

def log_warmup_progress(current_candles: int, required_candles: int):
    """Log warmup progress periodically"""
    logger = logging.getLogger()  # System logger
    progress_pct = (current_candles / required_candles) * 100 if required_candles > 0 else 0
    logger.info(f"Warmup progress: {current_candles}/{required_candles} candles ({progress_pct:.0f}%)")

def log_reconnect(connection_id: str, reason: str = ""):
    """Log reconnection attempts"""
    logger = logging.getLogger('websocket')
    message = f"WebSocket reconnecting: {connection_id}"
    if reason:
        message += f" - {reason}"
    logger.warning(message)

def log_websocket_event(message: str, level: str = 'INFO'):
    """Log websocket events"""
    logger = logging.getLogger('websocket')
    if level.upper() == 'WARNING':
        logger.warning(message)
    elif level.upper() == 'ERROR':
        logger.error(message)
    else:
        logger.info(message)