# Risk Assessment: C3.3 Queue Reordering Fix

## Предложенное решение
Убрать async queue, делать synchronous logging

```python
# BEFORE (async queue):
def log_new_candle(coin: str, candle_data: dict):
    _candle_log_queue.put_nowait((coin, candle_data))

async def _candle_log_worker():
    while True:
        batch = []
        while not _candle_log_queue.empty():
            batch.append(_candle_log_queue.get_nowait())
        for coin, candle_data in batch:
            file_handler.emit(log_record)
        await asyncio.sleep(0.5)

# AFTER (synchronous):
def log_new_candle(coin: str, candle_data: dict):
    file_handler = JSONFileHandler(...)
    file_handler.emit(log_record)  # IMMEDIATE write
```

---

## 🔴 РИСКИ

### Риск #1: Blocking I/O в критичном пути
**Проблема**: `file_handler.emit()` делает `f.write()` → disk I/O

**Критичный путь**:
```
WebSocket receives trade
  → _process_trade_to_candle (with lock!)
     → Timer finalizes candle
        → log_new_candle
           → file_handler.emit() ← DISK WRITE HERE
```

**Если disk slow** (HDD, network drive):
- Write занимает 5-50ms
- **Lock держится 5-50ms!**
- Другие трейды waiting на lock
- **Missed trades или delays!**

**Severity**: 🔴 CRITICAL

---

### Риск #2: File lock contention
**Проблема**: Множественные одновременные writes в один файл

**Сценарий**:
- 59 монет
- Timer срабатывает каждые 10s
- Все 59 свечей создаются почти одновременно
- 59 одновременных `file_handler.emit()`

**Windows file locking**:
- Может сериализовать writes
- Последняя свеча ждет первые 58
- **Delay до 59 * 5ms = 295ms!**

**Severity**: ⚠️ HIGH

---

### Риск #3: Loss of batching efficiency
**Текущее решение** (async queue):
- Worker обрабатывает batch из N свечей
- Открывает файл 1 раз
- Пишет N записей
- Закрывает файл 1 раз

**Новое решение** (synchronous):
- Каждая свеча открывает файл
- Пишет 1 запись
- Закрывает файл
- **N × (open + write + close) operations!**

**Impact**: Если 59 монет * 6 свечей/минуту = 354 file opens/minute

**Severity**: ⚠️ MEDIUM

---

### Риск #4: Console logging overhead
**Проблема**: console logging ТОЖЕ делается в `log_new_candle`:

```python
logger.info(f"Candle {coin} | {timestamp} | ...")  # Console write
```

Console I/O медленнее чем file I/O на Windows!

**Severity**: ⚠️ MEDIUM

---

## ✅ АЛЬТЕРНАТИВНЫЕ РЕШЕНИЯ

### Solution #1: Sequence Numbers (ЛУЧШЕЕ)
```python
# В TradeWebSocket.__init__:
self._candle_sequence = 0
self._sequence_lock = asyncio.Lock()

# В finalization timer:
async with self._sequence_lock:
    candle['sequence'] = self._candle_sequence
    self._candle_sequence += 1

# При логировании:
log_new_candle(symbol, candle)  # Async queue как раньше

# Worker sorts by sequence before writing:
batch = sorted(batch, key=lambda x: x[1].get('sequence', 0))
```

**Плюсы**:
- ✅ Сохраняет async queue (no blocking)
- ✅ Гарантирует порядок
- ✅ Minimal overhead

**Минусы**:
- Нужен дополнительный lock (но он быстрый)

---

### Solution #2: Single-threaded Logging
```python
# Создать отдельный asyncio.Queue для логирования
_logging_queue = asyncio.Queue(maxsize=1000)

async def _logging_worker():
    while True:
        coin, candle_data = await _logging_queue.get()  # Awaitable!
        file_handler.emit(log_record)  # One at a time
        _logging_queue.task_done()

# В log_new_candle:
await _logging_queue.put((coin, candle_data))  # Blocks if full
```

**Плюсы**:
- ✅ Single writer = no reordering
- ✅ Non-blocking (asyncio)

**Минусы**:
- ⚠️ Если queue full → blocks critical path
- ⚠️ Нужен maxsize tuning

---

### Solution #3: Timestamp-based Sorting in Worker
```python
# Текущий worker, но sort перед записью:
async def _candle_log_worker():
    while True:
        batch = []
        while not _candle_log_queue.empty():
            batch.append(_candle_log_queue.get_nowait())

        # SORT BY TIMESTAMP!
        batch = sorted(batch, key=lambda x: x[1]['timestamp'])

        for coin, candle_data in batch:
            file_handler.emit(log_record)
```

**Плюсы**:
- ✅ Minimal code change
- ✅ No new locks

**Минусы**:
- ⚠️ Batch может содержать свечи разных монет
- ⚠️ Если две свечи имеют одинаковый timestamp (forward-fill) → sorting unstable

---

## 🎯 РЕКОМЕНДАЦИЯ

**Solution #1 (Sequence Numbers)** - BEST CHOICE

**Почему**:
1. ✅ Zero риск blocking I/O
2. ✅ Гарантированный порядок
3. ✅ Minimal overhead (~1μs per candle)
4. ✅ Keeps async queue benefits

**Implementation**:
```python
# websocket_handler.py:33
self._candle_sequence = 0  # Global sequence counter

# websocket_handler.py:320 (в finalization timer)
# Перед append to buffer:
completed_candle['_sequence'] = self._candle_sequence
self._candle_sequence += 1
self.candles_buffer[symbol].append(completed_candle)

# config.py:307 (в worker)
# Sort batch by sequence:
batch = sorted(batch, key=lambda x: x[1].get('_sequence', 0))
```

**Risks**: NONE (sequence counter increment is atomic in Python)

---

## ❌ НЕ РЕКОМЕНДУЕТСЯ

**Synchronous logging** - TOO RISKY

Причины:
- 🔴 Disk I/O в critical path
- 🔴 File lock contention
- 🔴 Loss of batching

**Только если**: Система работает на SSD с <1ms write latency И нет множественных connections
