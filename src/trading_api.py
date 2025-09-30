"""
Module for interacting with trading APIs (Bybit)
Includes HTTP timeouts and comprehensive error handling
"""
import requests
# import logging
from typing import List, Dict, Optional
from .config import MIN_DAILY_VOLUME, HTTP_TIMEOUT, CONNECT_TIMEOUT, BLACKLISTED_COINS

# Configure logging
# logger = logging.getLogger(__name__)

# Configure requests session with proper timeouts
session = requests.Session()
session.timeout = (CONNECT_TIMEOUT, HTTP_TIMEOUT)  # (connect_timeout, read_timeout)

def get_recent_trades(symbol: str, limit: int = 100) -> Optional[List[Dict]]:
    """
    Get recent trades for a symbol from Bybit API with timeouts
    """
    url = "https://api.bybit.com/v5/market/recent-trade"
    params = {
        'category': 'linear',
        'symbol': symbol,
        'limit': limit
    }

    try:
        response = session.get(url, params=params, timeout=(CONNECT_TIMEOUT, HTTP_TIMEOUT))
        response.raise_for_status()  # Raise an exception for bad status codes

        data = response.json()
        if data['retCode'] == 0:
            trades = []
            for trade in data['result']['list']:
                trades.append({
                    'timestamp': int(trade['time']),
                    'price': float(trade['price']),
                    'size': float(trade['size']),
                    'side': trade['side']
                })
            return trades
        else:
            # logger.error(f"API Error for {symbol}: {data['retMsg']}")
            return None

    except requests.exceptions.Timeout:
        # logger.error(f"Timeout error for {symbol} (timeout: {HTTP_TIMEOUT}s)")
        return None
    except requests.exceptions.ConnectionError as e:
        # logger.error(f"Connection error for {symbol}: {e}")
        return None
    except requests.exceptions.HTTPError as e:
        # logger.error(f"HTTP error for {symbol}: {e}")
        return None
    except ValueError as e:
        # logger.error(f"JSON decode error for {symbol}: {e}")
        return None
    except Exception as e:
        # logger.error(f"Unexpected error for {symbol}: {type(e).__name__}: {e}")
        return None


def get_futures_symbols() -> List[str]:
    """
    Get list of all futures symbols from Bybit with timeouts
    """
    url = "https://api.bybit.com/v5/market/tickers"
    params = {
        'category': 'linear'
    }

    try:
        response = session.get(url, params=params, timeout=(CONNECT_TIMEOUT, HTTP_TIMEOUT))
        response.raise_for_status()

        data = response.json()
        if data['retCode'] == 0:
            symbols = [item['symbol'] for item in data['result']['list']]
            # logger.info(f"Retrieved {len(symbols)} symbols from Bybit")
            return symbols
        else:
            # logger.error(f"API Error getting symbols: {data['retMsg']}")
            return []

    except requests.exceptions.Timeout:
        # logger.error(f"Timeout error getting symbols (timeout: {HTTP_TIMEOUT}s)")
        return []
    except requests.exceptions.ConnectionError as e:
        # logger.error(f"Connection error getting symbols: {e}")
        return []
    except requests.exceptions.HTTPError as e:
        # logger.error(f"HTTP error getting symbols: {e}")
        return []
    except ValueError as e:
        # logger.error(f"JSON decode error getting symbols: {e}")
        return []
    except Exception as e:
        # logger.error(f"Unexpected error getting symbols: {type(e).__name__}: {e}")
        return []


def get_all_symbols_by_volume(min_volume: float = MIN_DAILY_VOLUME) -> List[str]:
    """
    Get all symbols from Bybit and filter them by volume
    """
    # Get all available symbols
    all_symbols = get_futures_symbols()
    if not all_symbols:
        # logger.warning("No symbols retrieved, returning empty list")
        return []

    # Create a map of symbol to volume for filtering
    url = "https://api.bybit.com/v5/market/tickers"
    params = {
        'category': 'linear'
    }

    try:
        response = session.get(url, params=params, timeout=(CONNECT_TIMEOUT, HTTP_TIMEOUT))
        response.raise_for_status()

        data = response.json()
        if data['retCode'] == 0:
            volume_map = {}
            for item in data['result']['list']:
                try:
                    # Volume is typically in the 'turnover24h' field (24h turnover/volume)
                    volume_24h = float(item.get('turnover24h', 0))
                    volume_map[item['symbol']] = volume_24h
                except (ValueError, TypeError):
                    volume_map[item['symbol']] = 0

            # Filter symbols that have volume >= min_volume and not in blacklist
            filtered_by_volume = [symbol for symbol in all_symbols if volume_map.get(symbol, 0) >= min_volume]
            filtered_symbols = [symbol for symbol in filtered_by_volume if symbol not in BLACKLISTED_COINS]

            blacklisted_count = len(filtered_by_volume) - len(filtered_symbols)
            # logger.info(f"Filtered {len(filtered_symbols)} of {len(all_symbols)} symbols by volume (min: {min_volume}), excluded {blacklisted_count} blacklisted coins")
            return filtered_symbols
        else:
            # logger.error(f"API Error getting ticker data for volume filter: {data['retMsg']}")
            return []  # Return empty list if filtering fails

    except requests.exceptions.Timeout:
        # logger.error(f"Timeout error getting ticker data for volume filter (timeout: {HTTP_TIMEOUT}s)")
        return []
    except requests.exceptions.ConnectionError as e:
        # logger.error(f"Connection error getting ticker data for volume filter: {e}")
        return []
    except requests.exceptions.HTTPError as e:
        # logger.error(f"HTTP error getting ticker data for volume filter: {e}")
        return []
    except ValueError as e:
        # logger.error(f"JSON decode error getting ticker data for volume filter: {e}")
        return []
    except Exception as e:
        # logger.error(f"Unexpected error getting ticker data for volume filter: {type(e).__name__}: {e}")
        return []