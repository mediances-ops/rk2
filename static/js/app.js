// ============= CONFIGURATION =============
const API_URL = '/api';
let currentLanguage = localStorage.getItem('selectedLanguage') || 'FR';
let currentReperageId = localStorage.getItem('currentReperageId') || null;
let translations = {};
let autoSaveTimer = null;

// ============= INITIALISATION =============
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Initialisation du formulaire de repérage');
    
    // NOUVEAU : Vérifier si des données fixer sont passées par Flask
    console.log('🔍 DEBUG: window.FIXER_DATA =', window.FIXER_DATA);
    
    if (window.FIXER_DATA) {
        console.log('📋 Données fixer détectées:', window.FIXER_DATA);
        
        // Utiliser la langue du fixer
        if (window.FIXER_DATA.langue_default) {
            currentLanguage = window.FIXER_DATA.langue_default;
            localStorage.setItem('selectedLanguage', currentLanguage);
            console.log('✅ Langue définie:', currentLanguage);
        }
        
        // Si un repérage existant est fourni, l'utiliser
        if (window.FIXER_DATA.reperage_id) {
            currentReperageId = window.FIXER_DATA.reperage_id;
            localStorage.setItem('currentReperageId', currentReperageId);
            console.log('📂 Repérage en brouillon trouvé:', currentReperageId);
        } else {
            console.log('📄 Aucun brouillon existant');
        }
    } else {
        console.log('⚠️ Aucune donnée FIXER_DATA détectée');
    }
    
    // Charger les traductions
    await loadTranslations(currentLanguage);
    
    // Initialiser les event listeners
    initLanguageSelector();
    initTabs();
    initForms();
    initFileUpload();
    initProgressTracking(); // NOUVEAU: Initialiser le compteur de progression
    initChat(); // NOUVEAU: Initialiser le système de chat
    
    // Charger ou créer un repérage
    await initReperage();
    
    // NOUVEAU : Pré-remplir les champs fixer si des données sont fournies
    if (window.FIXER_DATA) {
        console.log('🔧 Tentative de pré-remplissage des champs...');
        setTimeout(() => {
            if (window.FIXER_DATA.fixer_nom) {
                console.log('  → Nom:', window.FIXER_DATA.fixer_nom);
                const nomInput = document.querySelector('input[name="fixer_nom"]');
                console.log('  → Input nom trouvé:', nomInput);
                if (nomInput) nomInput.value = window.FIXER_DATA.fixer_nom;
            }
            if (window.FIXER_DATA.fixer_email) {
                console.log('  → Email:', window.FIXER_DATA.fixer_email);
                const emailInput = document.querySelector('input[name="fixer_email"]');
                console.log('  → Input email trouvé:', emailInput);
                if (emailInput) emailInput.value = window.FIXER_DATA.fixer_email;
            }
            if (window.FIXER_DATA.fixer_telephone) {
                console.log('  → Téléphone:', window.FIXER_DATA.fixer_telephone);
                const telInput = document.querySelector('input[name="fixer_telephone"]');
                console.log('  → Input tel trouvé:', telInput);
                if (telInput) telInput.value = window.FIXER_DATA.fixer_telephone;
            }
            console.log('✅ Pré-remplissage terminé');
        }, 1000);
    }
    
    // Auto-sauvegarde toutes les 30 secondes
    startAutoSave();
    
    console.log('✅ Formulaire prêt !');
});

// ============= TRADUCTIONS =============
async function loadTranslations(lang) {
    try {
        const response = await fetch(`${API_URL}/i18n/${lang}`);
        translations = await response.json();
        applyTranslations();
        currentLanguage = lang;
        localStorage.setItem('selectedLanguage', lang);
    } catch (error) {
        console.error('Erreur chargement traductions:', error);
    }
}

function applyTranslations() {
    console.log("🌍 Application des traductions...");
    
    try {
        // 1. Traduire les éléments avec data-i18n (LABELS, TITRES)
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            const translation = getNestedTranslation(translations, key);
            
            if (translation) {
                element.textContent = translation;
            }
        });
        
        // 2. Traduire les placeholders avec data-i18n-placeholder
        document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
            const key = element.getAttribute('data-i18n-placeholder');
            const translation = getNestedTranslation(translations, key);
            
            if (translation) {
                element.placeholder = translation;
            }
        });
        
        console.log("✅ Traductions appliquées avec succès!");
        
    } catch (error) {
        console.error("❌ Erreur application traductions:", error);
    }
}

// Fonction helper pour naviguer dans l'objet JSON
function getNestedTranslation(obj, path) {
    const keys = path.split('.');
    let result = obj;
    
    for (const key of keys) {
        if (result && result[key] !== undefined) {
            result = result[key];
        } else {
            return null;
        }
    }
    
    return result;
}

// Fonction helper pour naviguer dans l'objet JSON
function getNestedTranslation(obj, path) {
    const keys = path.split('.');
    let result = obj;
    
    for (const key of keys) {
        if (result && result[key] !== undefined) {
            result = result[key];
        } else {
            return null;
        }
    }
    
    return result;
}

// Fonction helper pour naviguer dans l'objet JSON
function getNestedTranslation(obj, path) {
    const keys = path.split('.');
    let result = obj;
    
    for (const key of keys) {
        if (result && result[key] !== undefined) {
            result = result[key];
        } else {
            console.warn(`⚠️ Clé introuvable: ${path}`);
            return null;
        }
    }
    
    return result;
}

function initLanguageSelector() {
    const langButtons = document.querySelectorAll('.lang-btn');
    
    // Marquer la langue active
    langButtons.forEach(btn => {
        if (btn.dataset.lang === currentLanguage) {
            btn.classList.add('active');
        }
        
        btn.addEventListener('click', async function() {
            langButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            await loadTranslations(this.dataset.lang);
        });
    });
}

// ============= ONGLETS =============
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            
            // Retirer classe active
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            // Ajouter classe active
            this.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });
    
    // NOUVEAUX TABS POUR LES 3 LIEUX
    const lieuTabs = document.querySelectorAll('.lieu-tab');
    const lieuContents = document.querySelectorAll('.lieu-content');
    
    lieuTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const lieuNum = this.getAttribute('data-lieu');
            
            // Retirer classe active
            lieuTabs.forEach(t => t.classList.remove('active'));
            lieuContents.forEach(c => c.classList.remove('active'));
            
            // Ajouter classe active
            this.classList.add('active');
            document.getElementById(`lieu-${lieuNum}`).classList.add('active');
        });
    });
}

// ============= GESTION REPÉRAGE =============
async function initReperage() {
    if (currentReperageId) {
        // Charger repérage existant
        await loadReperage(currentReperageId);
    } else {
        // NE PLUS créer automatiquement de repérage
        // Afficher message d'instruction
        console.log('ℹ️ Aucun repérage actif. Veuillez utiliser le bouton "Nouveau Repérage" depuis le dashboard admin.');
    }
}

async function createNewReperage() {
    try {
        const response = await fetch(`${API_URL}/reperages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                langue_interface: currentLanguage,
                statut: 'brouillon'
            })
        });
        
        const reperage = await response.json();
        currentReperageId = reperage.id;
        localStorage.setItem('currentReperageId', currentReperageId);
        
        console.log('✅ Nouveau repérage créé:', reperage.id);
        showNotification('Nouveau repérage créé', 'success');
    } catch (error) {
        console.error('Erreur création repérage:', error);
        showNotification('Erreur lors de la création', 'error');
    }
}

async function loadReperage(id) {
    try {
        const response = await fetch(`${API_URL}/reperages/${id}`);
        if (!response.ok) {
            throw new Error(`Repérage ${id} non trouvé`);
        }
        const reperage = await response.json();
        
        // Remplir les formulaires avec les données
        fillFormData(reperage);
        
        console.log('✅ Repérage chargé:', id);
    } catch (error) {
        console.error('Erreur chargement repérage:', error);
        // NE PLUS créer automatiquement si le repérage n'existe pas
        // L'utilisateur doit utiliser le modal "Nouveau Repérage" depuis le dashboard
        showNotification('Repérage non trouvé', 'error');
        currentReperageId = null;
        localStorage.removeItem('currentReperageId');
    }
}

function fillFormData(reperage) {
    // Fixer info
    setInputValue('fixer_nom', reperage.fixer_nom);
    setInputValue('fixer_email', reperage.fixer_email);
    setInputValue('fixer_telephone', reperage.fixer_telephone);
    
    // Territoire
    setInputValue('pays', reperage.pays);
    setInputValue('region', reperage.region);
    
    if (reperage.territoire_data) {
        Object.keys(reperage.territoire_data).forEach(key => {
            setInputValue(key, reperage.territoire_data[key]);
        });
    }
    
    // Épisode
    if (reperage.episode_data) {
        Object.keys(reperage.episode_data).forEach(key => {
            setInputValue(key, reperage.episode_data[key]);
        });
    }
    
    // Gardiens
    if (reperage.gardiens && reperage.gardiens.length > 0) {
        reperage.gardiens.forEach((gardien, index) => {
            fillGardienData(gardien, index + 1);
        });
    }
}

function setInputValue(name, value) {
    const input = document.querySelector(`[name="${name}"]`);
    if (input && value) {
        input.value = value;
    }
}

function fillGardienData(gardien, ordre) {
    Object.keys(gardien).forEach(key => {
        setInputValue(`gardien${ordre}_${key}`, gardien[key]);
    });
}

// ============= SAUVEGARDE AUTOMATIQUE =============
function startAutoSave() {
    autoSaveTimer = setInterval(async () => {
        await saveReperage(false);
    }, 30000); // 30 secondes
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
        
        const result = await response.json();
        
        if (showMessage) {
            showNotification('Sauvegarde réussie', 'success');
        }
        
        console.log('💾 Sauvegarde automatique effectuée');
    } catch (error) {
        console.error('Erreur sauvegarde:', error);
        if (showMessage) {
            showNotification('Erreur lors de la sauvegarde', 'error');
        }
    }
}

function collectFormData() {
    const formData = {
        langue_interface: currentLanguage,
        fixer_nom: getInputValue('fixer_nom'),
        fixer_email: getInputValue('fixer_email'),
        fixer_telephone: getInputValue('fixer_telephone'),
        pays: getInputValue('pays'),
        region: getInputValue('region'),
        territoire_data: {},
        episode_data: {},
        gardiens: [],  // ✅ NOUVEAU
        lieux: []      // ✅ NOUVEAU
    };
    
    // Collecter données territoire
    const territoireFields = ['ville', 'population', 'langues', 'climat', 'histoire', 
                              'traditions', 'fetes', 'acces', 'hebergement', 'contacts'];
    territoireFields.forEach(field => {
        const value = getInputValue(field);
        if (value) formData.territoire_data[field] = value;
    });
    
    // Collecter données épisode
    const episodeFields = ['angle', 'fete', 'arc', 'moments', 'contraintes', 
                           'sensibles', 'autorisations', 'budget', 'notes'];
    episodeFields.forEach(field => {
        const value = getInputValue(field);
        if (value) formData.episode_data[field] = value;
    });
    
    // ✅ NOUVEAU : Collecter les 3 gardiens
    for (let i = 1; i <= 3; i++) {
        const gardienData = {
            ordre: i,
            nom: getInputValue(`gardien${i}_nom`),
            prenom: getInputValue(`gardien${i}_prenom`),
            age: parseInt(getInputValue(`gardien${i}_age`)) || null,
            genre: getInputValue(`gardien${i}_genre`),
            fonction: getInputValue(`gardien${i}_fonction`),
            savoir_transmis: getInputValue(`gardien${i}_savoir`),
            adresse: getInputValue(`gardien${i}_adresse`),
            telephone: getInputValue(`gardien${i}_telephone`),
            email: getInputValue(`gardien${i}_email`),
            contact_intermediaire: getInputValue(`gardien${i}_contact`),
            histoire_personnelle: getInputValue(`gardien${i}_histoire`),
            evaluation_cinegenie: getInputValue(`gardien${i}_evaluation`),
            langues_parlees: getInputValue(`gardien${i}_langues`)
        };
        
        // Ajouter seulement si au moins le nom est rempli
        if (gardienData.nom || gardienData.prenom) {
            formData.gardiens.push(gardienData);
        }
    }
    
    // ✅ NOUVEAU : Collecter les 3 lieux
    for (let i = 1; i <= 3; i++) {
        const lieuData = {
            numero_lieu: i,
            nom: getInputValue(`lieu${i}_nom`),
            type_environnement: getInputValue(`lieu${i}_type`),
            description_visuelle: getInputValue(`lieu${i}_description`),
            elements_symboliques: getInputValue(`lieu${i}_elements`),
            points_vue_remarquables: getInputValue(`lieu${i}_points_vue`),
            cinegenie: getInputValue(`lieu${i}_cinegenie`),
            axes_camera: getInputValue(`lieu${i}_axes`),
            moments_favorables: getInputValue(`lieu${i}_moments`),
            ambiance_sonore: getInputValue(`lieu${i}_ambiance`),
            adequation_narration: getInputValue(`lieu${i}_adequation`),
            accessibilite: getInputValue(`lieu${i}_accessibilite`),
            securite: getInputValue(`lieu${i}_securite`),
            electricite: getInputValue(`lieu${i}_electricite`),
            espace_equipe: getInputValue(`lieu${i}_espace`),
            protection_meteo: getInputValue(`lieu${i}_protection`),
            contraintes_meteo: getInputValue(`lieu${i}_contraintes_meteo`),
            autorisations_necessaires: getInputValue(`lieu${i}_autorisations`)
        };
        
        // Ajouter seulement si au moins le nom est rempli
        if (lieuData.nom) {
            formData.lieux.push(lieuData);
        }
    }
    
    return formData;
}

function getInputValue(name) {
    const input = document.querySelector(`[name="${name}"]`);
    return input ? input.value : '';
}

// ============= GARDIENS =============
async function saveGardien(ordre) {
    if (!currentReperageId) return;
    
    const gardienData = {
        ordre: ordre,
        nom: getInputValue(`gardien${ordre}_nom`),
        prenom: getInputValue(`gardien${ordre}_prenom`),
        age: parseInt(getInputValue(`gardien${ordre}_age`)) || null,
        genre: getInputValue(`gardien${ordre}_genre`),
        fonction: getInputValue(`gardien${ordre}_fonction`),
        savoir_transmis: getInputValue(`gardien${ordre}_savoir`),
        adresse: getInputValue(`gardien${ordre}_adresse`),
        telephone: getInputValue(`gardien${ordre}_telephone`),
        email: getInputValue(`gardien${ordre}_email`),
        contact_intermediaire: getInputValue(`gardien${ordre}_contact`),
        histoire_personnelle: getInputValue(`gardien${ordre}_histoire`),
        evaluation_cinegenie: getInputValue(`gardien${ordre}_evaluation`),
        langues_parlees: getInputValue(`gardien${ordre}_langues`)
    };
    
    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}/gardiens`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(gardienData)
        });
        
        const result = await response.json();
        console.log('✅ Gardien sauvegardé:', result);
    } catch (error) {
        console.error('Erreur sauvegarde gardien:', error);
    }
}

// ============= UPLOAD FICHIERS =============
function initFileUpload() {
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    const filesList = document.getElementById('files-list');
    
    if (!dropArea || !fileInput) return;
    
    // Clic sur zone pour ouvrir sélecteur
    dropArea.addEventListener('click', () => fileInput.click());
    
    // Drag & Drop
    dropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropArea.classList.add('drag-over');
    });
    
    dropArea.addEventListener('dragleave', () => {
        dropArea.classList.remove('drag-over');
    });
    
    dropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dropArea.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        handleFiles(files);
    });
    
    // Sélection de fichiers
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });
}

async function handleFiles(files) {
    const fileArray = Array.from(files);
    
    for (let file of fileArray) {
        await uploadFile(file);
    }
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('categorie', 'general');
    
    const progressBar = document.getElementById('upload-progress');
    const progressBarFill = document.querySelector('.progress-bar');
    const progressText = document.querySelector('.progress-text');
    
    if (progressBar) {
        progressBar.classList.add('active');
        progressText.textContent = `Upload de ${file.name}...`;
    }
    
    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        // Ajouter à la liste des fichiers
        addFileToPreview(result);
        
        showNotification('Fichier uploadé avec succès', 'success');
        
        if (progressBar) {
            progressBar.classList.remove('active');
        }
    } catch (error) {
        console.error('Erreur upload:', error);
        showNotification('Erreur lors de l\'upload', 'error');
        
        if (progressBar) {
            progressBar.classList.remove('active');
        }
    }
}

function addFileToPreview(media) {
    const filesList = document.getElementById('files-list');
    if (!filesList) return;
    
    const fileItem = document.createElement('div');
    fileItem.className = 'file-item';
    fileItem.innerHTML = `
        ${media.type === 'photo' ? `<img src="/uploads/thumbnails/thumb_${media.nom_fichier}" alt="${media.nom_original}">` : ''}
        <span>${media.nom_original}</span>
        <button class="delete-btn" onclick="deleteFile(${media.id})">×</button>
    `;
    
    filesList.appendChild(fileItem);
}

async function deleteFile(mediaId) {
    if (!confirm('Supprimer ce fichier ?')) return;
    
    try {
        await fetch(`${API_URL}/medias/${mediaId}`, {
            method: 'DELETE'
        });
        
        // Recharger la liste
        await loadMedias();
        
        showNotification('Fichier supprimé', 'success');
    } catch (error) {
        console.error('Erreur suppression:', error);
        showNotification('Erreur lors de la suppression', 'error');
    }
}

async function loadMedias() {
    if (!currentReperageId) return;
    
    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
        const medias = await response.json();
        
        const filesList = document.getElementById('files-list');
        if (filesList) {
            filesList.innerHTML = '';
            medias.forEach(media => addFileToPreview(media));
        }
    } catch (error) {
        console.error('Erreur chargement médias:', error);
    }
}

// ============= FORMULAIRES =============
function initForms() {
    // Empêcher soumission par défaut des formulaires
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            saveReperage(true);
        });
    });
    
    // Boutons d'action
    const btnSave = document.getElementById('btn-save');
    const btnSubmit = document.getElementById('btn-submit');
    const btnExportPdf = document.getElementById('btn-export-pdf');
    
    if (btnSave) {
        btnSave.addEventListener('click', () => saveReperage(true));
    }
    
    if (btnSubmit) {
        btnSubmit.addEventListener('click', async () => {
            await submitReperage();
        });
    }
    
    if (btnExportPdf) {
        btnExportPdf.addEventListener('click', () => exportPdf());
    }
}

async function submitReperage() {
    if (!currentReperageId) return;
    
    if (!confirm('Voulez-vous soumettre ce repérage ? Il ne pourra plus être modifié.')) {
        return;
    }
    
    try {
        // D'abord sauvegarder
        await saveReperage(false);
        
        // Puis soumettre
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}/submit`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        showNotification('Repérage soumis avec succès !', 'success');
        
        // Désactiver les champs de formulaire
        document.querySelectorAll('input, textarea').forEach(el => {
            el.disabled = true;
        });
    } catch (error) {
        console.error('Erreur soumission:', error);
        showNotification('Erreur lors de la soumission', 'error');
    }
}

function exportPdf() {
    showNotification('Export PDF en cours...', 'info');
    window.open(`/admin/reperage/${currentReperageId}/pdf`, '_blank');
}

// ============= NOTIFICATIONS =============
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// ============= COMPTEUR DE PROGRESSION =============
function calculateProgress() {
    const allInputs = document.querySelectorAll('input:not([type="file"]):not([type="hidden"]), textarea, select');
    let totalFields = 0;
    let filledFields = 0;
    
    allInputs.forEach(input => {
        // Ignorer les champs désactivés ou en lecture seule
        if (input.disabled || input.readOnly) return;
        
        totalFields++;
        
        // Vérifier si le champ est rempli
        const value = input.value?.trim();
        if (value && value.length > 0) {
            filledFields++;
        }
    });
    
    // Calculer le pourcentage
    const percentage = totalFields > 0 ? Math.round((filledFields / totalFields) * 100) : 0;
    
    // Mettre à jour l'interface
    updateProgressDisplay(percentage, filledFields, totalFields);
    
    return { percentage, filledFields, totalFields };
}

function updateProgressDisplay(percentage, filled, total) {
    const progressBar = document.getElementById('progress-bar');
    const progressPercentage = document.getElementById('progress-percentage');
    const progressFilled = document.getElementById('progress-filled');
    const progressTotal = document.getElementById('progress-total');
    
    if (progressBar) {
        progressBar.style.width = percentage + '%';
    }
    
    if (progressPercentage) {
        progressPercentage.textContent = percentage + '%';
    }
    
    if (progressFilled) {
        progressFilled.textContent = filled;
    }
    
    if (progressTotal) {
        progressTotal.textContent = total;
    }
    
    // Changer la couleur selon la progression
    const container = document.getElementById('progress-container');
    if (container) {
        if (percentage < 30) {
            container.style.background = 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)';
        } else if (percentage < 70) {
            container.style.background = 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)';
        } else {
            container.style.background = 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)';
        }
    }
}

// Mettre à jour la progression à chaque changement
function initProgressTracking() {
    const allInputs = document.querySelectorAll('input:not([type="file"]):not([type="hidden"]), textarea, select');
    
    allInputs.forEach(input => {
        input.addEventListener('input', () => {
            // Débounce pour éviter trop de calculs
            clearTimeout(window.progressTimer);
            window.progressTimer = setTimeout(calculateProgress, 500);
        });
        
        input.addEventListener('change', calculateProgress);
    });
    
    // Calcul initial
    setTimeout(calculateProgress, 1000);
}

// ============= UTILITAIRES =============
// Nettoyer avant de quitter
window.addEventListener('beforeunload', (e) => {
    saveReperage(false);
});

// ============= SYSTÈME DE CHAT =============
let chatOpen = false;
let chatPollingInterval = null;
let lastMessageCount = 0;
let lastMessagesJsonFixer = ''; // Pour détecter les changements

function initChat() {
    const chatToggleBtn = document.getElementById('chat-toggle-btn');
    const chatCloseBtn = document.getElementById('chat-close-btn');
    const chatPanel = document.getElementById('chat-panel');
    const chatInput = document.getElementById('chat-input');
    const chatSendBtn = document.getElementById('chat-send-btn');
    
    if (!chatToggleBtn) return;
    
    // Ouvrir/fermer le chat
    chatToggleBtn.addEventListener('click', () => {
        chatOpen = !chatOpen;
        chatPanel.classList.toggle('active', chatOpen);
        
        if (chatOpen) {
            lastMessagesJsonFixer = ''; // Reset
            loadMessages();
            startChatPolling();
            chatInput.focus();
        } else {
            stopChatPolling();
        }
    });
    
    chatCloseBtn.addEventListener('click', () => {
        chatOpen = false;
        chatPanel.classList.remove('active');
        stopChatPolling();
    });
    
    // Envoyer message
    chatSendBtn.addEventListener('click', sendMessage);
    
    // Entrée pour envoyer (Shift+Entrée = saut de ligne)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Indicateur "en train d'écrire..."
    let typingTimeout;
    chatInput.addEventListener('input', () => {
        clearTimeout(typingTimeout);
        // Ici on pourrait envoyer une notification "en train d'écrire"
        // Pour une version future avec WebSockets
    });
    
    // Charger le compteur de messages non lus
    updateUnreadCount();
    
    // Polling périodique pour nouveaux messages (si chat fermé)
    setInterval(() => {
        if (!chatOpen) {
            updateUnreadCount();
        }
    }, 10000); // Toutes les 10 secondes
}

async function loadMessages() {
    if (!currentReperageId) return;
    
    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
        if (!response.ok) throw new Error('Erreur chargement messages');
        
        const messages = await response.json();
        
        // Vérifier si les messages ont changé
        const newMessagesJson = JSON.stringify(messages);
        if (newMessagesJson === lastMessagesJsonFixer) {
            // Pas de changement, ne rien faire
            return;
        }
        
        // Messages ont changé, mettre à jour
        lastMessagesJsonFixer = newMessagesJson;
        displayMessages(messages);
        
        // Marquer les messages de la production comme lus
        markProductionMessagesAsRead(messages);
        
        // Scroll vers le bas
        scrollToBottom();
        
    } catch (error) {
        console.error('Erreur chargement messages:', error);
    }
}

function displayMessages(messages) {
    const chatMessages = document.getElementById('chat-messages');
    
    if (messages.length === 0) {
        chatMessages.innerHTML = `
            <div class="chat-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
                <p>Aucun message pour le moment</p>
                <small>Les messages avec la production apparaîtront ici</small>
            </div>
        `;
        return;
    }
    
    chatMessages.innerHTML = messages.map(msg => {
        const date = new Date(msg.created_at);
        const timeStr = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
        
        return `
            <div class="chat-message ${msg.auteur_type}">
                <div class="chat-message-header">
                    <span class="chat-message-author ${msg.auteur_type}">${msg.auteur_nom}</span>
                    <span class="chat-message-time">${timeStr}</span>
                </div>
                <div class="chat-message-bubble">
                    ${escapeHtml(msg.contenu)}
                </div>
            </div>
        `;
    }).join('');
}

async function sendMessage() {
    const chatInput = document.getElementById('chat-input');
    const content = chatInput.value.trim();
    
    if (!content || !currentReperageId) {
        console.warn('❌ Impossible envoyer message:', { content, currentReperageId });
        return;
    }
    
    try {
        // Récupérer le nom du fixer de plusieurs sources
        let auteurNom = 'Fixer';
        
        // Source 1: FIXER_DATA injecté par Flask
        if (window.FIXER_DATA?.fixer_nom) {
            auteurNom = window.FIXER_DATA.fixer_nom;
        } 
        // Source 2: Champ du formulaire
        else {
            const nomInput = document.querySelector('[name="fixer_nom"]');
            if (nomInput && nomInput.value) {
                auteurNom = nomInput.value;
            }
        }
        
        console.log('📤 Envoi message:', { auteurNom, content, reperageId: currentReperageId });
        
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                auteur_type: 'fixer',
                auteur_nom: auteurNom,
                contenu: content
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            console.error('❌ Erreur API:', errorData);
            throw new Error('Erreur envoi message');
        }
        
        console.log('✅ Message envoyé avec succès');
        
        // Vider l'input
        chatInput.value = '';
        
        // Recharger les messages
        await loadMessages();
        
        showNotification('Message envoyé', 'success');
        
    } catch (error) {
        console.error('❌ Erreur envoi message:', error);
        showNotification('Erreur lors de l\'envoi du message', 'error');
    }
}

async function markProductionMessagesAsRead(messages) {
    const unreadProductionMessages = messages.filter(msg => 
        msg.auteur_type === 'production' && !msg.lu
    );
    
    for (const msg of unreadProductionMessages) {
        try {
            await fetch(`${API_URL}/messages/${msg.id}/read`, {
                method: 'PUT'
            });
        } catch (error) {
            console.error('Erreur marquage lu:', error);
        }
    }
    
    // Mettre à jour le badge
    updateUnreadCount();
}

async function updateUnreadCount() {
    if (!currentReperageId) return;
    
    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}/messages/unread-count?for=fixer`);
        if (!response.ok) return;
        
        const data = await response.json();
        const badge = document.getElementById('chat-badge');
        
        if (badge) {
            if (data.count > 0) {
                badge.textContent = data.count;
                badge.style.display = 'flex';
            } else {
                badge.style.display = 'none';
            }
        }
        
    } catch (error) {
        console.error('Erreur comptage messages non lus:', error);
    }
}

function startChatPolling() {
    // Recharger les messages toutes les 5 secondes quand le chat est ouvert
    chatPollingInterval = setInterval(loadMessages, 5000);
}

function stopChatPolling() {
    if (chatPollingInterval) {
        clearInterval(chatPollingInterval);
        chatPollingInterval = null;
    }
}

function scrollToBottom() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
}
// AJOUTE CE CODE À LA FIN DE TON app.js POUR VOIR CE QUI SE PASSE

console.log("=== DEBUG I18N ===");

// Vérifier si les traductions se chargent
document.addEventListener('DOMContentLoaded', async () => {
    console.log("🔍 Test chargement traductions...");
    
    try {
        const response = await fetch('/api/i18n/FR');
        const data = await response.json();
        console.log("✅ Traductions FR chargées:", data);
        console.log("📝 Structure:", Object.keys(data));
        
        // Vérifier si les éléments existent
        const elementsWithI18n = document.querySelectorAll('[data-i18n]');
        console.log(`📌 ${elementsWithI18n.length} éléments avec data-i18n trouvés`);
        
        const elementsWithPlaceholder = document.querySelectorAll('[data-i18n-placeholder]');
        console.log(`📌 ${elementsWithPlaceholder.length} éléments avec data-i18n-placeholder trouvés`);
        
        // Tester l'application des traductions
        if (window.applyTranslations) {
            console.log("🔧 Fonction applyTranslations existe");
            window.translations = data;
            window.applyTranslations();
            console.log("✅ applyTranslations() appelée");
        } else {
            console.error("❌ Fonction applyTranslations introuvable!");
        }
        
    } catch (error) {
        console.error("❌ Erreur:", error);
    }
});

console.log("=== FIN DEBUG I18N ===");