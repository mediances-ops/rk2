#!/usr/bin/env python3
"""
🚀 ROOTSKEEPERS - SCRIPT DE MISE À JOUR AUTOMATIQUE (CORRIGÉ)
Exécutez ce script dans le dossier reperage-production
Il appliquera TOUTES les modifications automatiquement
"""

import os
import re
import shutil
from datetime import datetime

# Couleurs terminal
class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg):
    print(f"{Color.GREEN}✅ {msg}{Color.END}")

def print_error(msg):
    print(f"{Color.RED}❌ {msg}{Color.END}")

def print_info(msg):
    print(f"{Color.BLUE}ℹ️  {msg}{Color.END}")

def print_warning(msg):
    print(f"{Color.YELLOW}⚠️  {msg}{Color.END}")

print("""
╔══════════════════════════════════════════════════════════════╗
║     🚀 ROOTSKEEPERS - MISE À JOUR AUTOMATIQUE               ║
╚══════════════════════════════════════════════════════════════╝
""")

# Vérifier qu'on est dans le bon dossier
if not os.path.exists('app.py'):
    print_error("Ce script doit être exécuté dans le dossier reperage-production")
    print_info("Usage: python update_rootskeepers.py")
    exit(1)

# Créer backup
backup_folder = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
print_info(f"Création backup dans: {backup_folder}/")
os.makedirs(backup_folder, exist_ok=True)

# ======================================================================
# 1. MODIFIER app.js - Correction traductions
# ======================================================================
print("\n" + "="*60)
print("1️⃣  MODIFICATION: static/js/app.js")
print("="*60)

app_js_path = 'static/js/app.js'
if os.path.exists(app_js_path):
    # Backup
    shutil.copy(app_js_path, os.path.join(backup_folder, 'app.js.backup'))
    
    with open(app_js_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remplacer la fonction applyTranslations
    new_apply_function = '''function applyTranslations() {
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
}'''
    
    # Trouver et remplacer
    pattern = r'function applyTranslations\(\)[\s\S]*?^}'
    content = re.sub(pattern, new_apply_function, content, flags=re.MULTILINE)
    
    with open(app_js_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print_success("app.js modifié - Traductions corrigées")
else:
    print_error(f"Fichier non trouvé: {app_js_path}")

# ======================================================================
# 2. MODIFIER index.html - Supprimer intro + Progress (FORMULAIRE FIXER)
# ======================================================================
print("\n" + "="*60)
print("2️⃣  MODIFICATION: templates/index.html (Formulaire Fixer)")
print("="*60)

index_path = 'templates/index.html'
if os.path.exists(index_path):
    # Backup
    shutil.copy(index_path, os.path.join(backup_folder, 'index.html.backup'))
    
    with open(index_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    modified_lines = []
    skip_until = -1
    
    for i, line in enumerate(lines, 1):
        # Sauter les lignes du bloc intro
        if i <= skip_until:
            continue
            
        # Détecter début bloc intro
        if '<!-- INTRODUCTION -->' in line:
            skip_until = i + 5  # Sauter le bloc complet
            print_info("Suppression bloc introduction (lignes ~77-83)")
            continue
        
        # Changer "Progression du repérage" → "Progress"
        if 'Progression du repérage' in line:
            line = line.replace('Progression du repérage', 'Progress')
            print_info('Changement: "Progression du repérage" → "Progress"')
        
        modified_lines.append(line)
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.writelines(modified_lines)
    
    print_success("index.html modifié (intro supprimée + Progress)")
else:
    print_error(f"Fichier non trouvé: {index_path}")

# ======================================================================
# 3. MODIFIER admin_dashboard.html - Ajouter panneau IA (TABLEAU DE BORD ADMIN)
# ======================================================================
print("\n" + "="*60)
print("3️⃣  MODIFICATION: templates/admin_dashboard.html (PANNEAU IA)")
print("="*60)

admin_dashboard_path = 'templates/admin_dashboard.html'
if os.path.exists(admin_dashboard_path):
    # Backup
    shutil.copy(admin_dashboard_path, os.path.join(backup_folder, 'admin_dashboard.html.backup'))
    
    with open(admin_dashboard_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Ajouter le panneau IA avant </body>
    final_lines = []
    for i, line in enumerate(lines):
        if '</body>' in line:
            # Insérer le code du panneau IA
            ai_panel_code = '''
<!-- ========================================
     PANNEAU IA LATÉRAL GAUCHE
     ======================================== -->
<button class="ai-floating-btn" onclick="toggleAIPanel()" title="Assistant IA RootsKeepers">
    <i data-lucide="brain-circuit" style="width: 28px; height: 28px;"></i>
</button>

<div class="ai-panel-overlay" id="aiPanelOverlay" onclick="closeAIPanel()"></div>

<div class="ai-panel" id="aiPanel">
    <div class="ai-panel-header">
        <div style="display: flex; align-items: center; gap: 12px;">
            <i data-lucide="brain-circuit" style="width: 24px; height: 24px; color: white;"></i>
            <h3 style="margin: 0; color: white; font-size: 1.1rem;">Assistant IA RootsKeepers</h3>
        </div>
        <button class="ai-panel-close" onclick="closeAIPanel()">
            <i data-lucide="x" style="width: 20px; height: 20px;"></i>
        </button>
    </div>
    
    <div class="ai-panel-body">
        <iframe 
            src="https://destinationsetcuisines.com/site" 
            frameborder="0"
            style="width: 100%; height: 100%; border: none;"
            title="Assistant IA RootsKeepers"
        ></iframe>
    </div>
</div>

<script>
// ========================================
// PANNEAU IA - JAVASCRIPT
// ========================================

function toggleAIPanel() {
    const panel = document.getElementById('aiPanel');
    const overlay = document.getElementById('aiPanelOverlay');
    
    if (panel.classList.contains('active')) {
        closeAIPanel();
    } else {
        openAIPanel();
    }
}

function openAIPanel() {
    const panel = document.getElementById('aiPanel');
    const overlay = document.getElementById('aiPanelOverlay');
    
    panel.classList.add('active');
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
    
    // Réinitialiser les icônes Lucide
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

function closeAIPanel() {
    const panel = document.getElementById('aiPanel');
    const overlay = document.getElementById('aiPanelOverlay');
    
    panel.classList.remove('active');
    overlay.classList.remove('active');
    document.body.style.overflow = '';
}

// Fermer avec Échap
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeAIPanel();
    }
});
</script>

'''
            final_lines.append(ai_panel_code)
            print_success("Panneau IA ajouté au tableau de bord admin")
        
        final_lines.append(line)
    
    with open(admin_dashboard_path, 'w', encoding='utf-8') as f:
        f.writelines(final_lines)
    
    print_success("admin_dashboard.html modifié")
else:
    print_error(f"Fichier non trouvé: {admin_dashboard_path}")

# ======================================================================
# 4. AJOUTER CSS pour panneau IA dans style.css
# ======================================================================
print("\n" + "="*60)
print("4️⃣  MODIFICATION: static/css/style.css")
print("="*60)

css_path = 'static/css/style.css'
if os.path.exists(css_path):
    # Backup
    shutil.copy(css_path, os.path.join(backup_folder, 'style.css.backup'))
    
    # Vérifier si le CSS n'existe pas déjà
    with open(css_path, 'r', encoding='utf-8') as f:
        existing_css = f.read()
    
    if '.ai-floating-btn' not in existing_css:
        with open(css_path, 'a', encoding='utf-8') as f:
            css_ai_panel = '''

/* ========================================
   PANNEAU IA - STYLES
   ======================================== */

/* Bouton flottant gauche */
.ai-floating-btn {
    position: fixed;
    left: 20px;
    bottom: 20px;
    width: 60px;
    height: 60px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 999;
    transition: all 0.3s ease;
}

.ai-floating-btn:hover {
    transform: scale(1.1);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
}

/* Overlay sombre */
.ai-panel-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
    z-index: 1000;
}

.ai-panel-overlay.active {
    opacity: 1;
    visibility: visible;
}

/* Panneau latéral */
.ai-panel {
    position: fixed;
    left: -75%;
    top: 0;
    width: 75%;
    height: 100vh;
    background: white;
    box-shadow: 4px 0 20px rgba(0, 0, 0, 0.2);
    z-index: 1001;
    transition: left 0.3s ease;
    display: flex;
    flex-direction: column;
}

.ai-panel.active {
    left: 0;
}

/* Header du panneau */
.ai-panel-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.ai-panel-close {
    background: rgba(255, 255, 255, 0.2);
    color: white;
    border: none;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
}

.ai-panel-close:hover {
    background: rgba(255, 255, 255, 0.3);
    transform: rotate(90deg);
}

/* Corps du panneau (iframe) */
.ai-panel-body {
    flex: 1;
    overflow: hidden;
    background: #f5f5f5;
}

/* Responsive mobile */
@media (max-width: 768px) {
    .ai-panel {
        width: 90%;
        left: -90%;
    }
    
    .ai-floating-btn {
        width: 50px;
        height: 50px;
        left: 15px;
        bottom: 15px;
    }
}
'''
            f.write(css_ai_panel)
        print_success("CSS panneau IA ajouté à style.css")
    else:
        print_warning("CSS panneau IA déjà présent, ignoré")
else:
    print_error(f"Fichier non trouvé: {css_path}")

# ======================================================================
# RÉSUMÉ
# ======================================================================
print("\n" + "="*60)
print("🎉 MISE À JOUR TERMINÉE !")
print("="*60)

print_success("✅ app.js: Traductions corrigées")
print_success("✅ index.html: Intro supprimée + Progress")
print_success("✅ admin_dashboard.html: Panneau IA ajouté ⬅️ TABLEAU DE BORD ADMIN")
print_success("✅ style.css: Styles panneau IA ajoutés")
print_info(f"📦 Backup sauvegardé dans: {backup_folder}/")

print("\n" + "="*60)
print("📝 PROCHAINES ÉTAPES")
print("="*60)
print("1. Redémarrez le serveur (START_SERVER.bat)")
print("2. ALLEZ SUR LE TABLEAU DE BORD ADMIN (/admin)")
print("3. Testez le panneau IA (bouton cerveau gauche) 🧠")
print("4. Testez les traductions dans le formulaire fixer (FR/GB/IT/ESP)")
print("\n")
