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
    initChat();
    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); 
    }
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('chat-toggle-btn')?.addEventListener('click', () => document.getElementById('chat-panel').style.right = '0');
    document.getElementById('chat-close-btn')?.addEventListener('click', () => document.getElementById('chat-panel').style.right = '-400px');
});

// FIX 4 : i18n Robustesse
async function loadTranslations(lang) {
    try {
        const response = await fetch(`${API_URL}/i18n/${lang}`);
        translations = await response.json();
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const keys = el.getAttribute('data-i18n').split('.');
            let val = translations;
            keys.forEach(k => { val = val ? val[k] : null; });
            if (val) el.textContent = val;
        });
        currentLanguage = lang;
    } catch (e) { console.error("Erreur dictionnaire:", e); }
}

function initLanguageSelector() {
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.addEventListener('click', () => loadTranslations(btn.dataset.lang));
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
    // Remplissage Racine
    document.querySelectorAll('input[name], textarea[name]').forEach(input => {
        const name = input.name;
        if (data[name]) input.value = data[name];
        else if (data.territoire_data && data.territoire_data[name]) input.value = data.territoire_data[name];
        else if (data.episode_data && data.episode_data[name]) input.value = data.episode_data[name];
    });
    // Remplissage Segmenté Gardiens/Lieux (Fix 2)
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
    // SEGMENTATION SÉCURISÉE (Fix 2)
    const data = { progression: p, territoire_data: {}, episode_data: {}, gardiens: [], lieux: [] };
    const epKeys = ['angle', 'fete', 'arc', 'moments', 'contraintes', 'sensibles', 'autorisations', 'budget', 'notes'];

    // 1. Collecte Gardiens
    for (let i = 1; i <= 3; i++) {
        let g = { ordre: i };
        ['nom', 'prenom', 'age', 'genre', 'fonction', 'savoir', 'histoire', 'evaluation', 'langues', 'adresse', 'telephone', 'email', 'contact'].forEach(k => {
            g[k] = document.querySelector(`[name="gardien${i}_${k}"]`)?.value;
        });
        if (g.nom) data.gardiens.push(g);
    }
    // 2. Collecte Lieux
    for (let i = 1; i <= 3; i++) {
        let l = { numero_lieu: i };
        ['nom', 'type', 'description', 'cinegenie', 'axes', 'points_vue', 'moments', 'ambiance', 'adequation', 'accessibilite', 'securite', 'electricite', 'espace', 'protection', 'permis'].forEach(k => {
            l[k] = document.querySelector(`[name="lieu${i}_${k}"]`)?.value;
        });
        if (l.nom) data.lieux.push(l);
    }
    // 3. Dispatching Reste
    document.querySelectorAll('input[name], textarea[name]').forEach(el => {
        if (['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'].includes(el.name)) data[el.name] = el.value;
        else if (epKeys.includes(el.name)) data.episode_data[el.name] = el.value;
        else if (!el.name.startsWith('gardien') && !el.name.startsWith('lieu')) data.territoire_data[el.name] = el.value;
    });

    await fetch(`${API_URL}/reperages/${currentReperageId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (notif) alert("✅ Synchronisé (" + p + "%)");
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
    const medias = await res.json();
    document.getElementById('files-list').innerHTML = medias.map(m => `
        <div class="file-item"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%; height:120px; object-fit:cover; border-radius:8px;"></div>
    `).join('');
}

function initChat() {
    document.getElementById('chat-send-btn').onclick = async () => {
        const input = document.getElementById('chat-input');
        if (!input.value) return;
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ auteur_type: 'fixer', auteur_nom: 'Correspondant', contenu: input.value })
        });
        input.value = '';
    };
}

function initForms() {
    document.querySelectorAll('input, textarea').forEach(el => {
        el.oninput = () => { clearTimeout(window.t); window.t = setTimeout(calculateProgress, 500); };
    });
}
