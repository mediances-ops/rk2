/**
 * DOC-OS V.35 - SYSTEME INTEGRAL DE SYNCHRONISATION
 * Architecte : Denis Durand
 * Règle d'or : AUCUNE SIMPLIFICATION
 */

// ============= CONFIGURATION & ETAT GLOBAL =============
const API_URL = '/api';
let currentLanguage = localStorage.getItem('selectedLanguage') || 'FR';
let currentReperageId = window.REPERAGE_ID || null;
let translations = {};

// ============= INITIALISATION SYSTEME =============
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Lancement du Cerveau Front-end DOC-OS...');

    // Synchronisation avec les données injectées par Flask
    if (window.FIXER_DATA) {
        currentLanguage = window.FIXER_DATA.langue_default || 'FR';
        currentReperageId = window.FIXER_DATA.reperage_id;
    }

    // Chargement des modules critiques
    await loadTranslations(currentLanguage);
    initLanguageSelector();
    initTabs();
    initFileUpload();
    initChat();
    initForms();

    // Restauration de la Substance
    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); 
    }

    // Auto-sauvegarde de sécurité (toutes les 2 minutes)
    setInterval(() => saveReperage(false), 120000);
    
    if (typeof lucide !== 'undefined') lucide.createIcons();
});

// ============= MODULE 1 : MULTILINGUE (i18n) =============
async function loadTranslations(lang) {
    try {
        const response = await fetch(`${API_URL}/i18n/${lang}`);
        if (!response.ok) throw new Error('Dictionnaire inaccessible');
        translations = await response.json();
        
        // Traduction DATA-I18N (Libellés)
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translation = getNestedTranslation(translations, key);
            if (translation) el.textContent = translation;
        });

        // Traduction DATA-I18N-PLACEHOLDER (Inputs)
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            const translation = getNestedTranslation(translations, key);
            if (translation) el.placeholder = translation;
        });

        currentLanguage = lang;
        localStorage.setItem('selectedLanguage', lang);
    } catch (error) {
        console.error('Erreur i18n:', error);
    }
}

// Navigation récursive dans le JSON (Soudure i18n)
function getNestedTranslation(obj, path) {
    return path.split('.').reduce((prev, curr) => {
        return prev ? prev[curr] : null;
    }, obj);
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

// ============= MODULE 2 : CALCUL DE PROGRESSION (SYNC 112) =============
function calculateProgress() {
    const fields = document.querySelectorAll('input[name], textarea[name], select[name]');
    let total = 0;
    let filled = 0;

    fields.forEach(input => {
        // Exclusion stricte des métadonnées d'identité (5 champs)
        const excluded = ['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'];
        if (!excluded.includes(input.name)) {
            total++;
            // Validé si au moins 2 caractères saisis
            if (input.value && input.value.trim().length >= 2) {
                filled++;
            }
        }
    });

    const percentage = total > 0 ? Math.round((filled / total) * 100) : 0;
    
    // Pilotage visuel (Synchronisé 112 champs)
    const bar = document.getElementById('progress-bar');
    const textPercent = document.getElementById('progress-percentage');
    const textFilled = document.getElementById('progress-filled');

    if (bar) bar.style.width = percentage + '%';
    if (textPercent) textPercent.textContent = percentage + '%';
    if (textFilled) textFilled.textContent = filled;

    return percentage;
}

// ============= MODULE 3 : FLUX DE DONNÉES SEGMENTÉ (CRUD) =============
async function loadReperage(id) {
    try {
        const response = await fetch(`${API_URL}/reperages/${id}`);
        const data = await response.json();
        
        // 1. Remplissage des racines et des données JSON brutes
        document.querySelectorAll('input[name], textarea[name], select[name]').forEach(el => {
            const name = el.name;
            if (data[name]) el.value = data[name];
            else if (data.territoire_data && data.territoire_data[name]) el.value = data.territoire_data[name];
            else if (data.episode_data && data.episode_data[name]) el.value = data.episode_data[name];
        });

        // 2. Remplissage récursif des Gardiens (Segmentation SQL)
        if (data.gardiens) {
            data.gardiens.forEach(g => {
                Object.keys(g).forEach(key => {
                    const el = document.querySelector(`[name="gardien${g.ordre}_${key}"]`);
                    if (el) el.value = g[key];
                });
            });
        }

        // 3. Remplissage récursif des Lieux (Segmentation SQL)
        if (data.lieux) {
            data.lieux.forEach(l => {
                Object.keys(l).forEach(key => {
                    const el = document.querySelector(`[name="lieu${l.numero_lieu}_${key}"]`);
                    if (el) el.value = l[key];
                });
            });
        }

        // Déclenchement du calcul de pilotage (Délai de rendu DOM)
        setTimeout(calculateProgress, 1000);
    } catch (error) {
        console.error('Erreur chargement données:', error);
    }
}

async function saveReperage(showNotif = true) {
    if (!currentReperageId) return;

    const currentPercent = calculateProgress();
    const formData = collectFormData();
    formData.progression = currentPercent; // Envoi direct pour la Jauge Admin

    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (response.ok && showNotif) {
            alert("✅ Synchronisation réussie (" + currentPercent + "%)");
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

    // Définition des clés EPISODE (Segmentation pour impression)
    const episodeKeys = ['angle', 'fete', 'arc', 'moments', 'contraintes', 'sensibles', 'autorisations', 'budget', 'notes'];

    // 1. Collecte Gardiens (L'intégralité sans simplification)
    for (let i = 1; i <= 3; i++) {
        let g = { ordre: i };
        ['nom', 'prenom', 'age', 'genre', 'fonction', 'savoir', 'histoire', 'evaluation', 'langues', 'adresse', 'telephone', 'email', 'contact'].forEach(k => {
            const val = document.querySelector(`[name="gardien${i}_${k}"]`)?.value;
            if (val) g[k] = val;
        });
        if (g.nom || g.prenom) data.gardiens.push(g);
    }

    // 2. Collecte Lieux (L'intégralité sans simplification)
    for (let i = 1; i <= 3; i++) {
        let l = { numero_lieu: i };
        ['nom', 'type', 'description', 'cinegenie', 'axes', 'points_vue', 'moments', 'ambiance', 'adequation', 'accessibilite', 'securite', 'electricite', 'espace', 'protection', 'permis'].forEach(k => {
            const val = document.querySelector(`[name="lieu${i}_${k}"]`)?.value;
            if (val) l[k] = val;
        });
        if (l.nom) data.lieux.push(l);
    }

    // 3. Collecte des racines et segmentation JSON
    document.querySelectorAll('input[name], textarea[name], select[name]').forEach(el => {
        const name = el.name;
        const val = el.value;

        if (['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'].includes(name)) {
            data[name] = val;
        } else if (episodeKeys.includes(name)) {
            data.episode_data[name] = val;
        } else if (!name.startsWith('gardien') && !name.startsWith('lieu')) {
            data.territoire_data[name] = val;
        }
    });

    return data;
}

// ============= MODULE 4 : MÉDIAS (UPLOAD & PERSISTANCE) =============
function initFileUpload() {
    const area = document.getElementById('drop-area');
    const input = document.getElementById('file-input');
    if (!area || !input) return;

    area.onclick = () => input.click();
    input.onchange = async (e) => {
        for (let file of e.target.files) {
            const fd = new FormData(); 
            fd.append('file', file);
            await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd });
        }
        await loadMedias(); // Rafraîchissement immédiat de la galerie
        alert("📷 Photos sauvegardées.");
    };
}

async function loadMedias() {
    if (!currentReperageId) return;
    try {
        const response = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
        const medias = await response.json();
        const container = document.getElementById('files-list');
        if (container) {
            container.innerHTML = medias.map(m => `
                <div class="file-item" style="border: 1px solid #ddd; padding: 10px; border-radius: 8px; background: white; text-align:center;">
                    <img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width: 100%; height: 120px; object-fit: cover; border-radius: 4px;">
                    <span style="display: block; font-size: 0.7rem; margin-top: 5px; overflow: hidden; white-space: nowrap;">${m.nom_original}</span>
                </div>
            `).join('');
        }
    } catch (e) { console.error('Erreur chargement médias:', e); }
}

// ============= MODULE 5 : CHAT COLLABORATIF =============
function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    const sendBtn = document.getElementById('chat-send-btn');
    const closeBtn = document.getElementById('chat-close-btn');

    if (!toggle) return;

    toggle.onclick = () => {
        document.getElementById('chat-panel').style.right = '0';
        loadMessages();
    };

    closeBtn.onclick = () => {
        document.getElementById('chat-panel').style.right = '-400px';
    };

    sendBtn.onclick = async () => {
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
    };
}

async function loadMessages() {
    if (!currentReperageId) return;
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    const container = document.getElementById('chat-messages');
    container.innerHTML = msgs.map(m => `
        <div class="chat-message ${m.auteur_type}">
            <div class="chat-message-header"><strong>${m.auteur_nom}</strong></div>
            <div class="chat-message-bubble">${m.contenu}</div>
        </div>
    `).join('');
    container.scrollTop = container.scrollHeight;
}

// ============= MODULE 6 : INTERFACE (TABS & EVENTS) =============
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
        };
    });

    document.querySelectorAll('.lieu-tab').forEach(tab => {
        tab.onclick = () => {
            document.querySelectorAll('.lieu-tab, .lieu-content').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`lieu-${tab.dataset.lieu}`).classList.add('active');
        };
    });
}

function initForms() {
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    
    // Mise à jour de la jauge en temps réel (Debounce 500ms)
    document.querySelectorAll('input, textarea').forEach(el => {
        el.oninput = () => {
            clearTimeout(window.calcTimer);
            window.calcTimer = setTimeout(calculateProgress, 500);
        };
    });
}
