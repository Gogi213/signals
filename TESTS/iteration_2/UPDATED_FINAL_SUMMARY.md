# ОБНОВЛЕННЫЙ ФИНАЛЬНЫЙ САММАРИ - Iteration 2

## Дата: 2025-10-01

## Критические обновления после ре-валидации

---

## 🔴 ПРОБЛЕМА #1: C2.1 ЧАСТИЧНО НЕВЕРНАЯ → C6.1 WebSocket Instability

### Оригинальная гипотеза C2.1:
Volume filter uses 24h window → low-activity coins pass

### Ре-валидация (User observation):
**$319M turnover24h coin НЕ МОЖЕТ иметь 49 dead intervals (490 секунд без трейдов)**

### Результаты ре-валидации:
```
FARTCOINUSDT:
  - 49 consecutive zero-volume candles
  - Timestamps: уникальные (НЕ queue reordering)
  - Forward-fill: confirmed (price 0.6223 везде)
  - Время: 06:25-06:34 UTC
  - System logs: 7 "Connected to WebSocket" за короткое время
```

### ✅ НОВАЯ ROOT CAUSE: C6.1 - WebSocket Connection Instability

**Доказательства**:
1. 7 reconnections в system.json
2. 49 consecutive forward-fill свечей = NO TRADES for 490s
3. Timer продолжает создавать свечи даже когда connection мертв

**Проблема в коде** (websocket_handler.py:243-347):
```python
async def _candle_finalization_timer(self):
    for symbol in self.coins:
        # Creates forward-fill даже если WebSocket connection dead!
        elif current_data['last_close_price'] is not None:
            completed_candle = {..., 'volume': 0}  # Forward-fill
```

**Timer НЕ проверяет**:
- Состояние WebSocket connection
- Когда последний раз получали trades
- Есть ли активные connections

**Решение**:
```python
# websocket_handler.py: Add connection health tracking
self._last_trade_time = {}  # Track last trade per symbol

async def _candle_finalization_timer(self):
    for symbol in self.coins:
        # Check if we got trades recently
        time_since_last_trade = current_time - self._last_trade_time.get(symbol, 0)

        if time_since_last_trade > 60000:  # 60 seconds without trades
            # Skip forward-fill, log warning
            logger.warning(f"No trades for {symbol} in 60s, skipping forward-fill")
            continue

        # Normal forward-fill logic
```

**Приоритет**: 🔴 КРИТИЧНО

---

## 🔴 ПРОБЛЕМА #3: C3.3 Queue Reordering - РЕШЕНИЕ ПЕРЕСМОТРЕНО

### Оригинальное решение:
Убрать async queue → synchronous logging

### ⚠️ РИСКИ (User observation):
1. **Blocking I/O в critical path** - disk write держит lock
2. **File lock contention** - 59 монет пишут одновременно
3. **Loss of batching** - 354 file opens/minute

### ✅ НОВОЕ РЕШЕНИЕ: Sequence Numbers (БЕЗОПАСНОЕ)

```python
# websocket_handler.py
class TradeWebSocket:
    def __init__(self, ...):
        self._candle_sequence = 0  # Global counter

    async def _candle_finalization_timer(self):
        # Before appending candle:
        completed_candle['_sequence'] = self._candle_sequence
        self._candle_sequence += 1
        self.candles_buffer[symbol].append(completed_candle)
        log_new_candle(symbol, completed_candle)

# config.py
async def _candle_log_worker():
    while True:
        batch = []
        while not _candle_log_queue.empty():
            batch.append(_candle_log_queue.get_nowait())

        # SORT BY SEQUENCE!
        batch = sorted(batch, key=lambda x: x[1].get('_sequence', 0))

        for coin, candle_data in batch:
            file_handler.emit(log_record)
```

**Плюсы**:
- ✅ Zero risk (no blocking I/O)
- ✅ Гарантированный порядок
- ✅ Keeps async queue benefits
- ✅ Minimal overhead

**Приоритет**: ⚠️ ВАЖНО

---

## 🔴 ПРОБЛЕМА #5: C3.6 + C6.6 - signals.json Incomplete

### User observation (КОРРЕКТНОЕ):
Console показывает:
```
📊 ❌ NO SIGNAL for ONDOUSDT | Candles: 211 | Passed: [...] | Failed: [...]
```

signals.json содержит:
```json
{"validation_error": "Insufficient data: 19 candles", "criteria_details": {}}
```

### Две проблемы:

#### 1. **C5.1 (validated)**: Warmup=10, signal_processor=20
Период 10-20 свечей логируется без criteria_details

**Решение**:
```python
# config.py
WARMUP_INTERVALS = 20  # Match signal_processor
```

#### 2. **C6.6 (новая гипотеза)**: signals.json STOPS logging after 20 candles?

**Возможная причина**: Другой validation_error блокирует логирование

**Проверка кода** (config.py:150-163):
```python
if signal_data:
    if 'validation_error' in signal_data:
        val_err = signal_data['validation_error']
        if val_err and not val_err.startswith('Insufficient data'):
            return  # ← БЛОКИРУЕТ логирование!
```

**Возможные validation_errors которые блокируют**:
- "No trades in last candle (forward-fill)"
- "Invalid candle X: high < low"
- "Invalid candle X: close out of range"

**Если монета имеет forward-fill свечи (volume=0)** → signal_processor возвращает:
```python
if candles[-1]['volume'] == 0:
    detailed_info['validation_error'] = 'No trades in last candle (forward-fill)'
    return False, detailed_info  # ← НЕ логируется в signals.json!
```

**Вывод**: Монеты с forward-fill (48.3%!) НЕ логируются после 20 свечей!

**Решение**:
```python
# config.py:154 - Allow logging forward-fill signals too
if val_err and not val_err.startswith('Insufficient data') and \
   not val_err.startswith('No trades in last candle'):
    # Still skip invalid candles, but log forward-fill
    if 'Invalid candle' not in val_err:
        return
```

**Приоритет**: ⚠️ ВАЖНО

---

## ИТОГОВАЯ ТАБЛИЦА ПРОБЛЕМ (ОБНОВЛЕННАЯ)

| # | Проблема | ROOT CAUSE | Приоритет | Статус |
|---|----------|------------|-----------|--------|
| 1 | 48.3% zero-volume | ~~C2.1 volume filter~~ → **C6.1 WebSocket instability** | 🔴 КРИТИЧНО | Re-validated |
| 2 | Warmup logging broken | C2.5 logging interval | ⚠️ ВАЖНО | Validated |
| 3 | 19.5% duplicate timestamps | C3.3 queue reordering | ⚠️ ВАЖНО | Solution updated |
| 4 | Warmup/signal mismatch | C5.1 (10 vs 20) | ⚠️ ВАЖНО | Validated |
| 5 | signals.json incomplete | C5.1 + **C6.6 forward-fill blocks logging** | ⚠️ ВАЖНО | New finding |
| 6 | Memory leak | C4.4 multiple processes | ⚠️ Test issue | Validated |

---

## ОБНОВЛЕННЫЕ ПРИОРИТЕТЫ ФИКСОВ

### 🔴 КРИТИЧНО #1: WebSocket Connection Health Check (C6.1)
```python
# websocket_handler.py: Add health tracking
self._last_trade_time = {}
self._connection_healthy = {}

async def _candle_finalization_timer(self):
    for symbol in self.coins:
        time_since_last_trade = current_time - self._last_trade_time.get(symbol, 0)

        if time_since_last_trade > 60000:  # 60s no trades
            logger.warning(f"No trades for {symbol} in 60s")
            continue  # Skip forward-fill

        # Normal logic
```

### ⚠️ ВАЖНО #2: Fix warmup mismatch (C5.1)
```python
# config.py
WARMUP_INTERVALS = 20
```

### ⚠️ ВАЖНО #3: Sequence numbers for queue (C3.3)
```python
# Add sequence counter (см. выше)
```

### ⚠️ ВАЖНО #4: Allow forward-fill logging (C6.6)
```python
# config.py:154
if val_err and not val_err.startswith('Insufficient data') and \
   'Invalid candle' not in val_err:
    # Log forward-fill signals too
    pass
```

### ⚠️ ВАЖНО #5: Fix warmup logging (C2.5)
```python
# main.py:139
if min_candles - last_warmup_log >= 1 or ...:
```

---

## ВАЛИДИРОВАННЫЕ ГИПОТЕЗЫ (ФИНАЛ)

### Всего: 12 валидных (+ 1 pending)

1. ✅ H2.2 - Zero-volume 48.3%
2. ✅ H2.3 - Zero-interval 19.5%
3. ✅ H2.4 - Warmup logging broken
4. ✅ H2.6 - Memory leak +888MB/hour
5. ~~❌ C2.1 - Volume filter 24h (ОТКЛОНЕНА после ре-валидации)~~
6. ✅ C2.3 - Forward-fill correct
7. ✅ C2.5 - Warmup logging interval
8. ✅ C3.3 - Queue reordering
9. ✅ C3.6 - Signals.json incomplete
10. ✅ C4.4 - Multiple processes
11. ✅ C5.1 - Warmup/signal mismatch
12. ✅ **C6.1 - WebSocket instability** (NEW ROOT CAUSE!)
13. ⏳ C6.6 - Forward-fill blocks logging (pending full test)

---

## ЗАКЛЮЧЕНИЕ

**Цикл НЕ завершен** - найдена новая критическая проблема **C6.1**

**User observations оказались критически важными**:
1. ✅ FARTCOIN 49 zeros статистически невозможны → нашли WebSocket instability
2. ✅ signals.json должен содержать criteria → нашли forward-fill blocking
3. ✅ Synchronous logging рискован → пересмотрели решение

**Следующий шаг**:
1. Применить C6.1 fix (WebSocket health check)
2. Применить остальные 4 фикса
3. Повторить аудит после фиксов

---

*Обновлено: 2025-10-01*
*Статус: IN PROGRESS (C6.1 critical finding)*
*Валидных гипотез: 12 (+ 1 pending)*
