const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;
const CONTEXT_TYPE = window.location.pathname.includes('/admin') ? 'production' : 'fixer';
let isLocked = false;

document.addEventListener('DOMContentLoaded', async function() {
    initTabs(); initFileUpload(); initEventListeners();
    if (currentReperageId) { 
        await loadReperage(); initChat(); await loadMedias(); 
        setInterval(() => { if(!isLocked) saveReperage(false); }, 60000); 
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
        if (data.statut === 'validé') lockInterface();
        calculateProgress();
    } catch (e) { console.error("Load failed", e); }
}

async function saveReperage(show) {
    if(isLocked) return;
    const payload = { progression_pourcent: calculateProgress() };
    document.querySelectorAll('.scouting-field').forEach(el => { payload[el.name] = el.value; });
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    if (res.ok && show) showToast("YOUR FORM HAS BEEN SAVED");
}

function calculateProgress() {
    const fields = document.querySelectorAll('.scouting-field');
    if (fields.length === 0) return 0;
    let filled = 0;
    fields.forEach(input => { if (input.value && input.value.trim().length > 1) filled++; });
    const percent = Math.min(100, Math.round((filled / 100) * 100));
    const bar = document.getElementById('progress-bar'); if (bar) bar.style.width = percent + '%';
    const label = document.getElementById('progress-percentage'); if (label) label.textContent = percent + '%';
    return percent;
}

function initChat() {
    const btn = document.getElementById('chat-toggle-btn');
    if(btn) btn.onclick = () => { document.getElementById('chat-panel')?.classList.toggle('active'); loadMessages(); };
    setInterval(checkNewMessages, 20000);
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    const cont = document.getElementById('chat-messages');
    if(cont) {
        cont.innerHTML = msgs.map(m => `<div class="msg-wrapper ${m.auteur_type === 'fixer' ? 'msg-fixer' : 'msg-production'}"><div class="bubble">${linkify(m.contenu)}</div></div>`).join('');
        cont.scrollTop = cont.scrollHeight;
    }
}

async function checkNewMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    const last = msgs[msgs.length - 1];
    if (last && last.auteur_type !== CONTEXT_TYPE) {
        document.getElementById('chat-toggle-btn').style.animation = 'pulse 1.5s infinite';
    }
}

function initFileUpload() {
    const area = document.getElementById('drop-area'); if (!area) return;
    area.onclick = () => document.getElementById('file-input')?.click();
    document.getElementById('file-input').onchange = async (e) => {
        for (let f of e.target.files) {
            const fd = new FormData(); fd.append('file', f);
            await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd });
        }
        await loadMedias();
    };
}

async function loadMedias() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
    const ms = await res.json();
    const list = document.getElementById('files-list');
    if(list) list.innerHTML = ms.map(m => `<div class="file-item" style="position:relative; width:180px;"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%; height:180px; object-fit:cover; border-radius:12px;">${!isLocked ? `<button onclick="window.deleteMedia(${m.id})" style="position:absolute; top:10px; right:10px; background:rgba(231,76,60,0.8); color:white; border:none; border-radius:50%; width:30px; height:30px; cursor:pointer;"><i data-lucide="trash-2"></i></button>` : ''}</div>`).join('');
    lucide.createIcons();
}

window.deleteMedia = async function(id) { if(confirm("Delete?")) { await fetch(`${API_URL}/medias/${id}`, { method: 'DELETE' }); await loadMedias(); } };
function lockInterface() { isLocked = true; document.getElementById('lock-banner').style.display = 'block'; document.querySelectorAll('.scouting-field, .btn').forEach(el => { el.disabled = true; el.style.opacity = '0.6'; }); }
function showToast(msg) { const t = document.getElementById('toast'); if(t) { t.textContent = msg; t.style.display = 'block'; setTimeout(() => t.style.display = 'none', 3000); } }
function linkify(t) { return t.replace(/(\b(https?):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig, (u) => `<a href="${u}" target="_blank" style="color:inherit;text-decoration:underline;">${u}</a>`); }
