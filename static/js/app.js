/**
 * DOC-OS V.74.3 SUPRÊME - DEFENSIVE NESTED ENGINE
 */
const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;
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
        
        // SOUDURE V.74.3 : Unpacking intelligent des réservoirs
        document.querySelectorAll('.scouting-field').forEach(input => {
            const name = input.name;
            let val = data[name]; // Racine
            if (data.territory && data.territory[name]) val = data.territory[name];
            if (data.festivity && data.festivity[name]) val = data.festivity[name];
            for (let i = 1; i <= 3; i++) {
                const pair = data[`pair_${i}`];
                if (pair && pair[name]) val = pair[name];
            }
            if (val !== undefined && val !== null) input.value = val;
        });
        if (data.statut !== 'brouillon' && data.statut !== 'soumis') lockInterface();
        calculateProgress();
    } catch (e) { console.error("Persistence failed", e); }
}

async function saveReperage(show) {
    if(isLocked) return;
    const payload = { progression_pourcent: calculateProgress() };
    document.querySelectorAll('.scouting-field').forEach(el => { payload[el.name] = el.value; });
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
        });
        if (res.ok && show) {
            const t = document.getElementById('toast');
            if(t) { t.style.display = 'block'; setTimeout(() => t.style.display = 'none', 3000); }
        }
    } catch(e) {}
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
    if (banner) banner.style.display = 'block';
    document.querySelectorAll('.scouting-field, .btn').forEach(el => {
        if (!el.id?.includes('chat')) { el.disabled = true; el.style.opacity = '0.6'; }
    });
}

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            btn.classList.add('active');
            const target = btn.getAttribute('data-tab');
            const el = document.getElementById(target);
            if(el) el.classList.add('active');
        };
    });
}

function initFileUpload() {
    const area = document.getElementById('drop-area');
    if (!area) return;
    area.onclick = () => document.getElementById('file-input')?.click();
    document.getElementById('file-input').onchange = async (e) => {
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
    if(list) {
        list.innerHTML = ms.map(m => `<img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:180px; height:180px; object-fit:cover; border-radius:12px; border:1px solid #eee; margin:10px;">`).join('');
    }
}

function initChat() {
    const btn = document.getElementById('chat-toggle-btn');
    if(btn) btn.onclick = () => document.getElementById('chat-panel')?.classList.toggle('active');
}

function initEventListeners() {
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());
}
