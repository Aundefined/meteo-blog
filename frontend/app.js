const WEATHER_URL = './weather.json';
const MAP_URL = './spain.svg';

// Mapeo de nombre de comunidad al ID del SVG
const SVG_ID_MAP = {
  'Andalucía':             'andalusia',
  'Aragón':                'aragon',
  'Asturias':              'asturias',
  'Islas Baleares':        'balearic-islands',
  'Canarias':              'canary-islands',
  'Cantabria':             'cantabria',
  'Castilla y León':       'castile-and-leon',
  'Castilla-La Mancha':    'castile-la-mancha',
  'Cataluña':              'catalonia',
  'Extremadura':           'extremadura',
  'Galicia':               'galicia',
  'Comunidad de Madrid':   'madrid',
  'Región de Murcia':      'murcia',
  'Navarra':               'navarre',
  'La Rioja':              'la-rioja',
  'País Vasco':            'basque-country',
  'Comunitat Valenciana':  'valencia',
};

const CIELO_EMOJI = {
  // Específicos con lluvia primero (antes que sus variantes sin lluvia)
  'Intervalos nubosos con lluvia': '🌦️',
  'Cubierto con lluvia': '🌧️',
  'Nuboso con lluvia': '🌦️',
  'Chubascos': '🌧️',
  'Tormenta': '⛈️',
  'Nieve': '🌨️',
  'Niebla': '🌫️',
  // Genéricos después
  'Despejado': '☀️',
  'Poco nuboso': '🌤️',
  'Intervalos nubosos': '⛅',
  'Nubes altas': '🌥️',
  'Muy nuboso': '☁️',
  'Cubierto': '☁️',
  'Nuboso': '☁️',
  'Sin datos': '❓',
};

function getEmoji(cielo) {
  if (!cielo) return '❓';
  for (const [key, emoji] of Object.entries(CIELO_EMOJI)) {
    if (cielo.toLowerCase() === key.toLowerCase()) return emoji;
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

function getRainFill(prob) {
  if (prob === null || prob === undefined) return '#e2e8f0';
  if (prob >= 75) return '#1d4ed8';
  if (prob >= 50) return '#3b82f6';
  if (prob >= 25) return '#93c5fd';
  return '#dbeafe';
}

async function loadMap(comunidades) {
  const res = await fetch(MAP_URL);
  const svgText = await res.text();

  const container = document.getElementById('spain-map');
  container.innerHTML = svgText;

  const svg = container.querySelector('svg');
  svg.setAttribute('width', '100%');
  svg.removeAttribute('height');

  // Mover las Canarias justo debajo de la península (eliminar el hueco vacío)
  const canaryPath = svg.getElementById('canary-islands');
  if (canaryPath) {
    try {
      let mainlandMaxY = 0;
      for (const p of svg.querySelectorAll('path')) {
        if (p.id === 'canary-islands') continue;
        const b = p.getBBox();
        mainlandMaxY = Math.max(mainlandMaxY, b.y + b.height);
      }
      const canaryBox = canaryPath.getBBox();
      const dy = mainlandMaxY + 15 - canaryBox.y;
      canaryPath.setAttribute('transform', `translate(0, ${dy})`);
    } catch (e) {}
  }

  const tooltip = document.getElementById('map-tooltip');

  comunidades.forEach(c => {
    const svgId = SVG_ID_MAP[c.nombre];
    if (!svgId) return;
    const path = svg.getElementById(svgId);
    if (!path) return;

    path.style.fill = getRainFill(c.prob_lluvia);
    path.style.stroke = '#fff';
    path.style.strokeWidth = '1';
    path.style.cursor = 'pointer';
    path.style.transition = 'opacity 0.15s';

    // Añadir emoji centrado sobre el path (teniendo en cuenta transforms aplicados)
    try {
      let tx = 0, ty = 0;
      const tr = path.getAttribute('transform');
      if (tr) {
        const m = tr.match(/translate\(([-\d.]+)[,\s]+([-\d.]+)\)/);
        if (m) { tx = parseFloat(m[1]); ty = parseFloat(m[2]); }
      }
      const bbox = path.getBBox();
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', bbox.x + bbox.width / 2 + tx);
      text.setAttribute('y', bbox.y + bbox.height / 2 + 6 + ty);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('font-size', '12');
      text.setAttribute('pointer-events', 'none');
      text.textContent = getEmoji(c.cielo);
      svg.appendChild(text);
    } catch (e) {}

    path.addEventListener('mouseenter', () => {
      path.style.opacity = '0.75';
      const lluvia = c.prob_lluvia !== null ? `${c.prob_lluvia}%` : 'Sin datos';
      const tmax = c.temp_max !== null ? `${c.temp_max}°` : '—';
      const tmin = c.temp_min !== null ? `${c.temp_min}°` : '—';
      tooltip.textContent = `${c.nombre} — ${c.cielo} · ${tmax}/${tmin} · 💧 ${lluvia}`;
      tooltip.classList.remove('hidden');
    });

    path.addEventListener('mouseleave', () => {
      path.style.opacity = '1';
      tooltip.classList.add('hidden');
    });
  });

  // Ajustar viewBox al contenido real (ya sin el hueco)
  try {
    const bbox = svg.getBBox();
    const pad = 10;
    svg.setAttribute('viewBox', `${bbox.x - pad} ${bbox.y - pad} ${bbox.width + pad * 2} ${bbox.height + pad * 2}`);
  } catch (e) {}
}

async function load() {
  try {
    const res = await fetch(WEATHER_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    document.getElementById('updated-at').textContent =
      `Actualizado: ${formatDate(data.updated_at)}`;

    document.getElementById('summary-text').textContent = data.summary;

    await loadMap(data.comunidades);

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
