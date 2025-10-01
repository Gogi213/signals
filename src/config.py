"""
Configuration module - direct settings without environment variables
"""
import os
import json
# import logging
from datetime import datetime
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

# Logging configuration
LOG_LEVEL = 'INFO'
LOGS_DIR = 'logs'

# Create logs directory if it doesn't exist
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Async logging queue for candles (to prevent time drift)
import asyncio
import queue
_candle_log_queue = queue.Queue()
_candle_log_task = None


class JSONFormatter:
    """Custom JSON formatter for structured logging to files"""

    def format(self, record):
        """Format log record as JSON"""
        # Get message - handle both callable and string
        if hasattr(record, 'getMessage') and callable(record.getMessage):
            message = record.getMessage()
        elif hasattr(record, 'message'):
            message = record.message
        else:
            message = str(record)

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': getattr(record, 'levelname', 'INFO'),
            'message': message
        }

        # Add custom fields if present
        if hasattr(record, 'coin'):
            log_entry['coin'] = record.coin
        if hasattr(record, 'signal_type'):
            log_entry['signal_type'] = record.signal_type
        if hasattr(record, 'criteria_details'):
            log_entry['criteria_details'] = record.criteria_details
        if hasattr(record, 'failed_criteria'):
            log_entry['failed_criteria'] = record.failed_criteria
        if hasattr(record, 'candle_data'):
            log_entry['candle_data'] = record.candle_data

        return json.dumps(log_entry, ensure_ascii=False)


class JSONFileHandler:
    """Custom file handler that writes JSON formatted logs"""

    def __init__(self, filename):
        """Initialize handler with filename"""
        self.filename = filename
        self.formatter = JSONFormatter()

    def emit(self, record):
        """Write log record to file"""
        try:
            log_line = self.formatter.format(record)
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
                f.flush()  # Force write to disk
        except Exception:
            pass  # Silently ignore logging errors


def setup_logging():
    """Setup logging - console only (file logging done via custom handlers)"""
    import logging

    # Console formatter
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # Setup root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)


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


def log_signal(coin: str, signal: bool, signal_data: dict = None, warmup_complete: bool = False):
    """
    Log trading signal with full details for all criteria
    Only logs signals after warmup is complete
    Logs signals that have real trading activity (skips forward-fill and invalid candles)
    Also writes to logs/signals.json
    """
    import logging

    # Skip if warmup not complete
    if not warmup_complete:
        return

    # Skip validation errors (forward-fill, invalid candles)
    # These are not useful for signal analysis - market is inactive
    if signal_data:
        validation_error = signal_data.get('validation_error', '')
        if validation_error:
            return  # Skip: "No trades in last candle (forward-fill)", "Invalid candle", etc.

        # Also check criteria-level validation_error
        if 'criteria' in signal_data:
            criteria = signal_data['criteria']
            criteria_error = criteria.get('validation_error', '')
            if criteria_error:
                return  # Skip: "Warmup", "Insufficient data", etc.

    logger = logging.getLogger(__name__)

    # File logging to signals.json (only for valid, active signals)
    file_handler = JSONFileHandler(os.path.join(LOGS_DIR, 'signals.json'))
    log_record = type('obj', (object,), {
        'levelname': 'INFO',
        'getMessage': lambda self: f"Signal for {coin}: {signal}",
        'coin': coin,
        'signal_type': 'true' if signal else 'false',
        'criteria_details': signal_data.get('criteria', {}) if signal_data else {}
    })()
    file_handler.emit(log_record)
    
    if signal_data and 'criteria' in signal_data:
        criteria = signal_data['criteria']
        candle_count = signal_data.get('candle_count', 0)
        
        # Prepare criteria details
        if 'criteria_details' in criteria:
            # Detailed criteria logging
            criteria_details = criteria['criteria_details']
            failed_criteria = []
            passed_criteria = []
            
            for crit_name, details in criteria_details.items():
                current_val = _format_number(details.get('current', 'N/A'))
                threshold_val = _format_number(details.get('threshold', 'N/A'))

                if details.get('passed', False):
                    passed_criteria.append(f"{crit_name}({current_val})")
                else:
                    failed_criteria.append(f"{crit_name}({current_val} vs {threshold_val})")
            
            # Format the log message
            status = "✅ SIGNAL" if signal else "❌ NO SIGNAL"
            passed_str = ", ".join(passed_criteria) if passed_criteria else "none"
            failed_str = ", ".join(failed_criteria) if failed_criteria else "none"
            
            logger.info(f"📊 {status} for {coin} | Candles: {candle_count} | "
                       f"Passed: [{passed_str}] | Failed: [{failed_str}]")
        else:
            # Simple criteria logging
            low_vol = criteria.get('low_vol', False)
            narrow_rng = criteria.get('narrow_rng', False)
            high_natr = criteria.get('high_natr', False)
            growth_filter = criteria.get('growth_filter', False)
            
            failed_criteria = []
            passed_criteria = []
            
            if low_vol: passed_criteria.append("low_vol");
            else: failed_criteria.append("low_vol")
            if narrow_rng: passed_criteria.append("narrow_rng");
            else: failed_criteria.append("narrow_rng")
            if high_natr: passed_criteria.append("high_natr");
            else: failed_criteria.append("high_natr")
            if growth_filter: passed_criteria.append("growth_filter");
            else: failed_criteria.append("growth_filter")
            
            status = "✅ SIGNAL" if signal else "❌ NO SIGNAL"
            passed_str = ", ".join(passed_criteria) if passed_criteria else "none"
            failed_str = ", ".join(failed_criteria) if failed_criteria else "none"
            
            logger.info(f"📊 {status} for {coin} | Candles: {candle_count} | "
                       f"Passed: [{passed_str}] | Failed: [{failed_str}]")
    else:
        status = "✅ SIGNAL" if signal else "❌ NO SIGNAL"
        logger.info(f"📊 {status} for {coin}")


def log_connection_info(coin_count: int):
    """Log connection information - console and file"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔗 Connected to WebSocket for {coin_count} coins")

    # File logging to system.json
    file_handler = JSONFileHandler(os.path.join(LOGS_DIR, 'system.json'))
    log_record = type('obj', (object,), {
        'levelname': 'INFO',
        'getMessage': lambda self: f"Connected to WebSocket for {coin_count} coins"
    })()
    file_handler.emit(log_record)


def log_warmup_progress(current_candles: int, required_candles: int):
    """Log warmup progress periodically - console and file"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔥 Warmup: {current_candles}/{required_candles} candles completed")

    # File logging to system.json
    file_handler = JSONFileHandler(os.path.join(LOGS_DIR, 'system.json'))
    log_record = type('obj', (object,), {
        'levelname': 'INFO',
        'getMessage': lambda self: f"Warmup progress: {current_candles}/{required_candles}"
    })()
    file_handler.emit(log_record)


def log_reconnect(connection_id: str, reason: str = ""):
    """Log reconnection attempts - console and file"""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"🔄 Reconnecting {connection_id}: {reason}")

    # File logging to websocket.json
    file_handler = JSONFileHandler(os.path.join(LOGS_DIR, 'websocket.json'))
    log_record = type('obj', (object,), {
        'levelname': 'WARNING',
        'getMessage': lambda self: f"Reconnecting {connection_id}: {reason}"
    })()
    file_handler.emit(log_record)


def log_websocket_event(message: str, level: str = 'INFO'):
    """Log websocket events - console and file"""
    import logging
    logger = logging.getLogger(__name__)
    if level == 'WARNING':
        logger.warning(f"📡 {message}")
    else:
        logger.info(f"📡 {message}")

    # File logging to websocket.json
    file_handler = JSONFileHandler(os.path.join(LOGS_DIR, 'websocket.json'))
    log_record = type('obj', (object,), {
        'levelname': level,
        'getMessage': lambda self: message
    })()
    file_handler.emit(log_record)


async def _candle_log_worker():
    """Background worker that processes candle logs asynchronously"""
    import logging
    from datetime import datetime

    logger = logging.getLogger(__name__)
    file_handler = JSONFileHandler(os.path.join(LOGS_DIR, 'websocket.json'))

    while True:
        try:
            # Process all available logs without blocking
            batch = []
            while not _candle_log_queue.empty():
                try:
                    batch.append(_candle_log_queue.get_nowait())
                except queue.Empty:
                    break

            # Sort by sequence to preserve order
            batch = sorted(batch, key=lambda x: x[1].get('_sequence', 0))

            # Write batch to file
            for coin, candle_data in batch:
                # Console log
                timestamp = datetime.fromtimestamp(candle_data['timestamp']/1000).strftime('%H:%M:%S')
                logger.info(f"🕯️  {coin} | {timestamp} | O:{candle_data['open']:.4f} H:{candle_data['high']:.4f} L:{candle_data['low']:.4f} C:{candle_data['close']:.4f} V:{candle_data['volume']:.2f}")

                # File log
                log_record = type('obj', (object,), {
                    'levelname': 'INFO',
                    'getMessage': lambda self: f"Candle for {coin}",
                    'coin': coin,
                    'candle_data': candle_data
                })()
                file_handler.emit(log_record)

            # Sleep briefly to avoid busy-wait
            await asyncio.sleep(0.5)

        except Exception as e:
            # Don't crash the worker on errors
            await asyncio.sleep(1)


def start_candle_logging():
    """Start the async candle logging worker"""
    global _candle_log_task
    if _candle_log_task is None:
        try:
            loop = asyncio.get_running_loop()
            _candle_log_task = loop.create_task(_candle_log_worker())
        except RuntimeError:
            # Event loop not running yet - will be started later
            pass


def log_new_candle(coin: str, candle_data: dict):
    """Log new candle data - async via queue to prevent time drift"""
    if candle_data:
        # Queue for async processing - non-blocking
        try:
            _candle_log_queue.put_nowait((coin, candle_data))
        except queue.Full:
            pass  # Skip if queue is full (shouldn't happen)