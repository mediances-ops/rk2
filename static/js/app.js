/**
 * DOC-OS V.72.1 SUPRÊME - UNIVERSAL SYNC ENGINE
 * ÉTAT : STABLE - ROBUST DATA CAPTURE (FIX SAVE BUG)
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
        // Sauvegarde auto toutes les 60 secondes
        setInterval(() => { if(!window.isLocked) saveReperage(false); }, 60000); 
    }
});

function showToast(msg, isWarning = false) {
    const t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.style.background = isWarning ? 'var(--secondary)' : '#27ae60';
    t.style.display = 'block';
    setTimeout(() => { t.style.display = 'none'; }, 4000);
}

function linkify(text) {
    if(!text) return "";
    const urlRegex = /(\b(https?):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig;
    return text.replace(urlRegex, (url) => `<a href="${url}" target="_blank" style="color:inherit; text-decoration:underline;">${url}</a>`);
}

function initEventListeners() {
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());
    // On écoute tous les inputs pour la progression
    document.querySelectorAll('input[name], textarea[name]').forEach(el => {
        el.addEventListener('input', () => calculateProgress());
    });
}

// SOUDURE V.72.1 : Capture universelle par attribut "name"
async function saveReperage(show) {
    if(window.isLocked) return;
    
    const payload = { progression_pourcent: calculateProgress() };
    
    // TRACABILITÉ : On prend TOUS les champs qui ont un nom, sans exception de classe
    const fields = document.querySelectorAll('input[name], textarea[name], select[name]');
    fields.forEach(el => {
        payload[el.name] = el.value;
    });

    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (res.ok && show) showToast("YOUR FORM HAS BEEN SAVED");
        if (res.status === 403) lockInterface();
    } catch (e) { 
        console.error("Critical Sync Error", e);
        if(show) alert("Connection lost. Data not saved.");
    }
}

async function loadReperage() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`);
        const data = await res.json();
        
        // Hydratation profonde (déballage des réservoirs)
        document.querySelectorAll('input[name], textarea[name], select[name]').forEach(input => {
            const name = input.name;
            let val = data[name];
            
            if (data.territory && data.territory[name] !== undefined) val = data.territory[name];
            if (data.festivity && data.festivity[name] !== undefined) val = data.festivity[name];
            
            for (let i = 1; i <= 3; i++) {
                const pair = data[`pair_${i}`];
                const shortName = name.replace(`gardien${i}_`, '').replace(`lieu${i}_`, '');
                if (pair && pair[shortName] !== undefined) val = pair[shortName];
            }

            if (val !== null && val !== undefined) input.value = val;
        });

        if (data.statut !== 'brouillon') lockInterface();
        calculateProgress();
    } catch (e) { console.error("Persistence failed to load", e); }
}

function calculateProgress() {
    // Calcul basé sur les champs métier (contenant la classe scouting-field ou simplement présents)
    const fields = document.querySelectorAll('input[name], textarea[name]');
    let filled = 0;
    fields.forEach(input => {
        if (input.value && input.value.trim().length > 1 && !input.readOnly) filled++;
    });
    const percent = Math.min(100, filled); // Capé à 100
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
    setInterval(() => { if(panel.classList.contains('active')) loadMessages(); }, 15000);
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
            html += `<div class="msg-wrapper ${isMe ? 'msg-me' : 'msg-them'}"><div class="msg-meta ${m.auteur_type === 'fixer' ? 'color-fixer' : 'color-production'}">${m.auteur_nom}</div><div class="bubble">${linkify(m.contenu)}<div style="font-size:0.6rem; opacity:0.5; margin-top:5px; text-align:right;">${d.toLocaleTimeString('en-GB', {hour:'2-digit', minute:'2-digit'})}</div></div></div>`;
        });
        container.innerHTML = html; container.scrollTop = container.scrollHeight;
    }
}

function lockInterface() { 
    window.isLocked = true; 
    document.getElementById('lock-banner').style.display = 'block'; 
    document.querySelectorAll('input, textarea, button:not(.chat-toggle-btn):not(#chat-close-btn)').forEach(el => { el.disabled = true; el.style.opacity = '0.6'; }); 
}

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            btn.classList.add('active'); document.getElementById(btn.dataset.tab).classList.add('active');
        };
    });
}

function initFileUpload() {
    const area = document.getElementById('drop-area');
    const input = document.getElementById('file-input');
    if (area && input) {
        area.onclick = () => { if(!window.isLocked) input.click(); };
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
        list.innerHTML = ms.map(m => {
            const ext = m.nom_fichier.split('.').pop().toUpperCase();
            const isPDF = (m.type === 'pdf' || ext === 'PDF');
            const mediaContent = isPDF 
                ? `<div onclick="window.open('/uploads/${currentReperageId}/${m.nom_fichier}')" style="width:100%; height:180px; background:#f1f5f9; border-radius:12px; display:flex; flex-direction:column; align-items:center; justify-content:center; cursor:pointer;"><i data-lucide="file-text" style="width:40px; height:40px; color:#64748b;"></i></div>`
                : `<img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%; height:180px; object-fit:cover; border-radius:12px;">`;
            return `<div class="file-item" style="position:relative; width:180px;">${mediaContent}<div style="position:absolute; bottom:10px; left:10px; background:rgba(44,62,80,0.8); color:white; font-size:0.6rem; font-weight:900; padding:2px 8px; border-radius:4px;">${ext}</div><button onclick="window.deleteMedia(${m.id})" style="position:absolute; top:10px; right:10px; background:rgba(231,76,60,0.8); color:white; border:none; border-radius:50%; width:30px; height:30px; cursor:pointer; display:flex; align-items:center; justify-content:center;"><i data-lucide="trash-2" style="width:16px;"></i></button></div>`;
        }).join('');
        lucide.createIcons();
    }
}
