/**
 * DOC-OS V.52 SUPRÊME - MOTEUR DE SYNCHRONISATION INTÉGRALE
 */
const API_URL = '/api';
let currentLanguage = localStorage.getItem('selectedLanguage') || 'FR';
let currentReperageId = window.REPERAGE_ID || null;
let translations = {};

// ============= INITIALISATION PRIORITAIRE =============
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Lancement DOC-OS V.52');

    // 1. Liaison immédiate des boutons (même si le reste échoue)
    initForms();

    if (window.FIXER_DATA) {
        currentLanguage = window.FIXER_DATA.langue_default || 'FR';
        currentReperageId = window.FIXER_DATA.reperage_id;
    }

    // 2. Chargement asynchrone protégé
    try {
        await loadTranslations(currentLanguage);
        initLanguageSelector();
        initTabs();
        initFileUpload();
        initChat();

        if (currentReperageId) {
            await loadReperage(currentReperageId);
            await loadMedias(); 
        }
    } catch (e) {
        console.error("Erreur critique initialisation:", e);
    }

    setInterval(() => saveReperage(false), 120000);
    if (typeof lucide !== 'undefined') lucide.createIcons();
});

// ============= MODULE i18n (SÉCURISÉ) =============
async function loadTranslations(lang) {
    try {
        const response = await fetch(`${API_URL}/i18n/${lang}`);
        if (!response.ok) throw new Error('Dictionnaire inaccessible');
        translations = await response.json();
        applyTranslations();
        currentLanguage = lang;
        localStorage.setItem('selectedLanguage', lang);
    } catch (e) { console.warn("i18n error, utilisation du cache local."); }
}

function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const val = key.split('.').reduce((p, c) => p && p[c], translations);
        if (val) el.textContent = val;
    });
}

// ============= MODULE PROGRESSION (101 POINTS) =============
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

// ============= MODULE SAUVEGARDE (SOUDURE FIX 3) =============
async function saveReperage(notif) {
    if (!currentReperageId) return;
    const p = calculateProgress();
    const data = collectFormData();
    data.progression = p;

    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (res.ok && notif) alert("✅ Données Synchronisées (" + p + "%)");
    } catch (e) { alert("❌ Erreur de connexion au serveur."); }
}

function collectFormData() {
    const data = { territoire_data: {}, particularite_data: {}, fete_data: {}, episode_data: {}, gardiens: [], lieux: [] };
    const partKeys = ['angle', 'fete_nom', 'contraintes', 'arc', 'moments', 'sensibles', 'budget', 'notes'];
    const feteKeys = ['fete_lieu_date', 'fete_pourquoi', 'fete_origines', 'fete_deroulement', 'fete_visuel', 'fete_responsable'];

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
    return data;
}

// ============= MODULES INTERFACE =============
function initChat() {
    document.getElementById('chat-toggle-btn').onclick = () => { document.getElementById('chat-panel').classList.add('active'); loadMessages(); };
    document.getElementById('chat-close-btn').onclick = () => document.getElementById('chat-panel').classList.remove('active');
    document.getElementById('chat-send-btn').onclick = async () => {
        const input = document.getElementById('chat-input');
        if (!input.value) return;
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ auteur_type: 'fixer', auteur_nom: window.FIXER_DATA.prenom || 'Fixer', contenu: input.value })
        });
        input.value = ''; loadMessages();
    };
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    document.getElementById('chat-messages').innerHTML = msgs.map(m => {
        const isFixer = m.auteur_type === 'fixer';
        return `<div class="msg-wrapper ${isFixer ? 'msg-fixer' : 'msg-production'}"><div class="bubble">${m.contenu}</div><div class="msg-meta">${m.auteur_nom}</div></div>`;
    }).join('');
    const container = document.getElementById('chat-messages'); container.scrollTop = container.scrollHeight;
}

function initForms() {
    document.getElementById('btn-save').onclick = () => saveReperage(true);
    document.getElementById('btn-submit').onclick = async () => {
        await saveReperage(false);
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}/submit`, { method: 'POST' });
        if (res.ok) alert("🚀 Dossier transmis !");
    };
}
// ... (initTabs, loadReperage, initFileUpload, loadMedias identiques V51)
function initTabs() { document.querySelectorAll('.tab-btn').forEach(btn => { btn.onclick = () => { document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active')); btn.classList.add('active'); document.getElementById(btn.dataset.tab).classList.add('active'); }; }); }
async function loadReperage(id) { const res = await fetch(`${API_URL}/reperages/${id}`); const data = await res.json(); document.querySelectorAll('input[name], textarea[name]').forEach(input => { const n = input.name; if (data[n]) input.value = data[n]; else if (data.territoire_data && data.territoire_data[n]) input.value = data.territoire_data[n]; else if (data.particularite_data && data.particularite_data[n]) input.value = data.particularite_data[n]; else if (data.fete_data && data.fete_data[n]) input.value = data.fete_data[n]; }); if (data.gardiens) data.gardiens.forEach(g => { Object.keys(g).forEach(k => { const el = document.querySelector(`[name="gardien${g.ordre}_${k}"]`); if (el) el.value = g[k]; }); }); if (data.lieux) data.lieux.forEach(l => { Object.keys(l).forEach(k => { const el = document.querySelector(`[name="lieu${l.numero_lieu}_${k}"]`); if (el) el.value = l[k]; }); }); setTimeout(calculateProgress, 1000); }
function initFileUpload() { const area = document.getElementById('drop-area'); if (!area) return; area.onclick = () => document.getElementById('file-input').click(); document.getElementById('file-input').onchange = async (e) => { for (let file of e.target.files) { const fd = new FormData(); fd.append('file', file); await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd }); } await loadMedias(); }; }
async function loadMedias() { const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`); const ms = await res.json(); document.getElementById('files-list').innerHTML = ms.map(m => `<div class="file-item"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100px;height:140px;object-fit:cover;border-radius:10px;"></div>`).join(''); }
