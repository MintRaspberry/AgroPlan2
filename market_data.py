import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import database
import logging

logger = logging.getLogger(__name__)


class MarketDataService:
    def __init__(self):
        self.sources = {
            'min_agriculture': 'https://api.mcx.ru/api/v1/',  # Пример API (мок)
            'agro_birzha': 'https://agro-birzha.ru/api/'  # Пример API (мок)
        }

    def get_current_prices(self, crops: List[str], region: str = "Центральный федеральный округ") -> Dict[str, float]:
        """Получить текущие рыночные цены на культуры"""
        prices = {}

        for crop in crops:
            # Пытаемся получить цену из базы данных
            db_price = database.db.get_current_market_price(crop, region)
            if db_price:
                prices[crop] = db_price
            else:
                # Если нет в базе, используем мок-данные
                prices[crop] = self._get_mock_price(crop)

        return prices

    def update_prices_from_external(self, region: str = "Центральный федеральный округ"):
        """Обновление цен из внешних источников (мок-реализация)"""
        # В реальном приложении здесь был бы парсинг сайтов Минсельхоза и аграрных бирж
        mock_prices = {
            "пшеница озимая": 15200,
            "пшеница яровая": 14200,
            "ячмень яровой": 12500,
            "овёс": 11500,
            "горох": 25500,
            "соя": 36000,
            "подсолнечник": 46000,
            "рапс яровой": 28500,
            "лён": 30500,
            "картофель": 21000,
            "свёкла сахарная": 18500,
            "кукуруза на зерно": 12500,
            "гречиха": 33000,
            "люцерна": 18500
        }

        today = datetime.now().strftime('%Y-%m-%d')
        for crop, price in mock_prices.items():
            database.db.update_market_price(crop, price, today, region, "Минсельхоз РФ")

        logger.info(f"Обновлены рыночные цены для {len(mock_prices)} культур")

    def get_price_trend(self, crop: str, days: int = 30, region: str = "Центральный федеральный округ") -> List[Dict]:
        """Получить тренд цен за период"""
        # Мок-реализация тренда цен
        base_price = database.db.get_current_market_price(crop, region) or self._get_mock_price(crop)
        trends = []

        for i in range(days, 0, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            # Имитация колебаний цен
            fluctuation = (i % 7 - 3) * 0.01  # Небольшие колебания
            price = base_price * (1 + fluctuation)

            trends.append({
                'date': date,
                'price': round(price, 2),
                'change_percent': round(fluctuation * 100, 1)
            })

        return trends

    def calculate_profitability(self, crop: str, area: float, expected_yield: float,
                                region: str = "Центральный федеральный округ") -> Dict:
        """Расчет рентабельности выращивания культуры"""
        crop_rule = database.db.get_crop_rule(crop)
        if not crop_rule:
            return {}

        current_price = self.get_current_prices([crop], region).get(crop, 0)

        # Расчет затрат (упрощенный)
        fertilizer_cost = (crop_rule['fertilizer_n'] * 50 +  # Цена за кг N
                           crop_rule['fertilizer_p'] * 40 +  # Цена за кг P
                           crop_rule['fertilizer_k'] * 30)  # Цена за кг K

        other_costs = 15000  # Прочие затраты на гектар (семена, обработка, уборка)
        total_costs_per_ha = fertilizer_cost + other_costs

        # Расчет доходов
        revenue_per_ha = expected_yield * current_price
        profit_per_ha = revenue_per_ha - total_costs_per_ha
        profitability = (profit_per_ha / total_costs_per_ha) * 100 if total_costs_per_ha > 0 else 0

        return {
            'crop': crop,
            'area': area,
            'expected_yield': expected_yield,
            'market_price': current_price,
            'revenue_per_ha': round(revenue_per_ha, 2),
            'costs_per_ha': round(total_costs_per_ha, 2),
            'profit_per_ha': round(profit_per_ha, 2),
            'profitability_percent': round(profitability, 1),
            'total_revenue': round(revenue_per_ha * area, 2),
            'total_profit': round(profit_per_ha * area, 2)
        }

    def _get_mock_price(self, crop: str) -> float:
        """Мок-цены для демонстрации"""
        mock_prices = {
            "пшеница озимая": 15000,
            "пшеница яровая": 14000,
            "ячмень яровой": 12000,
            "овёс": 11000,
            "горох": 25000,
            "соя": 35000,
            "подсолнечник": 45000,
            "рапс яровой": 28000,
            "лён": 30000,
            "картофель": 20000,
            "свёкла сахарная": 18000,
            "кукуруза на зерно": 12000,
            "гречиха": 32000,
            "люцерна": 18000
        }
        return mock_prices.get(crop, 10000)


# Глобальный экземпляр сервиса рыночных данных
market_data_service = MarketDataService()
