/**
 * DOC-OS V.61 - CERVEAU DE SYNCHRONISATION RK
 */
const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;

document.addEventListener('DOMContentLoaded', async function() {
    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); 
    }
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', async () => {
        if(confirm("Submit final dossier?")) { await saveReperage(false); await fetch(`${API_URL}/reperages/${currentReperageId}/submit`, {method:'POST'}); location.reload(); }
    });
    initTabs(); initFileUpload(); initChat();
});

async function loadReperage(id) {
    const res = await fetch(`${API_URL}/reperages/${id}`);
    const data = await res.json();
    document.querySelectorAll('input[name], textarea[name]').forEach(i => { if(data[i.name]) i.value = data[i.name]; });
}

async function saveReperage(notif) {
    const data = {};
    document.querySelectorAll('input[name], textarea[name]').forEach(el => { data[el.name] = el.value; });
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
    if (res.ok && notif) alert("✅ Draft Synchronized.");
}

function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    const panel = document.getElementById('chat-panel');
    if (!toggle) return;
    toggle.onclick = () => { panel.classList.toggle('active'); if (panel.classList.contains('active')) loadMessages(); };
    document.getElementById('chat-close-btn').onclick = () => document.getElementById('chat-panel').classList.remove('active');
    document.getElementById('chat-send-btn').onclick = async () => {
        const input = document.getElementById('chat-input');
        if (!input.value) return;
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ auteur_type: 'fixer', auteur_nom: 'Correspondent', contenu: input.value }) });
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
function initFileUpload() { const area = document.getElementById('drop-area'); area.onclick = () => document.getElementById('file-input').click(); document.getElementById('file-input').onchange = async (e) => { for (let file of e.target.files) { const fd = new FormData(); fd.append('file', file); await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd }); } await loadMedias(); }; }
async function loadMedias() { const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`); const ms = await res.json(); document.getElementById('files-list').innerHTML = ms.map(m => `<div class="file-item"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%;height:140px;object-fit:cover;border-radius:10px;"></div>`).join(''); }
