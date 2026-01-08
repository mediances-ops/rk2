// ============= CONFIGURATION & GLOBALES =============
const API_URL = '/api';
let currentLanguage = localStorage.getItem('selectedLanguage') || 'FR';
let currentReperageId = window.REPERAGE_ID || null;
let translations = {};

// ============= INITIALISATION =============
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Initialisation DOC-OS V.24 - Synchronisation Totale');

    // Récupération des données injectées par le serveur
    if (window.FIXER_DATA) {
        currentLanguage = window.FIXER_DATA.langue_default || 'FR';
        currentReperageId = window.FIXER_DATA.reperage_id;
    }

    // Chargement des modules
    await loadTranslations(currentLanguage);
    initLanguageSelector();
    initTabs();
    initFileUpload();
    initChat();
    initForms();

    // Chargement des données existantes
    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); // Affiche les photos dès l'ouverture
    }

    // Auto-sauvegarde de sécurité toutes les 2 minutes
    setInterval(() => saveReperage(false), 120000);
    
    if (typeof lucide !== 'undefined') lucide.createIcons();
});

// ============= MODULE i18n (MULTILINGUE) =============
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

// ============= MODULE PROGRESSION (SYNC ADMIN) =============
function calculateProgress() {
    // Ciblage des champs substantiels
    const fields = document.querySelectorAll('input[name], textarea[name], select[name]');
    let total = 0;
    let filled = 0;

    fields.forEach(input => {
        // On exclut les métadonnées pour ne pas fausser le calcul de la substance
        const excluded = ['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'];
        if (!excluded.includes(input.name)) {
            total++;
            if (input.value && input.value.trim().length > 2) {
                filled++;
            }
        }
    });

    const percentage = total > 0 ? Math.round((filled / total) * 100) : 0;
    
    // Mise à jour de l'interface Correspondent
    const bar = document.getElementById('progress-bar');
    const textPercent = document.getElementById('progress-percentage');
    const textFilled = document.getElementById('progress-filled');
    const textTotal = document.getElementById('progress-total');

    if (bar) bar.style.width = percentage + '%';
    if (textPercent) textPercent.textContent = percentage + '%';
    if (textFilled) textFilled.textContent = filled;
    if (textTotal) textTotal.textContent = total;

    return percentage;
}

// ============= MODULE DATA (CRUD) =============
async function loadReperage(id) {
    try {
        const response = await fetch(`${API_URL}/reperages/${id}`);
        const data = await response.json();
        
        // Remplissage intelligent des champs
        document.querySelectorAll('input[name], textarea[name], select[name]').forEach(el => {
            const name = el.name;
            if (data[name]) el.value = data[name];
            else if (data.territoire_data && data.territoire_data[name]) el.value = data.territoire_data[name];
            else if (data.episode_data && data.episode_data[name]) el.value = data.episode_data[name];
        });

        // Remplissage récursif Gardiens et Lieux
        if (data.gardiens) {
            data.gardiens.forEach(g => {
                Object.keys(g).forEach(key => {
                    const el = document.querySelector(`[name="gardien${g.ordre}_${key}"]`);
                    if (el) el.value = g[key];
                });
            });
        }
        if (data.lieux) {
            data.lieux.forEach(l => {
                Object.keys(l).forEach(key => {
                    const el = document.querySelector(`[name="lieu${l.numero_lieu}_${key}"]`);
                    if (el) el.value = l[key];
                });
            });
        }

        setTimeout(calculateProgress, 1000);
    } catch (error) {
        console.error('Erreur chargement:', error);
    }
}

async function saveReperage(showNotif = true) {
    if (!currentReperageId) return;

    const progressVal = calculateProgress();
    const formData = collectFormData();
    formData.progression = progressVal; // Synchronisation forcée pour l'Admin

    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (response.ok && showNotif) {
            alert("✅ Données synchronisées : " + progressVal + "%");
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

    // Clés réservées à la section Épisode pour le PDF
    const episodeKeys = ['angle', 'fete', 'arc', 'moments', 'contraintes', 'sensibles', 'autorisations', 'budget', 'notes'];

    document.querySelectorAll('input[name], textarea[name], select[name]').forEach(el => {
        const name = el.name;
        const val = el.value;

        if (['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'].includes(name)) {
            data[name] = val;
        } else if (episodeKeys.includes(name)) {
            data.episode_data[name] = val;
        } else {
            data.territoire_data[name] = val;
        }
    });

    return data;
}

// ============= MODULE MÉDIAS (UPLOAD & VIEW) =============
function initFileUpload() {
    const area = document.getElementById('drop-area');
    if (!area) return;
    area.onclick = () => document.getElementById('file-input').click();
    document.getElementById('file-input').onchange = async (e) => {
        for (let file of e.target.files) {
            const fd = new FormData(); 
            fd.append('file', file);
            await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd });
        }
        await loadMedias(); // Recharge immédiate de la galerie photos
        alert("📷 Médias enregistrés.");
    };
}

async function loadMedias() {
    if (!currentReperageId) return;
    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
        const medias = await response.json();
        const list = document.getElementById('files-list');
        if (list) {
            list.innerHTML = medias.map(m => `
                <div class="file-item" style="border: 1px solid #ddd; padding: 10px; border-radius: 8px; background: white; text-align:center;">
                    <img src="/uploads/${currentReperageId}/${m.nom_fichier}" 
                         style="width: 100%; height: 120px; object-fit: cover; border-radius: 4px;">
                    <span style="display: block; font-size: 0.75rem; margin-top: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ${m.nom_original}
                    </span>
                </div>
            `).join('');
        }
    } catch (e) { console.error('Erreur médias:', e); }
}

// ============= MODULE CHAT COLLABORATIF =============
function initChat() {
    const toggleBtn = document.getElementById('chat-toggle-btn');
    const closeBtn = document.getElementById('chat-close-btn');
    const sendBtn = document.getElementById('chat-send-btn');

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

// ============= MODULE INTERFACE (TABS) =============
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(this.dataset.tab).classList.add('active');
            calculateProgress();
        });
    });

    document.querySelectorAll('.lieu-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.lieu-tab, .lieu-content').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(`lieu-${this.dataset.lieu}`).classList.add('active');
        });
    });
}

function initForms() {
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.querySelectorAll('input, textarea').forEach(el => {
        el.addEventListener('input', () => {
            clearTimeout(window.calcTimer);
            window.calcTimer = setTimeout(calculateProgress, 500);
        });
    });
}
