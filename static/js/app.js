/**
 * DOC-OS V.56 SUPRÊME RADICAL - SYNC 100 & GPS & LOCK
 */
const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;

document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 DOC-OS V.56 Radical Launch');

    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); 
    }

    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());

    initTabs();
    initFileUpload();
    initChat();
    
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
            total = 100; // Force denominator to 100
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
        document.querySelectorAll('input[name], textarea[name]').forEach(input => {
            if (data[input.name] !== undefined) input.value = data[input.name];
        });
        if (data.statut === 'soumis') lockInterface();
        calculateProgress();
    } catch (e) { console.error(e); }
}

function lockInterface() {
    document.getElementById('lock-banner').style.display = 'block';
    document.querySelectorAll('input, textarea, button:not(.chat-toggle-btn):not(#chat-close-btn)').forEach(el => el.disabled = true);
    document.body.style.cursor = 'not-allowed';
}

async function submitToProduction() {
    // REQUIRED FIELDS VALIDATION (40 FIELDS)
    const required = document.querySelectorAll('[required]');
    let missing = [];
    required.forEach(el => { if(!el.value.trim()) missing.push(el.previousElementSibling.textContent); });
    
    if (missing.length > 0) {
        alert("⚠️ MISSING SUBSTANCE :\n" + missing.join("\n"));
        return;
    }

    if (confirm("SUBMIT FINAL DOSSIER? Data will be locked.")) {
        await saveReperage(false);
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}/submit`, { method: 'POST' });
        if (res.ok) {
            alert("🚀 DOSSIER SUBMITTED TO PRODUCTION");
            location.reload();
        }
    }
}

async function saveReperage(notif) {
    const p = calculateProgress();
    const data = { progression: p };
    document.querySelectorAll('input[name], textarea[name]').forEach(el => { data[el.name] = el.value; });

    const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (res.ok && notif) alert("✅ SUBSTANCE & PROGRESS SAVED (" + p + "%)");
}

function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    if (!toggle) return;
    toggle.onclick = () => { document.getElementById('chat-panel').classList.add('active'); loadMessages(); };
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
    document.getElementById('chat-messages').innerHTML = msgs.map(m => {
        const isFixer = m.auteur_type === 'fixer';
        return `<div class="msg-wrapper ${isFixer ? 'msg-fixer' : 'msg-production'}">
            <div class="bubble" style="background: ${isFixer ? 'rgba(230,126,34,0.7)' : 'rgba(44,62,80,0.7)'}; backdrop-filter: blur(8px); color: white;">${m.contenu}</div>
            <div class="msg-meta">${isFixer ? 'Local Correspondent' : 'Production Team'}</div>
        </div>`;
    }).join('');
    document.getElementById('chat-messages').scrollTop = 99999;
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
    document.getElementById('files-list').innerHTML = ms.map(m => `<div class="file-item"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100px;height:140px;object-fit:cover;border-radius:10px;"></div>`).join('');
}
