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
    if (currentReperageId) await loadReperage(currentReperageId);
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
});

async function loadTranslations(lang) {
    const res = await fetch(`${API_URL}/i18n/${lang}`);
    translations = await res.json();
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const val = el.getAttribute('data-i18n').split('.').reduce((p, c) => p && p[c], translations);
        if (val) el.textContent = val;
    });
    currentLanguage = lang;
}

function calculateProgress() {
    const fields = document.querySelectorAll('input[name], textarea[name]');
    let total = 0; let filled = 0;
    fields.forEach(f => {
        if (!['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'].includes(f.name)) {
            total++; if (f.value && f.value.trim().length > 2) filled++;
        }
    });
    const p = Math.round((filled / total) * 100);
    document.getElementById('progress-bar').style.width = p + '%';
    document.getElementById('progress-percentage').textContent = p + '%';
    document.getElementById('progress-filled').textContent = filled;
    return p;
}

async function loadReperage(id) {
    const res = await fetch(`${API_URL}/reperages/${id}`);
    const data = await res.json();
    document.querySelectorAll('input[name], textarea[name]').forEach(input => {
        const n = input.name;
        if (data[n]) input.value = data[n];
        else if (data.territoire_data && data.territoire_data[n]) input.value = data.territoire_data[n];
        else if (data.particularite_data && data.particularite_data[n]) input.value = data.particularite_data[n];
        else if (data.fete_data && data.fete_data[n]) input.value = data.fete_data[n];
        else if (data.episode_data && data.episode_data[n]) input.value = data.episode_data[n];
    });
    if (data.gardiens) data.gardiens.forEach(g => {
        Object.keys(g).forEach(k => {
            const el = document.querySelector(`[name="gardien${g.ordre}_${k}"]`);
            if (el) el.value = g[k];
        });
    });
    if (data.lieux) data.lieux.forEach(l => {
        Object.keys(l).forEach(k => {
            const el = document.querySelector(`[name="lieu${l.numero_lieu}_${k}"]`);
            if (el) el.value = l[k];
        });
    });
    setTimeout(calculateProgress, 1000);
}

async function saveReperage(notif) {
    const p = calculateProgress();
    const data = { progression: p, territoire_data: {}, particularite_data: {}, fete_data: {}, episode_data: {}, gardiens: [], lieux: [] };
    
    // Segmentation des clés
    const partKeys = ['angle', 'fete_nom', 'contraintes', 'arc', 'moments', 'sensibles', 'budget', 'notes'];
    const feteKeys = ['fete_lieu_date', 'fete_pourquoi', 'fete_origines', 'fete_deroulement', 'fete_visuel', 'fete_responsable'];

    // Collecte Triptyques
    for (let i = 1; i <= 3; i++) {
        let g = { ordre: i };
        ['nom_prenom', 'age', 'fonction', 'savoir', 'histoire', 'psychologie', 'evaluation', 'langues', 'contact', 'intermediaire'].forEach(k => {
            g[k] = document.querySelector(`[name="gardien${i}_${k}"]`)?.value;
        });
        if (g.nom_prenom) data.gardiens.push(g);
        let l = { numero_lieu: i };
        ['nom', 'type', 'description', 'cinegenie', 'axes', 'points_vue', 'moments', 'son', 'adequation', 'acces', 'securite', 'elec', 'espace', 'meteo', 'permis'].forEach(k => {
            l[k] = document.querySelector(`[name="lieu${i}_${k}"]`)?.value;
        });
        if (l.nom) data.lieux.push(l);
    }

    document.querySelectorAll('input[name], textarea[name]').forEach(el => {
        if (['fixer_nom', 'pays', 'region'].includes(el.name)) data[el.name] = el.value;
        else if (partKeys.includes(el.name)) data.particularite_data[el.name] = el.value;
        else if (feteKeys.includes(el.name)) data.fete_data[el.name] = el.value;
        else if (!el.name.startsWith('gardien') && !el.name.startsWith('lieu')) data.territoire_data[el.name] = el.value;
    });

    await fetch(`${API_URL}/reperages/${currentReperageId}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
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
}

function initChat() {
    document.getElementById('chat-send-btn').onclick = async () => {
        const input = document.getElementById('chat-input');
        if (!input.value) return;
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ auteur_type: 'fixer', auteur_nom: 'Correspondant', contenu: input.value }) });
        input.value = '';
    };
}
