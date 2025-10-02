"""
Тест для сбора данных OHLCV за 2 минуты для указанных монет
Собирает свечные данные сразу после агрегации и выводит OHLCV
"""
import sys
import os
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.websocket_handler import TradeWebSocket
from src.config import start_candle_logging

# Указанные монеты для теста
TEST_SYMBOLS = [
    '0GUSDT',
    '1000BONKUSDT',
    'ALPINEUSDT',
    'ASTERUSDT',
    'AVNTUSDT',
    'BIOSUSDT',
    'BLESSUSDT',
    'EDENUSDT',
    'EIGENUSDT'
]

async def test_ohlcv_collection():
    """Тест сбора OHLCV данных за 2 минуты"""
    print("=" * 80)
    print("ТЕСТ СБОРА OHLCV ДАННЫХ ЗА 2 МИНУТЫ")
    print("=" * 80)
    
    print(f"\n📊 Тестируемые монеты ({len(TEST_SYMBOLS)}):")
    for i, symbol in enumerate(TEST_SYMBOLS, 1):
        print(f"   {i}. {symbol}")
    
    # Создаем директорию для результатов если не существует
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    
    # Инициализируем логирование свечей
    start_candle_logging()
    await asyncio.sleep(0.5)
    
    # Создаем WebSocket для указанных монет
    aggregator = TradeWebSocket(TEST_SYMBOLS)
    ws_task = asyncio.create_task(aggregator.start_connection())
    
    print("\n🔗 Подключение к WebSocket...")
    await asyncio.sleep(2)  # Даем время на подключение
    
    print("\n⏳ Сбор данных OHLCV в течение 2 минут (120 секунд)...")
    print("📊 Агрегация 10-секундных свечей в реальном времени:")
    print("-" * 90)
    
    start_time = time.time()
    collection_duration = 120  # 2 минуты
    last_10sec_report = start_time
    
    # Структура для хранения OHLCV данных
    ohlcv_data = {}
    
    try:
        while time.time() - start_time < collection_duration:
            await asyncio.sleep(0.5)  # Более частая проверка для детализации
            current_time = time.time()
            
            # Проверяем новые свечи каждые 10 секунд для наглядности
            if current_time - last_10sec_report >= 10:
                elapsed = int(current_time - start_time)
                current_10sec_period = (elapsed // 10) + 1
                
                print(f"\n🕯️ 10-секундный период #{current_10sec_period} (время: {elapsed}s):")
                print("-" * 90)
                print(f"{'Монета':<15} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10} {'Volume':<12}")
                print("-" * 90)
                
                period_has_data = False
                
                for symbol in TEST_SYMBOLS:
                    candles = aggregator.candles_buffer.get(symbol, [])
                    if candles:
                        if symbol not in ohlcv_data:
                            ohlcv_data[symbol] = []
                        
                        # Добавляем только новые свечи
                        last_candle_count = len(ohlcv_data[symbol])
                        new_candles = candles[last_candle_count:]
                        
                        for candle in new_candles:
                            # Форматируем временную метку
                            candle_time = datetime.fromtimestamp(candle['timestamp'] / 1000)
                            
                            ohlcv_entry = {
                                'timestamp': candle['timestamp'],
                                'time_str': candle_time.strftime('%H:%M:%S'),
                                'open': candle['open'],
                                'high': candle['high'],
                                'low': candle['low'],
                                'close': candle['close'],
                                'volume': candle['volume']
                            }
                            ohlcv_data[symbol].append(ohlcv_entry)
                        
                        # Показываем последнюю свечу для каждой монеты
                        if candles:
                            last_candle = candles[-1]
                            print(f"{symbol:<15} {last_candle['open']:<10.6f} {last_candle['high']:<10.6f} "
                                  f"{last_candle['low']:<10.6f} {last_candle['close']:<10.6f} {last_candle['volume']:<12.2f}")
                            period_has_data = True
                        else:
                            print(f"{symbol:<15} {'Нет данных':<58}")
                    else:
                        print(f"{symbol:<15} {'Нет данных':<58}")
                
                if not period_has_data:
                    print("📝 За этот период данных еще нет, агрегация продолжается...")
                
                last_10sec_report = current_time
    
    except KeyboardInterrupt:
        print("\n⚠️ Тест прерван")
    finally:
        await aggregator.stop()
        await asyncio.sleep(1)
    
    # Финальный отчет
    print("\n" + "=" * 80)
    print("ФИНАЛЬНЫЙ ОТЧЕТ OHLCV")
    print("=" * 80)
    
    elapsed = int(time.time() - start_time)
    print(f"\n⏱️ Длительность сбора: {elapsed} секунд")
    
    # Сохраняем результаты в JSON файл
    results_file = results_dir / f"ohlcv_2min_{int(start_time)}.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(ohlcv_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Результаты сохранены в: {results_file}")
    
    # Вывод статистики по каждой монете
    print(f"\n📊 Статистика по монетам:")
    print("-" * 80)
    print(f"{'Монета':<15} {'Свечей':<8} {'Объем':<12} {'Последняя цена':<12} {'Время':<10}")
    print("-" * 80)
    
    total_candles_all = 0
    total_volume_all = 0
    
    for symbol in TEST_SYMBOLS:
        candles = ohlcv_data.get(symbol, [])
        candle_count = len(candles)
        
        if candle_count > 0:
            last_candle = candles[-1]
            total_volume = sum(c['volume'] for c in candles)
            last_price = last_candle['close']
            last_time = last_candle['time_str']
            
            print(f"{symbol:<15} {candle_count:<8} {total_volume:<12.2f} {last_price:<12.6f} {last_time:<10}")
            
            total_candles_all += candle_count
            total_volume_all += total_volume
        else:
            print(f"{symbol:<15} {'0':<8} {'0.00':<12} {'N/A':<12} {'N/A':<10}")
    
    print("-" * 80)
    print(f"{'ИТОГО':<15} {total_candles_all:<8} {total_volume_all:<12.2f} {'-':<12} {'-':<10}")
    
    # Вывод последних 5 свечей для каждой монеты
    print(f"\n🕯️ Последние 5 свечей для каждой монеты:")
    print("-" * 80)
    
    for symbol in TEST_SYMBOLS:
        candles = ohlcv_data.get(symbol, [])
        if candles:
            print(f"\n{symbol}:")
            print(f"{'Время':<10} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10} {'Volume':<10}")
            print("-" * 60)
            
            # Показываем последние 5 свечей
            recent_candles = candles[-5:]
            for candle in recent_candles:
                print(f"{candle['time_str']:<10} "
                      f"{candle['open']:<10.6f} "
                      f"{candle['high']:<10.6f} "
                      f"{candle['low']:<10.6f} "
                      f"{candle['close']:<10.6f} "
                      f"{candle['volume']:<10.2f}")
        else:
            print(f"\n{symbol}: Нет данных")
    
    print("\n" + "=" * 80)
    print("✅ ТЕСТ ЗАВЕРШЕН")
    print("=" * 80)
    
    return True

async def main():
    """Главная функция теста"""
    try:
        success = await test_ohlcv_collection()
        return success
    except Exception as e:
        print(f"\n❌ ОШИБКА ТЕСТА: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)