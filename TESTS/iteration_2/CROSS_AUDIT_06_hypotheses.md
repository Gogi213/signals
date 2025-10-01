# Cross-Audit #6: FARTCOIN Dead Intervals Mystery

## Проблема
FARTCOINUSDT ($319M turnover24h) имеет **49 consecutive dead intervals** (490 секунд без трейдов).

**User observation**: Это статистически невозможно для высоколиквидной монеты.

## Факты из ре-валидации:
1. ✅ Timestamps уникальные (не дубликаты)
2. ✅ Forward-fill confirmed (price 0.6223 везде)
3. ✅ Время: 06:25-06:34 UTC (раннее утро)
4. ❌ 146 zero-volume свечей из 215 (68%!)

---

## Новые гипотезы

### 🔴 C6.1 - WebSocket Connection Dropped
**Утверждение**: Соединение с Bybit оборвалось на 490 секунд, reconnect не произошел вовремя

**Проверка в коде** (websocket_handler.py:86-98):
```python
async def _start_single_connection(self, coins_for_connection: List[str]):
    reconnect_delay = 5  # Start with 5 seconds delay
    max_reconnect_delay = 60  # Max 60 seconds delay

    while self.running:
        try:
            async with websockets.connect(...) as websocket:
                # Subscribe and receive
```

**Проблема**: Если connection timeout = 30s, но reconnect delay растет экспоненциально:
- 1st reconnect: 5s delay
- 2nd reconnect: 7.5s delay
- 3rd reconnect: 11.25s delay
- ...
- Nth reconnect: до 60s delay

**За 490 секунд могло быть много failed reconnects!**

**Валидация**: Проверить logs/websocket.json на reconnection events

---

### 🔴 C6.2 - Timer Creates Candles Without Checking Connection
**Утверждение**: Finalization timer создает forward-fill даже когда WebSocket мертв

**Код** (websocket_handler.py:243-347):
```python
async def _candle_finalization_timer(self):
    while self.running:
        # Create candles for ALL symbols
        for symbol in self.coins:
            # Check if we have trades
            trades_for_boundary = self._trades_by_interval[symbol].get(boundary, [])
            if trades_for_boundary:
                # Real candle
            elif current_data['last_close_price'] is not None:
                # Forward-fill  ← СОЗДАЕТСЯ ДАЖЕ ЕСЛИ CONNECTION МЕРТВ!
```

**Проблема**: Timer НЕ проверяет состояние WebSocket connection!

**Результат**: Если connection умер → 0 новых трейдов → бесконечный forward-fill

---

### 🔴 C6.3 - Bybit API Rate Limiting
**Утверждение**: Bybit заблокировал соединение из-за rate limit

**Проверка**: 59 монет / 3 per connection = 20 соединений одновременно

Bybit limits:
- Max 500 connections per IP
- Max 120 requests/minute per connection

**20 connections НЕ должны быть проблемой**

**Вероятность**: НИЗКАЯ

---

### 🔴 C6.4 - FARTCOIN Delisted или Trading Halt
**Утверждение**: Bybit временно остановил торговлю FARTCOIN в 06:25-06:34

**Проверка**: Нужно проверить Bybit API status за это время

**Вероятность**: СРЕДНЯЯ (возможно maintenance)

---

### 🔴 C6.5 - Bug in _trades_by_interval Cleanup
**Утверждение**: Трейды есть, но они не попадают в _trades_by_interval

**Код** (websocket_handler.py:383-389):
```python
# Add the trade to its specific interval
self._trades_by_interval[symbol][interval_key].append(trade_data)
```

**Проверка в finalization** (websocket_handler.py:291):
```python
trades_for_boundary = self._trades_by_interval[symbol].get(boundary, [])
```

**Возможная проблема**: Если `interval_key != boundary` из-за рассинхронизации → трейды не находятся!

**Валидация**: Добавить debug logging

---

## План валидации

1. **C6.1** - Проверить websocket.json на reconnection events
2. **C6.2** - Добавить connection health check в timer
3. **C6.4** - Проверить Bybit API status history
4. **C6.5** - Debug logging для _trades_by_interval

---

## Приоритет

**C6.1 и C6.2 - КРИТИЧНО**: Если connection умер, система должна:
1. Перестать создавать forward-fill свечи
2. Попытаться reconnect агрессивно
3. Логировать reconnection attempts

**C2.1 статус**: ЧАСТИЧНО НЕВЕРНАЯ
- Volume filter работает правильно ($319M проходит)
- НО проблема НЕ в low activity монет
- Проблема в WebSocket connection stability!
