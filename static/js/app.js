const API_URL = '/api';
let currentLanguage = localStorage.getItem('selectedLanguage') || 'FR';
let currentReperageId = window.REPERAGE_ID || null;
let translations = {};

document.addEventListener('DOMContentLoaded', async function() {
    if (window.FIXER_DATA) {
        currentLanguage = window.FIXER_DATA.langue_default || 'FR';
        currentReperageId = window.FIXER_DATA.reperage_id;
    }
    await loadTranslations(currentLanguage);
    initLanguageSelector();
    initTabs();
    initFileUpload();
    initChat();
    initForms();
    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); 
    }
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
});

async function loadTranslations(lang) {
    try {
        const res = await fetch(`${API_URL}/i18n/${lang}`);
        translations = await res.json();
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const keys = el.getAttribute('data-i18n').split('.');
            let val = translations;
            keys.forEach(k => { val = val ? val[k] : null; });
            if (val) el.textContent = val;
        });
        currentLanguage = lang;
    } catch (e) { console.error("i18n error", e); }
}

function initLanguageSelector() {
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadTranslations(btn.dataset.lang);
        };
    });
}

function calculateProgress() {
    const fields = document.querySelectorAll('input[name], textarea[name]');
    let total = 0; let filled = 0;
    fields.forEach(input => {
        if (!['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'].includes(input.name)) {
            total++;
            if (input.value && input.value.trim().length > 2) filled++;
        }
    });
    const percent = total > 0 ? Math.round((filled / total) * 100) : 0;
    document.getElementById('progress-bar').style.width = percent + '%';
    document.getElementById('progress-percentage').textContent = percent + '%';
    document.getElementById('progress-filled').textContent = filled;
    document.getElementById('progress-total').textContent = total;
    return percent;
}

async function loadReperage(id) {
    const res = await fetch(`${API_URL}/reperages/${id}`);
    const data = await res.json();
    document.querySelectorAll('input[name], textarea[name]').forEach(input => {
        const n = input.name;
        if (data[n]) input.value = data[n];
        else if (data.territoire_data && data.territoire_data[n]) input.value = data.territoire_data[n];
        else if (data.episode_data && data.episode_data[n]) input.value = data.episode_data[n];
    });
    if (data.gardiens) {
        data.gardiens.forEach(g => {
            Object.keys(g).forEach(k => {
                const el = document.querySelector(`[name="gardien${g.ordre}_${k}"]`);
                if (el) el.value = g[k];
            });
        });
    }
    if (data.lieux) {
        data.lieux.forEach(l => {
            Object.keys(l).forEach(k => {
                const el = document.querySelector(`[name="lieu${l.numero_lieu}_${k}"]`);
                if (el) el.value = l[k];
            });
        });
    }
    setTimeout(calculateProgress, 1000);
}

async function saveReperage(notif) {
    const p = calculateProgress();
    const data = { progression: p, territoire_data: {}, episode_data: {}, gardiens: [], lieux: [] };
    const epKeys = ['angle', 'fete', 'arc', 'moments', 'contraintes', 'sensibles', 'autorisations', 'budget', 'notes'];

    for (let i = 1; i <= 3; i++) {
        let g = { ordre: i };
        ['nom', 'prenom', 'age', 'genre', 'fonction', 'savoir', 'histoire', 'evaluation', 'langues', 'adresse', 'telephone', 'email', 'contact'].forEach(k => {
            g[k] = document.querySelector(`[name="gardien${i}_${k}"]`)?.value;
        });
        if (g.nom) data.gardiens.push(g);
        let l = { numero_lieu: i };
        ['nom', 'type', 'description', 'cinegenie', 'axes', 'points_vue', 'moments', 'ambiance', 'adequation', 'accessibilite', 'securite', 'electricite', 'espace', 'protection', 'permis'].forEach(k => {
            l[k] = document.querySelector(`[name="lieu${i}_${k}"]`)?.value;
        });
        if (l.nom) data.lieux.push(l);
    }

    document.querySelectorAll('input[name], textarea[name]').forEach(el => {
        if (['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'].includes(el.name)) data[el.name] = el.value;
        else if (epKeys.includes(el.name)) data.episode_data[el.name] = el.value;
        else if (!el.name.startsWith('gardien') && !el.name.startsWith('lieu')) data.territoire_data[el.name] = el.value;
    });

    const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (res.ok && notif) alert("✅ Synchronisé (" + p + "%)");
}

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
        };
    });
    document.querySelectorAll('.lieu-tab').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.lieu-tab, .lieu-content').forEach(el => el.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`lieu-${btn.dataset.lieu}`).classList.add('active');
        };
    });
}

async function loadMedias() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
    const ms = await res.json();
    document.getElementById('files-list').innerHTML = ms.map(m => `
        <div class="file-item"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%; height:120px; object-fit:cover; border-radius:8px;"></div>
    `).join('');
}

function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    if (!toggle) return;
    toggle.onclick = () => { document.getElementById('chat-panel').style.right = '0'; loadMessages(); };
    document.getElementById('chat-close-btn').onclick = () => document.getElementById('chat-panel').style.right = '-400px';
    document.getElementById('chat-send-btn').onclick = async () => {
        const input = document.getElementById('chat-input');
        if (!input.value) return;
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ auteur_type: 'fixer', auteur_nom: 'Correspondant', contenu: input.value }) });
        input.value = ''; loadMessages();
    };
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    document.getElementById('chat-messages').innerHTML = msgs.map(m => `
        <div class="chat-message ${m.auteur_type}"><div class="chat-message-header"><strong>${m.auteur_nom}</strong></div><div class="chat-message-bubble">${m.contenu}</div></div>
    `).join('');
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
        await loadMedias(); alert("📷 Photos sauvegardées.");
    };
}

function initForms() {
    document.querySelectorAll('input, textarea').forEach(el => {
        el.oninput = () => { clearTimeout(window.t); window.t = setTimeout(calculateProgress, 500); };
    });
}
