// ============= CONFIGURATION & VARIABLES GLOBALES =============
const API_URL = '/api';
let currentLanguage = localStorage.getItem('selectedLanguage') || 'FR';
let currentReperageId = window.REPERAGE_ID || null;
let translations = {};

// ============= INITIALISATION AU CHARGEMENT DU DOM =============
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Initialisation DOC-OS V.23 - Système de Synchronisation');

    // Détection des données injectées par Flask (Formulaire distant)
    if (window.FIXER_DATA) {
        currentLanguage = window.FIXER_DATA.langue_default || 'FR';
        currentReperageId = window.FIXER_DATA.reperage_id;
    }

    // Chargement des modules fondamentaux
    await loadTranslations(currentLanguage);
    initLanguageSelector();
    initTabs();
    initFileUpload();
    initChat();
    initForms();

    // Chargement des données métier
    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); // Affiche les photos déjà présentes sur le serveur
    }

    // Auto-sauvegarde de sécurité toutes les 2 minutes
    setInterval(() => saveReperage(false), 120000);
    
    // Initialisation des icônes Lucide
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
});

// ============= MODULE 1 : SYSTÈME MULTILINGUE (i18n) =============
async function loadTranslations(lang) {
    try {
        const response = await fetch(`${API_URL}/i18n/${lang}`);
        if (!response.ok) throw new Error('Dictionnaire introuvable');
        translations = await response.json();
        applyTranslations();
        currentLanguage = lang;
        localStorage.setItem('selectedLanguage', lang);
    } catch (error) {
        console.error('Erreur chargement i18n:', error);
    }
}

function applyTranslations() {
    // Traduction des textes simples
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const translation = getNestedTranslation(translations, key);
        if (translation) el.textContent = translation;
    });
    // Traduction des placeholders (champs de saisie)
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

// ============= MODULE 2 : CALCUL ET AFFICHAGE DE PROGRESSION =============
function calculateProgress() {
    // On cible les champs qui portent un attribut name (Substance)
    const substanceFields = document.querySelectorAll('input[name], textarea[name], select[name]');
    let total = 0;
    let filled = 0;

    substanceFields.forEach(input => {
        // Exclusion des métadonnées de structure (fixer, pays, région)
        const excluded = ['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'];
        if (!excluded.includes(input.name)) {
            total++;
            // Un champ est considéré rempli s'il contient au moins 3 caractères
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
    
    // Affichage des chiffres bruts pour le correspondant (Test 0/0 résolu)
    if (textFilled) textFilled.textContent = filled;
    if (textTotal) textTotal.textContent = total;
}

// ============= MODULE 3 : FLUX DE DONNÉES (CRUD & SYNC) =============
async function loadReperage(id) {
    try {
        const response = await fetch(`${API_URL}/reperages/${id}`);
        const data = await response.json();
        
        // Remplissage des données à la racine
        document.querySelectorAll('input[name], textarea[name], select[name]').forEach(el => {
            const name = el.name;
            if (data[name]) el.value = data[name];
            // Remplissage des données segmentées (JSON)
            else if (data.territoire_data && data.territoire_data[name]) el.value = data.territoire_data[name];
            else if (data.episode_data && data.episode_data[name]) el.value = data.episode_data[name];
        });

        // Remplissage récursif Gardiens et Lieux (logique V.22)
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

        // Calcul initial après chargement (avec délai pour rendu navigateur)
        setTimeout(calculateProgress, 1000);
    } catch (error) {
        console.error('Erreur loadReperage:', error);
    }
}

async function saveReperage(showNotificationFlag = true) {
    if (!currentReperageId) return;

    // Synchronisation forcée du pourcentage
    const progress = calculateProgress();
    const formData = collectFormData();
    formData.progression = progress.percentage; // C'est cette valeur qui sera vue par l'Admin

    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (response.ok && showNotificationFlag) {
            alert("✅ Données synchronisées avec la production (" + progress.percentage + "%)");
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

    // Liste des clés appartenant à la section ÉPISODE pour segmentation PDF
    const episodeKeys = ['angle', 'fete', 'arc', 'moments', 'contraintes', 'sensibles', 'autorisations', 'budget', 'notes'];

    document.querySelectorAll('input[name], textarea[name], select[name]').forEach(el => {
        const name = el.name;
        const val = el.value;

        // Dispatching selon la nature du champ
        if (['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'].includes(name)) {
            data[name] = val;
        } else if (episodeKeys.includes(name)) {
            data.episode_data[name] = val;
        } else {
            // Par défaut dans Territoire (inclut gardiens et lieux si non parsés)
            data.territoire_data[name] = val;
        }
    });

    return data;
}

// ============= MODULE 4 : MÉDIAS & UPLOAD (VOLUME RAILWAY) =============
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
            const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, {
                method: 'POST',
                body: formData
            });
            if (res.ok) console.log('File uploaded:', file.name);
        } catch (e) { 
            console.error('Upload error:', e); 
        }
    }
    // Rechargement immédiat de la galerie après upload
    await loadMedias();
    alert("📷 Médias sauvegardés sur le serveur.");
}

async function loadMedias() {
    if (!currentReperageId) return;
    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
        const medias = await response.json();
        const listContainer = document.getElementById('files-list');
        if (listContainer) {
            listContainer.innerHTML = medias.map(m => `
                <div class="file-item" style="border: 1px solid #E0DED9; padding: 10px; border-radius: 8px; background: white;">
                    <img src="/uploads/${currentReperageId}/${m.nom_fichier}" 
                         style="width: 100%; height: 120px; object-fit: cover; border-radius: 4px;"
                         alt="${m.nom_original}">
                    <span style="display: block; font-size: 0.8rem; margin-top: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ${m.nom_original}
                    </span>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Erreur chargement médias:', error);
    }
}

// ============= MODULE 5 : COLLABORATION (CHAT) =============
function initChat() {
    const toggleBtn = document.getElementById('chat-toggle-btn');
    const closeBtn = document.getElementById('chat-close-btn');
    const sendBtn = document.getElementById('chat-send-btn');

    if (!toggleBtn) return;

    toggleBtn.addEventListener('click', () => {
        document.getElementById('chat-panel').classList.add('active');
        loadMessages();
    });

    closeBtn.addEventListener('click', () => {
        document.getElementById('chat-panel').classList.remove('active');
    });

    sendBtn.addEventListener('click', async () => {
        const input = document.getElementById('chat-input');
        const content = input.value.trim();
        if (!content) return;

        try {
            await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    auteur_type: 'fixer',
                    auteur_nom: document.querySelector('[name="fixer_nom"]')?.value || 'Correspondant',
                    contenu: content
                })
            });
            input.value = '';
            loadMessages();
        } catch (e) {
            console.error('Chat error:', e);
        }
    });
}

async function loadMessages() {
    if (!currentReperageId) return;
    try {
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
    } catch (e) {
        console.error('Erreur chargement messages:', e);
    }
}

// ============= MODULE 6 : INTERFACE UTILISATEUR (ONGLETS) =============
function initTabs() {
    // Navigation principale
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const targetId = this.getAttribute('data-tab');
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(targetId).classList.add('active');
            // Recalculer la progression au changement d'onglet si nécessaire
            calculateProgress();
        });
    });

    // Navigation des lieux (Triptyque)
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

function initForms() {
    const btnSave = document.getElementById('btn-save');
    if (btnSave) {
        btnSave.addEventListener('click', () => saveReperage(true));
    }
    
    // Écouteur global pour mettre à jour la jauge en temps réel lors de la saisie
    document.querySelectorAll('input, textarea, select').forEach(el => {
        el.addEventListener('input', () => {
            // Utilisation d'un debounce léger pour la performance
            clearTimeout(window.calcTimer);
            window.calcTimer = setTimeout(calculateProgress, 500);
        });
    });
}
