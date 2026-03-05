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

async function loadReperage() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}?t=${new Date().getTime()}`);
        const data = await res.json();
        
        document.querySelectorAll('.scouting-field').forEach(input => {
            const name = input.name;
            let val = data[name]; // Racine
            if (data.territory && data.territory[name] !== undefined) val = data.territory[name];
            if (data.festivity && data.festivity[name] !== undefined) val = data.festivity[name];
            for (let i = 1; i <= 3; i++) {
                const pair = data[`pair_${i}`];
                if (pair && pair[name.replace(`gardien${i}_`, '').replace(`lieu${i}_`, '')] !== undefined) {
                     val = pair[name.replace(`gardien${i}_`, '').replace(`lieu${i}_`, '')];
                }
            }
            if (val !== undefined && val !== null) input.value = val;
        });
        if (data.statut === 'validé') lockInterface();
        calculateProgress();
    } catch (e) { console.error("Persistence failed", e); }
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

// ... [Fonctions Chat, Medias et linkify identiques à V.75.0] ...
function initChat() {
    const btn = document.getElementById('chat-toggle-btn');
    if(btn) btn.onclick = () => { document.getElementById('chat-panel')?.classList.toggle('active'); loadMessages(); };
}
async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    const cont = document.getElementById('chat-messages');
    if(cont) {
        cont.innerHTML = msgs.map(m => `<div class="msg-wrapper ${m.auteur_type === 'fixer' ? 'msg-fixer' : 'msg-production'}"><div class="bubble">${m.contenu}</div></div>`).join('');
        cont.scrollTop = cont.scrollHeight;
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
    if(list) list.innerHTML = ms.map(m => `<div class="file-item" style="position:relative; width:180px;"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%; height:180px; object-fit:cover; border-radius:12px;"></div>`).join('');
}
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            btn.classList.add('active'); document.getElementById(btn.dataset.tab).classList.add('active');
        };
    });
}
function initEventListeners() {
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());
}
function showToast(msg) { const t = document.getElementById('toast'); if(t) { t.textContent = msg; t.style.display = 'block'; setTimeout(() => t.style.display = 'none', 3000); } }
