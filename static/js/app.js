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
    
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
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
            await loadTranslations(this.dataset.lang);
            document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

async function loadReperage(id) {
    const res = await fetch(`${API_URL}/reperages/${id}`);
    const data = await res.json();
    fillFormData(data);
    // Délai pour laisser le temps aux champs d'être peuplés
    setTimeout(calculateProgress, 1000);
}

function fillFormData(data) {
    document.querySelectorAll('input[name], textarea[name], select[name]').forEach(input => {
        const name = input.name;
        if (data[name]) input.value = data[name];
        else if (data.territoire_data && data.territoire_data[name]) input.value = data.territoire_data[name];
        else if (data.episode_data && data.episode_data[name]) input.value = data.episode_data[name];
    });
}

function calculateProgress() {
    // Liste des champs SUBSTANTIELS à compter
    const inputs = document.querySelectorAll('input[name], textarea[name]');
    let total = 0; let filled = 0;
    
    inputs.forEach(input => {
        // Exclure les champs d'identité Fixer
        if (!['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'].includes(input.name)) {
            total++;
            if (input.value && input.value.trim().length > 2) filled++;
        }
    });

    const percent = total > 0 ? Math.round((filled / total) * 100) : 0;
    
    // Affichage
    if (document.getElementById('progress-bar')) document.getElementById('progress-bar').style.width = percent + '%';
    if (document.getElementById('progress-percentage')) document.getElementById('progress-percentage').textContent = percent + '%';
    if (document.getElementById('progress-filled')) document.getElementById('progress-filled').textContent = filled;
    if (document.getElementById('progress-total')) document.getElementById('progress-total').textContent = total;
    
    return percent;
}

async function saveReperage(notif) {
    if (!currentReperageId) return;
    const currentPercent = calculateProgress();
    const data = { 
        progression: currentPercent, // Envoi direct du chiffre calculé
        territoire_data: {}, 
        episode_data: {}, 
        gardiens: [], 
        lieux: [] 
    };

    document.querySelectorAll('input[name], textarea[name]').forEach(el => {
        if (['fixer_nom', 'fixer_email', 'pays', 'region'].includes(el.name)) data[el.name] = el.value;
        else data.territoire_data[el.name] = el.value;
    });

    await fetch(`${API_URL}/reperages/${currentReperageId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (notif) alert("✅ Données synchronisées : " + currentPercent + "%");
}

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(this.dataset.tab).classList.add('active');
        });
    });
    document.querySelectorAll('.lieu-tab').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.lieu-tab, .lieu-content').forEach(el => el.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(`lieu-${this.dataset.lieu}`).classList.add('active');
        });
    });
}

function initFileUpload() {
    const area = document.getElementById('drop-area');
    if (!area) return;
    area.addEventListener('click', () => document.getElementById('file-input').click());
    document.getElementById('file-input').addEventListener('change', async (e) => {
        for (let file of e.target.files) {
            const fd = new FormData(); fd.append('file', file);
            await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd });
        }
        alert("📷 Photos sauvegardées.");
    });
}

function initChat() {
    document.getElementById('chat-toggle-btn')?.addEventListener('click', () => {
        document.getElementById('chat-panel').classList.add('active');
        loadMessages();
    });
    document.getElementById('chat-close-btn')?.addEventListener('click', () => {
        document.getElementById('chat-panel').classList.remove('active');
    });
    document.getElementById('chat-send-btn')?.addEventListener('click', async () => {
        const input = document.getElementById('chat-input');
        if (!input.value) return;
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ auteur_type: 'fixer', auteur_nom: 'Correspondant', contenu: input.value })
        });
        input.value = '';
        loadMessages();
    });
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    document.getElementById('chat-messages').innerHTML = msgs.map(m => `
        <div class="chat-message ${m.auteur_type}">
            <div class="chat-message-header"><strong>${m.auteur_nom}</strong></div>
            <div class="chat-message-bubble">${m.contenu}</div>
        </div>
    `).join('');
}
