# Критическая проблема: Потеря данных в обработке WebSocket

## Описание проблемы

В методе `_process_trade_to_candle()` в файле `src/websocket_handler.py` существует критическая ошибка, приводящая к потере накопленных сделок при переключении между 10-секундными периодами свечей.

## Текущая логика (строки 356-360)

```python
else:
    # Trade from future period - means current candle period ended
    # Timer will finalize old candle and we start accumulating for new period
    current_data['candle_start_time'] = candle_start_time
    current_data['trades'] = [trade_data]
```

## Проблемный сценарий

1. Система накапливает сделки для периода 10:00-10:00:10
2. В 10:00:08 приходит сделка из 10:00:15 (например, из-за задержки в передаче или синхронизации)
3. Текущая логика заменяет накопленные сделки для периода 10:00:0-10:00:10 новой сделкой из 10:00:15
4. При этом предыдущие сделки теряются без финализации свечи

## Последствия

- Потеря накопленных сделок без финализации соответствующей свечи
- Нарушение целостности данных для технического анализа и сигналов
- Возможное неправильное формирование свечей

## Рекомендуемое решение

Модифицировать логику метода `_process_trade_to_candle()` следующим образом:

```python
else:
    # Trade from future period - finalize current candle before starting new one
    # Check if we have accumulated trades that need to be finalized
    if current_data['trades'] and current_data['candle_start_time'] is not None:
        # Create and finalize the current candle with accumulated trades
        completed_candle = create_candle_from_trades(
            current_data['trades'],
            current_data['candle_start_time']
        )
        # Add to buffer to ensure it's not lost
        self.candles_buffer[symbol].append(completed_candle)
        
        # Trim buffer if needed
        if len(self.candles_buffer[symbol]) > WARMUP_INTERVALS:
            self.candles_buffer[symbol] = self.candles_buffer[symbol][-WARMUP_INTERVALS:]
    
    # Start new candle for future period
    current_data['candle_start_time'] = candle_start_time
    current_data['trades'] = [trade_data]
```

## Дополнительные соображения

1. Также необходимо учитывать промежуточные периоды между текущим и будущим периодом для корректного заполнения пропусков
2. Может потребоваться обновление `last_finalized_boundary` при финализации свечи в процессе
3. Необходимо протестировать сценарии с несколькими пропущенными периодами между текущим и полученным

## Влияние на систему

- Потеря данных влияет на точность сигналов
- Может повлиять на логику прогрева системы
- Влияет на целостность исторических данных