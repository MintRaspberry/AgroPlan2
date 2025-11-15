// Глобальные переменные для карты и рисования
let map;
let drawnItems;

// Функция для расчета площади полигона в гектарах
function calculatePolygonArea(latLngs) {
    if (!latLngs || latLngs.length < 3) return 0;

    let area = 0;
    const earthRadius = 6378137; // Радиус Земли в метрах

    for (let i = 0; i < latLngs.length; i++) {
        const j = (i + 1) % latLngs.length;
        const p1 = latLngs[i];
        const p2 = latLngs[j];

        area += (p2.lng - p1.lng) * Math.PI / 180 *
                Math.cos((p1.lat + p2.lat) * Math.PI / 360) *
                Math.sin(p2.lat * Math.PI / 180 - p1.lat * Math.PI / 180);
    }

    area = earthRadius * earthRadius * Math.abs(area) / 2;
    return area / 10000; // Конвертируем в гектары
}

// Инициализация карты для создания поля
function initCreateMap(centerLat = 55.7558, centerLng = 37.6173, zoom = 5) {
    console.log('Инициализация карты...');

    try {
        // Инициализация карты
        map = L.map('map').setView([centerLat, centerLng], zoom);

        // Добавляем базовый слой
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        // Инициализируем слой для нарисованных объектов
        drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        // Настройка инструментов рисования
        const drawControl = new L.Control.Draw({
            position: 'topright',
            draw: {
                polygon: {
                    allowIntersection: false,
                    drawError: {
                        color: '#e1e100',
                        message: '<strong>Ошибка:</strong> полигоны не могут пересекаться!'
                    },
                    shapeOptions: {
                        color: '#10b981',
                        fillColor: '#10b981',
                        fillOpacity: 0.3,
                        weight: 3
                    }
                },
                polyline: false,
                rectangle: false,
                circle: false,
                circlemarker: false,
                marker: false
            },
            edit: {
                featureGroup: drawnItems,
                remove: true
            }
        });

        map.addControl(drawControl);

        // Обработчики событий рисования
        map.on(L.Draw.Event.CREATED, function (e) {
            const layer = e.layer;

            if (e.layerType === 'polygon') {
                // Удаляем предыдущие полигоны
                drawnItems.clearLayers();
                drawnItems.addLayer(layer);

                // Получаем координаты
                const coordinates = layer.getLatLngs()[0].map(latLng => [latLng.lat, latLng.lng]);

                // Рассчитываем площадь
                const area = calculatePolygonArea(layer.getLatLngs()[0]);
                const areaHectares = area.toFixed(2);

                // Вычисляем центр
                const center = calculateCenter(coordinates);

                // Заполняем поля формы
                document.getElementById('polygonCoords').value = JSON.stringify(coordinates);
                document.getElementById('fieldArea').value = areaHectares;
                document.getElementById('centerLat').value = center.lat;
                document.getElementById('centerLng').value = center.lng;

                // Показываем информацию
                updateFieldInfo(areaHectares, coordinates.length, center.lat, center.lng);

                // Активируем кнопку сохранения
                const saveBtn = document.getElementById('saveFieldBtn');
                if (saveBtn) saveBtn.disabled = false;
            }
        });

        map.on(L.Draw.Event.DELETED, function (e) {
            // Очищаем поля формы
            document.getElementById('polygonCoords').value = '';
            document.getElementById('fieldArea').value = '';
            document.getElementById('centerLat').value = '';
            document.getElementById('centerLng').value = '';

            const fieldInfo = document.getElementById('fieldInfo');
            if (fieldInfo) fieldInfo.style.display = 'none';

            const saveBtn = document.getElementById('saveFieldBtn');
            if (saveBtn) saveBtn.disabled = true;
        });

        // Добавляем контроль масштаба
        L.control.scale({ imperial: false, metric: true }).addTo(map);

        console.log('Карта инициализирована');

    } catch (error) {
        console.error('Ошибка инициализации карты:', error);
        showNotification('Ошибка загрузки карты', 'error');
    }
}

// Вычислить центр полигона
function calculateCenter(points) {
    const lats = points.map(p => p[0]);
    const lngs = points.map(p => p[1]);

    return {
        lat: lats.reduce((a, b) => a + b) / lats.length,
        lng: lngs.reduce((a, b) => a + b) / lngs.length
    };
}

// Обновление информации о поле
function updateFieldInfo(area, points, centerLat, centerLng) {
    const fieldInfo = document.getElementById('fieldInfo');
    const areaElement = document.getElementById('calculatedArea');
    const pointsElement = document.getElementById('polygonPoints');

    if (fieldInfo && areaElement && pointsElement) {
        areaElement.textContent = area + ' га';
        pointsElement.textContent = points;
        fieldInfo.style.display = 'block';
    }
}

// Сохранение поля
async function saveField() {
    const name = document.getElementById('fieldName')?.value.trim();
    const area = document.getElementById('fieldArea')?.value;
    const polygonCoords = document.getElementById('polygonCoords')?.value;

    if (!name) {
        showNotification('Пожалуйста, введите название поля', 'error');
        return;
    }

    if (!polygonCoords) {
        showNotification('Пожалуйста, нарисуйте поле на карте', 'error');
        return;
    }

    try {
        const formData = new FormData();
        formData.append('name', name);
        formData.append('area', area);
        formData.append('polygon_coords', polygonCoords);
        formData.append('soil_type', 'суглинок');

        const response = await fetch('/fields', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            showNotification('Поле успешно сохранено!', 'success');
            setTimeout(() => {
                window.location.href = '/fields';
            }, 1500);
        } else {
            throw new Error('Ошибка сервера');
        }
    } catch (error) {
        console.error('Ошибка сохранения поля:', error);
        showNotification('Ошибка при сохранении поля', 'error');
    }
}

// Показать уведомление
function showNotification(message, type = 'info') {
    // Удаляем существующие уведомления
    const existingNotifications = document.querySelectorAll('.notification');
    existingNotifications.forEach(notification => {
        if (notification.parentElement) {
            notification.remove();
        }
    });

    // Создаем новое уведомление
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()">×</button>
    `;
    document.body.appendChild(notification);

    // Автоматическое скрытие через 5 секунд
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('map')) {
        setTimeout(() => initCreateMap(), 500);
    }

    const saveBtn = document.getElementById('saveFieldBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveField);
    }
});