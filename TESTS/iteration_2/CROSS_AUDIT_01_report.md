# Iteration 2 - Cross-Audit #1: Report

## Дата
2025-10-01

## Входные данные
Валидированные гипотезы из Audit #1:
- **H2.2** - Zero-volume 48.3%
- **H2.3** - Zero-interval 19.5%
- **H2.4** - Warmup logging broken

## Цель
Найти КОРНЕВЫЕ ПРИЧИНЫ проблем из Audit #1

---

## Итоговая статистика

### Новые гипотезы
| ID | Гипотеза | Статус | Приоритет |
|----|----------|--------|-----------|
| C2.1 | Volume filter allows low-activity coins | ✅ VALID | 🔴 КРИТИЧНО |
| C2.2 | Time-of-day correlation | ⏳ Skipped | ✅ НИЗКИЙ |
| C2.3 | Excessive forward-fill (follow-up C2.1) | ✅ VALID | ⚠️ ВАЖНО |
| C2.4 | Double logging race condition | ❌ INVALID | - |
| C2.5 | Warmup logging interval too large | ✅ VALID | ⚠️ ВАЖНО |

**Валидировано**: 3/5 (60%)
**Отклонено**: 1/5 (20%)
**Пропущено**: 1/5 (20%)

---

## Валидированные корневые причины

### ✅ C2.1 - Volume Filter Allows Low-Activity Coins
**Статус**: VALID (ROOT CAUSE for H2.2)

**Проблема**:
Монеты с 82% zero-volume свечей ПРОХОДЯТ фильтр MIN_DAILY_VOLUME = 80M

**Данные**:
```
FARTCOINUSDT:
  Turnover (24h): $318,926,361 USDT (passes!)
  Real-time zero-volume: 82.6%

FFUSDT:
  Turnover (24h): $247,416,915 USDT (passes!)
  Real-time zero-volume: 82.6%

DRIFTUSDT:
  Turnover (24h): $97,431,920 USDT (passes!)
  Real-time zero-volume: 81.8%
```

**Корневая причина**:
`turnover24h` включает ВСЕ 24 часа, включая пиковые периоды активности.
Но в текущий момент (04:29 UTC = раннее утро) эти монеты имеют очень низкую активность.

**Следствия**:
- 48.3% zero-volume свечей (H2.2) - ПРЯМОЕ следствие
- Бесполезная нагрузка на систему - обработка неактивных монет
- Forward-fill создает множество пустых свечей

**Решение**:
1. Использовать более короткое окно (1h, 4h вместо 24h)
2. Добавить фильтр по текущей активности (трейдов за последние 10 минут)
3. Динамически исключать монеты с >50% zero-volume за последний час

---

### ✅ C2.3 - Excessive Forward-Fill is Correct Behavior
**Статус**: VALID (следствие C2.1)

**Вывод**:
Forward-fill работает **ПРАВИЛЬНО**. Проблема не в механизме forward-fill, а в том, что низкоактивные монеты не должны были мониториться вообще.

**Логика forward-fill** (из websocket_handler.py):
```python
elif current_data['last_close_price'] is not None:
    # No trades for this period - forward-fill with last price
    completed_candle = {
        'timestamp': boundary,
        'open': current_data['last_close_price'],
        'high': current_data['last_close_price'],
        'low': current_data['last_close_price'],
        'close': current_data['last_close_price'],
        'volume': 0  # Correctly marked as zero
    }
```

**Наблюдение**:
- Max consecutive zeros: 51 (510 секунд без трейдов!)
- Это НЕ баг forward-fill, это правильное отражение отсутствия активности

**Решение**:
Фильтровать монеты на входе (C2.1), а не исправлять forward-fill.

---

### ✅ C2.5 - Warmup Logging Interval Too Large
**Статус**: VALID (ROOT CAUSE for H2.4)

**Проблема**:
main.py:139-142 использует условие `>= 10` для WARMUP_INTERVALS=10

**Код**:
```python
if min_candles - last_warmup_log >= 10 or (min_candles == 1 and last_warmup_log == 0):
    log_warmup_progress(min_candles, WARMUP_INTERVALS)
    last_warmup_log = min_candles
```

**Логика**:
- min_candles=1, last_warmup_log=0 → LOG "1/10", set last_warmup_log=1
- min_candles=2-10 → НЕТ ЛОГА (1 + 10 = 11 > 10)
- min_candles=11 → LOG НО warmup уже завершен!

**Решение**:
Изменить условие на `>= 5` или `>= 1` для более частого логирования.

**Альтернатива**:
Логировать при каждом изменении min_candles в диапазоне 1-10.

---

### ❌ C2.4 - Double Logging Race Condition
**Статус**: INVALID

**Гипотеза**:
log_new_candle вызывается дважды для одной свечи

**Проверка**:
```bash
grep "log_new_candle" в коде:
  - websocket_handler.py:325 (единственный вызов)
```

**Вывод**:
Только ОДИН вызов log_new_candle во всем коде. Race condition НЕТ.

**Альтернативная гипотеза для H2.3**:
19.5% zero-interval pairs - это НЕ дубликаты логирования, а особенность данных.
Требуется deeper dive.

---

## Анализ H2.3 - Zero-Interval (requires deeper investigation)

**Проблема**: 19.5% пар свечей имеют interval=0ms

**Проверка кода финализации**:
```python
# websocket_handler.py:287-328
while boundary < current_boundary:
    # Create candle for each 10s boundary
    completed_candle = create_candle_from_trades(..., boundary)

    # Append to buffer
    self.candles_buffer[symbol].append(completed_candle)

    # Log candle
    log_new_candle(symbol, completed_candle)

    # Advance boundary
    boundary += candle_interval_ms  # +10000
```

**Вопрос**: Как получается interval=0 если boundary всегда увеличивается на 10000?

**Новая гипотеза C2.6**: Logger асинхронен, timestamps могут перемешиваться
```python
# config.py:348-355
def log_new_candle(coin: str, candle_data: dict):
    """Log new candle data - async via queue"""
    if candle_data:
        try:
            _candle_log_queue.put_nowait((coin, candle_data))  # ASYNC!
        except queue.Full:
            pass
```

**Проблема**: Queue может обрабатывать свечи НЕ в порядке поступления!

**Результат**: В logs/websocket.json свечи записываются в случайном порядке → при сортировке по timestamp появляются дубликаты.

---

## Новые гипотезы для следующего кросс-аудита

### 🔴 C2.6 - Async Logging Reorders Candles
**Утверждение**: _candle_log_queue обрабатывает свечи не по порядку
**Источник**: H2.3 (19.5% zero-interval) + async logging
**Приоритет**: 🔴 КРИТИЧНО
**Валидация**: Проверить порядок записи в websocket.json vs порядок создания свечей

---

## Итоговые метрики

```
Cross-Audit #1:
  Hypotheses: 5 total
  Validated: 3 (60%)
  Invalid: 1 (20%)
  Skipped: 1 (20%)

Root Causes Found:
  1. Volume filter uses 24h window (C2.1)
  2. Warmup logging interval too large (C2.5)
  3. Forward-fill is correct, filter is wrong (C2.3)

New Hypotheses Generated:
  1. Async logging reorders candles (C2.6) - pending

Audit #1 + Cross #1 Combined:
  Total hypotheses: 12 (7 + 5)
  Validated: 6 (H2.2, H2.3, H2.4, C2.1, C2.3, C2.5)
  Invalid: 1 (C2.4)
  Pending: 4 (H2.1, H2.5, H2.6, H2.7)
  Skipped: 1 (C2.2)
```

---

## Следующий шаг

**Cross-Audit #2** будет фокусироваться на:
1. C2.6 - Async logging order
2. H2.1 & H2.6 - Buffer growth / memory (требует 5-min test)
3. H2.7 - 0 TRUE signals

**Ожидание**: 2-3 валидных гипотезы в Cross-Audit #2.

**Условие завершения цикла**: Когда кросс-аудит не находит новых валидных гипотез.
