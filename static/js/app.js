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
    if (currentReperageId) await loadReperage(currentReperageId);
    
    // Auto-save et sync toutes les 60s
    setInterval(() => saveReperage(false), 60000);
});

async function loadTranslations(lang) {
    const res = await fetch(`${API_URL}/i18n/${lang}`);
    translations = await res.json();
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const keys = el.getAttribute('data-i18n').split('.');
        let val = translations;
        keys.forEach(k => { val = val ? val[k] : null; });
        if (val) el.textContent = val;
    });
}

function initLanguageSelector() {
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            await loadTranslations(this.dataset.lang);
        });
    });
}

async function loadReperage(id) {
    const res = await fetch(`${API_URL}/reperages/${id}`);
    const data = await res.json();
    fillFormData(data);
    setTimeout(calculateProgress, 800); // Laisse le temps au DOM de se remplir
}

function fillFormData(data) {
    const inputs = document.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
        const name = input.name;
        if (data[name]) input.value = data[name];
        else if (data.territoire_data && data.territoire_data[name]) input.value = data.territoire_data[name];
        else if (data.episode_data && data.episode_data[name]) input.value = data.episode_data[name];
    });
    // Remplissage spécifique gardiens et lieux si nécessaire
}

function calculateProgress() {
    const allInputs = document.querySelectorAll('input:not([type="hidden"]), textarea, select');
    let total = 0; let filled = 0;
    allInputs.forEach(input => {
        total++;
        if (input.value && input.value.trim().length > 1) filled++;
    });
    const percent = Math.round((filled / total) * 100);
    updateProgressDisplay(percent, filled, total);
    return { percentage: percent };
}

function updateProgressDisplay(percent, filled, total) {
    const bar = document.getElementById('progress-bar');
    const txtPercent = document.getElementById('progress-percentage');
    const txtStats = document.getElementById('progress-filled');
    const txtTotal = document.getElementById('progress-total');
    
    if (bar) bar.style.width = percent + '%';
    if (txtPercent) txtPercent.textContent = percent + '%';
    if (txtStats) txtStats.textContent = filled; // Correction: Affiche le nombre réel
    if (txtTotal) txtTotal.textContent = total;   // Correction: Affiche le total réel
}

async function saveReperage(show) {
    if (!currentReperageId) return;
    const progress = calculateProgress();
    const formData = collectFormData();
    formData.progression = progress.percentage; // Envoi pour sync admin

    await fetch(`${API_URL}/reperages/${currentReperageId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    });
    if (show) alert("Synchronisation réussie");
}

function collectFormData() {
    const data = { territoire_data: {}, episode_data: {}, gardiens: [], lieux: [] };
    document.querySelectorAll('input, textarea, select').forEach(el => {
        if (['fixer_nom', 'fixer_email', 'pays', 'region'].includes(el.name)) data[el.name] = el.value;
        else data.territoire_data[el.name] = el.value;
    });
    return data;
}

// ... (initFileUpload, initChat, initTabs restent identiques à la V17)
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });
}
function initChat() {
    document.getElementById('chat-send-btn')?.addEventListener('click', async () => {
        const input = document.getElementById('chat-input');
        if (!input.value) return;
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ auteur_type: 'fixer', auteur_nom: 'Correspondant', contenu: input.value })
        });
        input.value = '';
    });
}
