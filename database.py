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
        self.init_crop_rules()

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

        conn.commit()
        conn.close()
        print("База данных инициализирована")

    def init_crop_rules(self):
        """Инициализация базовых правил для культур"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Базовые правила для основных культур
        base_crops = [
            ("пшеница", "Злаковые"),
            ("картофель", "Пасленовые"),
            ("подсолнечник", "Астровые"),
            ("горох", "Бобовые"),
            ("ячмень", "Злаковые"),
            ("кукуруза", "Злаковые"),
            ("овёс", "Злаковые"),
            ("соя", "Бобовые"),
            ("рожь", "Злаковые"),
            ("гречиха", "Гречишные"),
            ("лён", "Льновые")
        ]

        for crop, family in base_crops:
            try:
                cursor.execute('''
                INSERT OR IGNORE INTO crop_rules (crop, family)
                VALUES (?, ?)
                ''', (crop, family))
            except Exception as e:
                print(f"Ошибка при добавлении культуры {crop}: {e}")

        conn.commit()
        conn.close()
        print("Правила культур инициализированы")

    def create_field(self, name, area, latitude, longitude, polygon_coords, soil_type):
        """Создание нового поля с поддержкой полигонов"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            print(f"Создание поля в БД: name={name}, area={area}, lat={latitude}, lng={longitude}, soil_type={soil_type}")

            # Вычисляем bounding box если есть полигон
            bounding_box = None
            center_lat = latitude
            center_lng = longitude

            if polygon_coords and polygon_coords.strip():
                try:
                    coords = json.loads(polygon_coords)
                    lats = [point[0] for point in coords]
                    lngs = [point[1] for point in coords]

                    # Вычисляем bounding box
                    bbox = {
                        'min_lat': min(lats),
                        'max_lat': max(lats),
                        'min_lng': min(lngs),
                        'max_lng': max(lngs)
                    }
                    bounding_box = json.dumps(bbox)

                    # Если координаты центра не указаны, вычисляем их из полигона
                    if not (latitude and longitude):
                        center_lat = sum(lats) / len(lats)
                        center_lng = sum(lngs) / len(lngs)

                except Exception as e:
                    print(f"Ошибка обработки полигона: {e}")
                    bounding_box = None

            cursor.execute('''
            INSERT INTO fields (name, area, latitude, longitude, polygon_coords,
            center_lat, center_lng, bounding_box, soil_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, area, latitude, longitude, polygon_coords,
                  center_lat, center_lng, bounding_box, soil_type))

            field_id = cursor.lastrowid
            conn.commit()
            print(f"Поле успешно создано с ID: {field_id}")
            return field_id

        except Exception as e:
            print(f"Ошибка при создании поля в БД: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_all_fields(self):
        """Получение всех полей"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
            SELECT id, name, area, latitude, longitude, polygon_coords,
            center_lat, center_lng, soil_type, created_at
            FROM fields
            ORDER BY created_at DESC
            ''')

            fields = [dict(row) for row in cursor.fetchall()]
            return fields
        except Exception as e:
            print(f"Ошибка при получении полей: {e}")
            return []
        finally:
            conn.close()

    def get_field(self, field_id):
        """Получение поля по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
            SELECT id, name, area, latitude, longitude, polygon_coords,
            center_lat, center_lng, soil_type, created_at
            FROM fields
            WHERE id = ?
            ''', (field_id,))

            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"Ошибка при получении поля {field_id}: {e}")
            return None
        finally:
            conn.close()

    def delete_field(self, field_id):
        """Удаление поля"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Сначала удаляем связанные записи истории
            cursor.execute('DELETE FROM crop_history WHERE field_id = ?', (field_id,))
            # Затем удаляем поле
            cursor.execute('DELETE FROM fields WHERE id = ?', (field_id,))
            conn.commit()
            success = True
            print(f"Поле {field_id} успешно удалено")
        except Exception as e:
            print(f"Ошибка удаления поля {field_id}: {e}")
            conn.rollback()
            success = False
        finally:
            conn.close()

        return success

    def get_field_history(self, field_id):
        """Получение истории культур для поля"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
            SELECT ch.*, f.name as field_name, f.area as field_area
            FROM crop_history ch
            JOIN fields f ON ch.field_id = f.id
            WHERE ch.field_id = ?
            ORDER BY ch.year DESC,
            CASE
                WHEN ch.season = 'весна' THEN 1
                WHEN ch.season = 'лето' THEN 2
                WHEN ch.season = 'осень' THEN 3
                ELSE 4
            END
            ''', (field_id,))

            history = [dict(row) for row in cursor.fetchall()]
            return history
        except Exception as e:
            print(f"Ошибка при получении истории поля {field_id}: {e}")
            return []
        finally:
            conn.close()

    def add_crop_history(self, field_id, year, season, crop, yield_amount=None, notes=None):
        """Добавление записи в историю культур"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
            INSERT INTO crop_history (field_id, year, season, crop, yield_amount, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (field_id, year, season, crop, yield_amount, notes))

            history_id = cursor.lastrowid
            conn.commit()
            print(f"Запись истории добавлена с ID: {history_id}")
            return history_id
        except Exception as e:
            print(f"Ошибка при добавлении записи истории: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_all_history(self):
        """Получение всей истории"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
            SELECT ch.*, f.name as field_name, f.area as field_area
            FROM crop_history ch
            JOIN fields f ON ch.field_id = f.id
            ORDER BY ch.year DESC, ch.created_at DESC
            ''')

            history = [dict(row) for row in cursor.fetchall()]
            return history
        except Exception as e:
            print(f"Ошибка при получении всей истории: {e}")
            return []
        finally:
            conn.close()

    def get_history_by_year(self, year):
        """Получение истории по году"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
            SELECT ch.*, f.name as field_name, f.area as field_area
            FROM crop_history ch
            JOIN fields f ON ch.field_id = f.id
            WHERE ch.year = ?
            ORDER BY ch.created_at DESC
            ''', (year,))

            history = [dict(row) for row in cursor.fetchall()]
            return history
        except Exception as e:
            print(f"Ошибка при получении истории за год {year}: {e}")
            return []
        finally:
            conn.close()

    def get_history_entry(self, history_id):
        """Получение конкретной записи истории"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
            SELECT ch.*, f.name as field_name
            FROM crop_history ch
            JOIN fields f ON ch.field_id = f.id
            WHERE ch.id = ?
            ''', (history_id,))

            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"Ошибка при получении записи истории {history_id}: {e}")
            return None
        finally:
            conn.close()

    def delete_crop_history(self, history_id):
        """Удаление записи истории"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Получаем field_id перед удалением
            cursor.execute('SELECT field_id FROM crop_history WHERE id = ?', (history_id,))
            row = cursor.fetchone()
            field_id = row['field_id'] if row else None

            cursor.execute('DELETE FROM crop_history WHERE id = ?', (history_id,))
            conn.commit()
            print(f"Запись истории {history_id} удалена")
            return field_id
        except Exception as e:
            print(f"Ошибка удаления записи истории {history_id}: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_yield_statistics(self, field_id=None):
        """Получение статистики урожайности"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if field_id:
                cursor.execute('''
                SELECT crop, AVG(yield_amount) as avg_yield, COUNT(*) as count
                FROM crop_history
                WHERE field_id = ? AND yield_amount IS NOT NULL
                GROUP BY crop
                ORDER BY avg_yield DESC
                ''', (field_id,))
            else:
                cursor.execute('''
                SELECT crop, AVG(yield_amount) as avg_yield, COUNT(*) as count
                FROM crop_history
                WHERE yield_amount IS NOT NULL
                GROUP BY crop
                ORDER BY avg_yield DESC
                ''')

            stats = [dict(row) for row in cursor.fetchall()]
            return stats
        except Exception as e:
            print(f"Ошибка при получении статистики урожайности: {e}")
            return []
        finally:
            conn.close()


# Глобальный экземпляр базы данных
db = Database()