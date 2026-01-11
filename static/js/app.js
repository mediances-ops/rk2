/**
 * DOC-OS V.66 SUPRÊME MISSION CONTROL - SYNC ENGINE & CHAT MONITORING
 * SOUDURE FRONT-BACK : STRUCTURE RELATIONNELLE & 100 CHAMPS
 */

const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;
let isLocked = false;
let chatRefreshInterval = null;

document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Launching DOC-OS V.66 Supreme - Core Engine Integration');

    // 1. INITIALISATION DES LISTENERS
    initEventListeners();
    initTabs();
    initFileUpload();
    
    // 2. CHARGEMENT DES DONNÉES SI ID PRÉSENT
    if (currentReperageId) {
        await loadReperage();
        initChat(); // Initialise le chat et le polling
        await loadMedias();
    }
    
    // 3. LANCEMENT DU CALCUL DE PROGRESSION INITIAL
    calculateProgress();
});

/**
 * GESTION DES ÉVÉNEMENTS PRIORITAIRES
 */
function initEventListeners() {
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());
    
    // Surveillance en temps réel pour la progression
    document.querySelectorAll('input, textarea').forEach(el => {
        el.addEventListener('input', () => {
            if (!isLocked) calculateProgress();
        });
    });
}

/**
 * CALCUL DE PROGRESSION CERTIFIÉ (BASÉ SUR LA MATRICE 100)
 */
function calculateProgress() {
    // On cible uniquement les champs ayant un attribut "name" (données métier)
    const fields = document.querySelectorAll('.tab-content input[name], .tab-content textarea[name]');
    let filled = 0;
    let total = fields.length;

    fields.forEach(input => {
        // Un champ est considéré comme rempli s'il contient plus de 2 caractères
        if (input.value && input.value.trim().length > 2) {
            filled++;
        }
    });

    // On normalise sur une base 100 pour le contrat App 2
    // Même si le HTML contient un peu plus ou moins de 100 champs techniques
    const percent = Math.round((filled / total) * 100) || 0;
    
    // Mise à jour UI
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percentage');
    const progressFilled = document.getElementById('progress-filled');

    if (progressBar) progressBar.style.width = percent + '%';
    if (progressPercent) progressPercent.textContent = percent + '%';
    if (progressFilled) progressFilled.textContent = filled;

    return percent;
}

/**
 * CHARGEMENT ET HYDRATATION DU FORMULAIRE
 */
async function loadReperage() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`);
        const data = await res.json();

        if (res.status === 404) return;

        // Hydratation intelligente (mappage des champs plats et des réservoirs)
        document.querySelectorAll('input[name], textarea[name]').forEach(input => {
            const name = input.name;
            let value = null;

            // 1. Vérification dans les champs directs (Territoire / Fête)
            if (data[name] !== undefined) value = data[name];
            
            // 2. Vérification dans les réservoirs Territory (V.66)
            if (data.territory && data.territory[name] !== undefined) value = data.territory[name];
            
            // 3. Vérification dans les réservoirs Festivity (V.66)
            if (data.festivity && data.festivity[name] !== undefined) value = data.festivity[name];

            // 4. Vérification dans les Paires (Gardiens / Lieux)
            // Le moteur Python renvoie pair_1, pair_2, pair_3
            for (let i = 1; i <= 3; i++) {
                const pair = data[`pair_${i}`];
                if (pair) {
                    // On retire le préfixe pour matcher la clé JSON (ex: gardien1_nom -> nom)
                    const shortName = name.replace(`gardien${i}_`, '').replace(`lieu${i}_`, '');
                    if (pair[shortName] !== undefined) value = pair[shortName];
                }
            }

            if (value !== null) input.value = value;
        });

        // Verrouillage si le dossier n'est plus en brouillon
        if (data.statut !== 'brouillon') {
            lockInterface();
        }

        calculateProgress();
    } catch (e) {
        console.error("CRITICAL: Hydration failed", e);
    }
}

/**
 * SYNCHRONISATION DYNAMIQUE (BACK-END V.66 COMPATIBLE)
 */
async function saveReperage(showNotif) {
    if (isLocked) return;

    const progress = calculateProgress();
    const payload = { progression_pourcent: progress };

    // Collecte de tous les champs "name" du DOM
    document.querySelectorAll('input[name], textarea[name]').forEach(el => {
        payload[el.name] = el.value;
    });

    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.status === 403) {
            lockInterface();
            alert("⚠️ THIS DOSSIER IS LOCKED (SUBMITTED OR VALIDATED).");
            return;
        }

        if (res.ok && showNotif) {
            console.log("✅ SYNC SUCCESSFUL");
            // Optionnel : Notification visuelle légère
        }
    } catch (e) {
        console.error("SYNC ERROR", e);
    }
}

/**
 * WORKFLOW DE SOUMISSION FINALE
 */
async function submitToProduction() {
    if (isLocked) return;

    // Vérification sommaire des champs requis
    const required = document.querySelectorAll('[required]');
    let missing = [];
    required.forEach(el => {
        if (!el.value.trim()) {
            const label = el.previousElementSibling?.textContent || el.name;
            missing.push(label.replace('*', ''));
        }
    });

    if (missing.length > 0) {
        alert("⚠️ AT LEAST THESE FIELDS ARE REQUIRED :\n" + missing.join(", "));
        return;
    }

    if (confirm("🚀 DO YOU WANT TO SUBMIT THIS DOSSIER TO PRODUCTION?\nIt will be locked for further editing.")) {
        await saveReperage(false);
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}/submit`, { method: 'POST' });
        if (res.ok) {
            lockInterface();
            location.reload();
        }
    }
}

/**
 * GESTION DU CHAT AVEC POLLING (VISIBILITÉ DES NOTIFICATIONS)
 */
function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    const panel = document.getElementById('chat-panel');
    const sendBtn = document.getElementById('chat-send-btn');
    const input = document.getElementById('chat-input');

    if (!toggle) return;

    // Ouverture/Fermeture
    toggle.onclick = () => {
        panel.classList.toggle('active');
        if (panel.classList.contains('active')) {
            loadMessages();
            toggle.style.animation = 'none'; // Stop l'alerte visuelle
        }
    };

    document.getElementById('chat-close-btn').onclick = () => panel.classList.remove('active');

    // Envoi
    sendBtn.onclick = async () => {
        if (!input.value.trim()) return;
        const msg = {
            auteur_type: 'fixer',
            auteur_nom: 'Correspondent',
            contenu: input.value
        };
        await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(msg)
        });
        input.value = '';
        loadMessages();
    };

    // POLLING : Vérification toutes les 30 secondes des nouveaux messages
    chatRefreshInterval = setInterval(checkNewMessages, 30000);
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    const container = document.getElementById('chat-messages');
    
    if (container) {
        container.innerHTML = msgs.map(m => {
            const isFixer = m.auteur_type === 'fixer';
            return `
                <div class="msg-wrapper ${isFixer ? 'msg-fixer' : 'msg-production'}">
                    <div class="bubble">${m.contenu}</div>
                    <div class="meta">${m.auteur_nom}</div>
                </div>
            `;
        }).join('');
        container.scrollTop = container.scrollHeight;
    }
}

async function checkNewMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    const lastMsg = msgs[msgs.length - 1];
    const panel = document.getElementById('chat-panel');

    // Si le dernier message vient de la production et que le chat est fermé
    if (lastMsg && lastMsg.auteur_type === 'production' && !panel.classList.contains('active')) {
        const toggle = document.getElementById('chat-toggle-btn');
        toggle.style.animation = 'pulse 1s infinite'; // Alerte visuelle (besoin du CSS pulse)
    }
}

/**
 * VERROUILLAGE PHYSIQUE DE L'INTERFACE
 */
function lockInterface() {
    isLocked = true;
    const banner = document.getElementById('lock-banner');
    if (banner) banner.style.display = 'block';

    document.querySelectorAll('input, textarea, select, .btn').forEach(el => {
        // On ne bloque pas le chat ni les boutons de navigation
        if (!el.classList.contains('chat-toggle-btn') && el.id !== 'chat-close-btn') {
            el.disabled = true;
            el.style.opacity = '0.6';
            el.style.pointerEvents = 'none';
        }
    });
}

/**
 * UTILITAIRES (TABS & FILES)
 */
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
        };
    });
}

function initFileUpload() {
    const area = document.getElementById('drop-area');
    const input = document.getElementById('file-input');
    if (!area) return;

    area.onclick = () => input.click();
    
    input.onchange = async (e) => {
        for (let file of e.target.files) {
            const fd = new FormData();
            fd.append('file', file);
            await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd });
        }
        await loadMedias();
    };
}

async function loadMedias() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
    const ms = await res.json();
    const list = document.getElementById('files-list');
    if (list) {
        list.innerHTML = ms.map(m => `
            <div class="file-item">
                <img src="/uploads/${currentReperageId}/${m.nom_fichier}" alt="Media">
            </div>
        `).join('');
    }
}
