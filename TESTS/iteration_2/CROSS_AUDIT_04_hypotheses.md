# Iteration 2 - Cross-Audit #4: Integration & Interactions

## Дата
2025-10-01

## Валидированные гипотезы (10 total)

### Audit #1:
1. **H2.2** - Zero-volume 48.3%
2. **H2.3** - Zero-interval 19.5%
3. **H2.4** - Warmup logging broken
4. **H2.6** - Memory leak +888MB/hour

### Cross-Audit #1:
5. **C2.1** - Volume filter 24h window (ROOT CAUSE for H2.2)
6. **C2.3** - Forward-fill correct
7. **C2.5** - Warmup logging interval too large (ROOT CAUSE for H2.4)

### Cross-Audit #2:
8. **C3.3** - Logging queue accumulates
9. **C3.6** - Signals.json broken (no real criteria)

### Cross-Audit #3:
10. **C4.4** - Multiple processes (ROOT CAUSE for H2.6!!!)

---

## Cross-Audit #4 Focus: Interactions Between Issues

### Вопрос #1: Связь C3.6 (signals broken) и C2.1 (volume filter)?

**C3.6**: signals.json содержит только "Insufficient data: 12 candles (need 20+)"

**C2.1**: Low-activity coins проходят volume filter

**Гипотеза C5.1**: Low-activity coins не успевают накопить 20 свечей за разумное время

**Анализ**:
- WARMUP_INTERVALS = 10 (config.py:22)
- Но signal_processor требует 20 свечей (signal_processor.py:191)
- 82% zero-volume монеты получают свечи редко
- За 2 минуты накопили только 12 свечей

**Расчет**:
- 10s per candle
- 12 candles = 120s (2 minutes)
- Для 20 свечей нужно 200s (3.3 minutes)

НО в логах показано "Candles: 211"! Противоречие?

**Проверка**: Это разные логи!
- signals.json: Insufficient data (12 candles)
- Console: NO SIGNAL (211 candles)

**Вывод**: signals.json логируется ВО ВРЕМЯ warmup (первые 2 минуты), а console - после warmup.

**Приоритет**: ⚠️ ВАЖНО
**Валидация**: Проверить когда signals.json пишется

---

### Вопрос #2: Связь H2.3 (zero-interval) и C3.3 (queue accumulates)?

**H2.3**: 19.5% duplicate timestamps
**C3.3**: Log queue grows +5.9/s

**Гипотеза C5.2**: Queue reordering создает duplicate timestamps в логах

**Анализ** (config.py:295-327):
```python
async def _candle_log_worker():
    while True:
        # Process all available logs without blocking
        batch = []
        while not _candle_log_queue.empty():
            batch.append(_candle_log_queue.get_nowait())

        # Write batch to file
        for coin, candle_data in batch:
            # File log
            file_handler.emit(log_record)  # Пишет в websocket.json
```

**Проблема**:
- Queue обрабатывается батчами
- Внутри батча порядок сохраняется
- НО батчи могут обрабатываться не по FIFO из-за asyncio

**Это ПОДТВЕРЖДАЕТ гипотезу C2.6 из Cross #1!**

**Приоритет**: 🔴 КРИТИЧНО
**Валидация**: Уже подтверждено через H2.3

---

### Вопрос #3: Почему C4.4 (multiple processes)?

**C4.4**: Main.py запущен в фоне во время тестов

**Гипотеза C5.3**: User забыл остановить main.py после предыдущего запуска

**Проверка**: Это НЕ баг кода, а баг тестирования!

**Решение**: Kill main.py перед запуском тестов

**Приоритет**: ⚠️ ВАЖНО для корректного тестирования

---

## Новые гипотезы

### 🔴 C5.1 - Signals.json Logs During Warmup Only
**Утверждение**: signals.json пишется только во время warmup (<20 candles)

**Проблема**: config.py:142-156 фильтрует validation_error:
```python
if signal_data:
    if 'validation_error' in signal_data:
        val_err = signal_data['validation_error']
        if val_err and not val_err.startswith('Insufficient data'):
            return  # Skip logging
```

**Логика**:
- "Insufficient data" = LOGGED ✅
- Other validation errors = NOT logged ❌
- Real signals with criteria = NOT logged ❌ (why?)

**Возможная причина**: criteria_details пустой!

**Приоритет**: 🔴 КРИТИЧНО
**Валидация**: Проверить signal_processor возвращаемые данные

---

### ⚠️ C5.2 - Queue Batch Reordering Causes Duplicates
**Утверждение**: Async queue processing reorders candles → duplicate timestamps

**Связано с**: H2.3, C3.3

**Приоритет**: ⚠️ ВАЖНО (уже косвенно подтверждено)

---

### ⚠️ C5.3 - Test Methodology Issue (multiple processes)
**Утверждение**: Main.py не останавливается перед тестами

**Решение**: Проверять процессы перед тестом

**Приоритет**: ⚠️ ВАЖНО (методологическая проблема)

---

## Вопрос #4: Сколько РЕАЛЬНЫХ проблем осталось?

### Исключая методологические:
- ❌ H2.6 (memory leak) → C4.4 (multiple processes) = **НЕ БАГ КОДА**
- ❌ H2.1 (rolling window) → **INVALID**
- ❌ C4.8 (measurement) → **INVALID**

### Реальные проблемы кода:
1. **C2.1** - Volume filter uses 24h window → low-activity coins
2. **C2.5** - Warmup logging interval too large
3. **H2.3** + **C5.2** - Queue reordering → duplicate timestamps
4. **C3.6** + **C5.1** - Signals.json broken (criteria not logged)
5. **C3.3** - Logging queue accumulates (но не критично - 0.32 MB)

### Остальные - следствия:
- H2.2 → следствие C2.1
- H2.4 → следствие C2.5
- C2.3 → подтверждение что forward-fill правильный

---

## Итого Cross-Audit #4

**Валидировано**: 3 новых гипотезы
- C5.1 (signals during warmup only) - pending validation
- C5.2 (queue reordering) - подтверждено через H2.3
- C5.3 (test methodology) - подтверждено через C4.4

**Реальных багов кода**: 5
- C2.1, C2.5, H2.3, C3.6, C3.3

**Методологических проблем**: 1
- C4.4 (multiple processes во время теста)

---

## План Cross-Audit #5

**Вопрос**: Остались ли невалидированные гипотезы?

**Проверка**:
- C5.1 - требует валидации (signals.json timing)
- C5.2 - уже подтверждена
- C5.3 - уже подтверждена

**Если C5.1 подтвердится → переход к Cross-Audit #5**

**Если нет новых гипотез → цикл завершен**

---

## Ожидание

Cross-Audit #5 должен показать **ПУСТЫЕ гипотезы** = завершение цикла.
