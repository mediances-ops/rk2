# 🚀 LIVRAISON 2 - GUIDE COMPLET

## ✅ MODIFICATIONS TERMINÉES

### 1. RENOMMAGE DES CHAMPS (100% TERMINÉ) ✅

**Toutes les langues mises à jour** (FR, GB, ITAL, ESP) :

#### **Catégorie TERRITOIRE**
- ❌ ~~Climat / Saison de tournage envisagée~~
- ✅ **Date de tournage envisagée**

- ❌ ~~Fêtes locales / Calendrier culturel~~
- ✅ **Autres traditions**

#### **Catégorie ÉPISODE**
- ❌ ~~Angle narratif choisi~~
- ✅ **Particularité régionale**

- ❌ ~~Arc dramatique envisagé~~
- ✅ **Ce qu'il faut absolument filmer**

- ❌ ~~Notes production~~
- ✅ **Risques**

**Fichier modifié** : `translations/i18n.json`

---

## ⏳ MODIFICATIONS À FINALISER

### 2. INTERFACE 3 LIEUX AVEC TABS (À DÉVELOPPER)

**Objectif** : Permettre de saisir 3 lieux distincts (Lieu 1, Lieu 2, Lieu 3)

#### **Structure technique prête**
- ✅ Champ `numero_lieu` ajouté à la BDD
- ✅ Migration effectuée
- ⏳ Interface utilisateur à créer

#### **Ce qu'il faut faire**

**A. Modifier le formulaire (`index.html`)**

Ajouter des tabs pour les 3 lieux :
```html
<!-- Dans la section LIEUX -->
<div class="lieux-tabs">
    <button class="lieu-tab active" data-lieu="1">Lieu 1</button>
    <button class="lieu-tab" data-lieu="2">Lieu 2</button>
    <button class="lieu-tab" data-lieu="3">Lieu 3</button>
</div>

<div class="lieu-content" id="lieu-1">
    <!-- Tous les champs du lieu -->
</div>
<div class="lieu-content hidden" id="lieu-2">
    <!-- Tous les champs du lieu -->
</div>
<div class="lieu-content hidden" id="lieu-3">
    <!-- Tous les champs du lieu -->
</div>
```

**B. JavaScript pour les tabs**
```javascript
document.querySelectorAll('.lieu-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const lieuNum = tab.dataset.lieu;
        
        // Activer le tab
        document.querySelectorAll('.lieu-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        
        // Afficher le contenu
        document.querySelectorAll('.lieu-content').forEach(c => c.classList.add('hidden'));
        document.getElementById(`lieu-${lieuNum}`).classList.remove('hidden');
    });
});
```

**C. Modifier l'API pour sauvegarder 3 lieux**

Dans `app.py`, route `/api/reperages/<id>` :
```python
# Sauvegarder les 3 lieux
for lieu_num in [1, 2, 3]:
    lieu_data = data.get(f'lieu_{lieu_num}', {})
    if lieu_data.get('nom'):  # Si le lieu a un nom
        lieu = Lieu(
            reperage_id=reperage.id,
            numero_lieu=lieu_num,
            nom=lieu_data.get('nom'),
            # ... autres champs
        )
        session.add(lieu)
```

**D. Afficher les 3 lieux dans admin**

Dans `admin_reperage_detail.html` :
```html
{% for num in [1, 2, 3] %}
    {% set lieux_num = lieux|selectattr('numero_lieu', 'equalto', num)|list %}
    {% if lieux_num %}
        <h3>Lieu {{ num }}</h3>
        {% for lieu in lieux_num %}
            <!-- Affichage du lieu -->
        {% endfor %}
    {% endif %}
{% endfor %}
```

---

### 3. EXPORT PDF CORRIGÉ (À DÉVELOPPER)

**Problème actuel** : Ordre des champs et titrage

**Solution** : Modifier `generate_pdf()` dans `app.py`

```python
# Ordre correct : Région → Pays → Fixer
p.drawString(30, height - 100, f"Région: {reperage.region}")
p.drawString(30, height - 120, f"Pays: {reperage.pays}")
p.drawString(30, height - 140, f"Fixer: {reperage.fixer_nom}")

# Exporter les 3 lieux
lieux = session.query(Lieu).filter_by(reperage_id=reperage.id).order_by(Lieu.numero_lieu).all()
for lieu in lieux:
    p.drawString(30, y, f"Lieu {lieu.numero_lieu}: {lieu.nom}")
    y -= 20
```

---

### 4. PAGE FIXER AMÉLIORÉE (À DÉVELOPPER)

**Objectif** : Header avec région + Éditeur WYSIWYG

#### **A. Header avec région**

Dans la route `/fixer/<slug>`, passer la région :
```python
return render_template('index.html',
                      fixer_nom=fixer.prenom + ' ' + fixer.nom,
                      fixer_region=fixer.region,  # NOUVEAU
                      ...)
```

Dans `index.html` :
```html
<header>
    <h1>{{ fixer_region }}</h1>  <!-- Afficher la région -->
    <div class="subtitle">{{ fixer_nom }}</div>
</header>
```

#### **B. Éditeur WYSIWYG (TinyMCE)**

Ajouter TinyMCE dans `index.html` :
```html
<script src="https://cdn.tiny.cloud/1/no-api-key/tinymce/6/tinymce.min.js"></script>
<script>
tinymce.init({
    selector: 'textarea.wysiwyg',
    height: 300,
    menubar: false,
    plugins: 'lists link',
    toolbar: 'bold italic | bullist numlist | link'
});
</script>
```

Marquer les textarea à enrichir :
```html
<textarea class="wysiwyg" name="territoire_histoire"></textarea>
```

---

### 5. AUTHENTIFICATION ADMIN (À DÉVELOPPER)

**Solution simple** : Login avec mot de passe unique

#### **A. Variables d'environnement**

Créer `.env` :
```
ADMIN_PASSWORD=votre_mot_de_passe_securise
SECRET_KEY=votre_cle_secrete_flask
```

#### **B. Route de login**

```python
from flask import session, redirect
from werkzeug.security import check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == os.getenv('ADMIN_PASSWORD'):
            session['admin_logged_in'] = True
            return redirect('/admin')
        else:
            return render_template('admin_login.html', error=True)
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin/login')
```

#### **C. Protection des routes**

```python
def require_admin():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

@app.route('/admin')
def admin_dashboard():
    require_admin()
    # ... reste du code
```

#### **D. Template login**

Créer `templates/admin_login.html` :
```html
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login - RootsKeepers</title>
</head>
<body>
    <div class="login-container">
        <h1>RootsKeepers Admin</h1>
        <form method="POST">
            <input type="password" name="password" placeholder="Mot de passe" required>
            <button type="submit">Se connecter</button>
        </form>
        {% if error %}
        <p class="error">Mot de passe incorrect</p>
        {% endif %}
    </div>
</body>
</html>
```

---

### 6. MODAL LIEN FIXER DANS DASHBOARD (À DÉVELOPPER)

**Objectif** : Bouton dans chaque ligne du tableau pour voir/copier le lien

#### **Modifier `admin_dashboard.html`**

```html
<!-- Dans le tableau des repérages -->
<td>
    <button onclick="showFixerLink('{{ reperage.fixer_lien }}', '{{ reperage.fixer_nom }}')" 
            class="btn btn-small btn-secondary">
        <i data-lucide="link"></i> Lien
    </button>
</td>

<!-- Modal -->
<div id="fixerLinkModal" class="modal-overlay" onclick="closeFixerModal(event)">
    <div class="modal-content" onclick="event.stopPropagation()">
        <div class="modal-header">
            <h2 id="modalFixerName"></h2>
            <button class="modal-close" onclick="closeFixerModal()">&times;</button>
        </div>
        <div class="modal-body">
            <input type="text" id="fixerLinkInput" readonly style="width:100%">
            <button onclick="copyFixerLink()" class="btn btn-primary">
                <i data-lucide="copy"></i> Copier
            </button>
        </div>
    </div>
</div>

<script>
function showFixerLink(lien, nom) {
    document.getElementById('modalFixerName').textContent = nom;
    document.getElementById('fixerLinkInput').value = window.location.origin + lien;
    document.getElementById('fixerLinkModal').classList.add('active');
}

function closeFixerModal(e) {
    if (!e || e.target === e.currentTarget || e.target.classList.contains('modal-close')) {
        document.getElementById('fixerLinkModal').classList.remove('active');
    }
}

function copyFixerLink() {
    const input = document.getElementById('fixerLinkInput');
    input.select();
    document.execCommand('copy');
    alert('Lien copié !');
}
</script>
```

---

## 📋 RÉSUMÉ DES FICHIERS À MODIFIER

| Fichier | Modification | État |
|---------|--------------|------|
| `translations/i18n.json` | Renommage champs | ✅ FAIT |
| `index.html` | Interface 3 lieux tabs | ⏳ À faire |
| `app.py` | API 3 lieux | ⏳ À faire |
| `app.py` | Export PDF corrigé | ⏳ À faire |
| `app.py` | Authentification | ⏳ À faire |
| `admin_dashboard.html` | Modal lien fixer | ⏳ À faire |
| `admin_reperage_detail.html` | Affichage 3 lieux | ⏳ À faire |
| `.env` | Config auth | ⏳ À créer |
| `templates/admin_login.html` | Page login | ⏳ À créer |

---

## ⏱️ TEMPS DE DÉVELOPPEMENT ESTIMÉ

- Interface 3 lieux : **2h**
- Export PDF : **30 min**
- Authentification : **1h**
- Modal lien : **20 min**
- Tests : **30 min**

**Total : ~4h de développement**

---

## 🎯 PRIORITÉS RECOMMANDÉES

1. **Interface 3 lieux** (le plus complexe)
2. **Authentification** (sécurité)
3. **Export PDF** (fonctionnel)
4. **Modal lien** (UX)

---

Date: 1 décembre 2025
Version: 2.2 (Livraison 2 - Partielle)
