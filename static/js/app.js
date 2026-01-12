/**
 * DOC-OS V.67.1 SUPRÊME - ENGINE & PERSISTENCE
 * TRIPLE TRACEABILITY : NESTED DATA HYDRATION
 */

const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;
let isLocked = false;

document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Launching DOC-OS V.67.1 - 100 Fields Persistence Mode');
    initEventListeners();
    initTabs();
    initFileUpload();
    if (currentReperageId) {
        await loadReperage();
        initChat();
        await loadMedias();
    }
});

function initEventListeners() {
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());
    document.querySelectorAll('input, textarea').forEach(el => {
        el.addEventListener('input', () => { if (!isLocked) calculateProgress(); });
    });
}

function calculateProgress() {
    const fields = document.querySelectorAll('.tab-content input[name], .tab-content textarea[name]');
    let filled = 0;
    fields.forEach(input => { if (input.value && input.value.trim().length > 1) filled++; });
    const percent = Math.min(100, filled);
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
        
        // TRACABILITÉ : Hydratation depuis les réservoirs
        document.querySelectorAll('input[name], textarea[name]').forEach(input => {
            const name = input.name;
            let val = data[name]; // Racine
            if (data.territory && data.territory[name]) val = data.territory[name];
            if (data.festivity && data.festivity[name]) val = data.festivity[name];
            for (let i = 1; i <= 3; i++) {
                const pair = data[`pair_${i}`];
                const shortName = name.replace(`gardien${i}_`, '').replace(`lieu${i}_`, '');
                if (pair && pair[shortName]) val = pair[shortName];
            }
            if (val) input.value = val;
        });

        if (data.statut !== 'brouillon') lockInterface();
        calculateProgress();
    } catch (e) { console.error("Hydration failed", e); }
}

async function saveReperage(showToast) {
    if (isLocked) return;
    const payload = { progression_pourcent: calculateProgress() };
    document.querySelectorAll('input[name], textarea[name]').forEach(el => { payload[el.name] = el.value; });

    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok && showToast) {
            const t = document.getElementById('toast');
            t.style.display = 'block';
            setTimeout(() => { t.style.display = 'none'; }, 3000);
        }
    } catch (e) { console.error("Save failed", e); }
}

async function submitToProduction() {
    if (isLocked) return;
    // TRACABILITÉ : Vérification des astérisques
    const required = document.querySelectorAll('input[required], textarea[required]');
    let missing = [];
    required.forEach(el => { if(!el.value.trim()) missing.push(el.name); });

    if (missing.length > 0) {
        alert("⚠️ AT LEAST THESE FIELDS ARE REQUIRED FOR SUBMISSION.");
        return;
    }

    if (confirm("🚀 SUBMIT TO PRODUCTION? (Locked after)")) {
        await saveReperage(false);
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}/submit`, { method: 'POST' });
        if (res.ok) location.reload();
    }
}

function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    const panel = document.getElementById('chat-panel');
    if (!toggle) return;
    toggle.onclick = () => { panel.classList.toggle('active'); if (panel.classList.contains('active')) loadMessages(); };
    document.getElementById('chat-close-btn').onclick = () => panel.classList.remove('active');
    document.getElementById('chat-send-btn').onclick = async () => {
        const input = document.getElementById('chat-input');
        if (!input.value.trim()) return;
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ auteur_type: 'fixer', auteur_nom: 'Correspondent', contenu: input.value })
        });
        input.value = ''; loadMessages();
    };
    setInterval(async () => {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
        const msgs = await res.json();
        if (msgs.length > 0 && msgs[msgs.length-1].auteur_type === 'production' && !panel.classList.contains('active')) {
            toggle.style.animation = 'pulse 1s infinite';
        }
    }, 30000);
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    const cont = document.getElementById('chat-messages');
    if (cont) {
        cont.innerHTML = msgs.map(m => `<div class="msg-wrapper ${m.auteur_type === 'fixer' ? 'msg-fixer' : 'msg-production'}"><div class="bubble">${m.contenu}</div></div>`).join('');
        cont.scrollTop = cont.scrollHeight;
    }
}

function lockInterface() {
    isLocked = true;
    document.getElementById('lock-banner').style.display = 'block';
    document.querySelectorAll('input, textarea, button:not(.chat-toggle-btn):not(#chat-close-btn)').forEach(el => {
        el.disabled = true; el.style.opacity = '0.6';
    });
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
    if (!area) return;
    area.onclick = () => document.getElementById('file-input').click();
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
    if (list) list.innerHTML = ms.map(m => `<div class="file-item"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:150px;height:150px;object-fit:cover;border-radius:10px;"></div>`).join('');
}
