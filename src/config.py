"""
Configuration module with environment variable support
FIXED: Replaced hardcoded values with environment variables
"""
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Volume filter settings
MIN_DAILY_VOLUME = float(os.getenv('MIN_DAILY_VOLUME', '500000'))

# Strategy configuration
DEFAULT_STRATEGY_NAMES = os.getenv('STRATEGY_NAMES', 'xxx').split(',')
DEFAULT_SERVER_URLS = os.getenv('SERVER_URLS', 'localhost').split(',')

# Signal processing settings
DEFAULT_UPDATE_INTERVAL = float(os.getenv('SIGNAL_UPDATE_INTERVAL', '0.3'))
TRADES_BUFFER_SECONDS = int(os.getenv('TRADES_BUFFER_SECONDS', '20'))

# WebSocket configuration
WS_URL = os.getenv('WS_URL', 'wss://stream.bybit.com/v5/public/linear')
MAX_CONNECTIONS = int(os.getenv('MAX_CONNECTIONS', '12'))
MAX_COINS_PER_CONNECTION = int(os.getenv('MAX_COINS_PER_CONNECTION', '20'))

# HTTP request timeouts
HTTP_TIMEOUT = int(os.getenv('HTTP_TIMEOUT', '30'))
CONNECT_TIMEOUT = int(os.getenv('CONNECT_TIMEOUT', '10'))

# Trading bot configuration
BOT_PORTS = [int(port.strip()) for port in os.getenv('BOT_PORTS', '3001').split(',')]

# Logging configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()