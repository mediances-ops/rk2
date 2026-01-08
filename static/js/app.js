// ============= CONFIGURATION & GLOBALES =============
const API_URL = '/api';
let currentLanguage = localStorage.getItem('selectedLanguage') || 'FR';
let currentReperageId = window.REPERAGE_ID || null;
let translations = {};

// ============= INITIALISATION AU CHARGEMENT =============
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Initialisation DOC-OS V.19');

    // Récupération des données injectées par le serveur (Flask)
    if (window.FIXER_DATA) {
        currentLanguage = window.FIXER_DATA.langue_default || 'FR';
        currentReperageId = window.FIXER_DATA.reperage_id;
    }

    // Chargement immédiat des outils
    await loadTranslations(currentLanguage);
    initLanguageSelector();
    initTabs();
    initFileUpload();
    initChat();
    initForms();

    // Chargement des données si un ID est présent
    if (currentReperageId) {
        await loadReperage(currentReperageId);
    }

    // Auto-sauvegarde silencieuse toutes les 2 minutes
    setInterval(() => saveReperage(false), 120000);
    
    lucide.createIcons();
});

// ============= SYSTÈME MULTILINGUE (i18n) =============
async function loadTranslations(lang) {
    try {
        const response = await fetch(`${API_URL}/i18n/${lang}`);
        translations = await response.json();
        applyTranslations();
        currentLanguage = lang;
        localStorage.setItem('selectedLanguage', lang);
    } catch (error) {
        console.error('Erreur i18n:', error);
    }
}

function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const translation = getNestedTranslation(translations, key);
        if (translation) el.textContent = translation;
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        const translation = getNestedTranslation(translations, key);
        if (translation) el.placeholder = translation;
    });
}

function getNestedTranslation(obj, path) {
    return path.split('.').reduce((prev, curr) => prev ? prev[curr] : null, obj);
}

function initLanguageSelector() {
    document.querySelectorAll('.lang-btn').forEach(btn => {
        if (btn.dataset.lang === currentLanguage) btn.classList.add('active');
        btn.addEventListener('click', async function() {
            document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            await loadTranslations(this.dataset.lang);
        });
    });
}

// ============= CALCUL ET AFFICHAGE DE PROGRESSION =============
function calculateProgress() {
    // On cible tous les champs ayant un attribut "name"
    const fields = document.querySelectorAll('input[name], textarea[name], select[name]');
    let total = 0;
    let filled = 0;

    fields.forEach(input => {
        // On exclut les champs d'identité souvent pré-remplis pour ne pas fausser la progression
        const excluded = ['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'];
        if (!excluded.includes(input.name)) {
            total++;
            if (input.value && input.value.trim().length > 2) {
                filled++;
            }
        }
    });

    const percentage = total > 0 ? Math.round((filled / total) * 100) : 0;
    updateProgressDisplay(percentage, filled, total);
    return { percentage, filled, total };
}

function updateProgressDisplay(percentage, filled, total) {
    const bar = document.getElementById('progress-bar');
    const textPercent = document.getElementById('progress-percentage');
    const textFilled = document.getElementById('progress-filled');
    const textTotal = document.getElementById('progress-total');

    if (bar) bar.style.width = percentage + '%';
    if (textPercent) textPercent.textContent = percentage + '%';
    
    // Correction de l'affichage "X sur Y"
    if (textFilled) textFilled.textContent = filled;
    if (textTotal) textTotal.textContent = total;
}

// ============= CHARGEMENT ET SAUVEGARDE DES DONNÉES =============
async function loadReperage(id) {
    try {
        const response = await fetch(`${API_URL}/reperages/${id}`);
        const data = await response.json();
        
        // Remplissage des champs simples
        document.querySelectorAll('input[name], textarea[name], select[name]').forEach(el => {
            const name = el.name;
            if (data[name]) el.value = data[name];
            else if (data.territoire_data && data.territoire_data[name]) el.value = data.territoire_data[name];
            else if (data.episode_data && data.episode_data[name]) el.value = data.episode_data[name];
        });

        // Remplissage spécifique Gardiens (basé sur le préfixe gardienX_)
        if (data.gardiens) {
            data.gardiens.forEach(g => {
                Object.keys(g).forEach(key => {
                    const el = document.querySelector(`[name="gardien${g.ordre}_${key}"]`);
                    if (el) el.value = g[key];
                });
            });
        }

        // Remplissage spécifique Lieux (basé sur le préfixe lieuX_)
        if (data.lieux) {
            data.lieux.forEach(l => {
                Object.keys(l).forEach(key => {
                    const el = document.querySelector(`[name="lieu${l.numero_lieu}_${key}"]`);
                    if (el) el.value = l[key];
                });
            });
        }

        // Déclencher le calcul de progression après remplissage
        setTimeout(calculateProgress, 800);
    } catch (error) {
        console.error('Erreur loadReperage:', error);
    }
}

async function saveReperage(showNotificationFlag = true) {
    if (!currentReperageId) return;

    const progress = calculateProgress();
    const formData = collectFormData();
    formData.progression = progress.percentage; // Envoi du % réel pour le Dashboard Admin

    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (response.ok && showNotificationFlag) {
            alert("✅ Données synchronisées avec la production.");
        }
    } catch (error) {
        console.error('Erreur sauvegarde:', error);
    }
}

function collectFormData() {
    const data = { 
        territoire_data: {}, 
        episode_data: {}, 
        gardiens: [], 
        lieux: [] 
    };

    // Mapping intelligent des champs
    document.querySelectorAll('input[name], textarea[name], select[name]').forEach(el => {
        const name = el.name;
        const val = el.value;

        if (['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'].includes(name)) {
            data[name] = val;
        } else if (name.startsWith('gardien')) {
            // Extraction automatique vers territoire_data pour simplicité, ou parsing si nécessaire
            data.territoire_data[name] = val;
        } else if (name.startsWith('lieu')) {
            data.territoire_data[name] = val;
        } else {
            // Champs par défaut (Territoire et Episode)
            data.territoire_data[name] = val;
        }
    });

    return data;
}

// ============= INTERFACE : ONGLETS & UPLOAD =============
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

    document.querySelectorAll('.lieu-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const lieuNum = this.getAttribute('data-lieu');
            document.querySelectorAll('.lieu-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.lieu-content').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(`lieu-${lieuNum}`).classList.add('active');
        });
    });
}

function initFileUpload() {
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    if (!dropArea) return;

    dropArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFiles(e.target.files));
}

async function handleFiles(files) {
    for (let file of files) {
        const formData = new FormData();
        formData.append('file', file);
        try {
            await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, {
                method: 'POST',
                body: formData
            });
        } catch (e) { console.error('Upload error:', e); }
    }
    alert("📷 Médias envoyés au serveur.");
}

// ============= SYSTÈME DE CHAT =============
function initChat() {
    const sendBtn = document.getElementById('chat-send-btn');
    const toggleBtn = document.getElementById('chat-toggle-btn');
    const closeBtn = document.getElementById('chat-close-btn');

    toggleBtn?.addEventListener('click', () => {
        document.getElementById('chat-panel').classList.add('active');
        loadMessages();
    });

    closeBtn?.addEventListener('click', () => {
        document.getElementById('chat-panel').classList.remove('active');
    });

    sendBtn?.addEventListener('click', async () => {
        const input = document.getElementById('chat-input');
        if (!input.value.trim()) return;

        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                auteur_type: 'fixer',
                auteur_nom: document.querySelector('[name="fixer_nom"]')?.value || 'Correspondant',
                contenu: input.value
            })
        });
        input.value = '';
        loadMessages();
    });
}

async function loadMessages() {
    if (!currentReperageId) return;
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const messages = await res.json();
    const container = document.getElementById('chat-messages');
    container.innerHTML = messages.map(m => `
        <div class="chat-message ${m.auteur_type}">
            <div class="chat-message-header"><strong>${m.auteur_nom}</strong></div>
            <div class="chat-message-bubble">${m.contenu}</div>
        </div>
    `).join('');
    container.scrollTop = container.scrollHeight;
}

function initForms() {
    const btnSave = document.getElementById('btn-save');
    if (btnSave) btnSave.addEventListener('click', () => saveReperage(true));
}
