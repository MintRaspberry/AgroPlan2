// Функции для работы с графиками

function initYieldChart(statsData) {
    const ctx = document.getElementById('yieldChart');
    if (!ctx) {
        console.error('Элемент yieldChart не найден');
        return;
    }

    const context = ctx.getContext('2d');

    // Очищаем предыдущий график
    if (window.yieldChartInstance) {
        window.yieldChartInstance.destroy();
    }

    if (!statsData || !statsData.crops || statsData.crops.length === 0) {
        context.font = '16px Arial';
        context.fillStyle = '#6c757d';
        context.textAlign = 'center';
        context.fillText('Недостаточно данных для построения графика', ctx.width / 2, ctx.height / 2);
        return;
    }

    // Подготовка данных
    const crops = statsData.crops || [];
    const yields = statsData.yields || [];
    const counts = statsData.counts || [];

    // Создаем градиенты
    const gradient = context.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(100, 255, 218, 0.8)');
    gradient.addColorStop(1, 'rgba(100, 255, 218, 0.2)');

    window.yieldChartInstance = new Chart(context, {
        type: 'bar',
        data: {
            labels: crops,
            datasets: [{
                label: 'Средняя урожайность (т/га)',
                data: yields,
                backgroundColor: gradient,
                borderColor: '#64ffda',
                borderWidth: 2,
                borderRadius: 8,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#ccd6f6',
                        font: {
                            family: 'Inter'
                        }
                    }
                },
                title: {
                    display: true,
                    text: 'Урожайность по культурам',
                    color: '#e6f1ff',
                    font: {
                        family: 'Inter',
                        size: 16
                    }
                },
                tooltip: {
                    callbacks: {
                        afterLabel: function(context) {
                            const index = context.dataIndex;
                            return `Записей: ${counts[index]}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Урожайность (т/га)',
                        color: '#a8b2d1'
                    },
                    grid: {
                        color: 'rgba(100, 255, 218, 0.1)'
                    },
                    ticks: {
                        color: '#a8b2d1'
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#a8b2d1'
                    }
                }
            }
        }
    });
}

function initRotationTimeline(rotationData) {
    const ctx = document.getElementById('rotationChart');
    if (!ctx) {
        console.error('Элемент rotationChart не найден');
        return;
    }

    const context = ctx.getContext('2d');

    // Очищаем предыдущий график
    if (window.rotationChartInstance) {
        window.rotationChartInstance.destroy();
    }

    if (!rotationData || rotationData.length === 0) {
        context.font = '16px Arial';
        context.fillStyle = '#6c757d';
        context.textAlign = 'center';
        context.fillText('Недостаточно данных для построения графика', ctx.width / 2, ctx.height / 2);
        return;
    }

    // Группируем данные по годам и сезонам
    const years = [...new Set(rotationData.map(item => item.year))].sort();
    const seasons = ['весна', 'лето', 'осень'];

    const datasets = seasons.map(season => {
        const seasonData = years.map(year => {
            const item = rotationData.find(d => d.year === year && d.season === season);
            return item ? item.crop : null;
        });

        // Проверяем, есть ли данные для этого сезона
        const hasData = seasonData.some(val => val !== null);

        return {
            label: season,
            data: seasonData,
            borderColor: getSeasonColor(season),
            backgroundColor: getSeasonColor(season, 0.1),
            tension: 0.4,
            fill: false,
            pointBackgroundColor: seasonData.map(val => val ? getSeasonColor(season) : 'transparent'),
            pointBorderColor: seasonData.map(val => val ? getSeasonColor(season) : 'transparent'),
            pointRadius: seasonData.map(val => val ? 5 : 0)
        };
    }).filter(dataset => dataset.data.some(val => val !== null));

    // Если нет данных для графиков, показываем сообщение
    if (datasets.length === 0) {
        context.font = '16px Arial';
        context.fillStyle = '#6c757d';
        context.textAlign = 'center';
        context.fillText('Недостаточно данных для построения графика', ctx.width / 2, ctx.height / 2);
        return;
    }

    window.rotationChartInstance = new Chart(context, {
        type: 'line',
        data: {
            labels: years,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#ccd6f6',
                        font: {
                            family: 'Inter'
                        }
                    }
                },
                title: {
                    display: true,
                    text: 'История севооборота',
                    color: '#e6f1ff',
                    font: {
                        family: 'Inter',
                        size: 16
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.raw || 'нет данных'}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    display: false
                },
                x: {
                    title: {
                        display: true,
                        text: 'Год',
                        color: '#a8b2d1'
                    },
                    ticks: {
                        color: '#a8b2d1'
                    },
                    grid: {
                        color: 'rgba(100, 255, 218, 0.1)'
                    }
                }
            }
        }
    });
}

function getSeasonColor(season, opacity = 1) {
    const colors = {
        'весна': `rgba(76, 175, 80, ${opacity})`,
        'лето': `rgba(255, 193, 7, ${opacity})`,
        'осень': `rgba(121, 85, 72, ${opacity})`
    };
    return colors[season] || `rgba(100, 100, 100, ${opacity})`;
}

// Загрузка данных для графиков
async function loadYieldStats(fieldId = null) {
    try {
        const url = fieldId ? `/api/yield-stats?field_id=${fieldId}` : '/api/yield-stats';
        console.log('Загрузка статистики урожайности:', url);

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Получены данные статистики:', data);

        if (document.getElementById('yieldChart')) {
            initYieldChart(data);
        }
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
        // Показываем сообщение об ошибке на графике
        const ctx = document.getElementById('yieldChart');
        if (ctx) {
            const context = ctx.getContext('2d');
            context.font = '14px Arial';
            context.fillStyle = '#ef4444';
            context.textAlign = 'center';
            context.fillText('Ошибка загрузки данных', ctx.width / 2, ctx.height / 2);
        }
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('Инициализация графиков...');

    // Загружаем общую статистику урожайности
    loadYieldStats();

    // Инициализируем график севооборота если данные уже есть
    if (window.rotationData && document.getElementById('rotationChart')) {
        setTimeout(() => {
            initRotationTimeline(window.rotationData);
        }, 100);
    }
});

// Экспорт функций для глобального использования
window.initYieldChart = initYieldChart;
window.initRotationTimeline = initRotationTimeline;
window.loadYieldStats = loadYieldStats;