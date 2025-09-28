# Backlog

## WebSocket Connection Optimization
- Added max_coins_per_connection parameter to TradeWebSocket class to allow configuration of coins per connection
- Updated _calculate_needed_connections to use max_coins_per_connection instead of hardcoded 30
- Updated _distribute_symbols_to_connections to use max_coins_per_connection instead of hardcoded 30
- Updated logging messages to reflect configurable max coins per connection
- Set default max_coins_per_connection to 20 to improve connection stability

## Оптимизация обработки WebSocket соединений
- [2025-09-29] Улучшена обработка ошибок WebSocket соединений для предотвращения дублирования сообщений об ошибках
- [2025-09-29] Добавлена поддержка автоматического переподключения при разрывах соединений
- [2025-09-29] Оптимизирована логика обработки исключений в WebSocket соединениях
- [2025-09-29] Улучшена стабильность работы с большими списками монет (до 389 монет)
# Backlog

## Changes Made to WebSocket Handler Architecture

- **Date**: 2025-09-28
- **Change**: Redesigned WebSocket architecture to handle multiple connections with load distribution
- **Details**:
  - Implemented multiple WebSocket connections to distribute coins and avoid exchange limits
  - Maximum 30 coins per WebSocket connection to stay within Bybit's subscription limits
  - For 350 coins, system now uses up to 12 connections (350/30 ≈ 12 connections)
  - Added `_distribute_symbols_to_connections()` method to evenly distribute symbols across connections
  - Added `_calculate_needed_connections()` method to calculate required connections
  - Added `start_connection_with_display()` method for connections with trade flow display
  - Added console output showing how many WebSocket connections are being used
- **Reason**: Original architecture would use one WebSocket connection with potentially 350 subscriptions, which exceeds Bybit's limits
- **Files affected**: `src/websocket_handler.py`

## Previous Changes


## Изменения в проекте (2025-09-28)

### Добавлено
- Модульная архитектура проекта с папкой src/
- WebSocket-подключение для получения данных в реальном времени
- Агрегация трейдов в 10-секундные свечи
- Фильтрация монет по объему торгов (MIN_DAILY_VOLUME)
- Буферизация трейдов с очисткой старых данных
- Логирование и улучшенная обработка ошибок

### Улучшено
- Замена 1-минутных свечей на 10-секундные для более актуальных данных
- Разделение функциональности на отдельные модули для лучшей поддерживаемости
- Оптимизация производительности при расчете метрик

### Ошибки
- Исправлено несоответствие в конфигурации интервала обновления (DEFAULT_UPDATE_INTERVAL должен быть 6000 для 10 минут, а не 60000)

### Изменения для реализации сигналов
- Добавлен модуль src/signal_processor.py для вычисления условий сигналов
- Интегрирована функциональность сигналов в src/websocket_handler.py
- Обновлен main.py для отправки сигналов в момент их получения
- Созданы тесты для проверки функциональности сигналов

### Последние изменения (по требованиям пользователя)
- Обновлено логирование в main.py: теперь отображается только количество отфильтрованных монет, сигналы и события подключения/отключения WebSocket
- Добавлены обработчики событий подключения и отключения WebSocket
- Изменена логика обработки сигналов на непрерывную (в реальном времени) вместо фиксированных интервалов
- Уменьшено минимальное количество трейдов для расчета сигнала с 50 до 20 в websocket_handler.py
- Убраны лишние логи и выводы в консоль в websocket_handler.py для соответствия требованиям минимального логирования
- Изменено значение DEFAULT_UPDATE_INTERVAL в конфигурации, чтобы отразить работу системы в реальном времени
- Уменьшена пауза в цикле проверки сигналов до 0.3 секунды для более частой проверки
- Изменена архитектура WebSocket: теперь используется распределение монет по нескольким соединениям (до 30 монет на соединение) вместо одного соединения с 350 подписками