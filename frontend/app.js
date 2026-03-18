const WEATHER_URL = './weather.json';
const MAP_URL = './spain.svg';
const CHATBOT_URL = 'https://ezqbc96jig.execute-api.eu-west-1.amazonaws.com/';

const SESSION_ID = crypto.randomUUID();

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
  'Bruma': '🌫️',
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
  const c = cielo.toLowerCase();
  for (const [key, emoji] of Object.entries(CIELO_EMOJI)) {
    if (c.includes(key.toLowerCase())) return emoji;
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

function createMiniChart(dias, mode) {
  const W = 200, H = 58, pX = 6, pY = 6, lblH = 13;
  const n = dias.length;
  if (n < 2) return '';

  const DIAS_SHORT = ['Do', 'Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sá'];
  const MESES_SHORT = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
  const chartH = H - lblH;
  const xOf = i => pX + (i / (n - 1)) * (W - pX * 2);
  const tipDate = d => {
    const date = new Date(d.fecha + 'T12:00:00');
    return `${DIAS_SHORT[date.getDay()]} ${date.getDate()} ${MESES_SHORT[date.getMonth()]}`;
  };

  if (mode === 'rain') {
    const gapW = (W - pX * 2) / n;
    const barW = gapW * 0.55;
    const bars = dias.map((d, i) => {
      const prob = d.prob_lluvia ?? 0;
      const bH = Math.max(1, (prob / 100) * (chartH - pY));
      const x = pX + i * gapW + (gapW - barW) / 2;
      const y = chartH - bH;
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${bH.toFixed(1)}" rx="2" fill="${getRainFill(prob)}"><title>${tipDate(d)} — ${prob}%</title></rect>`;
    }).join('');
    const lbls = dias.map((d, i) => {
      const x = pX + i * gapW + gapW / 2;
      const day = new Date(d.fecha + 'T12:00:00').getDay();
      return `<text x="${x.toFixed(1)}" y="${H - 1}" text-anchor="middle" font-size="9" fill="#94a3b8">${DIAS_SHORT[day]}</text>`;
    }).join('');
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}">${bars}${lbls}</svg>`;
  }

  const temps = dias.flatMap(d => [d.temp_max, d.temp_min]).filter(t => t !== null);
  if (!temps.length) return '';
  const lo = Math.min(...temps) - 1, hi = Math.max(...temps) + 1;
  const yOf = t => pY + ((hi - t) / (hi - lo)) * (chartH - pY * 2);
  const pts = key => dias.map((d, i) => d[key] !== null ? [xOf(i), yOf(d[key]), d] : null).filter(Boolean);
  const maxPts = pts('temp_max');
  const minPts = pts('temp_min');
  const toLine = pts => pts.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const areaPts = [...maxPts, ...[...minPts].reverse()].map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const lbls = dias.map((d, i) => {
    const day = new Date(d.fecha + 'T12:00:00').getDay();
    return `<text x="${xOf(i).toFixed(1)}" y="${H - 1}" text-anchor="middle" font-size="9" fill="#94a3b8">${DIAS_SHORT[day]}</text>`;
  }).join('');
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}">
    <polygon points="${areaPts}" fill="#fff7ed" opacity="0.7"/>
    <polyline points="${toLine(maxPts)}" fill="none" stroke="#f97316" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
    <polyline points="${toLine(minPts)}" fill="none" stroke="#93c5fd" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
    ${maxPts.map(p => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2.5" fill="#f97316" pointer-events="none"/><circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="20" fill="transparent"><title>${tipDate(p[2])} — Max: ${p[2].temp_max}°</title></circle>`).join('')}
    ${minPts.map(p => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2.5" fill="#93c5fd" pointer-events="none"/><circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="20" fill="transparent"><title>${tipDate(p[2])} — Min: ${p[2].temp_min}°</title></circle>`).join('')}
    ${lbls}
  </svg>`;
}

function createCard(c, mode) {
  const emoji = getEmoji(c.cielo);
  const hasData = c.temp_max !== null;
  const chart = c.dias && c.dias.length > 1 ? createMiniChart(c.dias, mode) : '';

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
      ${chart ? `<div class="border-t border-slate-100 pt-2">${chart}</div>` : ''}
    </div>
  `;
}

function getRainFill(prob) {
  if (prob === null || prob === undefined) return '#e2e8f0';
  if (prob >= 90) return '#1e3a8a';
  if (prob >= 80) return '#1e40af';
  if (prob >= 70) return '#1d4ed8';
  if (prob >= 60) return '#2563eb';
  if (prob >= 50) return '#3b82f6';
  if (prob >= 40) return '#60a5fa';
  if (prob >= 30) return '#93c5fd';
  if (prob >= 20) return '#bae6fd';
  if (prob >= 10) return '#e0f2fe';
  return '#f0f9ff';
}

function getTempFill(temp) {
  if (temp === null || temp === undefined) return '#e2e8f0';
  if (temp >= 50) return '#7f0000';
  if (temp >= 40) return '#cc0000';
  if (temp >= 35) return '#ff3300';
  if (temp >= 30) return '#ff7700';
  if (temp >= 25) return '#ffbb00';
  if (temp >= 20) return '#ffee00';
  if (temp >= 15) return '#aadd00';
  if (temp >= 10) return '#55cc00';
  if (temp >= 5)  return '#00cc88';
  if (temp >= 0)  return '#00aaee';
  if (temp >= -10) return '#5566ff';
  if (temp >= -20) return '#9933cc';
  return '#880088';
}

let weatherData = null;
let mapComunidades = null;
let mapEmojiElements = {};

let sortAsc = false;

function sortComunidades(comunidades, mode) {
  const key = mode === 'rain' ? 'prob_lluvia' : 'temp_max';
  return [...comunidades].sort((a, b) => {
    const diff = sortAsc
      ? (a[key] ?? -Infinity) - (b[key] ?? -Infinity)
      : (b[key] ?? -Infinity) - (a[key] ?? -Infinity);
    return diff !== 0 ? diff : a.nombre.localeCompare(b.nombre, 'es');
  });
}

function renderCards() {
  const mode = document.querySelector('input[name="map-mode"]:checked')?.value || 'temp';
  document.getElementById('cards-grid').innerHTML = sortComunidades(mapComunidades, mode).map(c => createCard(c, mode)).join('');
  const magnitud = mode === 'rain' ? 'probabilidad de lluvia' : 'temperatura';
  const direccion = sortAsc ? 'de menor a mayor' : 'de mayor a menor';
  document.getElementById('sort-label').textContent = `${magnitud} ${direccion}`;
}

function getComunidadesForDay(dayIndex) {
  if (!weatherData) return [];
  return weatherData.comunidades.map(c => {
    const dia = c.dias && c.dias[dayIndex];
    return {
      nombre: c.nombre,
      capital: c.capital,
      temp_max: dia ? dia.temp_max : null,
      temp_min: dia ? dia.temp_min : null,
      prob_lluvia: dia ? dia.prob_lluvia : null,
      cielo: dia ? dia.cielo : 'Sin datos',
      dias: c.dias || [],
    };
  });
}

function updateMapColors(mode) {
  if (!mapComunidades) return;
  const svg = document.querySelector('#spain-map svg');
  if (!svg) return;
  mapComunidades.forEach(c => {
    const svgId = SVG_ID_MAP[c.nombre];
    if (!svgId) return;
    const path = svg.getElementById(svgId);
    if (!path) return;
    path.style.fill = mode === 'temp' ? getTempFill(c.temp_max) : getRainFill(c.prob_lluvia);
    const textEl = mapEmojiElements[c.nombre];
    if (textEl) textEl.textContent = getEmoji(c.cielo);
  });
  document.getElementById('legend-rain').classList.toggle('hidden', mode !== 'rain');
  document.getElementById('legend-temp').classList.toggle('hidden', mode !== 'temp');
}

function updateDayView(dayIndex) {
  mapComunidades = getComunidadesForDay(dayIndex);

  const mode = document.querySelector('input[name="map-mode"]:checked')?.value || 'temp';
  updateMapColors(mode);

  renderCards();

  document.querySelectorAll('#day-selector button').forEach((btn, i) => {
    btn.className = `px-4 py-2 rounded-xl text-sm font-semibold shadow-sm transition-colors ${
      i === dayIndex ? 'bg-blue-500 text-white' : 'bg-white text-slate-600 hover:bg-slate-100'
    }`;
  });
}

function initDaySelector() {
  const firstCcaa = weatherData.comunidades[0];
  const numDays = firstCcaa.dias ? Math.min(firstCcaa.dias.length, 5) : 1;
  const container = document.getElementById('day-selector');
  container.innerHTML = '';

  for (let i = 0; i < numDays; i++) {
    const fecha = firstCcaa.dias[i].fecha;
    let label;
    if (i === 0) {
      label = 'Hoy';
    } else {
      const d = new Date(fecha + 'T12:00:00');
      label = d.toLocaleDateString('es-ES', { weekday: 'short' });
      label = label.charAt(0).toUpperCase() + label.slice(1);
    }
    const btn = document.createElement('button');
    btn.textContent = label;
    btn.className = `px-4 py-2 rounded-xl text-sm font-semibold shadow-sm transition-colors ${
      i === 0 ? 'bg-blue-500 text-white' : 'bg-white text-slate-600 hover:bg-slate-100'
    }`;
    const idx = i;
    btn.addEventListener('click', () => updateDayView(idx));
    container.appendChild(btn);
  }
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

    path.style.fill = getTempFill(c.temp_max);
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
      mapEmojiElements[c.nombre] = text;
      svg.appendChild(text);
    } catch (e) {}

    const nombre = c.nombre;
    path.addEventListener('mouseenter', () => {
      path.style.opacity = '0.75';
      const current = mapComunidades ? mapComunidades.find(x => x.nombre === nombre) : c;
      const lluvia = current.prob_lluvia !== null ? `${current.prob_lluvia}%` : 'Sin datos';
      const tmax = current.temp_max !== null ? `${current.temp_max}°` : '—';
      const tmin = current.temp_min !== null ? `${current.temp_min}°` : '—';
      tooltip.textContent = `${current.nombre} — ${current.cielo} · ${tmax}/${tmin} · 💧 ${lluvia}`;
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
    weatherData = await res.json();

    document.getElementById('updated-at').textContent =
      `Actualizado: ${formatDate(weatherData.updated_at)}`;

    document.getElementById('summary-text').textContent = weatherData.summary;

    mapComunidades = getComunidadesForDay(0);
    await loadMap(mapComunidades);

    document.querySelectorAll('input[name="map-mode"]').forEach(radio => {
      radio.addEventListener('change', e => {
        const mode = e.target.value;
        updateMapColors(mode);
        renderCards();
      });
    });

    initDaySelector();

    renderCards();

  } catch (err) {
    console.error(err);
    document.getElementById('summary-box').classList.add('hidden');
    document.getElementById('error-box').classList.remove('hidden');
    document.getElementById('updated-at').textContent = '';
  }
}

load();

document.getElementById('sort-toggle').addEventListener('click', () => {
  sortAsc = !sortAsc;
  renderCards();
});

// ---------------------------------------------------------------------------
// Chatbot
// ---------------------------------------------------------------------------

const SUGGESTIONS = [
  '¿Qué tiempo hará mañana en Madrid?',
  '¿Cómo funciona la Lambda del fetcher?',
  '¿Qué modelo de IA usa y por qué?'
];

function addMessage(text, role) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  if (role === 'user') {
    div.className = 'self-end bg-blue-500 text-white text-sm rounded-2xl rounded-br-sm px-4 py-2 max-w-prose';
    div.textContent = text;
  } else {
    div.className = 'chat-bot-msg self-start bg-slate-100 text-slate-700 text-sm rounded-2xl rounded-bl-sm px-4 py-2 max-w-prose';
    div.innerHTML = marked.parse(text);
  }
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function setTyping(visible) {
  document.getElementById('chat-typing').classList.toggle('hidden', !visible);
  const container = document.getElementById('chat-messages');
  container.scrollTop = container.scrollHeight;
}

function initChat() {
  addMessage('Hola 👋 Soy Nuwe. Puedo contarte cómo está construido este proyecto o responderte preguntas sobre el tiempo en España. ¿En qué te puedo ayudar?', 'bot');

  const suggestionsEl = document.getElementById('chat-suggestions');
  SUGGESTIONS.forEach(s => {
    const btn = document.createElement('button');
    btn.textContent = s;
    btn.className = 'text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded-full transition-colors';
    btn.addEventListener('click', () => {
      document.getElementById('chat-input').value = s;
      sendMessage();
    });
    suggestionsEl.appendChild(btn);
  });
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const btn = document.getElementById('chat-btn');
  const question = input.value.trim();
  if (!question) return;

  addMessage(question, 'user');
  input.value = '';
  btn.disabled = true;
  setTyping(true);

  try {
    const res = await fetch(CHATBOT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pregunta: question, session_id: SESSION_ID }),
    });
    const data = await res.json();
    addMessage(data.respuesta || data.error, 'bot');
  } catch {
    addMessage('Error al conectar con el chatbot.', 'bot');
  } finally {
    setTyping(false);
    btn.disabled = false;
  }
}

document.getElementById('chat-btn').addEventListener('click', sendMessage);
document.getElementById('chat-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendMessage();
});

initChat();
