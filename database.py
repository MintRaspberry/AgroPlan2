import sqlite3
import json
import math
from datetime import datetime
from typing import List, Dict, Optional
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path="crop_rotation.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Таблица полей с расширенными геоданными
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            area REAL,
            latitude REAL,
            longitude REAL,
            polygon_coords TEXT,
            center_lat REAL,
            center_lng REAL,
            bounding_box TEXT,
            soil_type TEXT,
            climate_zone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Таблица истории культур
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS crop_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_id INTEGER,
            year INTEGER,
            season TEXT DEFAULT 'весна',
            crop TEXT,
            yield_amount REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (field_id) REFERENCES fields (id)
        )
        ''')

        # Добавляем столбец season если его нет
        try:
            cursor.execute("SELECT season FROM crop_history LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE crop_history ADD COLUMN season TEXT DEFAULT "весна"')

        # Таблица правил севооборота (расширенная)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS crop_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop TEXT UNIQUE,
            family TEXT,
            good_predecessors TEXT,
            bad_predecessors TEXT,
            nitrogen_effect TEXT,
            soil_requirements TEXT,
            recommended_successors TEXT,
            water_requirements TEXT,
            temperature_min REAL,
            temperature_max REAL,
            growing_season_days INTEGER,
            ph_min REAL,
            ph_max REAL,
            fertilizer_n REAL,
            fertilizer_p REAL,
            fertilizer_k REAL,
            market_price REAL,
            yield_potential REAL
        )
        ''')

        # Таблица климатических данных
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS climate_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_id INTEGER,
            date DATE,
            temperature_avg REAL,
            temperature_min REAL,
            temperature_max REAL,
            precipitation REAL,
            humidity REAL,
            wind_speed REAL,
            solar_radiation REAL,
            FOREIGN KEY (field_id) REFERENCES fields (id)
        )
        ''')

        # Таблица рыночных цен
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop TEXT,
            price REAL,
            date DATE,
            region TEXT,
            source TEXT
        )
        ''')

        # Заполняем правила севооборота на основе научных данных
        self._init_crop_rules(cursor)

        # Заполняем начальные рыночные цены
        self._init_market_prices(cursor)

        conn.commit()
        conn.close()

    def _init_crop_rules(self, cursor):
        """Инициализация базы правил севооборота на основе научных данных"""
        # Данные основаны на рекомендациях РГАУ-МСХА им. Тимирязева и научных публикациях
        rules = [
            # Зерновые культуры
            ("пшеница озимая", "Злаковые",
             "горох,люцерна,клевер,кукуруза на силос,картофель ранний",
             "пшеница,ячмень,овёс,подсолнечник,свёкла",
             "нейтральное", "чернозёмы, каштановые, суглинки",
             "кукуруза,подсолнечник,рапс,бобовые", "средние", -15, 25, 280, 6.0, 7.5, 120, 60, 60, 15000, 4.5),

            ("пшеница яровая", "Злаковые",
             "бобовые,кукуруза,картофель,многолетние травы",
             "пшеница,ячмень,овёс",
             "нейтральное", "плодородные суглинки",
             "бобовые,кукуруза,рапс", "средние", 5, 30, 100, 6.0, 7.5, 100, 50, 50, 14000, 3.5),

            ("ячмень яровой", "Злаковые",
             "бобовые,картофель,кукуруза,свёкла",
             "ячмень,пшеница,овёс",
             "нейтральное", "различные почвы",
             "бобовые,кукуруза,рапс", "низкие", 5, 30, 85, 5.5, 7.5, 80, 40, 40, 12000, 3.0),

            ("овёс", "Злаковые",
             "бобовые,картофель,кукуруза,лён",
             "овёс,пшеница,ячмень",
             "нейтральное", "влаголюбив, суглинки",
             "бобовые,картофель,лён", "высокие", 5, 25, 100, 5.0, 7.0, 70, 35, 35, 11000, 2.5),

            # Бобовые культуры
            ("горох", "Бобовые",
             "зерновые,кукуруза,картофель",
             "горох,бобовые,подсолнечник",
             "обогащает азотом", "нейтральные суглинки",
             "пшеница,ячмень,кукуруза", "средние", 8, 25, 90, 6.0, 7.5, 30, 60, 60, 25000, 2.5),

            ("соя", "Бобовые",
             "зерновые,кукуруза,многолетние травы",
             "соя,бобовые,подсолнечник",
             "обогащает азотом", "плодородные суглинки",
             "пшеница,кукуруза,ячмень", "средние", 15, 30, 120, 6.0, 7.0, 40, 80, 80, 35000, 2.0),

            ("люцерна", "Бобовые",
             "зерновые,кукуруза,картофель",
             "люцерна,бобовые",
             "сильно обогащает азотом", "нейтральные дренированные",
             "зерновые,кукуруза,подсолнечник", "высокие", 5, 30, 365, 6.5, 7.5, 0, 60, 60, 18000, 8.0),

            # Технические культуры
            ("подсолнечник", "Астровые",
             "озимые зерновые,бобовые,кукуруза",
             "подсолнечник,свёкла,рапс,лён",
             "сильный потребитель", "чернозёмы, суглинки",
             "озимые,бобовые,кукуруза", "низкие", 10, 30, 120, 6.0, 7.5, 80, 60, 120, 45000, 2.5),

            ("рапс яровой", "Крестоцветные",
             "зерновые,бобовые,картофель",
             "рапс,капуста,редька",
             "нейтральное", "плодородные нейтральные",
             "зерновые,бобовые,кукуруза", "средние", 5, 25, 110, 6.0, 7.5, 120, 60, 120, 28000, 2.0),

            ("лён", "Льновые",
             "озимые,бобовые,картофель",
             "лён,подсолнечник,свёкла",
             "нейтральное", "суглинки нейтральные",
             "озимые,бобовые,кукуруза", "средние", 10, 25, 90, 6.0, 7.0, 60, 40, 60, 30000, 1.5),

            # Корнеплоды
            ("картофель", "Паслёновые",
             "озимые,бобовые,капуста,огурцы",
             "картофель,подсолнечник,томаты",
             "нейтральное", "лёгкие рыхлые",
             "озимые,бобовые,лён", "высокие", 10, 25, 120, 5.0, 6.5, 100, 80, 150, 20000, 25.0),

            ("свёкла сахарная", "Амарантовые",
             "озимые,бобовые,кукуруза",
             "свёкла,подсолнечник,рапс",
             "сильный потребитель", "чернозёмы, суглинки",
             "озимые,бобовые,ячмень", "высокие", 8, 25, 160, 6.5, 7.5, 120, 80, 150, 18000, 45.0),

            ("кукуруза на зерно", "Злаковые",
             "бобовые,озимые,картофель",
             "кукуруза,подсолнечник,свёкла",
             "сильный потребитель", "плодородные тёплые",
             "бобовые,озимые,соя", "средние", 15, 35, 130, 6.0, 7.5, 150, 70, 90, 12000, 6.0),

            ("гречиха", "Гречишные",
             "озимые,бобовые,картофель",
             "гречиха,подсолнечник,свёкла",
             "улучшает фосфор", "лёгкие прогреваемые",
             "озимые,бобовые,ячмень", "средние", 15, 25, 80, 5.5, 7.0, 60, 40, 60, 32000, 1.5)
        ]

        for rule in rules:
            cursor.execute('''
            INSERT OR IGNORE INTO crop_rules 
            (crop, family, good_predecessors, bad_predecessors, nitrogen_effect, 
             soil_requirements, recommended_successors, water_requirements,
             temperature_min, temperature_max, growing_season_days, ph_min, ph_max,
             fertilizer_n, fertilizer_p, fertilizer_k, market_price, yield_potential)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', rule)

    def _init_market_prices(self, cursor):
        """Инициализация начальных рыночных цен на основе данных Минсельхоза РФ"""
        # Средние цены по России за последний сезон (руб/тонна)
        prices = [
            ("пшеница озимая", 15000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("пшеница яровая", 14000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("ячмень яровой", 12000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("овёс", 11000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("горох", 25000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("соя", 35000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("подсолнечник", 45000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("рапс яровой", 28000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("лён", 30000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("картофель", 20000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("свёкла сахарная", 18000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("кукуруза на зерно", 12000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("гречиха", 32000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ"),
            ("люцерна", 18000, "2024-01-01", "Центральный федеральный округ", "Минсельхоз РФ")
        ]

        for price in prices:
            cursor.execute('''
            INSERT OR IGNORE INTO market_prices (crop, price, date, region, source)
            VALUES (?, ?, ?, ?, ?)
            ''', price)

    # Методы для работы с климатическими данными
    def save_climate_data(self, field_id: int, date: str, temp_avg: float, temp_min: float,
                          temp_max: float, precipitation: float, humidity: float,
                          wind_speed: float, solar_radiation: float):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO climate_data 
        (field_id, date, temperature_avg, temperature_min, temperature_max, 
         precipitation, humidity, wind_speed, solar_radiation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (field_id, date, temp_avg, temp_min, temp_max, precipitation,
              humidity, wind_speed, solar_radiation))

        conn.commit()
        conn.close()

    def get_climate_data(self, field_id: int, start_date: str, end_date: str):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT * FROM climate_data 
        WHERE field_id = ? AND date BETWEEN ? AND ?
        ORDER BY date
        ''', (field_id, start_date, end_date))

        data = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return data

    # Методы для работы с рыночными ценами
    def update_market_price(self, crop: str, price: float, date: str, region: str, source: str):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO market_prices (crop, price, date, region, source)
        VALUES (?, ?, ?, ?, ?)
        ''', (crop, price, date, region, source))

        conn.commit()
        conn.close()

    def get_current_market_price(self, crop: str, region: str = "Центральный федеральный округ"):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT price FROM market_prices 
        WHERE crop = ? AND region = ?
        ORDER BY date DESC 
        LIMIT 1
        ''', (crop, region))

        result = cursor.fetchone()
        conn.close()
        return result['price'] if result else None

    # Методы для аналитики с учетом климатических данных
    def get_yield_prediction(self, field_id: int, crop: str):
        """Прогноз урожайности на основе исторических данных и климатических условий"""
        field = self.get_field(field_id)
        if not field:
            return None

        # Базовый потенциал урожайности для культуры
        crop_rule = self.get_crop_rule(crop)
        if not crop_rule:
            return None

        base_yield = crop_rule.get('yield_potential', 0)

        # Корректировка на основе климатических данных
        climate_data = self.get_climate_data(field_id,
                                             datetime.now().replace(year=datetime.now().year - 1).strftime('%Y-%m-%d'),
                                             datetime.now().strftime('%Y-%m-%d'))

        if climate_data:
            # Упрощенная модель корректировки урожайности
            avg_temp = sum([d['temperature_avg'] for d in climate_data]) / len(climate_data)
            total_precipitation = sum([d['precipitation'] for d in climate_data])

            # Идеальные условия (эмпирические коэффициенты)
            ideal_temp = 20  # Средняя идеальная температура
            ideal_precipitation = 500  # мм за сезон

            temp_factor = 1 - abs(avg_temp - ideal_temp) / ideal_temp * 0.1
            precip_factor = 1 - abs(total_precipitation - ideal_precipitation) / ideal_precipitation * 0.1

            predicted_yield = base_yield * temp_factor * precip_factor
            return max(predicted_yield, base_yield * 0.5)  # Минимум 50% от потенциала

        return base_yield

    # Существующие методы остаются без изменений
    def create_field(self, name: str, area: Optional[float] = None,
                     latitude: Optional[float] = None, longitude: Optional[float] = None,
                     polygon_coords: Optional[str] = None, soil_type: str = "суглинок",
                     climate_zone: str = "умеренный") -> int:
        conn = self.get_connection()
        cursor = conn.cursor()

        # Вычисляем центр и bounding box если есть полигон
        center_lat = None
        center_lng = None
        bounding_box = None

        if polygon_coords:
            try:
                coords = json.loads(polygon_coords)
                if coords and len(coords) > 0:
                    # Вычисляем центр полигона
                    lats = [coord[0] for coord in coords]
                    lngs = [coord[1] for coord in coords]
                    center_lat = sum(lats) / len(lats)
                    center_lng = sum(lngs) / len(lngs)

                    # Вычисляем bounding box
                    min_lat, max_lat = min(lats), max(lats)
                    min_lng, max_lng = min(lngs), max(lngs)
                    bounding_box = json.dumps({
                        'min_lat': min_lat,
                        'max_lat': max_lat,
                        'min_lng': min_lng,
                        'max_lng': max_lng
                    })

                    # Если площадь не указана, вычисляем приблизительную
                    if not area:
                        area = self._calculate_polygon_area(coords)

            except Exception as e:
                logger.error(f"Ошибка обработки полигона: {e}")

        cursor.execute('''
        INSERT INTO fields (name, area, latitude, longitude, polygon_coords, 
                          center_lat, center_lng, bounding_box, soil_type, climate_zone)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, area, latitude, longitude, polygon_coords, center_lat,
              center_lng, bounding_box, soil_type, climate_zone))

        field_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return field_id

    def _calculate_polygon_area(self, coords: List[List[float]]) -> float:
        """Вычисляет приблизительную площадь полигона в гектарах"""
        if len(coords) < 3:
            return 0.0

        # Используем формулу гаусса для площади многоугольника
        area = 0.0
        n = len(coords)
        for i in range(n):
            j = (i + 1) % n
            area += coords[i][1] * coords[j][0] - coords[j][1] * coords[i][0]
        area = abs(area) / 2.0

        # Конвертация в гектары (приблизительно)
        area_hectares = area * 11100  # Упрощенная конвертация
        return round(max(area_hectares, 0.01), 2)

    def get_all_fields(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM fields ORDER BY created_at DESC')
        fields = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return fields

    def get_field(self, field_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM fields WHERE id = ?', (field_id,))
        row = cursor.fetchone()
        field = dict(row) if row else None
        conn.close()
        return field

    # Остальные существующие методы остаются без изменений...
    def update_field(self, field_id: int, name: str, area: Optional[float] = None,
                     polygon_coords: Optional[str] = None) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()

        # Пересчитываем геоданные если обновлен полигон
        center_lat = None
        center_lng = None
        bounding_box = None

        if polygon_coords:
            try:
                coords = json.loads(polygon_coords)
                if coords and len(coords) > 0:
                    lats = [coord[0] for coord in coords]
                    lngs = [coord[1] for coord in coords]
                    center_lat = sum(lats) / len(lats)
                    center_lng = sum(lngs) / len(lngs)

                    min_lat, max_lat = min(lats), max(lats)
                    min_lng, max_lng = min(lngs), max(lngs)
                    bounding_box = json.dumps({
                        'min_lat': min_lat,
                        'max_lat': max_lat,
                        'min_lng': min_lng,
                        'max_lng': max_lng
                    })

            except Exception as e:
                logger.error(f"Ошибка обработки полигона: {e}")

        cursor.execute('''
        UPDATE fields
        SET name = ?, area = ?, polygon_coords = ?, center_lat = ?, center_lng = ?, 
            bounding_box = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''', (name, area, polygon_coords, center_lat, center_lng, bounding_box, field_id))

        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def delete_field(self, field_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()

        # Удаляем связанную историю
        cursor.execute('DELETE FROM crop_history WHERE field_id = ?', (field_id,))
        # Удаляем климатические данные
        cursor.execute('DELETE FROM climate_data WHERE field_id = ?', (field_id,))
        # Удаляем поле
        cursor.execute('DELETE FROM fields WHERE id = ?', (field_id,))

        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def search_fields_by_location(self, lat: float, lng: float, radius_km: float = 10) -> List[Dict]:
        """Поиск полей в радиусе от заданной точки"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Упрощенный поиск по bounding box
        lat_range = radius_km / 111.0  # 1 градус широты ≈ 111 км
        lng_range = radius_km / (111.0 * abs(math.cos(math.radians(lat))))

        cursor.execute('''
        SELECT * FROM fields
        WHERE center_lat BETWEEN ? AND ?
        AND center_lng BETWEEN ? AND ?
        ''', (lat - lat_range, lat + lat_range, lng - lng_range, lng + lng_range))

        fields = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return fields

    # Методы для истории культур
    def add_crop_history(self, field_id: int, year: int, season: str, crop: str,
                         yield_amount: Optional[float] = None, notes: Optional[str] = None) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO crop_history (field_id, year, season, crop, yield_amount, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (field_id, year, season, crop, yield_amount, notes))
        history_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return history_id

    def get_field_history(self, field_id: int) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM crop_history
        WHERE field_id = ?
        ORDER BY year DESC, season DESC
        ''', (field_id,))
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return history

    def get_all_history(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            SELECT ch.*, f.name as field_name, f.area as field_area
            FROM crop_history ch
            JOIN fields f ON ch.field_id = f.id
            ORDER BY ch.year DESC, ch.season DESC, ch.created_at DESC
            ''')
        except sqlite3.OperationalError as e:
            logger.error(f"Ошибка при получении истории: {e}")
            cursor.execute('''
            SELECT ch.*, f.name as field_name, f.area as field_area
            FROM crop_history ch
            JOIN fields f ON ch.field_id = f.id
            ORDER BY ch.year DESC, ch.created_at DESC
            ''')
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return history

    def get_history_by_year(self, year: int) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            SELECT ch.*, f.name as field_name, f.area as field_area
            FROM crop_history ch
            JOIN fields f ON ch.field_id = f.id
            WHERE ch.year = ?
            ORDER BY ch.season DESC
            ''', (year,))
        except sqlite3.OperationalError:
            cursor.execute('''
            SELECT ch.*, f.name as field_name, f.area as field_area
            FROM crop_history ch
            JOIN fields f ON ch.field_id = f.id
            WHERE ch.year = ?
            ORDER BY ch.created_at DESC
            ''', (year,))
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return history

    def get_history_entry(self, history_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT ch.*, f.name as field_name
        FROM crop_history ch
        JOIN fields f ON ch.field_id = f.id
        WHERE ch.id = ?
        ''', (history_id,))
        row = cursor.fetchone()
        entry = dict(row) if row else None
        conn.close()
        return entry

    def delete_crop_history(self, history_id: int) -> Optional[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT field_id FROM crop_history WHERE id = ?', (history_id,))
        result = cursor.fetchone()
        field_id = result['field_id'] if result else None

        cursor.execute('DELETE FROM crop_history WHERE id = ?', (history_id,))
        conn.commit()
        conn.close()
        return field_id

    # Методы для аналитики
    def get_yield_statistics(self, field_id: Optional[int] = None) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()

        if field_id:
            cursor.execute('''
            SELECT crop, AVG(yield_amount) as avg_yield, COUNT(*) as count
            FROM crop_history
            WHERE field_id = ? AND yield_amount IS NOT NULL
            GROUP BY crop
            ''', (field_id,))
        else:
            cursor.execute('''
            SELECT crop, AVG(yield_amount) as avg_yield, COUNT(*) as count
            FROM crop_history
            WHERE yield_amount IS NOT NULL
            GROUP BY crop
            ''')

        stats = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return stats

    def get_field_rotation_history(self, field_id: int) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            SELECT year, season, crop, yield_amount
            FROM crop_history
            WHERE field_id = ?
            ORDER BY year,
            CASE season
                WHEN 'весна' THEN 1
                WHEN 'лето' THEN 2
                WHEN 'осень' THEN 3
                ELSE 4
            END
            ''', (field_id,))
        except sqlite3.OperationalError:
            cursor.execute('''
            SELECT year, crop, yield_amount
            FROM crop_history
            WHERE field_id = ?
            ORDER BY year
            ''', (field_id,))
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return history

    # Методы для рекомендаций
    def get_crop_rule(self, crop: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM crop_rules WHERE crop = ?', (crop,))
        row = cursor.fetchone()
        rule = dict(row) if row else None
        conn.close()
        return rule

    def get_all_crop_rules(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM crop_rules ORDER BY crop')
        rules = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rules

    def get_last_crop(self, field_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            SELECT crop, year, season FROM crop_history
            WHERE field_id = ?
            ORDER BY year DESC,
            CASE season
                WHEN 'весна' THEN 1
                WHEN 'лето' THEN 2
                WHEN 'осень' THEN 3
                ELSE 4
            END DESC
            LIMIT 1
            ''', (field_id,))
        except sqlite3.OperationalError:
            cursor.execute('''
            SELECT crop, year FROM crop_history
            WHERE field_id = ?
            ORDER BY year DESC
            LIMIT 1
            ''', (field_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None

    def get_successor_recommendations(self, last_crop: str, exclude_crops: Optional[List[str]] = None) -> List[str]:
        """Получить рекомендации по культурам-последователям"""
        if exclude_crops is None:
            exclude_crops = []

        conn = self.get_connection()
        cursor = conn.cursor()

        # Получаем правило для последней культуры
        cursor.execute('SELECT recommended_successors FROM crop_rules WHERE crop = ?', (last_crop,))
        result = cursor.fetchone()

        if result and result['recommended_successors']:
            successors = [s.strip() for s in result['recommended_successors'].split(',')]
            # Исключаем культуры из списка исключений
            successors = [s for s in successors if s not in exclude_crops]
            return successors

        conn.close()
        return []

    def get_crops_by_family(self, family: str) -> List[str]:
        """Получить все культуры из определенного семейства"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT crop FROM crop_rules WHERE family = ?', (family,))
        crops = [row['crop'] for row in cursor.fetchall()]
        conn.close()
        return crops


# Глобальный экземпляр базы данных
db = Database()
