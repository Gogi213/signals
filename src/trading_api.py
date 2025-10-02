"""
Module for interacting with trading APIs (Binance Futures)
Includes HTTP timeouts and comprehensive error handling
"""
import requests
from typing import List, Dict, Optional
from .config import MIN_DAILY_VOLUME, HTTP_TIMEOUT, CONNECT_TIMEOUT, BLACKLISTED_COINS

# Configure requests session with proper timeouts
session = requests.Session()
session.timeout = (CONNECT_TIMEOUT, HTTP_TIMEOUT)  # (connect_timeout, read_timeout)

# Binance Futures API base URL
BINANCE_FUTURES_BASE = "https://fapi.binance.com"

def get_recent_trades(symbol: str, limit: int = 100) -> Optional[List[Dict]]:
    """
    Get recent trades for a symbol from Binance Futures API with timeouts
    """
    url = f"{BINANCE_FUTURES_BASE}/fapi/v1/trades"
    params = {
        'symbol': symbol,
        'limit': limit
    }

    try:
        response = session.get(url, params=params, timeout=(CONNECT_TIMEOUT, HTTP_TIMEOUT))
        response.raise_for_status()

        data = response.json()
        # Binance returns array directly (no wrapper)
        trades = []
        for trade in data:
            trades.append({
                'timestamp': int(trade['time']),
                'price': float(trade['price']),
                'size': float(trade['qty']),
                'side': 'Sell' if trade['isBuyerMaker'] else 'Buy'  # Invert: buyerMaker means sell order filled
            })
        return trades

    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.HTTPError:
        return None
    except (ValueError, KeyError):
        return None
    except Exception:
        return None


def get_futures_symbols() -> List[str]:
    """
    Get list of all futures symbols from Binance with timeouts
    Filters only USDT pairs
    """
    url = f"{BINANCE_FUTURES_BASE}/fapi/v1/exchangeInfo"

    try:
        response = session.get(url, timeout=(CONNECT_TIMEOUT, HTTP_TIMEOUT))
        response.raise_for_status()

        data = response.json()
        symbols = [
            item['symbol'] for item in data['symbols']
            if item['status'] == 'TRADING' and item['symbol'].endswith('USDT')
        ]
        return symbols

    except requests.exceptions.Timeout:
        return []
    except requests.exceptions.ConnectionError:
        return []
    except requests.exceptions.HTTPError:
        return []
    except (ValueError, KeyError):
        return []
    except Exception:
        return []


def get_all_symbols_by_volume(min_volume: float = MIN_DAILY_VOLUME) -> List[str]:
    """
    Get all symbols from Binance and filter them by volume
    """
    all_symbols = get_futures_symbols()
    if not all_symbols:
        return []

    url = f"{BINANCE_FUTURES_BASE}/fapi/v1/ticker/24hr"

    try:
        response = session.get(url, timeout=(CONNECT_TIMEOUT, HTTP_TIMEOUT))
        response.raise_for_status()

        data = response.json()
        volume_map = {}
        for item in data:
            try:
                volume_24h = float(item.get('quoteVolume', 0))
                volume_map[item['symbol']] = volume_24h
            except (ValueError, TypeError, KeyError):
                volume_map[item['symbol']] = 0

        filtered_by_volume = [s for s in all_symbols if volume_map.get(s, 0) >= min_volume]
        filtered_symbols = [s for s in filtered_by_volume if s not in BLACKLISTED_COINS]

        return filtered_symbols

    except requests.exceptions.Timeout:
        return []
    except requests.exceptions.ConnectionError:
        return []
    except requests.exceptions.HTTPError:
        return []
    except (ValueError, KeyError):
        return []
    except Exception:
        return []