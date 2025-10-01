# Iteration 3 - Audit #1: Initial Hypotheses Generation

## Дата
2025-10-01

## Источники данных
1. **Код**: main.py, websocket_handler.py, candle_aggregator.py, signal_processor.py, config.py, trading_api.py
2. **Предыдущие аудиты**: iteration_1 и iteration_2 результаты
3. **Проблемы из iteration_2**:
   - Zero-volume candles: 48.3% (ожидалось ~2.4%)
   - Zero-interval candles: 19.5% (duplicate timestamps)
   - Warmup logging broken (только "1/10")
   - Отсутствие rolling window (потенциально memory leak)
   - Volume filter использует 24h window неправильно

## Анализ текущего состояния

### Изменения после iteration_2:
1. **websocket_handler.py**: Дедупликация работает (добавлена в iteration_1)
2. **config.py**: WARMUP_INTERVALS = 10 (было 25)
3. **trading_api.py**: Volume filter использует turnover24h
4. **candles_buffer**: Неограниченный рост (нет rolling window)

### Критические наблюдения из кода:

#### 1. Отсутствие Rolling Window (КРИТИЧНО)
```python
# websocket_handler.py:320-321
self.candles_buffer[symbol].append(completed_candle)
```
**Проблема**: Нет ограничения на размер буфера. В CLAUDE.md упоминается "rolling 100-candle limit", но код её не содержит.

#### 2. Volume Filter по 24h окну (ПРОБЛЕМА)
```python
# trading_api.py:129
volume_24h = float(item.get('turnover24h', 0))
```
**Проблема**: Монеты с высоким 24h volume могут иметь низкую текущую активность.

#### 3. Warmup Logging Interval (ПРОБЛЕМА)
```python
# main.py:139-142
if min_candles - last_warmup_log >= 10 or (min_candles == 1 and last_warmup_log == 0):
```
**Проблема**: Условие `>= 10` слишком большое для WARMUP_INTERVALS=10.

#### 4. Async Logging Reordering (ПОТЕНЦИАЛЬНАЯ ПРОБЛЕМА)
```python
# config.py:348-355
def log_new_candle(coin: str, candle_data: dict):
    """Log new candle data - async via queue to prevent time drift"""
    if candle_data:
        try:
            _candle_log_queue.put_nowait((coin, candle_data))  # ASYNC!
        except queue.Full:
            pass
```
**Проблема**: Queue может обрабатывать свечи не по порядку.

## Новые гипотезы для валидации

### H3.1 - Rolling Window отсутствует (КРИТИЧНО)
**Утверждение**: candles_buffer растет бесконечно без ограничения
**Источник**: websocket_handler.py:320, CLAUDE.md упоминает "rolling 100-candle limit"
**Влияние**: Утечка памяти, рост RSS пропорционально времени работы
**Приоритет**: 🔴 КРИТИЧНО
**Валидация**: Проверить размер candles_buffer через 5 минут работы

### H3.2 - Volume Filter по 24h окну (КРИТИЧНО)
**Утверждение**: MIN_DAILY_VOLUME фильтр позволяет монетам с низкой текущей активностью
**Источник**: 48.3% zero-volume из iteration_2
**Влияние**: Обработка низкоактивных монет, waste resources
**Приоритет**: 🔴 КРИТИЧНО
**Валидация**: Сравнить 24h volume с 1h/4h volume для проблемных монет

### H3.3 - Warmup Logging Interval (ВАЖНО)
**Утверждение**: Условие `>= 10` не подходит для WARMUP_INTERVALS=10
**Источник**: Только "1/10" лог из iteration_2
**Влияние**: Нет видимости прогресса warmup
**Приоритет**: ⚠️ ВАЖНО
**Валидация**: Изменить условие и проверить логирование

### H3.4 - Async Logging Reordering (ВАЖНО)
**Утверждение**: Async queue может переставлять свечи местами
**Источник**: 19.5% zero-interval из iteration_2
**Влияние**: Дубликаты в логах, путаница в данных
**Приоритет**: ⚠️ ВАЖНО
**Валидация**: Проверить порядок свечей в websocket.json

### H3.5 - Forward-fill для низкоактивных монет (ВАЖНО)
**Утверждение**: Forward-fill создается для монет с низкой активностью
**Источник**: 48.3% zero-volume из iteration_2
**Влияние**: Много пустых свечей, waste processing
**Приоритет**: ⚠️ ВАЖНО
**Валидация**: Проверить если проблема в volume filter или в forward-fill логике

### H3.6 - Signal criteria слишком строгие (ПОТЕНЦИАЛЬНО)
**Утверждение**: 0 TRUE signals за 240 секунд из iteration_2
**Источник**: 0 TRUE, 8148 FALSE signals
**Влияние**: Система не генерирует сигналы
**Приоритет**: ✅ СРЕДНИЙ
**Валидация**: Проверить критерии для типичных монет

## План валидации

1. **H3.1 & H3.2** - Запустить 5-минутный тест с мониторингом памяти и буфера
2. **H3.3** - Простой тест с фиксом логики
3. **H3.4** - Анализ порядка свечей в логах
4. **H3.5** - Проверить связь с volume filter
5. **H3.6** - Анализ критериев сигналов

## Ожидаемые результаты

### Валидные гипотезы (прогноз):
- H3.1 (Rolling Window) - Высокая вероятность
- H3.2 (Volume Filter) - Высокая вероятность  
- H3.3 (Warmup Logging) - Средняя вероятность

### Сомнительные:
- H3.6 (Signal criteria) - Может быть нормально