import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
import database
import logging

logger = logging.getLogger(__name__)


class WeatherService:
    def __init__(self, openweather_api_key: str = None):
        self.openweather_api_key = openweather_api_key
        self.base_url = "http://api.openweathermap.org/data/2.5"

    def get_current_weather(self, lat: float, lon: float) -> Optional[Dict]:
        """Получить текущую погоду по координатам"""
        if not self.openweather_api_key:
            logger.warning("OpenWeather API ключ не установлен")
            return self._get_mock_weather_data()

        try:
            url = f"{self.base_url}/weather"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.openweather_api_key,
                'units': 'metric',
                'lang': 'ru'
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return {
                'temperature': data['main']['temp'],
                'temperature_min': data['main']['temp_min'],
                'temperature_max': data['main']['temp_max'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': data['wind']['speed'],
                'weather_description': data['weather'][0]['description'],
                'precipitation': data.get('rain', {}).get('1h', 0) + data.get('snow', {}).get('1h', 0)
            }
        except Exception as e:
            logger.error(f"Ошибка получения погоды: {e}")
            return self._get_mock_weather_data()

    def get_forecast(self, lat: float, lon: float, days: int = 7) -> Optional[Dict]:
        """Получить прогноз погоды на несколько дней"""
        if not self.openweather_api_key:
            return self._get_mock_forecast(days)

        try:
            url = f"{self.base_url}/forecast"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.openweather_api_key,
                'units': 'metric',
                'lang': 'ru'
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            forecasts = []

            for item in data['list'][:days * 8]:  # 8 прогнозов в день
                forecast = {
                    'datetime': datetime.fromtimestamp(item['dt']),
                    'temperature': item['main']['temp'],
                    'temperature_min': item['main']['temp_min'],
                    'temperature_max': item['main']['temp_max'],
                    'humidity': item['main']['humidity'],
                    'precipitation': item.get('rain', {}).get('3h', 0) + item.get('snow', {}).get('3h', 0),
                    'wind_speed': item['wind']['speed'],
                    'weather_description': item['weather'][0]['description']
                }
                forecasts.append(forecast)

            return forecasts
        except Exception as e:
            logger.error(f"Ошибка получения прогноза: {e}")
            return self._get_mock_forecast(days)

    def get_historical_weather(self, lat: float, lon: float, start_date: str, end_date: str) -> Optional[Dict]:
        """Получить исторические данные о погоде (требуется платная подписка OpenWeather)"""
        # Для демонстрации используем мок-данные
        return self._get_mock_historical_data(start_date, end_date)

    def _get_mock_weather_data(self) -> Dict:
        """Мок-данные для демонстрации"""
        return {
            'temperature': 15.5,
            'temperature_min': 12.0,
            'temperature_max': 18.0,
            'humidity': 65,
            'pressure': 1013,
            'wind_speed': 3.2,
            'weather_description': 'переменная облачность',
            'precipitation': 0.0
        }

    def _get_mock_forecast(self, days: int) -> list:
        """Мок-прогноз для демонстрации"""
        forecasts = []
        base_date = datetime.now()

        for i in range(days):
            forecast_date = base_date + timedelta(days=i)
            forecasts.append({
                'datetime': forecast_date,
                'temperature': 15 + i,
                'temperature_min': 12 + i,
                'temperature_max': 18 + i,
                'humidity': 60 + i * 2,
                'precipitation': max(0, i - 2) * 2,  # Начинаем осадки с 3-го дня
                'wind_speed': 3.0,
                'weather_description': 'ясно' if i < 3 else 'небольшой дождь'
            })

        return forecasts

    def _get_mock_historical_data(self, start_date: str, end_date: str) -> list:
        """Мок-исторические данные для демонстрации"""
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end - start).days + 1

        data = []
        for i in range(days):
            current_date = start + timedelta(days=i)
            data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'temperature_avg': 15 + (i % 10) - 5,  # Колебания температуры
                'temperature_min': 10 + (i % 10) - 5,
                'temperature_max': 20 + (i % 10) - 5,
                'precipitation': 2.0 if i % 5 == 0 else 0.0,  # Осадки каждые 5 дней
                'humidity': 60 + (i % 20),
                'wind_speed': 3.0 + (i % 10) / 5,
                'solar_radiation': 150 + (i % 50)
            })

        return data


class ClimateAnalyzer:
    def __init__(self, db: database.Database, weather_service: WeatherService):
        self.db = db
        self.weather_service = weather_service

    def analyze_field_climate(self, field_id: int) -> Dict:
        """Анализ климатических условий для поля"""
        field = self.db.get_field(field_id)
        if not field:
            return {}

        # Получаем текущую погоду
        current_weather = self.weather_service.get_current_weather(
            field['latitude'] or 55.7558,
            field['longitude'] or 37.6173
        )

        # Получаем прогноз
        forecast = self.weather_service.get_forecast(
            field['latitude'] or 55.7558,
            field['longitude'] or 37.6173
        )

        # Анализируем климатическую зону
        climate_zone = self._determine_climate_zone(field, current_weather)

        # Сохраняем климатические данные
        if current_weather:
            self.db.save_climate_data(
                field_id,
                datetime.now().strftime('%Y-%m-%d'),
                current_weather['temperature'],
                current_weather['temperature_min'],
                current_weather['temperature_max'],
                current_weather['precipitation'],
                current_weather['humidity'],
                current_weather['wind_speed'],
                150  # Мок-данные солнечной радиации
            )

        return {
            'current_weather': current_weather,
            'climate_zone': climate_zone,
            'forecast_summary': self._summarize_forecast(forecast),
            'growing_season_info': self._get_growing_season_info(field)
        }

    def _determine_climate_zone(self, field: Dict, weather: Dict) -> str:
        """Определение климатической зоны на основе данных"""
        if not weather:
            return "умеренный"

        temp = weather.get('temperature', 15)
        if temp < 5:
            return "северный"
        elif temp < 15:
            return "умеренный"
        else:
            return "южный"

    def _summarize_forecast(self, forecast: list) -> Dict:
        """Суммаризация прогноза погоды"""
        if not forecast:
            return {}

        avg_temp = sum([f['temperature'] for f in forecast]) / len(forecast)
        total_precip = sum([f['precipitation'] for f in forecast])
        max_temp = max([f['temperature_max'] for f in forecast])
        min_temp = min([f['temperature_min'] for f in forecast])

        return {
            'avg_temperature': round(avg_temp, 1),
            'total_precipitation': round(total_precip, 1),
            'max_temperature': round(max_temp, 1),
            'min_temperature': round(min_temp, 1),
            'forecast_days': len(forecast)
        }

    def _get_growing_season_info(self, field: Dict) -> Dict:
        """Информация о вегетационном периоде"""
        # Упрощенная модель для разных климатических зон
        climate_zones = {
            "северный": {"start": "15 мая", "end": "15 сентября", "days": 120},
            "умеренный": {"start": "1 мая", "end": "30 сентября", "days": 150},
            "южный": {"start": "15 апреля", "end": "15 октября", "days": 180}
        }

        return climate_zones.get(field.get('climate_zone', 'умеренный'), climate_zones['умеренный'])


# Глобальный экземпляр сервиса погоды
weather_service = WeatherService()
