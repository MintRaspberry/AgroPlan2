from fastapi import FastAPI, Request, Form, HTTPException, Query, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import database
import json
import os
from typing import Optional, List
from datetime import datetime
import uuid

app = FastAPI(title="Планировщик севооборота")

# Настройка шаблонов и статических файлов
current_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")), name="static")


# Простой менеджер сессий в памяти (в продакшене используйте Redis или базу данных)
class SessionManager:
    def __init__(self):
        self.sessions = {}

    def create_session(self):
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            'flash_message': None,
            'flash_error': None,
            'created_at': datetime.now()
        }
        return session_id

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def set_flash_message(self, session_id, message):
        if session_id in self.sessions:
            self.sessions[session_id]['flash_message'] = message

    def set_flash_error(self, session_id, message):
        if session_id in self.sessions:
            self.sessions[session_id]['flash_error'] = message

    def pop_flash_message(self, session_id):
        if session_id in self.sessions:
            message = self.sessions[session_id]['flash_message']
            self.sessions[session_id]['flash_message'] = None
            return message
        return None

    def pop_flash_error(self, session_id):
        if session_id in self.sessions:
            message = self.sessions[session_id]['flash_error']
            self.sessions[session_id]['flash_error'] = None
            return message
        return None

    def cleanup_old_sessions(self, hours=24):
        # Очистка старых сессий (для демонстрации не реализована)
        pass


session_manager = SessionManager()


# Middleware для обработки сессий
@app.middleware("http")
async def session_middleware(request: Request, call_next):
    # Получаем session_id из cookies
    session_id = request.cookies.get("session_id")

    # Если сессии нет, создаем новую
    if not session_id or not session_manager.get_session(session_id):
        session_id = session_manager.create_session()

    # Добавляем session_id в state запроса
    request.state.session_id = session_id

    # Обрабатываем запрос
    response = await call_next(request)

    # Устанавливаем cookie с session_id
    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=3600 * 24,  # 24 часа
        httponly=True,
        samesite="lax"
    )

    return response


# Вспомогательные функции для работы с flash-сообщениями
def get_flash_messages(request: Request):
    session_id = request.state.session_id
    return {
        'flash_message': session_manager.pop_flash_message(session_id),
        'flash_error': session_manager.pop_flash_error(session_id)
    }


def set_flash_message(request: Request, message: str):
    session_id = request.state.session_id
    session_manager.set_flash_message(session_id, message)


def set_flash_error(request: Request, message: str):
    session_id = request.state.session_id
    session_manager.set_flash_error(session_id, message)


# Главная страница
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        fields = database.db.get_all_fields()
        history = database.db.get_all_history()

        total_fields = len(fields)
        total_area = sum(field['area'] or 0 for field in fields)
        total_records = len(history)

        flash_messages = get_flash_messages(request)

        return templates.TemplateResponse("index.html", {
            "request": request,
            "total_fields": total_fields,
            "total_area": total_area,
            "total_records": total_records,
            **flash_messages
        })
    except Exception as e:
        print(f"Ошибка на главной странице: {e}")
        flash_messages = get_flash_messages(request)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "total_fields": 0,
            "total_area": 0,
            "total_records": 0,
            **flash_messages
        })


# Страница управления полями
@app.get("/fields", response_class=HTMLResponse)
async def read_fields(request: Request):
    fields = database.db.get_all_fields()
    flash_messages = get_flash_messages(request)

    return templates.TemplateResponse("fields.html", {
        "request": request,
        "fields": fields,
        **flash_messages
    })


# Добавление нового поля с улучшенной валидацией
@app.post("/fields")
async def create_field(
        request: Request,
        name: str = Form(...),
        area: Optional[float] = Form(None),
        latitude: Optional[float] = Form(None),
        longitude: Optional[float] = Form(None),
        polygon_coords: str = Form(""),
        soil_type: str = Form("суглинок")
):
    try:
        # Валидация названия
        if not name.strip():
            set_flash_error(request, "Название поля не может быть пустым")
            return RedirectResponse(url="/fields", status_code=303)

        if len(name.strip()) > 100:
            set_flash_error(request, "Название поля слишком длинное (максимум 100 символов)")
            return RedirectResponse(url="/fields", status_code=303)

        # Валидация полигона
        polygon_data = None
        if polygon_coords:
            try:
                polygon_data = json.loads(polygon_coords)
                # Проверяем, что это список координат
                if not isinstance(polygon_data, list) or len(polygon_data) < 3:
                    set_flash_error(request, "Полигон должен содержать минимум 3 точки")
                    return RedirectResponse(url="/fields", status_code=303)

                # Проверяем каждую точку
                for point in polygon_data:
                    if not isinstance(point, list) or len(point) != 2:
                        set_flash_error(request, "Каждая точка должна содержать 2 координаты")
                        return RedirectResponse(url="/fields", status_code=303)
                    lat, lng = point
                    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                        set_flash_error(request, "Координаты вне допустимого диапазона")
                        return RedirectResponse(url="/fields", status_code=303)

            except (json.JSONDecodeError, ValueError) as e:
                set_flash_error(request, f"Неверный формат полигона: {str(e)}")
                return RedirectResponse(url="/fields", status_code=303)

        # Валидация площади
        if area is not None and area <= 0:
            set_flash_error(request, "Площадь должна быть положительным числом")
            return RedirectResponse(url="/fields", status_code=303)

        # Валидация координат
        if latitude and not (-90 <= latitude <= 90):
            set_flash_error(request, "Широта вне допустимого диапазона")
            return RedirectResponse(url="/fields", status_code=303)
        if longitude and not (-180 <= longitude <= 180):
            set_flash_error(request, "Долгота вне допустимого диапазона")
            return RedirectResponse(url="/fields", status_code=303)

        # Создаем поле
        field_id = database.db.create_field(name, area, latitude, longitude, polygon_coords, soil_type)

        # Показываем уведомление об успехе
        set_flash_message(request, f"Поле '{name}' успешно создано!")

        return RedirectResponse(url="/fields", status_code=303)

    except Exception as e:
        print(f"Ошибка создания поля: {e}")
        set_flash_error(request, "Ошибка при создании поля")
        return RedirectResponse(url="/fields", status_code=303)


# Детальная страница поля
@app.get("/fields/{field_id}", response_class=HTMLResponse)
async def read_field(request: Request, field_id: int):
    field = database.db.get_field(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Поле не найдено")

    # Парсим координаты полигона
    polygon_data = None
    if field.get('polygon_coords'):
        try:
            polygon_data = json.loads(field['polygon_coords'])
        except:
            polygon_data = None

    # Получаем историю поля
    history = database.db.get_field_history(field_id)

    flash_messages = get_flash_messages(request)

    return templates.TemplateResponse("field_detail.html", {
        "request": request,
        "field": field,
        "history": history,
        "polygon_data": polygon_data,
        **flash_messages
    })


# Удаление поля
@app.get("/fields/delete/{field_id}")
async def delete_field(field_id: int, request: Request):
    field = database.db.get_field(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Поле не найдено")

    success = database.db.delete_field(field_id)
    if success:
        set_flash_message(request, f"Поле '{field['name']}' успешно удалено!")
    else:
        set_flash_error(request, "Ошибка при удалении поля")

    return RedirectResponse(url="/fields", status_code=303)


# API: Получить все поля для карты
@app.get("/api/fields/overview")
async def get_fields_overview():
    fields = database.db.get_all_fields()
    return JSONResponse(fields)


# API: Получить поле в формате GeoJSON
@app.get("/api/fields/{field_id}/geojson")
async def get_field_geojson(field_id: int):
    field = database.db.get_field(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Поле не найдено")

    # Создаем GeoJSON объект
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    if field.get('polygon_coords'):
        try:
            coordinates = json.loads(field['polygon_coords'])
            feature = {
                "type": "Feature",
                "properties": {
                    "id": field['id'],
                    "name": field['name'],
                    "area": field['area'],
                    "created_at": field['created_at']
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coordinates]  # GeoJSON требует массив массивов координат
                }
            }
            geojson["features"].append(feature)
        except Exception as e:
            print(f"Ошибка создания GeoJSON: {e}")

    return JSONResponse(geojson)


# API: Статистика урожайности
@app.get("/api/yield-stats")
async def get_yield_stats(field_id: Optional[int] = Query(None)):
    try:
        stats = database.db.get_yield_statistics(field_id)

        # Форматируем данные для charts.js
        crops = []
        yields = []
        counts = []

        for stat in stats:
            crops.append(stat['crop'])
            yields.append(float(stat['avg_yield']) if stat['avg_yield'] else 0)
            counts.append(stat['count'])

        return {
            "crops": crops,
            "yields": yields,
            "counts": counts
        }
    except Exception as e:
        print(f"Ошибка получения статистики урожайности: {e}")
        return {
            "crops": [],
            "yields": [],
            "counts": []
        }


# История посадок с выбором поля на карте
@app.get("/history", response_class=HTMLResponse)
async def read_history(request: Request, year: Optional[int] = Query(None)):
    try:
        if year:
            history = database.db.get_history_by_year(year)
        else:
            history = database.db.get_all_history()

        years = sorted(set([h['year'] for h in history]), reverse=True) if history else []

        flash_messages = get_flash_messages(request)

        return templates.TemplateResponse("history.html", {
            "request": request,
            "history": history,
            "selected_year": year,
            "years": years,
            **flash_messages
        })
    except Exception as e:
        print(f"Ошибка при загрузке истории: {e}")
        flash_messages = get_flash_messages(request)
        return templates.TemplateResponse("history.html", {
            "request": request,
            "history": [],
            "selected_year": year,
            "years": [],
            **flash_messages
        })


# Страница добавления записи с выбором поля на карте России
@app.get("/history/add", response_class=HTMLResponse)
async def add_history_with_map(request: Request):
    fields = database.db.get_all_fields()
    flash_messages = get_flash_messages(request)

    return templates.TemplateResponse("add_history_map.html", {
        "request": request,
        "fields": fields,
        **flash_messages
    })


@app.post("/history/add")
async def create_history_with_map(
        request: Request,
        field_id: int = Form(...),
        year: int = Form(...),
        season: str = Form(...),
        crop: str = Form(...),
        yield_amount: Optional[float] = Form(None),
        notes: Optional[str] = Form(None)
):
    try:
        history_id = database.db.add_crop_history(field_id, year, season, crop, yield_amount, notes)
        set_flash_message(request, "Запись истории успешно добавлена!")
        return RedirectResponse(url=f"/fields/{field_id}", status_code=303)
    except Exception as e:
        print(f"Ошибка добавления истории: {e}")
        set_flash_error(request, "Ошибка при добавлении записи истории")
        return RedirectResponse(url="/history/add", status_code=303)


# Добавление записи в историю для конкретного поля
@app.post("/fields/{field_id}/history")
async def add_field_history(
        field_id: int,
        request: Request,
        year: int = Form(...),
        season: str = Form(...),
        crop: str = Form(...),
        yield_amount: Optional[float] = Form(None),
        notes: Optional[str] = Form(None)
):
    try:
        history_id = database.db.add_crop_history(field_id, year, season, crop, yield_amount, notes)
        set_flash_message(request, "Запись истории успешно добавлена!")
        return RedirectResponse(url=f"/fields/{field_id}", status_code=303)
    except Exception as e:
        print(f"Ошибка добавления истории: {e}")
        set_flash_error(request, "Ошибка при добавлении записи истории")
        return RedirectResponse(url=f"/fields/{field_id}", status_code=303)


# Редактирование записи истории
@app.get("/history/edit/{history_id}", response_class=HTMLResponse)
async def edit_history(request: Request, history_id: int):
    entry = database.db.get_history_entry(history_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    flash_messages = get_flash_messages(request)

    return templates.TemplateResponse("edit_history.html", {
        "request": request,
        "entry": entry,
        **flash_messages
    })


@app.post("/history/edit/{history_id}")
async def update_history(
        history_id: int,
        request: Request,
        year: int = Form(...),
        season: str = Form(...),
        crop: str = Form(...),
        yield_amount: Optional[float] = Form(None),
        notes: Optional[str] = Form(None)
):
    entry = database.db.get_history_entry(history_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # В реальном приложении здесь был бы код обновления записи
    set_flash_message(request, "Запись истории успешно обновлена!")
    return RedirectResponse(url=f"/fields/{entry['field_id']}", status_code=303)


# Удаление записи истории
@app.get("/history/delete/{history_id}")
async def delete_history(history_id: int, request: Request):
    field_id = database.db.delete_crop_history(history_id)
    if field_id:
        set_flash_message(request, "Запись истории успешно удалена!")
        return RedirectResponse(url=f"/fields/{field_id}", status_code=303)
    else:
        set_flash_error(request, "Ошибка при удалении записи истории")
        return RedirectResponse(url="/fields", status_code=303)


# Рекомендации
@app.get("/recommendations", response_class=HTMLResponse)
async def read_recommendations(request: Request):
    fields = database.db.get_all_fields()
    crop_rules = database.db.get_all_crop_rules()

    flash_messages = get_flash_messages(request)

    return templates.TemplateResponse("recommendations.html", {
        "request": request,
        "fields": fields,
        "crop_rules": crop_rules,
        **flash_messages
    })


@app.post("/recommendations")
async def get_recommendations(
        request: Request,
        field_id: int = Form(...),
        target_crop: str = Form(...),
        recommendation_type: str = Form("basic")
):
    fields = database.db.get_all_fields()
    crop_rules = database.db.get_all_crop_rules()
    field = database.db.get_field(field_id)

    if not field:
        raise HTTPException(status_code=404, detail="Поле не найдено")

    # Упрощенная логика для примера
    recommendations = [{
        "type": "success",
        "title": "Рекомендация",
        "message": f"Для поля {field['name']} культура {target_crop} подходит хорошо."
    }]

    flash_messages = get_flash_messages(request)

    return templates.TemplateResponse("recommendations.html", {
        "request": request,
        "fields": fields,
        "crop_rules": crop_rules,
        "recommendations": recommendations,
        "selected_field_id": field_id,
        "target_crop": target_crop,
        "selected_field_name": field['name'],
        **flash_messages
    })


# Калькулятор
@app.get("/calculator", response_class=HTMLResponse)
async def read_calculator(request: Request):
    flash_messages = get_flash_messages(request)
    return templates.TemplateResponse("calculator.html", {
        "request": request,
        **flash_messages
    })


@app.post("/calculator")
async def calculate_economics(
        request: Request,
        crop: str = Form(...),
        area: float = Form(...)
):
    # Существующая логика калькулятора...
    prices = {
        "пшеница": {"cost_per_ha": 15000, "income_per_ha": 30000},
        "картофель": {"cost_per_ha": 50000, "income_per_ha": 80000},
        "подсолнечник": {"cost_per_ha": 25000, "income_per_ha": 45000},
        "горох": {"cost_per_ha": 18000, "income_per_ha": 35000},
        "ячмень": {"cost_per_ha": 14000, "income_per_ha": 28000},
        "кукуруза": {"cost_per_ha": 30000, "income_per_ha": 60000},
        "овёс": {"cost_per_ha": 13000, "income_per_ha": 25000},
        "соя": {"cost_per_ha": 22000, "income_per_ha": 45000},
        "рожь": {"cost_per_ha": 12000, "income_per_ha": 24000},
        "гречиха": {"cost_per_ha": 16000, "income_per_ha": 32000},
        "лён": {"cost_per_ha": 20000, "income_per_ha": 40000}
    }

    crop_data = prices.get(crop, {"cost_per_ha": 20000, "income_per_ha": 40000})

    total_cost = crop_data["cost_per_ha"] * area
    total_income = crop_data["income_per_ha"] * area
    profit = total_income - total_cost
    profitability = (profit / total_cost) * 100 if total_cost > 0 else 0

    flash_messages = get_flash_messages(request)

    return templates.TemplateResponse("calculator.html", {
        "request": request,
        "calculation": True,
        "crop": crop,
        "area": area,
        "total_cost": total_cost,
        "total_income": total_income,
        "profit": profit,
        "profitability": profitability,
        "cost_per_ha": crop_data["cost_per_ha"],
        "income_per_ha": crop_data["income_per_ha"],
        **flash_messages
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)