/**
 * DOC-OS VERSION : V.73.6 SUPRÊME MISSION CONTROL
 * ÉTAT : STABLE - CACHE-BUSTING ACTIVATED
 */

const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;
const CONTEXT_TYPE = window.location.pathname.includes('/admin') ? 'production' : 'fixer';
let isLocked = false;

document.addEventListener('DOMContentLoaded', async function() {
    initTabs(); initFileUpload(); initEventListeners();
    if (currentReperageId) { 
        await loadReperage(); 
        initChat(); 
        await loadMedias(); 
        setInterval(() => { if(!isLocked) saveReperage(false); }, 60000);
    }
});

async function loadReperage() {
    try {
        // SOUDURE V.73.6 : Ajout d'un timestamp unique pour forcer la lecture serveur (Anti-Cache)
        const timestamp = new Date().getTime();
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}?t=${timestamp}`, {
            method: 'GET',
            headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }
        });
        const data = await res.json();
        
        document.querySelectorAll('.scouting-field').forEach(input => {
            const name = input.name;
            if (data[name] !== undefined && data[name] !== null) {
                input.value = data[name];
            }
        });
        if (data.statut !== 'brouillon') lockInterface();
        calculateProgress();
    } catch (e) { console.error("Load failed", e); }
}

async function saveReperage(show) {
    if(isLocked) return;
    const payload = { progression_pourcent: calculateProgress() };
    document.querySelectorAll('.scouting-field').forEach(el => { payload[el.name] = el.value; });
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok && show) showToast("YOUR FORM HAS BEEN SAVED");
    } catch (e) { console.error("Save failed", e); }
}

// --- LOGIQUE CHAT, TABS ET MEDIAS (MAINTENUE INTÉGRALEMENT) ---
function initTabs() {
    const buttons = document.querySelectorAll('.tab-btn');
    const contents = document.querySelectorAll('.tab-content');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-tab');
            buttons.forEach(b => b.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(target)?.classList.add('active');
        });
    });
}
function initEventListeners() {
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());
    document.querySelectorAll('.scouting-field').forEach(el => { el.addEventListener('input', () => calculateProgress()); });
}
function calculateProgress() {
    const fields = document.querySelectorAll('.scouting-field');
    let filled = 0;
    fields.forEach(input => { if (input.value && input.value.trim().length > 1) filled++; });
    const percent = Math.min(100, Math.round((filled / 100) * 100));
    const bar = document.getElementById('progress-bar');
    if (bar) bar.style.width = percent + '%';
    document.getElementById('progress-percentage').textContent = percent + '%';
    document.getElementById('progress-filled').textContent = filled;
    return percent;
}
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
    setInterval(checkNewMessages, 20000);
}
async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    const container = document.getElementById('chat-messages');
    if (!container) return;
    let html = ''; let lastDate = null;
    msgs.forEach(m => {
        const d = new Date(m.created_at);
        const ds = d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' });
        if (ds !== lastDate) { html += `<div class="day-separator"><span>${ds}</span></div>`; lastDate = ds; }
        const isMe = m.auteur_type === CONTEXT_TYPE;
        html += `<div class="msg-wrapper ${isMe ? 'msg-me' : 'msg-them'}"><div class="msg-meta ${m.auteur_type === 'fixer' ? 'color-fixer' : 'color-production'}">${m.auteur_nom}</div><div class="bubble"><div class="msg-content">${linkify(m.contenu)}</div><div style="font-size:0.6rem; opacity:0.5; margin-top:5px; text-align:right;">${d.toLocaleTimeString('en-GB', {hour:'2-digit', minute:'2-digit'})}</div></div></div>`;
    });
    container.innerHTML = html; container.scrollTop = container.scrollHeight;
}
async function checkNewMessages() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
        const msgs = await res.json();
        const panel = document.getElementById('chat-panel');
        if (msgs.length > 0) {
            const last = msgs[msgs.length - 1];
            if (panel.classList.contains('active')) { loadMessages(); }
            else if (last.auteur_type !== CONTEXT_TYPE) { document.getElementById('chat-toggle-btn').style.animation = 'pulse 1.5s infinite'; showToast("YOU RECEIVED A NEW MESSAGE", true); }
        }
    } catch(e) {}
}
function initFileUpload() {
    const area = document.getElementById('drop-area');
    const input = document.getElementById('file-input');
    if (!area || !input) return;
    area.onclick = () => { if(!isLocked) input.click(); };
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
    if (list) {
        list.innerHTML = ms.map(m => {
            const ext = m.nom_fichier.split('.').pop().toUpperCase();
            const mediaContent = (m.type === 'pdf' || ext === 'PDF') 
                ? `<div onclick="window.open('/uploads/${currentReperageId}/${m.nom_fichier}')" style="width:100%; height:180px; background:#f1f5f9; border-radius:12px; display:flex; flex-direction:column; align-items:center; justify-content:center; cursor:pointer;"><i data-lucide="file-text" style="width:40px; height:40px; color:#64748b;"></i></div>`
                : `<img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%; height:180px; object-fit:cover; border-radius:12px;">`;
            return `<div class="file-item" style="position:relative; width:180px;">${mediaContent}<div style="position:absolute; bottom:10px; left:10px; background:rgba(44,62,80,0.8); color:white; font-size:0.6rem; font-weight:900; padding:2px 8px; border-radius:4px;">${ext}</div>${!isLocked ? `<button onclick="window.deleteMedia(${m.id})" style="position:absolute; top:10px; right:10px; background:rgba(231,76,60,0.8); color:white; border:none; border-radius:50%; width:30px; height:30px; cursor:pointer; display:flex; align-items:center; justify-content:center; backdrop-filter:blur(5px);"><i data-lucide="trash-2" style="width:16px;"></i></button>` : ''}</div>`;
        }).join('');
        lucide.createIcons();
    }
}
async function submitToProduction() {
    if (isLocked) return;
    const required = document.querySelectorAll('input[required], textarea[required]');
    let missing = [];
    required.forEach(el => { if(!el.value.trim()) missing.push(el.name); });
    if (missing.length > 0) { alert("⚠️ MISSING REQUIRED FIELDS."); return; }
    if (confirm("🚀 SUBMIT FINAL DOSSIER?")) {
        await saveReperage(false);
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}/submit`, { method: 'POST' });
        if (res.ok) location.reload();
    }
}
function lockInterface() { isLocked = true; document.getElementById('lock-banner').style.display = 'block'; document.querySelectorAll('input, textarea, button:not(.chat-toggle-btn):not(#chat-close-btn)').forEach(el => { el.disabled = true; el.style.opacity = '0.6'; }); }
function showToast(msg, isWarning = false) { const t = document.getElementById('toast'); if (!t) return; t.textContent = msg; t.style.background = isWarning ? 'var(--secondary)' : '#27ae60'; t.style.display = 'block'; setTimeout(() => { t.style.display = 'none'; }, 4000); }
function linkify(text) { const urlRegex = /(\b(https?):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig; return text.replace(urlRegex, (url) => `<a href="${url}" target="_blank" style="color:inherit; text-decoration:underline;">${url}</a>`); }
window.deleteMedia = async function(id) { if (!confirm("Delete file?")) return; const res = await fetch(`${API_URL}/medias/${id}`, { method: 'DELETE' }); if (res.ok) await loadMedias(); };
