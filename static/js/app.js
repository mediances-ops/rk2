/**
 * DOC-OS V.75.2 SUPRÊME - PERSISTENCE & MEDIA VAULT
 */
const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;
const CONTEXT_TYPE = window.location.pathname.includes('/admin') ? 'production' : 'fixer';
let isLocked = false;

document.addEventListener('DOMContentLoaded', async function() {
    initTabs(); initFileUpload(); initEventListeners();
    if (currentReperageId) { 
        await loadReperage(); initChat(); await loadMedias(); 
        setInterval(() => { if(!isLocked) saveReperage(false); }, 60000); // Auto-save
    }
});

async function loadReperage() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}?t=${new Date().getTime()}`);
        const data = await res.json();
        document.querySelectorAll('.scouting-field').forEach(input => {
            const name = input.name;
            let val = data[name];
            if (data.territory && data.territory[name] !== undefined) val = data.territory[name];
            if (data.festivity && data.festivity[name] !== undefined) val = data.festivity[name];
            for (let i = 1; i <= 3; i++) {
                const pair = data[`pair_${i}`];
                const key = name.replace(`gardien${i}_`, '').replace(`lieu${i}_`, '');
                if (pair && pair[key] !== undefined) val = pair[key];
            }
            if (val !== undefined && val !== null) input.value = val;
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
        cont.innerHTML = msgs.map(m => `<div class="msg-wrapper ${m.auteur_type === 'fixer' ? 'msg-me' : 'msg-them'}"><div class="bubble">${linkify(m.contenu)}</div></div>`).join('');
        cont.scrollTop = cont.scrollHeight;
    }
}

async function checkNewMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    if (msgs.length > 0 && msgs[msgs.length - 1].auteur_type !== CONTEXT_TYPE) {
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
    if (list) {
        list.innerHTML = ms.map(m => {
            const ext = m.nom_fichier.split('.').pop().toUpperCase();
            const isPDF = m.type === 'pdf' || ext === 'PDF';
            const content = isPDF ? `<div onclick="window.open('/uploads/${currentReperageId}/${m.nom_fichier}')" style="width:100%; height:180px; background:#f1f5f9; border-radius:12px; display:flex; align-items:center; justify-content:center; cursor:pointer;"><i data-lucide="file-text" style="width:40px; height:40px;"></i></div>` : `<img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%; height:180px; object-fit:cover; border-radius:12px;">`;
            return `<div class="file-item" style="position:relative; width:180px;">${content}<div style="position:absolute; bottom:10px; left:10px; background:rgba(0,0,0,0.7); color:white; font-size:0.6rem; padding:2px 8px; border-radius:4px;">${ext}</div>${!isLocked ? `<button onclick="window.deleteMedia(${m.id})" style="position:absolute; top:10px; right:10px; background:#e74c3c; color:white; border:none; border-radius:50%; width:30px; height:30px; cursor:pointer;"><i data-lucide="trash-2" style="width:14px"></i></button>` : ''}</div>`;
        }).join('');
        lucide.createIcons();
    }
}

window.deleteMedia = async function(id) { if(confirm("Delete?")) { await fetch(`${API_URL}/medias/${id}`, { method: 'DELETE' }); await loadMedias(); } };
function lockInterface() { isLocked = true; const b = document.getElementById('lock-banner'); if(b) b.style.display='block'; document.querySelectorAll('.scouting-field, .btn').forEach(el => { if(!el.id?.includes('chat')){el.disabled=true; el.style.opacity='0.6';} }); }
function showToast(msg) { const t=document.getElementById('toast'); if(t){t.textContent=msg; t.style.display='block'; setTimeout(()=>t.style.display='none',3000);} }
function linkify(t) { return t.replace(/(\b(https?):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig, (u) => `<a href="${u}" target="_blank" style="color:inherit;text-decoration:underline;">${u}</a>`); }
function initTabs() { document.querySelectorAll('.tab-btn').forEach(b => b.onclick = () => { document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active')); b.classList.add('active'); document.getElementById(b.getAttribute('data-tab'))?.classList.add('active'); }); }
