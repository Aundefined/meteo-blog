const WEATHER_URL = './weather.json';

const CIELO_EMOJI = {
  'Despejado': '☀️',
  'Poco nuboso': '🌤️',
  'Intervalos nubosos': '⛅',
  'Nubes altas': '🌥️',
  'Nuboso': '☁️',
  'Muy nuboso': '☁️',
  'Cubierto': '☁️',
  'Cubierto con lluvia': '🌧️',
  'Nuboso con lluvia': '🌦️',
  'Intervalos nubosos con lluvia': '🌦️',
  'Chubascos': '🌧️',
  'Tormenta': '⛈️',
  'Nieve': '🌨️',
  'Niebla': '🌫️',
  'Sin datos': '❓',
};

function getEmoji(cielo) {
  if (!cielo) return '❓';
  for (const [key, emoji] of Object.entries(CIELO_EMOJI)) {
    if (cielo.toLowerCase().includes(key.toLowerCase())) return emoji;
  }
  return '🌡️';
}

function formatDate(isoString) {
  const d = new Date(isoString);
  return d.toLocaleString('es-ES', {
    weekday: 'long', day: 'numeric', month: 'long',
    hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Madrid'
  });
}

function rainColor(prob) {
  if (prob === null || prob === undefined) return 'text-slate-400';
  if (prob >= 70) return 'text-blue-600 font-semibold';
  if (prob >= 40) return 'text-blue-400';
  return 'text-slate-500';
}

function createCard(c) {
  const emoji = getEmoji(c.cielo);
  const hasData = c.temp_max !== null;

  return `
    <div class="bg-white rounded-2xl shadow p-5 flex flex-col gap-3">
      <div class="flex items-center justify-between">
        <div>
          <p class="font-semibold text-slate-800 text-sm">${c.nombre}</p>
          <p class="text-xs text-slate-400">${c.capital}</p>
        </div>
        <span class="text-3xl">${emoji}</span>
      </div>

      ${hasData ? `
        <div class="flex items-end gap-2">
          <span class="text-2xl font-bold text-slate-800">${c.temp_max}°</span>
          <span class="text-base text-slate-400 mb-0.5">${c.temp_min}°</span>
        </div>
        <div class="flex items-center justify-between text-xs">
          <span class="text-slate-500">${c.cielo}</span>
          <span class="${rainColor(c.prob_lluvia)}">💧 ${c.prob_lluvia}%</span>
        </div>
      ` : `
        <p class="text-sm text-slate-400">Sin datos disponibles</p>
      `}
    </div>
  `;
}

async function load() {
  try {
    const res = await fetch(WEATHER_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    document.getElementById('updated-at').textContent =
      `Actualizado: ${formatDate(data.updated_at)}`;

    document.getElementById('summary-text').textContent = data.summary;

    document.getElementById('cards-grid').innerHTML =
      data.comunidades.map(createCard).join('');

  } catch (err) {
    console.error(err);
    document.getElementById('summary-box').classList.add('hidden');
    document.getElementById('error-box').classList.remove('hidden');
    document.getElementById('updated-at').textContent = '';
  }
}

load();
