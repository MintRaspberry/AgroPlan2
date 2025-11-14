// Функции для работы с графиками
function initYieldChart(statsData) {
    const ctx = document.getElementById('yieldChart').getContext('2d');

    if (!statsData || !statsData.crops || statsData.crops.length === 0) {
        ctx.font = '16px Arial';
        ctx.fillStyle = '#6c757d';
        ctx.textAlign = 'center';
        ctx.fillText('Недостаточно данных для построения графика', ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }

    // Подготовка данных
    const crops = statsData.crops || [];
    const yields = statsData.yields || [];
    const counts = statsData.counts || [];

    // Создаем градиенты
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(76, 175, 80, 0.8)');
    gradient.addColorStop(1, 'rgba(76, 175, 80, 0.2)');

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: crops,
            datasets: [{
                label: 'Средняя урожайность (т/га)',
                data: yields,
                backgroundColor: gradient,
                borderColor: '#4caf50',
                borderWidth: 2,
                borderRadius: 8,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'Урожайность по культурам'
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
                        text: 'Урожайность (т/га)'
                    },
                    grid: {
                        color: 'rgba(0,0,0,0.1)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

function initRotationTimeline(rotationData) {
    const ctx = document.getElementById('rotationChart').getContext('2d');

    if (!rotationData || rotationData.length === 0) {
        ctx.font = '16px Arial';
        ctx.fillStyle = '#6c757d';
        ctx.textAlign = 'center';
        ctx.fillText('Недостаточно данных для построения графика', ctx.canvas.width / 2, ctx.canvas.height / 2);
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
            fill: true,
            pointBackgroundColor: seasonData.map(val => val ? getSeasonColor(season) : 'transparent'),
            pointBorderColor: seasonData.map(val => val ? getSeasonColor(season) : 'transparent'),
            pointRadius: seasonData.map(val => val ? 5 : 0)
        };
    }).filter(dataset => dataset.data.some(val => val !== null));

    // Если нет данных для графиков, показываем сообщение
    if (datasets.length === 0) {
        ctx.font = '16px Arial';
        ctx.fillStyle = '#6c757d';
        ctx.textAlign = 'center';
        ctx.fillText('Недостаточно данных для построения графика', ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: years,
            datasets: datasets
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'История севооборота'
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
                        text: 'Год'
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
        const response = await fetch(url);
        const data = await response.json();

        if (document.getElementById('yieldChart')) {
            initYieldChart(data);
        }
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Загружаем общую статистику урожайности
    loadYieldStats();
});
