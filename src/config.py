"""
Configuration module - direct settings without environment variables
"""
import os
import json
# import logging
from datetime import datetime
from typing import List

# Volume filter settings
MIN_DAILY_VOLUME = 150000000

# Blacklist configuration - coins to exclude from trading
BLACKLISTED_COINS = ['BTCUSDT','BTCPERP','ETHUSDT','SOLUSDT','XRPUSDT','LTCUSDT','ADAUSDT','DOGEUSDT','DOTUSDT','TRXUSDT']

# Strategy configuration
DEFAULT_STRATEGY_NAMES = ['xxx']
DEFAULT_SERVER_URLS = ['localhost', '192.168.1.100']

# Signal processing settings
DEFAULT_UPDATE_INTERVAL = 0.3
WARMUP_INTERVALS = 25  # Number of intervals to warm up before signals
CANDLE_INTERVAL_SECONDS = 10  # Each candle represents 10 seconds
# NOTE: TRADES_BUFFER_SECONDS removed - now using incremental candle building with rolling 100-candle limit

# WebSocket configuration
WS_URL = 'wss://stream.bybit.com/v5/public/linear'
MAX_CONNECTIONS = 20
MAX_COINS_PER_CONNECTION = 3

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


class JSONFormatter:
    """Custom JSON formatter for structured logging to files"""

    def format(self, record):
        """Format log record as JSON"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'message': record.getMessage()
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


def log_signal(coin: str, signal: bool, signal_data: dict = None):
    """
    Log trading signal with full details for all criteria
    Skips warmup/insufficient data logs but logs ALL post-warmup signals
    """
    import logging
    
    if signal_data and 'validation_error' in signal_data:
        validation_error = signal_data['validation_error']
        if validation_error and validation_error.startswith('Warmup:'):
            # Skip warmup logs
            return
    
    logger = logging.getLogger(__name__)
    
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
                if details.get('passed', False):
                    passed_criteria.append(f"{crit_name}({details.get('current', 'N/A')})")
                else:
                    failed_criteria.append(f"{crit_name}({details.get('current', 'N/A')} vs {details.get('threshold', 'N/A')})")
            
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
    """Log connection information"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔗 Connected to WebSocket for {coin_count} coins")


def log_warmup_progress(current_candles: int, required_candles: int):
    """Log warmup progress periodically"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔥 Warmup: {current_candles}/{required_candles} candles completed")


def log_reconnect(connection_id: str, reason: str = ""):
    """Log reconnection attempts"""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"🔄 Reconnecting {connection_id}: {reason}")


def log_websocket_event(message: str, level: str = 'INFO'):
    """Log websocket events"""
    import logging
    logger = logging.getLogger(__name__)
    if level == 'WARNING':
        logger.warning(f"📡 {message}")
    else:
        logger.info(f"📡 {message}")


def log_new_candle(coin: str, candle_data: dict):
    """Log new candle data"""
    import logging
    from datetime import datetime
    logger = logging.getLogger(__name__)
    
    if candle_data:
        timestamp = datetime.fromtimestamp(candle_data['timestamp']/1000).strftime('%H:%M:%S')
        logger.info(f"🕯️  {coin} | {timestamp} | O:{candle_data['open']:.4f} H:{candle_data['high']:.4f} L:{candle_data['low']:.4f} C:{candle_data['close']:.4f} V:{candle_data['volume']:.2f}")