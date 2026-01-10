/**
 * DOC-OS V.64 SUPRÊME MISSION CONTROL - SYNC 100 & CHAT
 */
const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;

document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Launching DOC-OS V.64 Supreme - Recovery Mode');

    // 1. LISTENERS PRIORITAIRES (SOUDURE ANTI-BLOCK)
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());
    initTabs(); initChat(); initFileUpload();

    // 2. CHARGEMENT DATA
    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); 
    }

    document.querySelectorAll('input, textarea').forEach(el => el.addEventListener('input', calculateProgress));
});

function calculateProgress() {
    const fields = document.querySelectorAll('input[name], textarea[name]');
    let filled = 0;
    fields.forEach(input => {
        const excluded = ['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'];
        if (!excluded.includes(input.name)) {
            if (input.value && input.value.trim().length > 2) filled++;
        }
    });
    const percent = Math.min(100, filled);
    document.getElementById('progress-bar').style.width = percent + '%';
    document.getElementById('progress-percentage').textContent = percent + '%';
    document.getElementById('progress-filled').textContent = filled;
    return percent;
}

async function loadReperage(id) {
    try {
        const res = await fetch(`${API_URL}/reperages/${id}`);
        const data = await res.json();
        // SOUDURE 1 : MAPPAGE DIRECT NAME <-> COLUMN
        document.querySelectorAll('input[name], textarea[name]').forEach(input => {
            if (data[input.name] !== undefined && data[input.name] !== null) {
                input.value = data[input.name];
            }
        });
        if (data.statut === 'soumis') lockInterface();
        calculateProgress();
    } catch (e) { console.error("Load fail", e); }
}

function lockInterface() {
    document.getElementById('lock-banner').style.display = 'block';
    document.querySelectorAll('input, textarea, button:not(.chat-toggle-btn):not(#chat-close-btn)').forEach(el => el.disabled = true);
}

async function saveReperage(notif) {
    const p = calculateProgress();
    const data = { progression: p };
    document.querySelectorAll('input[name], textarea[name]').forEach(el => data[el.name] = el.value);

    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (res.ok && notif) alert("✅ SUBSTANCE & PROGRESS SYNCHRONIZED (" + p + "%)");
    } catch (e) { alert("❌ Sync Error."); }
}

async function submitToProduction() {
    const required = document.querySelectorAll('[required]');
    let missing = [];
    required.forEach(el => { if(!el.value.trim()) missing.push(el.name); });
    if (missing.length > 0) { alert("⚠️ MISSING FIELDS :\n" + missing.join(", ")); return; }

    if (confirm("SUBMIT FINAL DOSSIER?")) {
        await saveReperage(false);
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}/submit`, { method: 'POST' });
        if (res.ok) { alert("🚀 DOSSIER SUBMITTED."); location.reload(); }
    }
}

function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    const panel = document.getElementById('chat-panel');
    if (!toggle) return;

    toggle.onclick = () => {
        panel.classList.toggle('active');
        if (panel.classList.contains('active')) loadMessages();
    };
    document.getElementById('chat-close-btn').onclick = () => document.getElementById('chat-panel').classList.remove('active');

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
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    const container = document.getElementById('chat-messages');
    container.innerHTML = msgs.map(m => {
        const isFixer = m.auteur_type === 'fixer';
        return `<div class="msg-wrapper ${isFixer ? 'msg-fixer' : 'msg-production'}"><div class="bubble" style="background: ${isFixer ? 'rgba(230,126,34,0.7)' : 'rgba(44,62,80,0.7)'}; backdrop-filter: blur(8px); color: white; padding:12px; border-radius:15px; margin-bottom:5px;">${m.contenu}</div><div style="font-size:0.7rem; font-weight:800; color:#95a5a6;">${m.auteur_nom}</div></div>`;
    }).join('');
    container.scrollTop = 99999;
}

function initTabs() { document.querySelectorAll('.tab-btn').forEach(btn => { btn.onclick = () => { document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active')); btn.classList.add('active'); document.getElementById(btn.dataset.tab).classList.add('active'); }; }); }
function initFileUpload() { const area = document.getElementById('drop-area'); if (!area) return; area.onclick = () => document.getElementById('file-input').click(); document.getElementById('file-input').onchange = async (e) => { for (let file of e.target.files) { const fd = new FormData(); fd.append('file', file); await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd }); } await loadMedias(); }; }
async function loadMedias() { const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`); const ms = await res.json(); document.getElementById('files-list').innerHTML = ms.map(m => `<div class="file-item"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100px;height:140px;object-fit:cover;border-radius:10px;"></div>`).join(''); }