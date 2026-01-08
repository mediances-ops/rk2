const API_URL = '/api';
let currentLanguage = localStorage.getItem('selectedLanguage') || 'FR';
let currentReperageId = window.REPERAGE_ID || null;

document.addEventListener('DOMContentLoaded', async function() {
    if (window.FIXER_DATA) {
        currentLanguage = window.FIXER_DATA.langue_default || 'FR';
        currentReperageId = window.FIXER_DATA.reperage_id;
    }
    await loadTranslations(currentLanguage);
    initTabs();
    initFileUpload();
    initChat();
    
    if (currentReperageId) {
        await loadReperage(currentReperageId);
        await loadMedias(); 
    }
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
});

async function loadTranslations(lang) {
    const res = await fetch(`${API_URL}/i18n/${lang}`);
    const trans = await res.json();
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const keys = el.getAttribute('data-i18n').split('.');
        let val = trans;
        keys.forEach(k => { val = val ? val[k] : null; });
        if (val) el.textContent = val;
    });
}

function calculateProgress() {
    const allInputs = document.querySelectorAll('input[name], textarea[name]');
    let total = 0; let filled = 0;
    allInputs.forEach(input => {
        if (!['fixer_nom', 'fixer_email', 'fixer_telephone', 'pays', 'region'].includes(input.name)) {
            total++;
            if (input.value && input.value.trim().length > 2) filled++;
        }
    });
    const percent = total > 0 ? Math.round((filled / total) * 100) : 0;
    document.getElementById('progress-bar').style.width = percent + '%';
    document.getElementById('progress-percentage').textContent = percent + '%';
    document.getElementById('progress-filled').textContent = filled;
    document.getElementById('progress-total').textContent = total;
    return percent;
}

async function loadReperage(id) {
    const res = await fetch(`${API_URL}/reperages/${id}`);
    const data = await res.json();
    document.querySelectorAll('input[name], textarea[name]').forEach(input => {
        const name = input.name;
        if (data[name]) input.value = data[name];
        else if (data.territoire_data && data.territoire_data[name]) input.value = data.territoire_data[name];
    });
    setTimeout(calculateProgress, 1000);
}

async function loadMedias() {
    if (!currentReperageId) return;
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
    const medias = await res.json();
    const list = document.getElementById('files-list');
    if (list) {
        list.innerHTML = medias.map(m => `
            <div class="file-item" style="border:1px solid #ddd; padding:5px; border-radius:8px; text-align:center;">
                <img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:100%; height:120px; object-fit:cover; border-radius:5px;">
                <small style="display:block; margin-top:5px; overflow:hidden;">${m.nom_original}</small>
            </div>
        `).join('');
    }
}

async function saveReperage(notif) {
    const p = calculateProgress();
    const data = { progression: p, territoire_data: {} };
    document.querySelectorAll('input[name], textarea[name]').forEach(el => {
        if (['fixer_nom', 'fixer_email', 'pays', 'region'].includes(el.name)) data[el.name] = el.value;
        else data.territoire_data[el.name] = el.value;
    });
    await fetch(`${API_URL}/reperages/${currentReperageId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (notif) alert("✅ Synchronisé (" + p + "%)");
}

function initFileUpload() {
    const area = document.getElementById('drop-area');
    if (!area) return;
    area.onclick = () => document.getElementById('file-input').click();
    document.getElementById('file-input').onchange = async (e) => {
        for (let file of e.target.files) {
            const fd = new FormData(); fd.append('file', file);
            await fetch(`${API_URL}/reperages/${currentReperageId}/medias`, { method: 'POST', body: fd });
        }
        await loadMedias(); // Rafraîchir les photos immédiatement
        alert("📷 Photo sauvegardée.");
    };
}

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = function() {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(this.dataset.tab).classList.add('active');
        };
    });
}

function initChat() {
    document.getElementById('chat-toggle-btn')?.addEventListener('click', () => {
        document.getElementById('chat-panel').classList.toggle('active');
    });
}
