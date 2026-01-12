/**
 * DOC-OS V.69.5 SUPRÊME - MEDIA VAULT ENHANCED
 * FEATURES : PHOTO/PDF DISCRIMINATION, FORMAT BADGES, AUTO-SAVE
 */

const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;
const CONTEXT_TYPE = window.location.pathname.includes('/admin') ? 'production' : 'fixer';
let isLocked = false;

document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Launching DOC-OS V.69.5 - Media Vault Specialist');
    initTabs(); initFileUpload(); initEventListeners();
    if (currentReperageId) { 
        await loadReperage(); 
        initChat(); 
        await loadMedias(); 
        setInterval(() => { if(!isLocked) saveReperage(false); }, 60000);
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
    const urlRegex = /(\b(https?|ftp|file):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig;
    return text.replace(urlRegex, function(url) {
        return '<a href="' + url + '" target="_blank" style="color:inherit; text-decoration:underline;">' + url + '</a>';
    });
}

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
    document.querySelectorAll('.scouting-field').forEach(el => {
        el.addEventListener('input', () => calculateProgress());
    });
}

function calculateProgress() {
    const fields = document.querySelectorAll('.scouting-field');
    if (fields.length === 0) return 0;
    let filled = 0;
    fields.forEach(input => { if (input.value && input.value.trim().length > 1) filled++; });
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
            const name = input.name;
            let val = data[name];
            if (data.territory && data.territory[name]) val = data.territory[name];
            if (data.festivity && data.festivity[name]) val = data.festivity[name];
            for (let i = 1; i <= 3; i++) {
                const pair = data[`pair_${i}`];
                const shortName = name.replace(`gardien${i}_`, '').replace(`lieu${i}_`, '');
                if (pair && pair[shortName] !== undefined) val = pair[shortName];
            }
            if (val !== undefined && val !== null) input.value = val;
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

async function submitToProduction() {
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

function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    const panel = document.getElementById('chat-panel');
    if (!toggle || !panel) return;
    toggle.onclick = () => { panel.classList.toggle('active'); if (panel.classList.contains('active')) loadMessages(); };
    document.getElementById('chat-close-btn').onclick = () => panel.classList.remove('active');
    document.getElementById('chat-send-btn').onclick = async () => {
        const input = document.getElementById('chat-input');
        if (!input.value.trim()) return;
        const msg = {
            auteur_type: CONTEXT_TYPE,
            auteur_nom: CONTEXT_TYPE === 'production' ? 'Production' : (window.FIXER_DATA?.prenom || 'Correspondent'),
            contenu: input.value
        };
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(msg)
        });
        input.value = ''; loadMessages();
    };
    setInterval(checkNewMessages, 20000);
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages${CONTEXT_TYPE === 'production' ? '?role=admin' : ''}`);
    const msgs = await res.json();
    const container = document.getElementById('chat-messages');
    if (!container) return;
    let html = ''; let lastDate = null;
    msgs.forEach(m => {
        const d = new Date(m.created_at);
        const ds = d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' });
        if (ds !== lastDate) { html += `<div class="day-separator"><span>${ds}</span></div>`; lastDate = ds; }
        const isMe = m.auteur_type === CONTEXT_TYPE;
        html += `<div class="msg-wrapper ${isMe ? 'msg-me' : 'msg-them'}">
            <div class="msg-meta ${m.auteur_type === 'fixer' ? 'color-fixer' : 'color-production'}">${m.auteur_nom}</div>
            <div class="bubble"><div class="msg-content">${linkify(m.contenu)}</div>
            <div style="font-size:0.6rem; opacity:0.5; margin-top:5px; text-align:right;">${d.toLocaleTimeString('en-GB', {hour:'2-digit', minute:'2-digit'})}</div></div>
        </div>`;
    });
    container.innerHTML = html; container.scrollTop = container.scrollHeight;
}

async function checkNewMessages() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
        const msgs = await res.json();
        if (msgs.length > 0) {
            const last = msgs[msgs.length - 1];
            const panel = document.getElementById('chat-panel');
            if (last.auteur_type !== CONTEXT_TYPE && !panel.classList.contains('active')) {
                document.getElementById('chat-toggle-btn').style.animation = 'pulse 1.5s infinite';
                showToast("YOU RECEIVED A NEW MESSAGE", true);
            }
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
            const isPDF = m.type === 'pdf' || ext === 'PDF';
            
            // TRACABILITÉ : Rendu conditionnel Photo vs PDF
            const mediaContent = isPDF 
                ? `<div onclick="window.open('/uploads/${currentReperageId}/${m.nom_fichier}')" style="width:100%; height:180px; background:#f1f5f9; border-radius:12px; display:flex; flex-direction:column; align-items:center; justify-content:center; cursor:pointer; border:1px solid #e2e8f0;"><i data-lucide="file-text" style="width:40px; height:40px; color:#64748b; margin-bottom:10px;"></i><span style="font-size:0.7rem; font-weight:800; color:#64748b; padding:0 10px; text-align:center;">${m.nom_fichier.substring(17)}</span></div>`
                : `<img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%; height:180px; object-fit:cover; border-radius:12px; border:1px solid #e2e8f0;">`;

            return `
                <div class="file-item" style="position:relative; width:180px;">
                    ${mediaContent}
                    <div style="position:absolute; bottom:10px; left:10px; background:rgba(44,62,80,0.8); color:white; font-size:0.6rem; font-weight:900; padding:2px 8px; border-radius:4px; backdrop-filter:blur(4px);">${ext}</div>
                    ${!isLocked ? `<button onclick="deleteMedia(${m.id})" style="position:absolute; top:10px; right:10px; background:rgba(231,76,60,0.8); color:white; border:none; border-radius:50%; width:30px; height:30px; cursor:pointer; display:flex; align-items:center; justify-content:center; backdrop-filter:blur(5px);"><i data-lucide="trash-2" style="width:16px;"></i></button>` : ''}
                </div>
            `;
        }).join('');
        lucide.createIcons();
    }
}

async function deleteMedia(id) {
    if (!confirm("Permanently delete this file?")) return;
    const res = await fetch(`${API_URL}/medias/${id}`, { method: 'DELETE' });
    if (res.ok) await loadMedias();
}

function lockInterface() {
    isLocked = true;
    document.getElementById('lock-banner').style.display = 'block';
    document.querySelectorAll('input, textarea, button:not(.chat-toggle-btn):not(#chat-close-btn)').forEach(el => {
        el.disabled = true; el.style.opacity = '0.6';
    });
}
