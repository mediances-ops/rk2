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
    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); // FIX : Charger les photos existantes
    }
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
});

// ... (loadTranslations et i18n restent identiques)

async function loadReperage(id) {
    const res = await fetch(`${API_URL}/reperages/${id}`);
    const data = await res.json();
    fillFormData(data);
    setTimeout(calculateProgress, 1000);
}

function calculateProgress() {
    // On compte uniquement les textarea et inputs visibles
    const inputs = document.querySelectorAll('.tab-content.active input[name], .tab-content.active textarea[name]');
    // Note: Pour un calcul global, enlever ".tab-content.active"
    const allInputs = document.querySelectorAll('input[name], textarea[name]');
    let total = 0; let filled = 0;
    
    allInputs.forEach(input => {
        if (!['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'].includes(input.name)) {
            total++;
            if (input.value && input.value.trim().length > 2) filled++;
        }
    });

    const percent = Math.round((filled / total) * 100);
    document.getElementById('progress-bar').style.width = percent + '%';
    document.getElementById('progress-percentage').textContent = percent + '%';
    document.getElementById('progress-filled').textContent = filled;
    document.getElementById('progress-total').textContent = total;
    return percent;
}

// FIX : Affichage des photos sur le formulaire
async function loadMedias() {
    if (!currentReperageId) return;
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
    const medias = await res.json();
    const list = document.getElementById('files-list');
    if (list) {
        list.innerHTML = medias.map(m => `
            <div class="file-item">
                <img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100px; height:100px; object-fit:cover;">
                <span>${m.nom_original}</span>
            </div>
        `).join('');
    }
}

async function saveReperage(notif) {
    const currentPercent = calculateProgress();
    const data = { progression: currentPercent, territoire_data: {}, episode_data: {} };
    document.querySelectorAll('input[name], textarea[name]').forEach(el => {
        if (['fixer_nom', 'fixer_email', 'pays', 'region'].includes(el.name)) data[el.name] = el.value;
        else data.territoire_data[el.name] = el.value;
    });
    await fetch(`${API_URL}/reperages/${currentReperageId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (notif) alert("Sauvegarde : " + currentPercent + "%");
}

// ... (initTabs, initChat et initFileUpload restent identiques à V20)
// Ajouter l'appel à loadMedias() dans initFileUpload après chaque upload
