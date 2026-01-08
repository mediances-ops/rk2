// ============= CONFIGURATION =============
const API_URL = '/api';
let currentLanguage = localStorage.getItem('selectedLanguage') || 'FR';
let currentReperageId = window.REPERAGE_ID || localStorage.getItem('currentReperageId') || null;
let translations = {};
let autoSaveTimer = null;

// ============= INITIALISATION =============
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Initialisation du formulaire DOC-OS');
    
    // Détection des données injectées par Flask
    if (window.FIXER_DATA) {
        if (window.FIXER_DATA.langue_default) {
            currentLanguage = window.FIXER_DATA.langue_default;
            localStorage.setItem('selectedLanguage', currentLanguage);
        }
        if (window.FIXER_DATA.reperage_id) {
            currentReperageId = window.FIXER_DATA.reperage_id;
            localStorage.setItem('currentReperageId', currentReperageId);
        }
    }
    
    // Charger les traductions
    await loadTranslations(currentLanguage);
    
    // Initialiser les composants
    initLanguageSelector();
    initTabs();
    initForms();
    initFileUpload();
    initProgressTracking();
    initChat();
    
    // Charger les données existantes
    if (currentReperageId) {
        await loadReperage(currentReperageId);
    }
    
    // Auto-sauvegarde toutes les 60 secondes
    startAutoSave();
    
    lucide.createIcons();
});

// ============= TRADUCTIONS (i18n) =============
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
    // 1. Labels et Titres
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        const translation = getNestedTranslation(translations, key);
        if (translation) element.textContent = translation;
    });
    
    // 2. Placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
        const key = element.getAttribute('data-i18n-placeholder');
        const translation = getNestedTranslation(translations, key);
        if (translation) element.placeholder = translation;
    });
}

function getNestedTranslation(obj, path) {
    const keys = path.split('.');
    let result = obj;
    for (const key of keys) {
        if (result && result[key] !== undefined) result = result[key];
        else return null;
    }
    return result;
}

function initLanguageSelector() {
    const langButtons = document.querySelectorAll('.lang-btn');
    langButtons.forEach(btn => {
        if (btn.dataset.lang === currentLanguage) btn.classList.add('active');
        btn.addEventListener('click', async function() {
            langButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            await loadTranslations(this.dataset.lang);
        });
    });
}

// ============= GESTION DES ONGLETS =============
function initTabs() {
    // Tabs Principaux
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });
    
    // Sub-tabs Lieux
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

// ============= SAUVEGARDE ET SYNC =============
async function loadReperage(id) {
    try {
        const response = await fetch(`${API_URL}/reperages/${id}`);
        if (!response.ok) throw new Error('Repérage introuvable');
        const reperage = await response.json();
        fillFormData(reperage);
        calculateProgress();
    } catch (error) {
        console.error('Erreur chargement:', error);
    }
}

function fillFormData(reperage) {
    // Identité
    setInputValue('fixer_nom', reperage.fixer_nom);
    setInputValue('fixer_email', reperage.fixer_email);
    setInputValue('fixer_telephone', reperage.fixer_telephone);
    setInputValue('pays', reperage.pays);
    setInputValue('region', reperage.region);
    
    // JSON Data
    if (reperage.territoire_data) {
        Object.keys(reperage.territoire_data).forEach(k => setInputValue(k, reperage.territoire_data[k]));
    }
    if (reperage.episode_data) {
        Object.keys(reperage.episode_data).forEach(k => setInputValue(k, reperage.episode_data[k]));
    }
    
    // Gardiens
    if (reperage.gardiens) {
        reperage.gardiens.forEach(g => {
            Object.keys(g).forEach(k => setInputValue(`gardien${g.ordre}_${k}`, g[k]));
        });
    }
    
    // Lieux
    if (reperage.lieux) {
        reperage.lieux.forEach(l => {
            Object.keys(l).forEach(k => setInputValue(`lieu${l.numero_lieu}_${k}`, l[k]));
        });
    }
}

async function saveReperage(showMessage = true) {
    if (!currentReperageId) return;
    
    try {
        const formData = collectFormData();
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        
        if (response.ok && showMessage) {
            showNotification('Sauvegarde réussie', 'success');
        }
    } catch (error) {
        console.error('Erreur sauvegarde:', error);
        if (showMessage) showNotification('Erreur réseau', 'error');
    }
}

function collectFormData() {
    const progress = calculateProgress(); 
    
    const formData = {
        langue_interface: currentLanguage,
        progression: progress.percentage, // SYNC PARFAITE
        fixer_nom: getInputValue('fixer_nom'),
        fixer_email: getInputValue('fixer_email'),
        fixer_telephone: getInputValue('fixer_telephone'),
        pays: getInputValue('pays'),
        region: getInputValue('region'),
        territoire_data: {},
        episode_data: {},
        gardiens: [],
        lieux: []
    };
    
    // Collecte Sections JSON
    ['ville', 'population', 'langues', 'climat', 'histoire', 'traditions', 'fetes', 'acces', 'hebergement', 'contacts']
    .forEach(f => { formData.territoire_data[f] = getInputValue(f); });
    
    ['angle', 'fete', 'arc', 'moments', 'contraintes', 'sensibles', 'autorisations', 'budget', 'notes']
    .forEach(f => { formData.episode_data[f] = getInputValue(f); });
    
    // Collecte Gardiens (1-3)
    for (let i = 1; i <= 3; i++) {
        const g = {
            ordre: i,
            nom: getInputValue(`gardien${i}_nom`), prenom: getInputValue(`gardien${i}_prenom`),
            age: parseInt(getInputValue(`gardien${i}_age`)) || null, genre: getInputValue(`gardien${i}_genre`),
            fonction: getInputValue(`gardien${i}_fonction`), savoir_transmis: getInputValue(`gardien${i}_savoir`),
            adresse: getInputValue(`gardien${i}_adresse`), telephone: getInputValue(`gardien${i}_telephone`),
            email: getInputValue(`gardien${i}_email`), contact_intermediaire: getInputValue(`gardien${i}_contact`),
            histoire_personnelle: getInputValue(`gardien${i}_histoire`), evaluation_cinegenie: getInputValue(`gardien${i}_evaluation`),
            langues_parlees: getInputValue(`gardien${i}_langues`)
        };
        if (g.nom || g.prenom) formData.gardiens.push(g);
    }
    
    // Collecte Lieux (1-3)
    for (let i = 1; i <= 3; i++) {
        const l = {
            numero_lieu: i,
            nom: getInputValue(`lieu${i}_nom`), type_environnement: getInputValue(`lieu${i}_type`),
            description_visuelle: getInputValue(`lieu${i}_description`), elements_symboliques: getInputValue(`lieu${i}_elements`),
            points_vue_remarquables: getInputValue(`lieu${i}_points_vue`), cinegenie: getInputValue(`lieu${i}_cinegenie`),
            axes_camera: getInputValue(`lieu${i}_axes`), moments_favorables: getInputValue(`lieu${i}_moments`),
            ambiance_sonore: getInputValue(`lieu${i}_ambiance`), adequation_narration: getInputValue(`lieu${i}_adequation`),
            accessibilite: getInputValue(`lieu${i}_accessibilite`), securite: getInputValue(`lieu${i}_securite`),
            electricite: getInputValue(`lieu${i}_electricite`), espace_equipe: getInputValue(`lieu${i}_espace`),
            protection_meteo: getInputValue(`lieu${i}_protection`), contraintes_meteo: getInputValue(`lieu${i}_contraintes_meteo`),
            autorisations_necessaires: getInputValue(`lieu${i}_autorisations`)
        };
        if (l.nom) formData.lieux.push(l);
    }
    return formData;
}

// ============= COMPTEUR PROGRESSION =============
function calculateProgress() {
    const allInputs = document.querySelectorAll('input:not([type="file"]):not([type="hidden"]), textarea, select');
    let totalFields = 0;
    let filledFields = 0;
    
    allInputs.forEach(input => {
        if (input.disabled || input.readOnly) return;
        totalFields++;
        const value = input.value?.trim();
        if (value && value.length > 1) filledFields++;
    });
    
    const percentage = totalFields > 0 ? Math.round((filledFields / totalFields) * 100) : 0;
    updateProgressDisplay(percentage, filledFields, totalFields);
    return { percentage, filledFields, totalFields };
}

function updateProgressDisplay(percentage, filled, total) {
    const bar = document.getElementById('progress-bar');
    const textPercent = document.getElementById('progress-percentage');
    const textFilled = document.getElementById('progress-filled');
    const textTotal = document.getElementById('progress-total');
    
    if (bar) bar.style.width = percentage + '%';
    if (textPercent) textPercent.textContent = percentage + '%';
    
    // CORRECTIF : Mise à jour des chiffres bruts
    if (textFilled) textFilled.textContent = filled;
    if (textTotal) textTotal.textContent = total;
}

function initProgressTracking() {
    document.querySelectorAll('input, textarea, select').forEach(el => {
        el.addEventListener('change', calculateProgress);
    });
}

// ============= CHAT SYSTÈME =============
let lastMessagesJson = '';

function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    const sendBtn = document.getElementById('chat-send-btn');
    if (!toggle) return;

    toggle.addEventListener('click', () => {
        document.getElementById('chat-panel').classList.toggle('active');
        loadMessages();
    });

    sendBtn.addEventListener('click', sendMessage);
    setInterval(updateUnreadCount, 10000);
}

async function loadMessages() {
    if (!currentReperageId) return;
    const response = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const messages = await response.json();
    const chatContainer = document.getElementById('chat-messages');
    
    chatContainer.innerHTML = messages.map(msg => `
        <div class="chat-message ${msg.auteur_type}">
            <div class="chat-message-header"><strong>${msg.auteur_nom}</strong></div>
            <div class="chat-message-bubble">${msg.contenu}</div>
        </div>
    `).join('');
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const content = input.value.trim();
    if (!content || !currentReperageId) return;

    await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            auteur_type: 'fixer',
            auteur_nom: getInputValue('fixer_nom') || 'Fixer',
            contenu: content
        })
    });
    input.value = '';
    loadMessages();
}

async function updateUnreadCount() {
    // Logique simplifiée : les messages sont marqués lus à l'ouverture par l'admin
}

// ============= UPLOAD MÉDIAS =============
function initFileUpload() {
    const area = document.getElementById('drop-area');
    const input = document.getElementById('file-input');
    if (!area) return;

    area.addEventListener('click', () => input.click());
    input.addEventListener('change', (e) => handleFiles(e.target.files));
}

async function handleFiles(files) {
    for (let file of files) {
        const formData = new FormData();
        formData.append('file', file);
        await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, {
            method: 'POST',
            body: formData
        });
    }
    showNotification('Fichiers envoyés', 'success');
}

// ============= HELPERS =============
function getInputValue(name) {
    const el = document.querySelector(`[name="${name}"]`);
    return el ? el.value : '';
}

function setInputValue(name, value) {
    const el = document.querySelector(`[name="${name}"]`);
    if (el && value !== undefined) el.value = value;
}

function startAutoSave() {
    setInterval(() => saveReperage(false), 60000);
}

function initForms() {
    const btnSave = document.getElementById('btn-save');
    if (btnSave) btnSave.addEventListener('click', () => saveReperage(true));
}

function showNotification(msg, type) {
    const div = document.createElement('div');
    div.className = `notification ${type}`;
    div.textContent = msg;
    document.body.appendChild(div);
    setTimeout(() => div.remove(), 3000);
}

