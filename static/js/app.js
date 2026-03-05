/**
 * DOC-OS V.73.5 SUPRÊME - ENGINE RESTORED
 */
const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;
const CONTEXT_TYPE = window.location.pathname.includes('/admin') ? 'production' : 'fixer';

document.addEventListener('DOMContentLoaded', async function() {
    initTabs(); initFileUpload(); initEventListeners();
    if (currentReperageId) {
        await loadReperage();
        initChat();
        await loadMedias();
        setInterval(() => saveReperage(false), 60000); // Auto-save
    }
});

function initEventListeners() {
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());
    document.querySelectorAll('.scouting-field').forEach(el => {
        el.addEventListener('input', () => calculateProgress());
    });
}

function calculateProgress() {
    const fields = document.querySelectorAll('.scouting-field');
    let filled = 0;
    fields.forEach(input => {
        if (input.value && input.value.trim().length > 1) filled++;
    });
    const percent = Math.min(100, Math.round((filled / 100) * 100));
    const bar = document.getElementById('progress-bar');
    if (bar) bar.style.width = percent + '%';
    document.getElementById('progress-percentage').textContent = percent + '%';
    document.getElementById('progress-filled').textContent = filled;
    return percent;
}

async function loadReperage() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`);
        const data = await res.json();
        document.querySelectorAll('.scouting-field').forEach(input => {
            if (data[input.name] !== undefined && data[input.name] !== null) {
                input.value = data[input.name];
            }
        });
        calculateProgress();
    } catch (e) { console.error("Load failed", e); }
}

async function saveReperage(showToast) {
    const payload = { progression_pourcent: calculateProgress() };
    document.querySelectorAll('.scouting-field').forEach(el => {
        payload[el.name] = el.value;
    });
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok && showToast) {
            const t = document.getElementById('toast');
            if (t) { t.style.display = 'block'; setTimeout(() => { t.style.display = 'none'; }, 3000); }
        }
    } catch (e) { console.error("Save error", e); }
}

// ... [Fonctions Chat et FileUpload maintenues de V.70.3] ...
function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    const panel = document.getElementById('chat-panel');
    if (!toggle || !panel) return;
    toggle.onclick = () => { panel.classList.toggle('active'); if (panel.classList.contains('active')) loadMessages(); };
    document.getElementById('chat-close-btn').onclick = () => panel.classList.remove('active');
    document.getElementById('chat-send-btn').onclick = async () => {
        const input = document.getElementById('chat-input');
        if (!input.value.trim()) return;
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ auteur_type: CONTEXT_TYPE, auteur_nom: CONTEXT_TYPE === 'production' ? 'Production' : (window.FIXER_DATA?.prenom || 'Correspondent'), contenu: input.value })
        });
        input.value = ''; loadMessages();
    };
}
async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    const container = document.getElementById('chat-messages');
    if (container) {
        container.innerHTML = msgs.map(m => `<div class="msg-wrapper ${m.auteur_type === 'fixer' ? 'msg-fixer' : 'msg-production'}"><div class="bubble">${m.contenu}</div></div>`).join('');
        container.scrollTop = container.scrollHeight;
    }
}
function initFileUpload() {
    const area = document.getElementById('drop-area');
    const input = document.getElementById('file-input');
    if (!area || !input) return;
    area.onclick = () => input.click();
    input.onchange = async (e) => {
        for (let file of e.target.files) {
            const fd = new FormData(); fd.append('file', file);
            await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd });
        }
        await loadMedias();
    };
}
async function loadMedias() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
    const ms = await res.json();
    const list = document.getElementById('files-list');
    if (list) list.innerHTML = ms.map(m => `<div class="file-item"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:180px;height:180px;object-fit:cover;border-radius:12px;"></div>`).join('');
}
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            btn.classList.add('active'); document.getElementById(btn.dataset.tab).classList.add('active');
        };
    });
}
