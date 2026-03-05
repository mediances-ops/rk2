/**
 * DOC-OS V.74.2 FINALE - DEFENSIVE ENGINE
 */
const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;
let isLocked = false;

document.addEventListener('DOMContentLoaded', async function() {
    initTabs(); initFileUpload(); initEventListeners();
    if (currentReperageId) {
        await loadReperage();
        initChat();
        await loadMedias();
    }
});

function initEventListeners() {
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());
    document.querySelectorAll('.scouting-field').forEach(el => el.addEventListener('input', calculateProgress));
}

async function loadReperage() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}?t=${new Date().getTime()}`);
        const data = await res.json();
        document.querySelectorAll('.scouting-field').forEach(input => {
            if (data[input.name] !== undefined) input.value = data[input.name];
        });
        if (data.statut !== 'brouillon') lockInterface();
        calculateProgress();
    } catch (e) { console.error("Hydration Error", e); }
}

async function saveReperage(show) {
    if(isLocked) return;
    const payload = { progression_pourcent: calculateProgress() };
    document.querySelectorAll('.scouting-field').forEach(el => { payload[el.name] = el.value; });
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    if (res.ok && show) {
        const t = document.getElementById('toast');
        if(t) { t.style.display = 'block'; setTimeout(() => t.style.display = 'none', 3000); }
    }
}

function calculateProgress() {
    const fields = document.querySelectorAll('.scouting-field');
    let filled = 0;
    fields.forEach(input => { if (input.value && input.value.trim().length > 1) filled++; });
    const percent = Math.min(100, Math.round((filled / 100) * 100));
    const bar = document.getElementById('progress-bar');
    if (bar) bar.style.width = percent + '%';
    const label = document.getElementById('progress-percentage');
    if (label) label.textContent = percent + '%';
    return percent;
}

function lockInterface() {
    isLocked = true;
    const banner = document.getElementById('lock-banner');
    if (banner) banner.style.display = 'block'; // SÉCURITÉ : Check null
    document.querySelectorAll('.scouting-field, .btn').forEach(el => {
        if (!el.id?.includes('chat')) { el.disabled = true; el.style.opacity = '0.6'; }
    });
}

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.getAttribute('data-tab'))?.classList.add('active');
        };
    });
}

// ... [Fonctions Chat, Medias et linkify identiques à V.70.3 mais avec vérification if(el)] ...
function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    if (!toggle) return;
    toggle.onclick = () => { document.getElementById('chat-panel')?.classList.toggle('active'); loadMessages(); };
}
async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    const cont = document.getElementById('chat-messages');
    if(cont) cont.innerHTML = msgs.map(m => `<div class="bubble">${m.contenu}</div>`).join('');
}
function initFileUpload() {
    const area = document.getElementById('drop-area');
    if (!area) return;
    area.onclick = () => document.getElementById('file-input')?.click();
}
async function loadMedias() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
    const ms = await res.json();
    const list = document.getElementById('files-list');
    if(list) list.innerHTML = ms.map(m => `<img src="/uploads/${currentReperageId}/${m.nom_fichier}" width="100">`).join('');
}
