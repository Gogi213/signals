# Iteration 2 - Cross-Audit #3: Unaccounted Memory Leak

## Дата
2025-10-01

## Входные данные

### Валидированные (всего 9):
- H2.2, H2.3, H2.4, H2.6
- C2.1, C2.3, C2.5
- C3.3, C3.6

### Cross-Audit #2 findings:
**Tracked sources = 0.54 MB, Actual growth = 30 MB**

**Огромное несоответствие**: 29.46 MB неучтенного роста!

---

## Deep Dive: Missing 30 MB

### Что мы проверили:
✅ candles_buffer - ограничен (H2.1 INVALID)
✅ _seen_trade_signatures - 0.18 MB (C3.1 INVALID)
✅ _trades_by_interval - 0.04 MB (C3.2 INVALID)
✅ _candle_log_queue - 0.32 MB (C3.3 VALID but small)

**Итого tracked**: 0.54 MB
**Actual growth**: 30 MB
**Missing**: 29.46 MB (98% неучтено!)

---

## Новые гипотезы

### 🔴 C4.1 - Python Objects Overhead
**Утверждение**: Каждый объект в Python имеет большой overhead

**Анализ**:
```python
# Каждая свеча - это dict:
candle = {
    'timestamp': 1234567890,
    'open': 0.1234,
    'high': 0.1235,
    'low': 0.1233,
    'close': 0.1234,
    'volume': 1000.0
}
```

**Размер в памяти**:
- Dict overhead: ~240 bytes
- 6 key-value pairs * ~50 bytes = ~300 bytes
- **Итого: ~540 bytes на свечу**

Но мы считали только длину списка:
- 59 монет * 11 свечей * 540 bytes = 350 KB (0.35 MB)

**Это НЕ объясняет 30 MB!**

**Приоритет**: ⚠️ ВАЖНО
**Валидация**: Нужен memory profiler

---

### 🔴 C4.2 - Logs Files Growth (не в RAM, но на диске)
**Утверждение**: Логи растут на диске, но мы меряем RSS

**Проверка**:
- Мы меряем `process.memory_info().rss` = Resident Set Size (RAM)
- Файлы logs/*.json не должны влиять на RSS

**Вывод**: Маловероятно

**Приоритет**: ✅ НИЗКИЙ

---

### 🔴 C4.3 - WebSocket Messages in Memory
**Утверждение**: websockets библиотека накапливает сообщения

**Анализ**:
- 20 WebSocket connections (59 coins / 3 per connection)
- Каждое соединение получает трейды в real-time
- Если receive buffer не очищается → накопление

**Расчет** (грубый):
- ~100 трейдов/s на 59 монет = ~170 трейдов/s
- Каждое сообщение ~200 bytes
- 120s * 170 * 200 bytes = 4 MB

**Это тоже мало для 30 MB!**

**Приоритет**: ⚠️ ВАЖНО

---

### 🔴 C4.4 - Multiple TradeWebSocket Instances
**Утверждение**: Создается несколько экземпляров aggregator

**Проверка кода** (test_01_buffer_memory_short.py:43-44):
```python
filtered_coins = get_all_symbols_by_volume()
aggregator = TradeWebSocket(filtered_coins)
```

**Но** мы запускаем это В ТЕСТЕ, а не в main().

Может быть:
1. Тест создает aggregator
2. main() тоже запущен в фоне?
3. Два aggregator → двойная память!

**Приоритет**: 🔴 КРИТИЧНО
**Валидация**: Проверить процессы

---

### 🔴 C4.5 - JSON Encoding in Log Queue
**Утверждение**: Логи сериализуются в JSON и хранятся как строки

**Анализ** (config.py:314-326):
```python
# В worker логирования
for coin, candle_data in batch:
    # Console log
    logger.info(f"...")

    # File log
    log_record = type('obj', (object,), {
        'levelname': 'INFO',
        'getMessage': lambda self: f"Candle for {coin}",
        'coin': coin,
        'candle_data': candle_data  # Dict stored here!
    })()
    file_handler.emit(log_record)
```

**Проблема**:
- candle_data хранится в log_record
- log_record хранится в queue (C3.3 показал 661 items)
- 661 свечей * 540 bytes = 0.36 MB

**Опять мало!**

**Приоритет**: ⚠️ ВАЖНО

---

### 🔴 C4.6 - Imports Cache / Module Caching
**Утверждение**: Python кеширует модули и их данные

**Анализ**:
Каждый раз когда делаем `from src.config import log_new_candle` - модуль загружается в память.

**Но** Python кеширует модули в `sys.modules`, не создает копии.

**Приоритет**: ✅ НИЗКИЙ

---

## Главная гипотеза

### 🔴🔴🔴 C4.7 - Console Logging Unicode Encoding
**Утверждение**: Console logging с unicode символами создает большие строки в памяти

**Анализ логов**:
```
2025-10-01 06:29:50 - INFO - 📊 ❌ NO SIGNAL for ONDOUSDT | Candles: 211 | Passed: [growth_filter(-0.08)] | Failed: [low_vol(4913.0 vs 0.0), narrow_rng(0.0001 vs 0.0), high_natr(0.017 vs 0.6)]
```

**Проблемы**:
1. Emoji (📊 ❌) - каждый ~4 bytes в UTF-8
2. Длинные строки (>200 символов)
3. Логируется для КАЖДОГО сигнала: 59 монет * 20 раз/минуту = 1180 логов/минуту
4. Python logging держит recent logs в памяти!

**Расчет**:
- 1180 логов/мин * 200 bytes/log * 2 minutes = 472 KB

**Опять мало!**

**НО** если учесть, что logging.StreamHandler буферизует:
- Handler может держать последние N логов
- logging module сам имеет memory overhead

**Приоритет**: ⚠️ ВАЖНО

---

## План валидации Cross-Audit #3

1. **C4.4** - Проверить нет ли множественных экземпляров aggregator
2. **C4.1** - Memory profiler для точного подсчета
3. **C4.7** - Отключить console logging и проверить память
4. **C4.3** - Проверить WebSocket buffers
5. **C4.5** - Проверить JSON encoding overhead

---

## Критическое наблюдение

**Из test_01 результатов**:
```
[270s] Memory: 69.16MB (+32.67MB, +89.5%)
[301s] Memory: 34.98MB (+-1.52MB, +-4.2%)  # РЕЗКИЙ СПАД!
```

**Память УПАЛА с 69 MB до 35 MB между 270s и 301s!**

Это означает:
1. Garbage Collector сработал
2. Или процесс перезапустился
3. Или memory measurement некорректен

**Новая гипотеза C4.8**: Memory measurement нестабилен

**Приоритет**: 🔴 КРИТИЧНО

---

## Ожидаемые результаты

**Высокая вероятность**:
- C4.4 (Multiple instances)
- C4.8 (Measurement error)

**Средняя вероятность**:
- C4.1 (Python overhead)
- C4.7 (Console logging)

**Низкая вероятность**:
- C4.3, C4.5, C4.6 (малые вклады)

**Цель**: Найти источник 30 MB leak ИЛИ доказать что measurement некорректен.
