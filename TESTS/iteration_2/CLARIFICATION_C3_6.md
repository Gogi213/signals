# Clarification: C3.6 & C5.1 - Signals.json Content Issue

## User Observation (CORRECT!)

**Ожидание**:
signals.json должен содержать:
```json
{
  "coin": "ONDOUSDT",
  "signal_type": "false",
  "criteria_details": {
    "low_vol": {"current": 4913.0, "threshold": 0.0, "passed": false},
    "narrow_rng": {"current": 0.0001, "threshold": 0.0, "passed": false},
    "high_natr": {"current": 0.017, "threshold": 0.6, "passed": false},
    "growth_filter": {"current": -0.08, "threshold": -0.1, "passed": true}
  }
}
```

**Реальность**:
signals.json содержит:
```json
{
  "coin": "XAUTUSDT",
  "signal_type": "false",
  "criteria_details": {
    "validation_error": "Insufficient data: 19 candles (need 20+)",
    "candle_count": 19,
    "criteria_details": {}  ← ПУСТО!
  }
}
```

---

## Root Cause Analysis

### Почему Console ЕСТЬ, а signals.json НЕТ?

**Console logging** (config.py:200-226):
```python
def log_signal(coin, signal, signal_data, warmup_complete):
    # ... validation checks ...

    logger.info(f"📊 {'✅ SIGNAL' if signal else '❌ NO SIGNAL'} for {coin} | ...")  # CONSOLE
```

**File logging** (config.py:167-176):
```python
def log_signal(coin, signal, signal_data, warmup_complete):
    # File logging to signals.json
    file_handler = JSONFileHandler(os.path.join(LOGS_DIR, 'signals.json'))
    log_record = type('obj', (object,), {
        'criteria_details': signal_data.get('criteria', {}) if signal_data else {}
        #                                    ^^^^^^^^^ БЕРЕТ 'criteria'
    })()
    file_handler.emit(log_record)
```

**Проблема**: File logging пишет `signal_data.get('criteria', {})`, но ПЕРЕД этим есть RETURN!

### Детальный flow:

```python
# config.py:133-164
def log_signal(coin, signal, signal_data, warmup_complete):
    # Skip if warmup not complete
    if not warmup_complete:
        return  # ← EXIT #1

    # Skip specific validation errors
    if signal_data:
        if 'validation_error' in signal_data:
            val_err = signal_data['validation_error']
            if val_err and not val_err.startswith('Insufficient data'):
                return  # ← EXIT #2 (forward-fill, invalid candles)

        if 'criteria' in signal_data:
            criteria = signal_data['criteria']
            if 'validation_error' in criteria:
                val_err = criteria['validation_error']
                if val_err and not val_err.startswith('Insufficient data'):
                    return  # ← EXIT #3

    # Дошли сюда = warmup_complete=True И ('Insufficient data' ИЛИ нет validation_error)

    # FILE LOGGING:
    file_handler.emit({
        'criteria_details': signal_data.get('criteria', {})  # ← Пишет 'criteria'
    })

    # CONSOLE LOGGING:
    if signal_data and 'criteria' in signal_data:
        criteria = signal_data['criteria']
        if 'criteria_details' in criteria:  # ← Проверяет 'criteria_details'
            # Detailed criteria logging
            passed_criteria = [...]
            failed_criteria = [...]
            logger.info(f"📊 ... | Passed: [...] | Failed: [...]")  # КОНСОЛЬ!
```

### Проблема в данных из signal_processor:

**Период 10-20 свечей** (signal_processor.py:190-192):
```python
if len(candles) < 20:
    detailed_info['validation_error'] = f'Insufficient data: {len(candles)} candles (need 20+)'
    return False, detailed_info  # ← criteria_details НЕ заполнены!
```

**Период 20+ свечей** (signal_processor.py:208-231):
```python
# Check all conditions with detailed values
low_vol_passed, low_vol_details = check_low_volume_condition(candles)
# ...

# Store detailed criteria
detailed_info['criteria_details'] = {  # ← ЗАПОЛНЯЮТСЯ!
    'low_vol': low_vol_details,
    'narrow_rng': narrow_rng_details,
    ...
}
```

---

## Вывод

**C3.6 и C5.1 КОРРЕКТНЫ**, но User observation добавляет ясности:

**Проблема НЕ в том что signals.json "broken"**, а в том что:

1. **Warmup=10, signal_processor=20** (C5.1)
   → Период 10-20 свечей логируется с "Insufficient data"
   → criteria_details пустые

2. **После 20 свечей criteria ДОЛЖНЫ появиться**
   → НО в моих тестах не успели накопить 20 свечей за 2 минуты

3. **Console logging работает после 20 свечей**
   → User видел console с "Candles: 211"
   → Значит система УЖЕ работала >20 свечей
   → signals.json ДОЛЖЕН содержать эти же данные!

---

## Новая гипотеза C6.6: signals.json Stops Logging After Warmup

**Проблема**: signals.json содержит ТОЛЬКО warmup период (10-20 свечей), а после 20 свечей ПЕРЕСТАЕТ писать!

**Возможная причина**: Какой-то другой validation_error появляется после 20 свечей и блокирует логирование.

**Валидация**: Запустить 5-минутный тест и проверить signals.json после 20 свечей.
