/**
 * DOC-OS V.72.0 SUPRÊME - PERSISTENCE & HYDRATION ENGINE
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
        setInterval(() => saveReperage(false), 60000); 
    }
});

// BUG 5 FIX : Moteur d'hydratation exhaustif
async function loadReperage() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`);
        const data = await res.json();
        
        document.querySelectorAll('.scouting-field').forEach(input => {
            const name = input.name;
            let val = null;

            // 1. Chercher à la racine
            if (data[name] !== undefined) val = data[name];
            // 2. Chercher dans Territory
            if (data.territory && data.territory[name] !== undefined) val = data.territory[name];
            // 3. Chercher dans Festivity
            if (data.festivity && data.festivity[name] !== undefined) val = data.festivity[name];
            // 4. Chercher dans les Paires (Gardien/Lieu)
            for (let i = 1; i <= 3; i++) {
                const pair = data[`pair_${i}`];
                const shortName = name.replace(`gardien${i}_`, '').replace(`lieu${i}_`, '');
                if (pair && pair[shortName] !== undefined) val = pair[shortName];
            }

            if (val !== null && val !== undefined) input.value = val;
        });

        if (data.statut !== 'brouillon') lockInterface();
        calculateProgress();
    } catch (e) { console.error("Persistence error", e); }
}

async function saveReperage(show) {
    const payload = { progression_pourcent: calculateProgress() };
    document.querySelectorAll('.scouting-field').forEach(el => { payload[el.name] = el.value; });
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
        });
        if (res.ok && show) {
            const t = document.getElementById('toast');
            if (t) { t.style.display = 'block'; setTimeout(() => { t.style.display = 'none'; }, 3000); }
        }
    } catch (e) { console.error("Save failed", e); }
}

function calculateProgress() {
    const fields = document.querySelectorAll('.scouting-field');
    let filled = 0;
    fields.forEach(input => { if (input.value && input.value.trim().length > 1) filled++; });
    const percent = Math.min(100, filled);
    document.getElementById('progress-bar').style.width = percent + '%';
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
    setInterval(loadMessages, 20000);
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages${CONTEXT_TYPE === 'production' ? '?role=admin' : ''}`);
    const msgs = await res.json();
    const container = document.getElementById('chat-messages');
    if (container) {
        let html = ''; let lastDate = null;
        msgs.forEach(m => {
            const d = new Date(m.created_at);
            const ds = d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' });
            if (ds !== lastDate) { html += `<div class="day-separator"><span>${ds}</span></div>`; lastDate = ds; }
            const isMe = m.auteur_type === CONTEXT_TYPE;
            html += `<div class="msg-wrapper ${isMe ? 'msg-me' : 'msg-them'}"><div class="msg-meta ${m.auteur_type === 'fixer' ? 'color-fixer' : 'color-production'}">${m.auteur_nom}</div><div class="bubble">${m.contenu}<div style="font-size:0.6rem; opacity:0.5; margin-top:5px; text-align:right;">${d.toLocaleTimeString('en-GB', {hour:'2-digit', minute:'2-digit'})}</div></div></div>`;
        });
        container.innerHTML = html; container.scrollTop = container.scrollHeight;
    }
}

function initTabs() {
    const buttons = document.querySelectorAll('.tab-btn');
    const contents = document.querySelectorAll('.tab-content');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-tab');
            buttons.forEach(b => b.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active'); document.getElementById(target)?.classList.add('active');
        });
    });
}

function initFileUpload() {
    const area = document.getElementById('drop-area');
    const input = document.getElementById('file-input');
    if (area && input) {
        area.onclick = () => input.click();
        input.onchange = async (e) => {
            for (let file of e.target.files) {
                const fd = new FormData(); fd.append('file', file);
                await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd });
            }
            await loadMedias();
        };
    }
}

async function loadMedias() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
    const ms = await res.json();
    const list = document.getElementById('files-list');
    if (list) {
        list.innerHTML = ms.map(m => `<div class="file-item" style="position:relative; width:180px;"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%; height:180px; object-fit:cover; border-radius:12px;"></div>`).join('');
    }
}

function lockInterface() { isLocked = true; document.getElementById('lock-banner').style.display = 'block'; document.querySelectorAll('input, textarea, button:not(.chat-toggle-btn):not(#chat-close-btn)').forEach(el => { el.disabled = true; el.style.opacity = '0.6'; }); }
