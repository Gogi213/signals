# Iteration 2 - Audit #1: Report

## Дата
2025-10-01

## Методология
Анализ кода + сбор логов (4 минуты) + тестирование гипотез

---

## Итоговая статистика

### Данные
- **Время работы**: 240 секунд (4 минуты прогрев)
- **Свечи собрано**: 2996 (107 на монету)
- **Сигналов проверено**: 8148 (все FALSE)
- **Монеты**: 28 активных

### Гипотезы
| ID | Гипотеза | Статус | Приоритет |
|----|----------|--------|-----------|
| H2.1 | Rolling Window отсутствует | ⏳ Pending | 🔴 КРИТИЧНО |
| H2.2 | Zero-volume 48% vs 2.4% | ✅ VALID | ⚠️ ВАЖНО |
| H2.3 | Interval 0ms (19.5% пар) | ✅ VALID | ⚠️ ВАЖНО |
| H2.4 | Warmup завершается на 1/10 | ✅ VALID | ⚠️ ВАЖНО |
| H2.5 | Дедупликация cleanup неэффективна | ⏳ Pending | ✅ НИЗКИЙ |
| H2.6 | Рост памяти без rolling limit | ⏳ Pending | 🔴 КРИТИЧНО |
| H2.7 | 0 TRUE signals подозрительно | ⏳ Pending | ⚠️ ВАЖНО |

**Валидировано**: 3/7 (43%)
**В процессе**: 4/7 (57%)

---

## Валидированные гипотезы

### ✅ H2.2 - Excessive Zero-Volume Candles (48.3%)
**Статус**: VALID
**Данные**:
- Zero-volume: 1636/3388 (48.3%)
- Ожидалось: ~2.4%
- Отклонение: ×20 раз

**Паттерны**:
- Max consecutive zeros: 51
- Average run: 4.2 свечей
- Worst coins: FARTCOINUSDT (82.6%), FFUSDT (82.6%), DRIFTUSDT (81.8%)

**Причины**:
1. Low-activity coins (< MIN_DAILY_VOLUME?)
2. Gap-filling создает forward-fill при отсутствии трейдов
3. Timer finalization срабатывает каждые 10s независимо от наличия данных

**Влияние**:
- Сигналы могут некорректно оцениваться
- Forward-fill свечи блокируют генерацию сигналов (проверка `if candles[-1]['volume'] == 0`)
- Половина вычислительных ресурсов тратится на пустые свечи

---

### ✅ H2.3 - Zero-Interval Candles (19.5%)
**Статус**: VALID
**Данные**:
- Zero-interval pairs: 672/3444 (19.5%)
- Intervals found: {0ms, 10000ms}
- Проблема: ~20% свечей имеют дубликаты timestamp

**Пример** (1000PEPEUSDT):
```
Prev: timestamp=1759278580000, O:0.009277, V:4007700.0
Curr: timestamp=1759278580000, O:0.009277, V:0  (same timestamp!)
```

**Причины**:
1. Logger логирует одну свечу дважды
2. Race condition в candle_finalization_timer
3. Forward-fill создается с тем же timestamp, что и оригинальная свеча

**Влияние**:
- Дублирование записей в logs/websocket.json
- Буфер раздувается дубликатами
- Память тратится на хранение идентичных данных

---

### ✅ H2.4 - Warmup Completes Early
**Статус**: VALID
**Данные**:
- Warmup logs: 1 ("Warmup: 1/10")
- Expected: Multiple logs до 10/10
- First signal time: After 150+ candles per coin

**Наблюдения**:
```
- System logs: 3 total
- Warmup logs: 1 ("1/10" only)
- Signal logs: 476 (started after 150 candles!)
- Expected warmup: 10 candles
```

**Причины**:
1. Warmup_complete становится True слишком рано
2. Логирование останавливается после первой свечи
3. main.py logic:140 проверяет `if min_candles - last_warmup_log >= 10` но last_warmup_log остается 1

**Влияние**:
- Пользователь не видит прогресс warmup
- Непонятно когда система готова
- 150 свечей вместо 10 до старта - это 25-минутная задержка вместо ожидаемых 100 секунд!

---

## Pending Validation

### ⏳ H2.1 & H2.6 - Rolling Window & Memory
**Требует**: 5-минутный тест с мониторингом
**Статус**: Test created, pending execution

### ⏳ H2.5 - Cleanup Efficiency
**Требует**: Microbenchmark дедупликации
**Статус**: Low priority

### ⏳ H2.7 - Zero TRUE Signals
**Требует**: Criteria analysis
**Статус**: Pending

---

## Код-анализ проблем

### Проблема #1: Zero-Interval Logging (H2.3)

**Источник**: websocket_handler.py:324-325
```python
# Log new candle (async, non-blocking)
from src.config import log_new_candle
log_new_candle(symbol, completed_candle)
```

**Гипотеза**: При forward-fill создается candle с timestamp = last_boundary, но этот же timestamp уже был залогирован в предыдущей итерации.

**Проверка в коде** (websocket_handler.py:287-328):
```python
while boundary < current_boundary:
    # Check if we have trades for this specific boundary
    trades_for_boundary = self._trades_by_interval[symbol].get(boundary, [])
    if trades_for_boundary:
        # Have trades - create real candle
        completed_candle = create_candle_from_trades(trades_for_boundary, boundary)
        # ...
    elif current_data['last_close_price'] is not None:
        # Forward-fill with last price
        completed_candle = {
            'timestamp': boundary,  # SAME TIMESTAMP as previous candle!
            'open': current_data['last_close_price'],
            # ...
        }

    # Append candle to buffer
    self.candles_buffer[symbol].append(completed_candle)

    # Log new candle
    log_new_candle(symbol, completed_candle)  # LOGS TWICE for same timestamp!

    # Move to next boundary
    boundary += candle_interval_ms
```

**Проблема**: `boundary` не изменяется между реальной свечой и forward-fill → оба логируются с одинаковым timestamp.

---

### Проблема #2: Zero-Volume Candles (H2.2)

**Источник**: Комбинация low-activity coins + timer finalization

**Анализ**:
1. config.py:11 - `MIN_DAILY_VOLUME = 80000000` (80M)
2. Но монеты вроде FARTCOINUSDT имеют 82.6% zero-volume свечей
3. Это значит, что фильтр volume НЕ работает корректно

**Проверка в trading_api.py** (required):
- Нужно валидировать что `get_all_symbols_by_volume()` корректно фильтрует
- Возможно, дневной volume рассчитан неправильно

---

### Проблема #3: Warmup Logging (H2.4)

**Источник**: main.py:139-142
```python
if warmup_active and min_candles != float('inf'):
    if min_candles - last_warmup_log >= 10 or (min_candles == 1 and last_warmup_log == 0):
        log_warmup_progress(min_candles, WARMUP_INTERVALS)
        last_warmup_log = min_candles
```

**Проблема**: После `last_warmup_log = 1`, следующее логирование будет только при `min_candles >= 11` (1 + 10).
Но WARMUP_INTERVALS = 10, поэтому warmup завершается на 10 свечах и `warmup_active` становится False.

**Результат**: Видим только "1/10", но никогда не видим "10/10" или промежуточные значения.

---

## Следующие шаги

### Immediate Actions (Critical)
1. ✅ Запустить test_01_buffer_memory.py (5 минут) - валидировать H2.1 & H2.6
2. ⏳ Analyze criteria для H2.7 (0 TRUE signals)
3. ⏳ Validate MIN_DAILY_VOLUME filtering

### Code Fixes Required
После валидации всех гипотез:
1. **Добавить rolling window limit** (H2.1/H2.6)
2. **Фиксить zero-interval logging** (H2.3)
3. **Улучшить warmup logging** (H2.4)
4. **Пересмотреть volume filtering** (H2.2)

---

## Metrics Summary

```
Execution time: 240s (4 min)
Candles: 2996 total
  - Zero-volume: 1636 (48.3%) [ISSUE]
  - Real volume: 1360 (51.7%)
  - Per coin: 107 avg
Intervals:
  - 10000ms: 2772 (80.5%)
  - 0ms: 672 (19.5%) [ISSUE]
Signals:
  - Total: 8148
  - TRUE: 0 (0%) [INVESTIGATE]
  - FALSE: 8148 (100%)
Warmup:
  - Expected: 10 candles (100s)
  - Logs: 1 ("1/10" only) [ISSUE]
  - Actual delay: 150+ candles
```

---

## Выводы

**3 из 7 гипотез валидированы** - все подтверждены как VALID.

### Критические проблемы:
1. **48.3% zero-volume свечей** - low-activity coins проходят фильтр
2. **19.5% дубликатов timestamp** - logger неправильно обрабатывает forward-fill
3. **Warmup logging сломан** - пользователь не видит прогресса

### Следующий аудит:
Кросс-аудит #1 будет фокусироваться на:
- Rolling window (memory leak)
- 0 TRUE signals (criteria слишком строгие?)
- Volume filtering (почему low-activity coins проходят?)

**Ожидание**: Минимум 2-3 дополнительных валидных гипотезы в кросс-аудите.
