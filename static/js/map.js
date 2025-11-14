// Глобальные переменные для карты и рисования
let map;
let drawnItems;
let drawControl;

// Инициализация карты для создания поля
function initCreateMap(centerLat = 55.7558, centerLng = 37.6173, zoom = 5) {
    console.log('Инициализация карты...');

    try {
        // Инициализация карты
        map = L.map('map').setView([centerLat, centerLng], zoom);
        console.log('Карта создана успешно');

        // Добавляем базовый слой
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        // Инициализируем слой для нарисованных объектов
        drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        // Настройка инструментов рисования
        drawControl = new L.Control.Draw({
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
                    },
                    showArea: true,
                    metric: true,
                    feet: false
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
            const type = e.layerType;
            const layer = e.layer;

            if (type === 'polygon') {
                // Удаляем предыдущие полигоны
                drawnItems.clearLayers();

                // Добавляем новый полигон
                drawnItems.addLayer(layer);

                // Получаем координаты и площадь
                const coordinates = layer.getLatLngs()[0].map(latLng => [latLng.lat, latLng.lng]);
                const area = L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]);
                const areaHectares = (area / 10000).toFixed(2);

                // Заполняем скрытые поля формы
                document.getElementById('polygonCoords').value = JSON.stringify(coordinates);
                document.getElementById('fieldArea').value = areaHectares;

                // Показываем информацию о поле
                updateFieldInfo(areaHectares, coordinates.length);
            }
        });

        map.on(L.Draw.Event.EDITED, function (e) {
            const layers = e.layers;
            layers.eachLayer(function (layer) {
                if (layer instanceof L.Polygon) {
                    const coordinates = layer.getLatLngs()[0].map(latLng => [latLng.lat, latLng.lng]);
                    const area = L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]);
                    const areaHectares = (area / 10000).toFixed(2);

                    document.getElementById('polygonCoords').value = JSON.stringify(coordinates);
                    document.getElementById('fieldArea').value = areaHectares;
                    updateFieldInfo(areaHectares, coordinates.length);
                }
            });
        });

        map.on(L.Draw.Event.DELETED, function (e) {
            document.getElementById('polygonCoords').value = '';
            document.getElementById('fieldArea').value = '';
            document.getElementById('fieldInfo').style.display = 'none';
        });

        // Добавляем контроль масштаба
        L.control.scale({ imperial: false, metric: true }).addTo(map);

        console.log('Карта инициализирована полностью');

    } catch (error) {
        console.error('Ошибка инициализации карты:', error);
        showNotification('Ошибка загрузки карты. Проверьте подключение к интернету.', 'error');
    }
}

// Инициализация карты для выбора полей
function initSelectionMap() {
    console.log('Инициализация карты выбора полей...');

    try {
        const mapElement = document.getElementById('selectionMap');
        if (!mapElement) {
            console.error('Элемент selectionMap не найден');
            return;
        }

        // Создаем карту
        const map = L.map('selectionMap').setView([55.7558, 37.6173], 5);

        // Добавляем слой карты
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        // Загружаем и отображаем поля
        loadFieldsForSelection(map);

        // Добавляем контроль масштаба
        L.control.scale({ imperial: false, metric: true }).addTo(map);

        console.log('Карта выбора инициализирована');

        return map;

    } catch (error) {
        console.error('Ошибка инициализации карты выбора:', error);
    }
}

// Загрузка полей для выбора
function loadFieldsForSelection(map) {
    fetch('/api/fields/overview')
        .then(response => response.json())
        .then(fields => {
            fields.forEach(field => {
                if (field.polygon_coords) {
                    try {
                        const polygonData = JSON.parse(field.polygon_coords);
                        const polygon = L.polygon(polygonData, {
                            color: '#10b981',
                            fillColor: '#10b981',
                            fillOpacity: 0.3,
                            weight: 2
                        }).addTo(map);

                        // Создаем попап с информацией
                        polygon.bindPopup(`
                            <div style="text-align: center;">
                                <h4 style="margin: 0 0 10px 0;">${field.name}</h4>
                                <p style="margin: 5px 0;"><strong>Площадь:</strong> ${field.area || 'не указана'} га</p>
                                <p style="margin: 5px 0;"><strong>ID:</strong> #${field.id}</p>
                                <button onclick="selectField(${field.id})"
                                        style="background: #10b981; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">
                                    ✅ Выбрать это поле
                                </button>
                            </div>
                        `);

                    } catch (e) {
                        console.error('Ошибка парсинга полигона:', e);
                    }
                }
            });

            // Если есть поля, центрируем карту на них
            if (fields.length > 0 && fields[0].center_lat && fields[0].center_lng) {
                map.setView([fields[0].center_lat, fields[0].center_lng], 10);
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки полей:', error);
        });
}

// Обновление информации о поле
function updateFieldInfo(area, points) {
    const fieldInfo = document.getElementById('fieldInfo');
    const areaElement = document.getElementById('calculatedArea');
    const pointsElement = document.getElementById('polygonPoints');

    if (fieldInfo && areaElement && pointsElement) {
        areaElement.textContent = area + ' га';
        pointsElement.textContent = points;
        fieldInfo.style.display = 'block';
    }
}

// Инициализация карты для просмотра поля
function initViewMap(polygonData, fieldName, fieldArea) {
    console.log('Инициализация карты просмотра...');

    try {
        const mapElement = document.getElementById('fieldMap');
        if (!mapElement) {
            console.error('Элемент fieldMap не найден');
            return;
        }

        // Создаем карту
        const map = L.map('fieldMap').setView([55.7558, 37.6173], 5);

        // Добавляем слой карты
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        if (polygonData && polygonData.length > 0) {
            // Создаем полигон
            const polygon = L.polygon(polygonData, {
                color: '#10b981',
                fillColor: '#10b981',
                fillOpacity: 0.3,
                weight: 3
            }).addTo(map);

            // Центрируем карту на полигоне
            map.fitBounds(polygon.getBounds());

            // Добавляем попап с информацией
            polygon.bindPopup(`
                <div style="text-align: center;">
                    <h4 style="margin: 0 0 10px 0; color: #065f46;">${fieldName}</h4>
                    <p style="margin: 5px 0;"><strong>Площадь:</strong> ${fieldArea} га</p>
                    <p style="margin: 5px 0;"><strong>Точек в полигоне:</strong> ${polygonData.length}</p>
                </div>
            `);
        }

        // Добавляем контроль масштаба
        L.control.scale({ imperial: false, metric: true }).addTo(map);

        console.log('Карта просмотра инициализирована');

    } catch (error) {
        console.error('Ошибка инициализации карты просмотра:', error);
    }
}

// Инициализация карты для обзора всех полей
function initOverviewMap(fieldsData) {
    console.log('Инициализация карты обзора...');

    try {
        const mapElement = document.getElementById('overviewMap');
        if (!mapElement) {
            console.error('Элемент overviewMap не найден');
            return;
        }

        // Создаем карту
        const map = L.map('overviewMap').setView([55.7558, 37.6173], 5);

        // Добавляем слой карты
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        // Создаем группу для всех полей
        const fieldsGroup = L.featureGroup();

        // Добавляем каждое поле на карту
        fieldsData.forEach(field => {
            if (field.polygon_coords) {
                try {
                    const polygonData = JSON.parse(field.polygon_coords);
                    const polygon = L.polygon(polygonData, {
                        color: '#10b981',
                        fillColor: '#10b981',
                        fillOpacity: 0.3,
                        weight: 2
                    }).bindPopup(`
                        <div style="text-align: center;">
                            <h4>${field.name}</h4>
                            <p>Площадь: ${field.area || 'не указана'} га</p>
                            <a href="/fields/${field.id}" class="btn btn-primary">Подробнее</a>
                        </div>
                    `);

                    fieldsGroup.addLayer(polygon);
                } catch (e) {
                    console.error('Ошибка парсинга полигона:', e);
                }
            }
        });

        // Добавляем группу на карту
        map.addLayer(fieldsGroup);

        // Центрируем карту на всех полях
        if (fieldsGroup.getLayers().length > 0) {
            map.fitBounds(fieldsGroup.getBounds());
        }

        // Добавляем контроль масштаба
        L.control.scale({ imperial: false, metric: true }).addTo(map);

        console.log('Карта обзора инициализирована');

    } catch (error) {
        console.error('Ошибка инициализации карты обзора:', error);
    }
}

// Переключение между ручным вводом и рисованием на карте
function toggleInputMethod() {
    const manualInput = document.getElementById('manualInput');
    const mapInput = document.getElementById('mapInput');
    const toggleBtn = document.getElementById('toggleInputBtn');

    if (manualInput.style.display === 'none') {
        // Переключаем на ручной ввод
        manualInput.style.display = 'block';
        mapInput.style.display = 'none';
        toggleBtn.textContent = '🗺️ Перейти к рисованию на карте';
        toggleBtn.classList.remove('btn-secondary');
        toggleBtn.classList.add('btn-primary');
    } else {
        // Переключаем на карту
        manualInput.style.display = 'none';
        mapInput.style.display = 'block';
        toggleBtn.textContent = '📝 Перейти к ручному вводу';
        toggleBtn.classList.remove('btn-primary');
        toggleBtn.classList.add('btn-secondary');

        // Инициализируем карту если она еще не инициализирована
        if (!map) {
            setTimeout(() => {
                console.log('Запуск инициализации карты...');
                initCreateMap();
            }, 100);
        }
    }
}

// Валидация формы
function validateFieldForm() {
    const name = document.getElementById('fieldName').value;
    const area = document.getElementById('fieldArea').value;

    if (!name.trim()) {
        showNotification('Пожалуйста, введите название поля', 'error');
        return false;
    }

    if (!area || parseFloat(area) <= 0) {
        showNotification('Пожалуйста, укажите площадь поля (можно нарисовать на карте)', 'error');
        return false;
    }

    return true;
}

// Показать уведомление
function showNotification(message, type = 'info') {
    // Создаем элемент уведомления если его нет
    let notification = document.querySelector('.notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        document.body.appendChild(notification);
    }

    notification.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()">×</button>
    `;
    notification.className = `notification notification-${type}`;

    // Автоматическое скрытие через 5 секунд
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Показать/скрыть инструкцию
function toggleInstructions() {
    const instructions = document.getElementById('mapInstructions');
    const toggleBtn = document.getElementById('toggleInstructionsBtn');

    if (instructions.style.display === 'none') {
        instructions.style.display = 'block';
        toggleBtn.textContent = '📋 Скрыть инструкцию';
    } else {
        instructions.style.display = 'none';
        toggleBtn.textContent = '📋 Показать инструкцию';
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM загружен, проверяем элементы карты...');

    // Инициализируем карту если есть элемент с id="map"
    if (document.getElementById('map')) {
        console.log('Найден элемент map, инициализируем карту...');
        setTimeout(() => initCreateMap(), 500);
    }

    // Инициализируем карту выбора если есть элемент с id="selectionMap"
    if (document.getElementById('selectionMap')) {
        console.log('Найден элемент selectionMap, инициализируем карту выбора...');
        setTimeout(() => initSelectionMap(), 500);
    }

    // Инициализируем карту обзора если есть элемент с id="overviewMap"
    if (document.getElementById('overviewMap')) {
        console.log('Найден элемент overviewMap');
        const fieldsData = window.fieldsData || [];
        setTimeout(() => initOverviewMap(fieldsData), 500);
    }

    // Инициализируем карту просмотра если есть элемент с id="fieldMap"
    if (document.getElementById('fieldMap')) {
        console.log('Найден элемент fieldMap');
        // Данные должны быть переданы из шаблона
        const polygonData = window.polygonData || [];
        const fieldName = window.fieldName || 'Поле';
        const fieldArea = window.fieldArea || '0';
        setTimeout(() => initViewMap(polygonData, fieldName, fieldArea), 500);
    }

    // Добавляем обработчики для кнопок переключения
    const toggleBtn = document.getElementById('toggleInputBtn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleInputMethod);
    }

    const instructionsBtn = document.getElementById('toggleInstructionsBtn');
    if (instructionsBtn) {
        instructionsBtn.addEventListener('click', toggleInstructions);
    }

    console.log('Инициализация завершена');
});

// Добавим в конец файла map.js

// Инициализация карты для обзора всех полей
function initOverviewMap(fieldsData) {
    console.log('Инициализация карты обзора...');

    try {
        const mapElement = document.getElementById('overviewMap');
        if (!mapElement) {
            console.error('Элемент overviewMap не найден');
            return;
        }

        // Создаем карту
        const map = L.map('overviewMap').setView([55.7558, 37.6173], 5);

        // Добавляем слой карты
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        // Создаем группу для всех полей
        const fieldsGroup = L.featureGroup();

        // Добавляем каждое поле на карту
        fieldsData.forEach(field => {
            if (field.polygon_coords) {
                try {
                    const polygonData = JSON.parse(field.polygon_coords);
                    const polygon = L.polygon(polygonData, {
                        color: '#10b981',
                        fillColor: '#10b981',
                        fillOpacity: 0.3,
                        weight: 2
                    }).bindPopup(`
                        <div style="text-align: center;">
                            <h4>${field.name}</h4>
                            <p>Площадь: ${field.area || 'не указана'} га</p>
                            <a href="/fields/${field.id}" class="btn btn-primary">Подробнее</a>
                        </div>
                    `);

                    fieldsGroup.addLayer(polygon);
                } catch (e) {
                    console.error('Ошибка парсинга полигона:', e);
                }
            } else if (field.latitude && field.longitude) {
                // Если нет полигона, но есть координаты, создаем маркер
                const marker = L.marker([field.latitude, field.longitude])
                    .bindPopup(`
                        <div style="text-align: center;">
                            <h4>${field.name}</h4>
                            <p>Площадь: ${field.area || 'не указана'} га</p>
                            <a href="/fields/${field.id}" class="btn btn-primary">Подробнее</a>
                        </div>
                    `);
                fieldsGroup.addLayer(marker);
            }
        });

        // Добавляем группу на карту
        map.addLayer(fieldsGroup);

        // Центрируем карту на всех полях
        if (fieldsGroup.getLayers().length > 0) {
            map.fitBounds(fieldsGroup.getBounds().pad(0.1));
        }

        // Добавляем контроль масштаба
        L.control.scale({ imperial: false, metric: true }).addTo(map);

        console.log('Карта обзора инициализирована');

    } catch (error) {
        console.error('Ошибка инициализации карты обзора:', error);
    }
}

// Функция для инициализации карты обзора
function initOverviewMap(fieldsData) {
    console.log('Инициализация карты обзора...');

    try {
        const mapElement = document.getElementById('overviewMap');
        if (!mapElement) {
            console.error('Элемент overviewMap не найден');
            return;
        }

        // Создаем карту
        const map = L.map('overviewMap').setView([55.7558, 37.6173], 5);

        // Добавляем слой карты
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        // Создаем группу для всех полей
        const fieldsGroup = L.featureGroup();

        // Добавляем каждое поле на карту
        fieldsData.forEach(field => {
            if (field.polygon_coords) {
                try {
                    const polygonData = JSON.parse(field.polygon_coords);
                    const polygon = L.polygon(polygonData, {
                        color: '#10b981',
                        fillColor: '#10b981',
                        fillOpacity: 0.3,
                        weight: 2
                    }).bindPopup(`
                        <div style="text-align: center;">
                            <h4>${field.name}</h4>
                            <p>Площадь: ${field.area || 'не указана'} га</p>
                            <a href="/fields/${field.id}" class="btn btn-primary">Подробнее</a>
                        </div>
                    `);

                    fieldsGroup.addLayer(polygon);
                } catch (e) {
                    console.error('Ошибка парсинга полигона:', e);
                }
            }
        });

        // Добавляем группу на карту
        map.addLayer(fieldsGroup);

        // Центрируем карту на всех полях
        if (fieldsGroup.getLayers().length > 0) {
            map.fitBounds(fieldsGroup.getBounds().pad(0.1));
        }

        // Добавляем контроль масштаба
        L.control.scale({ imperial: false, metric: true }).addTo(map);

        console.log('Карта обзора инициализирована');

    } catch (error) {
        console.error('Ошибка инициализации карты обзора:', error);
    }
}