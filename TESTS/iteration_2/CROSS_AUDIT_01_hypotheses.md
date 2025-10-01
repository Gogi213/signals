# Iteration 2 - Cross-Audit #1: Deep Dive into Validated Issues

## Дата
2025-10-01

## Входные данные
Валидированные гипотезы из Audit #1:
- **H2.2** - Zero-volume 48.3% (expected 2.4%)
- **H2.3** - Zero-interval 19.5% (duplicate timestamps)
- **H2.4** - Warmup logging broken (only "1/10")

## Цель кросс-аудита
Углубиться в причины каждой проблемы и найти КОРНЕВЫЕ ПРИЧИНЫ.

---

## Deep Dive: H2.2 - Zero-Volume Candles

### Исходная гипотеза
48.3% свечей имеют нулевой volume вместо ожидаемых 2.4%

### Вопросы для углубления

#### Q2.2.1: Почему low-activity coins проходят volume фильтр?

**Анализ кода** - trading_api.py (нужно прочитать):
```python
# config.py:11
MIN_DAILY_VOLUME = 80000000  # 80M

# trading_api.py - как используется?
def get_all_symbols_by_volume():
    # Фильтрация по MIN_DAILY_VOLUME
```

**Гипотеза C2.1**: Volume фильтр рассчитывается НЕПРАВИЛЬНО
- Bybit API может возвращать объем за 24 часа
- Но фильтр может проверять спотовый volume вместо futures
- Или volume в  USDT вместо нативной валюты

**Валидация**: Прочитать trading_api.py и проверить формулу расчета

#### Q2.2.2: Корреляция zero-volume со временем суток?

**Наблюдение из логов**:
```
Test ran: 04:29 - 04:33 (UTC)
```

**Гипотеза C2.2**: Low-activity времени суток
- Это раннее утро по Европе/США
- Азиатская сессия может быть менее активной для некоторых монет

**Валидация**: Сравнить zero-volume % в разное время суток

#### Q2.2.3: Forward-fill vs real zero-volume?

**Вопрос**: 48.3% - это все forward-fill или есть реальные периоды без трейдов?

**Гипотеза C2.3**: Forward-fill создается избыточно
- Timer срабатывает каждые 10s
- Даже если нет трейдов, создается forward-fill свеча
- Но некоторые монеты могут не иметь трейдов по 51 интервал подряд!

**Код анализ** (websocket_handler.py:304-313):
```python
elif current_data['last_close_price'] is not None:
    # No trades for this period - forward-fill with last price
    completed_candle = {
        'timestamp': boundary,
        'open': current_data['last_close_price'],
        'high': current_data['last_close_price'],
        'low': current_data['last_close_price'],
        'close': current_data['last_close_price'],
        'volume': 0
    }
```

**Вывод**: Forward-fill ПРАВИЛЬНЫЙ механизм, но используется для монет с крайне низкой активностью.

---

## Deep Dive: H2.3 - Zero-Interval Candles

### Исходная гипотеза
19.5% пар свечей имеют interval = 0ms (duplicate timestamp)

### Корневая причина

**Анализ паттерна из Test #3**:
```
Prev: timestamp=X, volume=4007700 (real candle)
Curr: timestamp=X, volume=0 (forward-fill with SAME timestamp!)
```

**Код анализ** - finalization timer создает ДВЕ свечи с одним timestamp:

1. **Первая итерация** (boundary = X):
   - Есть трейды → создается real candle с timestamp=X
   - log_new_candle(candle с timestamp=X)
   - boundary += 10000

2. **Следующая итерация** (boundary = X + 10000):
   - Нет трейдов → создается forward-fill с timestamp=X+10000
   - log_new_candle(candle с timestamp=X+10000)

**НО ПРОБЛЕМА**:
Смотрим код websocket_handler.py:287-328:

```python
while boundary < current_boundary:
    trades_for_boundary = self._trades_by_interval[symbol].get(boundary, [])
    if trades_for_boundary:
        # Create real candle
        completed_candle = create_candle_from_trades(trades_for_boundary, boundary)
        # ...
        del self._trades_by_interval[symbol][boundary]  # Remove processed

    elif current_data['last_close_price'] is not None:
        # Forward-fill
        completed_candle = {..., 'timestamp': boundary}

    # Append to buffer
    self.candles_buffer[symbol].append(completed_candle)

    # LOG HERE - correct timestamp
    log_new_candle(symbol, completed_candle)

    # Move forward
    boundary += candle_interval_ms
```

**Вывод**: Код ПРАВИЛЬНЫЙ! Каждая свеча должна иметь уникальный timestamp.

### Новая гипотеза C2.4: Logger вызывается ДВА РАЗА для одной свечи

**Возможная причина**:
1. log_new_candle вызывается из finalization timer
2. Но может быть ещё один вызов из другого места?

**Гипотеза C2.4**: Race condition - две задачи вызывают log_new_candle
- finalization_timer создает свечу
- Какая-то другая логика ТОЖЕ логирует ту же свечу

**Валидация**: Grep код для "log_new_candle" - сколько вызовов?

---

## Deep Dive: H2.4 - Warmup Logging

### Исходная гипотеза
Warmup logging останавливается на "1/10"

### Корневая причина

**Код анализ** (main.py:139-142):
```python
if warmup_active and min_candles != float('inf'):
    if min_candles - last_warmup_log >= 10 or (min_candles == 1 and last_warmup_log == 0):
        log_warmup_progress(min_candles, WARMUP_INTERVALS)
        last_warmup_log = min_candles
```

**Логика**:
- При min_candles=1 и last_warmup_log=0 → LOG "1/10", set last_warmup_log=1
- При min_candles=2-10 → НЕТ ЛОГА (разница <10)
- При min_candles=11 → LOG "11/10" НО warmup уже завершен!

**Проблема**: Условие `min_candles - last_warmup_log >= 10` слишком большое для WARMUP_INTERVALS=10.

### Гипотеза C2.5: Warmup logging интервал некорректен для WARMUP_INTERVALS=10

**Ожидание**: Логировать каждые 1-2 свечи или при каждом изменении
**Реальность**: Логируется только при +10 свечей

**Валидация**: Исправить код на `>= 1` вместо `>= 10` и перетестировать

---

## Новые гипотезы для валидации

### 🔴 C2.1 - Volume Filter Miscalculation
**Утверждение**: MIN_DAILY_VOLUME фильтр рассчитывается неправильно
**Источник**: 82.6% zero-volume у FARTCOINUSDT при MIN=80M
**Валидация**: Проверить trading_api.py и реальный volume из Bybit API

### ⚠️ C2.2 - Time-of-Day Correlation
**Утверждение**: Zero-volume коррелирует с временем суток (04:29 UTC = low activity)
**Источник**: Тесты запущены в раннее утро
**Валидация**: Повторить тесты в разное время суток

### 🔴 C2.3 - Excessive Forward-Fill for Low-Activity Coins
**Утверждение**: Forward-fill создается правильно, но монеты с низкой активностью не должны были пройти фильтр
**Источник**: 51 consecutive zero-volume candles = 510 секунд без трейдов
**Валидация**: Связано с C2.1

### 🔴 C2.4 - Double Logging Race Condition
**Утверждение**: log_new_candle вызывается дважды для одной свечи
**Источник**: 19.5% duplicate timestamps
**Валидация**: Grep "log_new_candle" в коде + добавить debug logging

### ⚠️ C2.5 - Warmup Logging Interval Too Large
**Утверждение**: Условие `>= 10` слишком большое для WARMUP_INTERVALS=10
**Источник**: Только 1 лог вместо ~10
**Валидация**: Изменить на `>= 1` и перетестировать

---

## План валидации Cross-Audit #1

1. **Read trading_api.py** - проверить volume фильтр (C2.1)
2. **Grep log_new_candle** - найти все вызовы (C2.4)
3. **Test C2.5** - простой фикс в main.py logging condition
4. **Analyze C2.2** - проверить timestamp распределение zero-volume свечей

---

## Ожидаемые результаты

**Валидные гипотезы** (прогноз):
- C2.1 (Volume filter) - Высокая вероятность
- C2.4 (Double logging) - Высокая вероятность
- C2.5 (Warmup interval) - 100% вероятность (очевидно из кода)

**Сомнительные**:
- C2.2 (Time-of-day) - Требует длительного тестирования
- C2.3 (Excessive forward-fill) - Следствие C2.1

**Цель**: Минимум 3 валидных гипотезы для продолжения кросс-аудитов.
