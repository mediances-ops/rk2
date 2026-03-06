/**
 * DOC-OS V.76.11 SUPRÊME - FINAL FUSION
 * PERSISTENCE, CHAT & MEDIA VAULT
 */
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

// --- CHARGEMENT HYBRIDE (CŒUR DU SYSTÈME) ---
async function loadReperage() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}?t=${new Date().getTime()}`);
        const data = await res.json();
        document.querySelectorAll('.scouting-field').forEach(input => {
            const name = input.name;
            let val = data[name]; 
            if (val === undefined || val === null) {
                // Recherche dans les tiroirs (Territory, Festivity, Pairs)
                if (data.territory && data.territory[name] !== undefined) val = data.territory[name];
                else if (data.festivity && data.festivity[name] !== undefined) val = data.festivity[name];
                else {
                    for (let i = 1; i <= 3; i++) {
                        const pair = data[`pair_${i}`];
                        const key = name.replace(`gardien${i}_`, '').replace(`lieu${i}_`, '');
                        if (pair && pair[key] !== undefined) val = pair[key];
                    }
                }
            }
            if (val !== undefined && val !== null) input.value = val;
        });
        if (data.statut === 'soumis' || data.statut === 'validé') lockInterface();
        calculateProgress();
    } catch (e) { console.error("Sync error", e); }
}

// --- SAUVEGARDE & PROGRESSION ---
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
    const fields = document.querySelectorAll('.scouting-field:not([readonly])');
    let filled = Array.from(fields).filter(i => i.value && i.value.trim().length > 1).length;
    const pct = Math.min(100, Math.round((filled / fields.length) * 100));
    const bar = document.getElementById('progress-bar');
    if (bar) bar.style.width = pct + '%';
    document.getElementById('progress-percentage').textContent = pct + '%';
    return pct;
}

// --- CHAT & MEDIA (RESTAURATION INTÉGRALE) ---
function initChat() {
    document.getElementById('chat-toggle-btn').onclick = () => { 
        document.getElementById('chat-panel').classList.toggle('active'); 
        loadMessages(); 
    };
    setInterval(checkNewMessages, 20000);
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    document.getElementById('chat-messages').innerHTML = msgs.map(m => `
        <div class="msg-wrapper ${m.auteur_type === 'fixer' ? 'msg-me' : 'msg-them'}">
            <div class="bubble">${m.contenu}</div>
        </div>`).join('');
    document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;
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
    area.onclick = () => document.getElementById('file-input').click();
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
    document.getElementById('files-list').innerHTML = ms.map(m => `
        <div class="file-item" style="position:relative; width:180px;">
            <img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%; height:180px; object-fit:cover; border-radius:12px;">
            ${!isLocked ? `<button onclick="window.deleteMedia(${m.id})" style="position:absolute; top:10px; right:10px; background:#e74c3c; color:white; border:none; border-radius:50%; width:30px; height:30px; cursor:pointer;">&times;</button>` : ''}
        </div>`).join('');
}

// --- UTILS ---
function initTabs() { document.querySelectorAll('.tab-btn').forEach(b => b.onclick = () => { document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active')); b.classList.add('active'); document.getElementById(b.getAttribute('data-tab')).classList.add('active'); }); }
function showToast(msg) { const t=document.getElementById('toast'); t.textContent=msg; t.style.display='block'; setTimeout(()=>t.style.display='none',3000); }
function initEventListeners() { document.getElementById('btn-save').onclick = () => saveReperage(true); }
