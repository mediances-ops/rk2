/**
 * DOC-OS V.77.0 SUPRÊME - HYBRID SYNC ENGINE
 * RÉSOUT LE PROBLÈME D'AFFICHAGE "HISTOIRE" & ONGLETS
 */

const API_URL = '/api';
const REPERAGE_ID = window.REPERAGE_ID;
const CONTEXT_TYPE = window.location.pathname.includes('/admin') ? 'production' : 'fixer';
let isLocked = false;

document.addEventListener('DOMContentLoaded', async () => {
    initTabs();
    initFileUpload();
    initEventListeners();
    
    if (REPERAGE_ID) {
        await loadReperage(); // Chargement initial
        initChat();
        await loadMedias();
        // Sauvegarde auto toutes les minutes
        setInterval(() => { if(!isLocked) saveReperage(false); }, 60000);
    }
});

/**
 * 1. LE CŒUR : CHARGEMENT ET MAPPING HYBRIDE
 * C'est ici que l'on règle le problème du champ "histoire"
 */
async function loadReperage() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}?t=${Date.now()}`);
        const data = await res.json();
        
        // 1. ON VIDE LES TIROIRS : On met tout dans un seul dictionnaire à plat
        let flatData = { ...data }; 
        
        if (data.territory) Object.assign(flatData, data.territory);
        if (data.festivity) Object.assign(flatData, data.festivity);
        
        for (let i = 1; i <= 3; i++) {
            const pair = data[`pair_${i}`];
            if (pair) {
                Object.keys(pair).forEach(key => {
                    // On crée les noms exacts attendus par tes inputs HTML
                    flatData[`gardien${i}_${key}`] = pair[key];
                    flatData[`lieu${i}_${key}`] = pair[key];
                });
            }
        }

        // 2. ON REMPLIT DE FORCE : On parcourt chaque champ du formulaire
        document.querySelectorAll('.scouting-field').forEach(field => {
            const savedValue = flatData[field.name];
            
            // Si on a une valeur en base pour ce nom de champ, on l'affiche
            if (savedValue !== undefined && savedValue !== null) {
                field.value = savedValue;
            }
        });

        console.log("✅ AFFICHAGE FORCÉ : Les données sont maintenant visibles.");
        if (typeof calculateProgress === 'function') calculateProgress();

    } catch (e) { 
        console.error("❌ ERREUR CRITIQUE CHARGEMENT :", e); 
    }
}
/**
 * 2. SAUVEGARDE UNITAIRE
 */
async function saveReperage(showToastFlag = true) {
    if(isLocked) return;
    const payload = { progression_pourcent: calculateProgress() };
    document.querySelectorAll('.scouting-field').forEach(f => { if(f.name) payload[f.name] = f.value; });

    try {
        const res = await fetch(`${API_URL}/reperages/${REPERAGE_ID}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (res.ok && showToastFlag) showToast("DONNÉES SAUVEGARDÉES");
        return res.ok;
    } catch (e) { return false; }
}

/**
 * 3. CALCUL DE PROGRESSION
 */
function calculateProgress() {
    const fields = document.querySelectorAll('.scouting-field:not([readonly])');
    const filled = Array.from(fields).filter(f => f.value && f.value.trim().length > 1).length;
    const pct = Math.min(100, Math.round((filled / fields.length) * 100));
    
    const bar = document.getElementById('progress-bar');
    const label = document.getElementById('progress-percentage');
    if (bar) bar.style.width = pct + '%';
    if (label) label.textContent = pct + '%';
    return pct;
}

/**
 * 4. MODULE CHAT & MEDIA (RESTAURATION)
 */
function initChat() {
    const btn = document.getElementById('chat-toggle-btn');
    if(btn) btn.onclick = () => { 
        document.getElementById('chat-panel').classList.toggle('active'); 
        loadMessages(); 
    };
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${REPERAGE_ID}/messages`);
    const msgs = await res.json();
    const cont = document.getElementById('chat-messages');
    if(cont) {
        cont.innerHTML = msgs.map(m => `<div class="msg-wrapper ${m.auteur_type === 'fixer' ? 'msg-me' : 'msg-them'}"><div class="bubble">${m.contenu}</div></div>`).join('');
        cont.scrollTop = cont.scrollHeight;
    }
}

async function loadMedias() {
    const res = await fetch(`${API_URL}/reperages/${REPERAGE_ID}/medias`);
    const ms = await res.json();
    const list = document.getElementById('files-list');
    if (list) {
        list.innerHTML = ms.map(m => `
            <div class="file-item" style="position:relative; width:180px;">
                <img src="/uploads/${REPERAGE_ID}/${m.nom_fichier}" style="width:100%; height:180px; object-fit:cover; border-radius:12px;">
                ${!isLocked ? `<button onclick="window.deleteMedia(${m.id})" style="position:absolute; top:10px; right:10px; background:red; color:white; border:none; border-radius:50%; width:25px; height:25px; cursor:pointer;">&times;</button>` : ''}
            </div>`).join('');
    }
}

/**
 * 5. NAVIGATION & UTILS
 */
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(b => b.onclick = () => {
        document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
        b.classList.add('active');
        document.getElementById(b.getAttribute('data-tab')).classList.add('active');
    });
}

function initFileUpload() {
    const area = document.getElementById('drop-area');
    if(area) area.onclick = () => document.getElementById('file-input').click();
    const input = document.getElementById('file-input');
    if(input) input.onchange = async (e) => {
        for (let f of e.target.files) {
            const fd = new FormData(); fd.append('file', f);
            await fetch(`${API_URL}/reperages/${REPERAGE_ID}/medias`, { method: 'POST', body: fd });
        }
        await loadMedias();
    };
}

function initEventListeners() {
    document.getElementById('btn-save').onclick = () => saveReperage(true);
    document.getElementById('btn-submit').onclick = async () => {
        if(confirm("SOUMETTRE À LA PRODUCTION ?")) {
            await saveReperage(false);
            const res = await fetch(`${API_URL}/reperages/${REPERAGE_ID}/submit`, { method: 'POST' });
            if(res.ok) window.location.reload();
        }
    };
}

function showToast(msg) { const t=document.getElementById('toast'); if(t){t.textContent=msg; t.style.display='block'; setTimeout(()=>t.style.display='none',3000); }}
window.deleteMedia = async (id) => { if(confirm("Supprimer ?")) { await fetch(`${API_URL}/medias/${id}`, { method: 'DELETE' }); await loadMedias(); }};
function lockInterface() { isLocked = true; document.getElementById('lock-banner').style.display='block'; document.querySelectorAll('.scouting-field, button:not(#chat-toggle-btn)').forEach(el => { el.disabled=true; el.style.opacity='0.6'; }); }
