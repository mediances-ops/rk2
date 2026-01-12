/**
 * DOC-OS V.68.3 SUPRÊME - ENGINE RESTORED
 * FIX TABS, CHAT, PROGRESSION AND PERSISTENCE
 */

const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;
const CONTEXT_TYPE = window.location.pathname.includes('/admin') ? 'production' : 'fixer';

document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎬 Launching DOC-OS V.68.3 - Full Stability Mode');
    
    // Initialisation séquentielle sécurisée
    try { initTabs(); } catch(e) { console.error("Tab init fail", e); }
    try { initFileUpload(); } catch(e) { console.error("File upload init fail", e); }
    try { initEventListeners(); } catch(e) { console.error("Events init fail", e); }
    
    if (currentReperageId) {
        await loadReperage();
        initChat();
        await loadMedias();
    }
});

function initTabs() {
    const buttons = document.querySelectorAll('.tab-btn');
    const contents = document.querySelectorAll('.tab-content');
    
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-tab');
            if (!target) return;
            
            buttons.forEach(b => b.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            const targetEl = document.getElementById(target);
            if (targetEl) targetEl.classList.add('active');
        });
    });
}

function initEventListeners() {
    document.getElementById('btn-save')?.addEventListener('click', () => saveReperage(true));
    document.getElementById('btn-submit')?.addEventListener('click', () => submitToProduction());
    
    document.querySelectorAll('input, textarea').forEach(el => {
        el.addEventListener('input', () => calculateProgress());
    });
}

function calculateProgress() {
    const fields = document.querySelectorAll('.tab-content input[name], .tab-content textarea[name]');
    if (fields.length === 0) return 0;
    
    let filled = 0;
    fields.forEach(input => {
        if (input.value && input.value.trim().length > 1) filled++;
    });

    const percent = Math.min(100, Math.round((filled / 100) * 100)); // Base 100
    
    const bar = document.getElementById('progress-bar');
    const label = document.getElementById('progress-percentage');
    const filledText = document.getElementById('progress-filled');

    if (bar) bar.style.width = percent + '%';
    if (label) label.textContent = percent + '%';
    if (filledText) filledText.textContent = filled;

    return percent;
}

async function loadReperage() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`);
        const data = await res.json();
        
        document.querySelectorAll('input[name], textarea[name]').forEach(input => {
            const name = input.name;
            let val = data[name]; // Racine
            
            if (data.territory && data.territory[name]) val = data.territory[name];
            if (data.festivity && data.festivity[name]) val = data.festivity[name];
            
            for (let i = 1; i <= 3; i++) {
                const pair = data[`pair_${i}`];
                const shortName = name.replace(`gardien${i}_`, '').replace(`lieu${i}_`, '');
                if (pair && pair[shortName] !== undefined) val = pair[shortName];
            }
            
            if (val !== undefined && val !== null) input.value = val;
        });

        if (data.statut !== 'brouillon') lockInterface();
        calculateProgress();
    } catch (e) { console.error("Persistence failed to load", e); }
}

async function saveReperage(showToast) {
    const payload = { progression_pourcent: calculateProgress() };
    document.querySelectorAll('input[name], textarea[name]').forEach(el => {
        payload[el.name] = el.value;
    });

    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (res.ok && showToast) {
            const t = document.getElementById('toast');
            if (t) {
                t.style.display = 'block';
                setTimeout(() => { t.style.display = 'none'; }, 3000);
            }
        }
    } catch (e) { console.error("Save error", e); }
}

async function submitToProduction() {
    const required = document.querySelectorAll('input[required], textarea[required]');
    let missing = [];
    required.forEach(el => { if(!el.value.trim()) missing.push(el.name); });

    if (missing.length > 0) {
        alert("⚠️ AT LEAST THESE FIELDS ARE REQUIRED FOR SUBMISSION.");
        return;
    }

    if (confirm("🚀 SUBMIT TO PRODUCTION? (Dossier will be locked)")) {
        await saveReperage(false);
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}/submit`, { method: 'POST' });
        if (res.ok) location.reload();
    }
}

function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    const panel = document.getElementById('chat-panel');
    const close = document.getElementById('chat-close-btn');
    const send = document.getElementById('chat-send-btn');

    if (!toggle || !panel) return;

    toggle.onclick = () => {
        panel.classList.toggle('active');
        if (panel.classList.contains('active')) loadMessages();
    };
    
    if (close) close.onclick = () => panel.classList.remove('active');

    if (send) {
        send.onclick = async () => {
            const input = document.getElementById('chat-input');
            if (!input.value.trim()) return;
            const msg = {
                auteur_type: CONTEXT_TYPE,
                auteur_nom: CONTEXT_TYPE === 'production' ? 'Production' : (window.FIXER_DATA?.prenom || 'Correspondent'),
                contenu: input.value
            };
            await fetch(`${API_URL}/reperages/${currentReperageId}/messages`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(msg)
            });
            input.value = '';
            loadMessages();
        };
    }
    
    setInterval(checkNewMessages, 20000);
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages${CONTEXT_TYPE === 'production' ? '?role=admin' : ''}`);
    const msgs = await res.json();
    const container = document.getElementById('chat-messages');
    if (!container) return;

    let html = '';
    let lastDate = null;

    msgs.forEach(m => {
        const d = new Date(m.created_at);
        const ds = d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' });
        if (ds !== lastDate) { html += `<div class="day-separator"><span>${ds}</span></div>`; lastDate = ds; }
        
        const isMe = m.auteur_type === CONTEXT_TYPE;
        html += `
            <div class="msg-wrapper ${isMe ? 'msg-me' : 'msg-them'}">
                <div class="msg-meta ${m.auteur_type === 'fixer' ? 'color-fixer' : 'color-production'}">${m.auteur_nom}</div>
                <div class="bubble">
                    <div class="msg-content">${m.contenu}</div>
                    <div style="font-size:0.6rem; opacity:0.5; margin-top:5px; text-align:right;">${d.toLocaleTimeString('en-GB', {hour:'2-digit', minute:'2-digit'})}</div>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
    container.scrollTop = container.scrollHeight;
}

async function checkNewMessages() {
    try {
        const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
        const msgs = await res.json();
        if (msgs.length > 0) {
            const last = msgs[msgs.length - 1];
            const panel = document.getElementById('chat-panel');
            if (last.auteur_type !== CONTEXT_TYPE && !panel.classList.contains('active')) {
                document.getElementById('chat-toggle-btn').style.animation = 'pulse 1.5s infinite';
            }
        }
    } catch(e) {}
}

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
        await loadMedias();
    };
}

async function loadMedias() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/medias`);
    const ms = await res.json();
    const list = document.getElementById('files-list');
    if (list) list.innerHTML = ms.map(m => `<div class="file-item"><img src="/uploads/${currentReperageId}/${m.nom_fichier}" style="width:180px;height:180px;object-fit:cover;border-radius:12px;"></div>`).join('');
}

function lockInterface() {
    document.getElementById('lock-banner').style.display = 'block';
    document.querySelectorAll('input, textarea, button:not(.chat-toggle-btn):not(#chat-close-btn)').forEach(el => {
        el.disabled = true; el.style.opacity = '0.6';
    });
}
