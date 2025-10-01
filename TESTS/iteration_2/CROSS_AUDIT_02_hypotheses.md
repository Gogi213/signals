# Iteration 2 - Cross-Audit #2: Memory Leak Deep Dive

## Дата
2025-10-01

## Входные данные
Все валидированные гипотезы до сих пор:
- **H2.2** - Zero-volume 48.3%
- **H2.3** - Zero-interval 19.5%
- **H2.4** - Warmup logging broken
- **H2.6** - Memory leak +888MB/hour ✨ НОВАЯ
- **C2.1** - Volume filter 24h window
- **C2.3** - Forward-fill correct
- **C2.5** - Warmup interval too large

## Отклоненные:
- **H2.1** - Rolling window works (buffer stayed at 11)
- **C2.4** - No double logging

## Фокус Cross-Audit #2
**H2.6 - Memory leak +888MB/hour** - новая критическая проблема!

---

## Deep Dive: H2.6 - Memory Leak

### Данные из теста
```
Initial memory: 32.10 MB
After 120s: 61.70 MB
Growth: +29.60 MB (+92.2%)
Projected 1-hour: +888 MB
```

### Вопрос #1: Откуда утечка если H2.1 INVALID?

**H2.1 показал**: Rolling window РАБОТАЕТ (buffer stayed at 11 vs expected 12)

Но **H2.6 показал**: Memory растет +888MB/hour!

**Противоречие**: Если buffer ограничен, откуда утечка памяти?

---

## Новые гипотезы

### 🔴 C3.1 - Deduplication Set Grows Unbounded
**Утверждение**: `_seen_trade_signatures` растет без ограничений

**Код анализ** (websocket_handler.py:356-376):
```python
# Deduplication check
signature = f"{trade_data['timestamp']}_{trade_data['price']}_{trade_data['size']}"

if signature in self._seen_trade_signatures[symbol]:
    return  # Skip duplicate

# Mark as seen
self._seen_trade_signatures[symbol].add(signature)

# Cleanup old signatures (periodic)
if len(self._seen_trade_signatures[symbol]) > 1000:
    current_time_ms = trade_data['timestamp']
    cutoff_time = current_time_ms - 60000  # 60 seconds ago
    self._seen_trade_signatures[symbol] = {
        sig for sig in self._seen_trade_signatures[symbol]
        if int(sig.split('_')[0]) >= cutoff_time
    }
```

**Проблема**: Cleanup срабатывает только при `> 1000`
- Для 59 монет = 59,000 сигнатур в памяти перед cleanup
- Каждая сигнатура ~50-100 bytes
- 59,000 * 75 bytes = 4.4 MB (примерно)

**Но** 4.4 MB не объясняет +888MB/hour!

**Приоритет**: ⚠️ ВАЖНО
**Валидация**: Мониторить размер `_seen_trade_signatures`

---

### 🔴 C3.2 - Trades_by_interval Accumulates
**Утверждение**: `_trades_by_interval` не очищается полностью

**Код анализ** (websocket_handler.py:383-389):
```python
# Add the trade to its specific interval
self._trades_by_interval[symbol][interval_key].append(trade_data)
```

**Где удаляется** (websocket_handler.py:301-302):
```python
# Remove the processed trades from _trades_by_interval
del self._trades_by_interval[symbol][boundary]
```

**Потенциальная проблема**:
- Если boundary пропускается (gap), trades остаются в памяти
- Forward-fill свечи НЕ удаляют trades (их нет)
- Для low-activity монет (82% zero-volume) trades могут накапливаться

**Приоритет**: 🔴 КРИТИЧНО
**Валидация**: Подсчитать размер `_trades_by_interval` через 2 минуты

---

### 🔴 C3.3 - Async Logging Queue Overflow
**Утверждение**: `_candle_log_queue` переполняется и хранит необработанные свечи

**Код анализ** (config.py:348-355):
```python
def log_new_candle(coin: str, candle_data: dict):
    """Log new candle data - async via queue"""
    if candle_data:
        try:
            _candle_log_queue.put_nowait((coin, candle_data))
        except queue.Full:
            pass  # Skip if queue is full
```

**Проблема**:
- Queue создается в config.py:55 - `_candle_log_queue = queue.Queue()`
- НЕТ maxsize! Безграничная очередь!
- Worker обрабатывает с `await asyncio.sleep(0.5)`
- Если свечей больше чем worker успевает обработать → очередь растет

**Расчет**:
- 59 монет * 6 свечей/минуту = 354 свечей/минуту
- Worker обрабатывает batch каждые 0.5s = 120 batches/минуту
- Если batch < 3 свечей → накопление!

**Приоритет**: 🔴 КРИТИЧНО
**Валидация**: Проверить `_candle_log_queue.qsize()` через 2 минуты

---

### ⚠️ C3.4 - WebSocket Connection Buffers
**Утверждение**: WebSocket библиотека накапливает необработанные сообщения

**Проблема**:
- 59 монет / 3 per connection = 20 соединений (websocket_handler.py:19)
- Каждое соединение имеет receive buffer
- Если обработка медленнее получения → buffers растут

**Приоритет**: ⚠️ ВАЖНО
**Валидация**: Сложно без глубокого profiling

---

### ⚠️ C3.5 - Python GC Not Collecting
**Утверждение**: Garbage Collector не успевает очищать память

**Проблема**:
- Рост +29MB за 120s = +242KB/s
- Python GC работает периодически
- Circular references могут задерживать освобождение

**Приоритет**: ✅ НИЗКИЙ
**Валидация**: Вызвать `gc.collect()` и проверить память

---

## План валидации Cross-Audit #2

1. **C3.2** (trades_by_interval) - Приоритет #1
2. **C3.3** (logging queue) - Приоритет #2
3. **C3.1** (deduplication set) - Приоритет #3
4. **C3.4** (websocket buffers) - Если 1-3 не объяснят
5. **C3.5** (GC) - Последняя проверка

---

## Ожидаемые результаты

**Высокая вероятность**:
- C3.2 (trades_by_interval) - Вероятно главная причина
- C3.3 (logging queue) - Вероятно вторичная причина

**Средняя вероятность**:
- C3.1 (deduplication) - Вклад небольшой

**Низкая вероятность**:
- C3.4, C3.5 - Вряд ли основная причина

**Цель**: Найти источник +888MB/hour утечки.
