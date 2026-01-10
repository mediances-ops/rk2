/**
 * DOC-OS V.52 SUPRÊME RADICAL - NO JSON RESERVOIRS / NO i18n
 */
const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;

document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Launching DOC-OS V.52 Radical');

    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); 
    }

    // Handlers
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', async () => {
        await saveReperage(false);
        await fetch(`${API_URL}/reperages/${currentReperageId}/submit`, { method: 'POST' });
        alert("🚀 Dossier Submitted to Production!");
    });

    initTabs();
    initFileUpload();
    initChat();
    
    // Live Progress
    document.querySelectorAll('input, textarea').forEach(el => {
        el.addEventListener('input', calculateProgress);
    });
});

function calculateProgress() {
    const fields = document.querySelectorAll('input[name], textarea[name]');
    let total = 0; let filled = 0;
    fields.forEach(input => {
        const excluded = ['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'];
        if (!excluded.includes(input.name)) {
            total++;
            if (input.value && input.value.trim().length > 2) filled++;
        }
    });
    const percent = total > 0 ? Math.round((filled / total) * 100) : 0;
    document.getElementById('progress-bar').style.width = percent + '%';
    document.getElementById('progress-percentage').textContent = percent + '%';
    document.getElementById('progress-filled').textContent = filled;
    return percent;
}

async function loadReperage(id) {
    const res = await fetch(`${API_URL}/reperages/${id}`);
    const data = await res.json();
    // Fill all inputs by name (Direct mapping)
    document.querySelectorAll('input[name], textarea[name]').forEach(input => {
        if (data[input.name]) input.value = data[input.name];
    });
    calculateProgress();
}

async function saveReperage(notif) {
    const p = calculateProgress();
    // Collect all named fields into a flat object
    const data = { progression: p };
    document.querySelectorAll('input[name], textarea[name]').forEach(el => {
        data[el.name] = el.value;
    });

    const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (res.ok && notif) alert("💾 Progress Synchronized (" + p + "%)");
}

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
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
        loadMedias();
    };
}

async function loadMedias() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
    const ms = await res.json();
    document.getElementById('files-list').innerHTML = ms.map(m => `<div class="file-item"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100px;height:100px;object-fit:cover;border-radius:10px;"></div>`).join('');
}

function initChat() {
    document.getElementById('chat-toggle-btn').onclick = () => { document.getElementById('chat-panel').classList.add('active'); loadMessages(); };
    document.getElementById('chat-close-btn').onclick = () => document.getElementById('chat-panel').classList.remove('active');
    document.getElementById('chat-send-btn').onclick = async () => {
        const input = document.getElementById('chat-input');
        if (!input.value) return;
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ auteur_type: 'fixer', auteur_nom: 'Fixer', contenu: input.value })
        });
        input.value = ''; loadMessages();
    };
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    document.getElementById('chat-messages').innerHTML = msgs.map(m => `<div class="msg-wrapper ${m.auteur_type === 'fixer' ? 'msg-fixer' : 'msg-production'}"><div class="bubble">${m.contenu}</div></div>`).join('');
}
