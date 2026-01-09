/**
 * DOC-OS V.48 - SYNCHRONISATION TOTALE & FIX MÉDIAS
 */
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
    initForms();
    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); 
    }
    // SOUDURE BOUTONS (FIX 1 & 5)
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());
});

// FIX 7 & 4 : i18n RÉCURSIF SOUDÉ
async function loadTranslations(lang) {
    try {
        const response = await fetch(`${API_URL}/i18n/${lang}`);
        translations = await response.json();
        applyTranslations();
        currentLanguage = lang;
        localStorage.setItem('selectedLanguage', lang);
    } catch (e) { console.error("i18n Failure", e); }
}

function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const val = key.split('.').reduce((p, c) => p && p[c], translations);
        if (val) el.textContent = val;
    });
}

// FIX 1 & 4 : UPLOAD & ACTUALISATION PHOTO
function initFileUpload() {
    const area = document.getElementById('drop-area');
    if (!area) return;
    area.onclick = () => document.getElementById('file-input').click();
    document.getElementById('file-input').onchange = async (e) => {
        for (let file of e.target.files) {
            const fd = new FormData();
            fd.append('file', file);
            const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd });
            if (res.ok) console.log("Photo Upload OK");
        }
        await loadMedias(); // ACTUALISATION IMMÉDIATE
        alert("📷 Photos enregistrées sur le serveur.");
    };
}

async function loadMedias() {
    if (!currentReperageId) return;
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
    const ms = await res.json();
    const list = document.getElementById('files-list');
    if (list) {
        list.innerHTML = ms.map(m => `
            <div class="file-item" style="border:1px solid #ddd; padding:10px; border-radius:12px; text-align:center; background:white;">
                <img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%;height:140px;object-fit:cover;border-radius:8px;">
                <small style="display:block;margin-top:5px;overflow:hidden;white-space:nowrap;">${m.nom_original}</small>
            </div>
        `).join('');
    }
}

// FIX 3 : SAUVEGARDE SEGMENTÉE (ZÉRO PERTE)
async function saveReperage(notif) {
    const p = calculateProgress();
    const data = { progression: p, territoire_data: {}, particularite_data: {}, fete_data: {}, episode_data: {}, gardiens: [], lieux: [] };
    
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
    // Mapping 5 Réservoirs
    const partKeys = ['angle', 'fete_nom', 'contraintes', 'arc', 'moments', 'sensibles', 'budget', 'notes'];
    const feteKeys = ['fete_lieu_date', 'fete_pourquoi', 'fete_origines', 'fete_deroulement', 'fete_visuel', 'fete_responsable'];

    document.querySelectorAll('input[name], textarea[name]').forEach(el => {
        if (['fixer_nom', 'pays', 'region'].includes(el.name)) data[el.name] = el.value;
        else if (partKeys.includes(el.name)) data.particularite_data[el.name] = el.value;
        else if (feteKeys.includes(el.name)) data.fete_data[el.name] = el.value;
        else if (!el.name.startsWith('gardien') && !el.name.startsWith('lieu')) data.territoire_data[el.name] = el.value;
    });

    const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
    if (res.ok && notif) alert("✅ Brouillon Synchronisé (" + p + "%)");
}

async function submitToProduction() {
    await saveReperage(false);
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/submit`, { method: 'POST' });
    if (res.ok) alert("🚀 DOSSIER SOUMIS À LA PRODUCTION AVEC SUCCÈS !");
}

// ... Restant (calculateProgress, initTabs, initChat, initForms) identiques V.47 ...
