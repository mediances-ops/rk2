#!/usr/bin/env python3
"""
CORRECTIF : Ajouter route /api/i18n/<lang> dans app.py
À exécuter dans le dossier reperage-production
"""

# Lire app.py
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Trouver la ligne @app.route('/admin/logout')
if "@app.route('/admin/logout')" in content:
    # Chercher après cette route
    logout_route = """@app.route('/admin/logout')
def admin_logout():
    \"\"\"Déconnexion admin (placeholder)\"\"\"
    return redirect('/admin')"""
    
    new_route = """@app.route('/admin/logout')
def admin_logout():
    \"\"\"Déconnexion admin (placeholder)\"\"\"
    return redirect('/admin')

@app.route('/api/i18n/<lang>')
def get_translations(lang):
    \"\"\"Retourner les traductions pour une langue spécifique\"\"\"
    import json
    try:
        with open('translations/i18n.json', 'r', encoding='utf-8') as f:
            all_translations = json.load(f)
        
        if lang in all_translations:
            return jsonify(all_translations[lang])
        else:
            return jsonify({'error': 'Language not found'}), 404
    except Exception as e:
        print(f"Erreur chargement traductions: {e}")
        return jsonify({'error': str(e)}), 500"""
    
    content = content.replace(logout_route, new_route)
    
    # Sauvegarder
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Route /api/i18n/<lang> ajoutée à app.py !")
else:
    print("❌ Route /admin/logout non trouvée")
