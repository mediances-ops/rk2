/**
 * DOC-OS V.68 SUPRÊME - INSTANT MESSAGING ENGINE
 * HARMONIZED RENDERING : ADMIN & FIXER CONTEXTS
 */

const API_URL = '/api';
let currentReperageId = window.REPERAGE_ID || null;
// Détecte si nous sommes côté Admin ou Fixer pour l'alignement (Me vs Them)
const CONTEXT_TYPE = window.location.pathname.includes('/admin') ? 'production' : 'fixer';

document.addEventListener('DOMContentLoaded', async function() {
    initTabs(); initFileUpload(); initEventListeners();
    if (currentReperageId) { await loadReperage(); initChat(); await loadMedias(); }
});

function initChat() {
    const toggle = document.getElementById('chat-toggle-btn');
    const panel = document.getElementById('chat-panel');
    if (!toggle) return;

    toggle.onclick = () => {
        panel.classList.toggle('active');
        if (panel.classList.contains('active')) { loadMessages(); toggle.style.animation = 'none'; }
    };
    document.getElementById('chat-close-btn').onclick = () => panel.classList.remove('active');

    document.getElementById('chat-send-btn').onclick = sendChatMessage;

    // Polling toutes les 20 secondes pour plus de réactivité
    setInterval(checkNewMessages, 20000);
}

async function sendChatMessage() {
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
    input.value = ''; await loadMessages();
}

async function loadMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages${CONTEXT_TYPE === 'production' ? '?role=admin' : ''}`);
    const msgs = await res.json();
    const container = document.getElementById('chat-messages');
    if (!container) return;

    let html = '';
    let lastDate = null;

    msgs.forEach(m => {
        const dateObj = new Date(m.created_at);
        const dayStr = dateObj.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' });
        const timeStr = dateObj.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });

        // Insertion ligne de séparation Jour
        if (dayStr !== lastDate) {
            html += `<div class="day-separator"><span>${dayStr}</span></div>`;
            lastDate = dayStr;
        }

        const isMe = m.auteur_type === CONTEXT_TYPE;
        const colorClass = m.auteur_type === 'fixer' ? 'color-fixer' : 'color-production';
        
        html += `
            <div class="msg-wrapper ${isMe ? 'msg-me' : 'msg-them'}">
                <div class="msg-meta ${colorClass}">${m.auteur_nom}</div>
                <div class="bubble">
                    <div class="msg-content">${m.contenu}</div>
                    <div class="msg-time">${timeStr}</div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
    container.scrollTop = container.scrollHeight;
}

async function checkNewMessages() {
    const res = await fetch(`${API_URL}/reperages/${currentReperageId}/messages`);
    const msgs = await res.json();
    if (msgs.length > 0) {
        const last = msgs[msgs.length - 1];
        const panel = document.getElementById('chat-panel');
        if (last.auteur_type !== CONTEXT_TYPE && !panel.classList.contains('active')) {
            document.getElementById('chat-toggle-btn').style.animation = 'pulse 1.5s infinite';
        }
    }
}

// ... [Reste des fonctions loadReperage, calculateProgress, loadMedias identiques à V.67.1] ...
