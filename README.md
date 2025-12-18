# 🎬 FORMULAIRE DE REPÉRAGE - LES GARDIENS DE LA TRADITION

## ✅ INSTALLATION COMPLÈTE

Votre prototype est prêt ! Tous les fichiers ont été créés.

---

## 📂 STRUCTURE DU PROJET

```
reperage-app/
├── app.py                      # Serveur Flask (backend)
├── models.py                   # Modèles base de données
├── requirements.txt            # Dépendances Python
├── reperage.db                 # Base de données SQLite (créée auto)
│
├── static/
│   ├── css/
│   │   └── style.css          # Tous les styles
│   ├── js/
│   │   └── app.js             # JavaScript principal
│   └── uploads/               # Fichiers uploadés
│       └── thumbnails/        # Miniatures photos
│
├── templates/
│   └── index.html             # Page principale du formulaire
│
└── translations/
    └── i18n.json              # Traductions FR/GB/ITAL/ESP
```

---

## 🚀 COMMENT DÉMARRER LE SERVEUR

### Option 1 : Depuis ce terminal

```bash
cd /home/claude/reperage-app
python3 app.py
```

### Option 2 : Commande complète

```bash
cd /home/claude/reperage-app && python3 app.py
```

Le serveur démarre sur : **http://localhost:5000**

---

## 🌐 FONCTIONNALITÉS DISPONIBLES

### ✅ Interface multilingue
- 🇫🇷 Français
- 🇬🇧 Anglais (British)
- 🇮🇹 Italien
- 🇪🇸 Espagnol

### ✅ Formulaire complet
- 5 onglets de saisie (Territoire, Épisode, Gardiens x2, Lieux)
- Champs pour toutes les informations nécessaires
- Validation des données

### ✅ Sauvegarde automatique
- Sauvegarde toutes les 30 secondes
- Sauvegarde lors de la fermeture du navigateur
- Reprise automatique du dernier repérage

### ✅ Upload de fichiers
- Drag & drop de photos
- Support JPG, PNG, HEIC, PDF
- Création automatique de miniatures
- Limite 50 MB par fichier

### ✅ Gestion des données
- Base de données SQLite
- Stockage de tous les repérages
- Export vers PDF (à implémenter)

---

## 📊 BASE DE DONNÉES

La base de données SQLite contient :

- **reperages** : Informations principales de chaque repérage
- **gardiens** : Les 3 gardiens de la tradition
- **lieux** : Lieux de tournage
- **medias** : Photos et documents uploadés

---

## 🔧 API DISPONIBLES

Le serveur expose une API REST complète :

### Repérages
- `GET /api/reperages` - Liste tous les repérages
- `GET /api/reperages/<id>` - Détails d'un repérage
- `POST /api/reperages` - Créer un repérage
- `PUT /api/reperages/<id>` - Modifier un repérage
- `DELETE /api/reperages/<id>` - Supprimer un repérage
- `POST /api/reperages/<id>/submit` - Soumettre un repérage

### Gardiens
- `GET /api/reperages/<id>/gardiens` - Liste des gardiens
- `POST /api/reperages/<id>/gardiens` - Ajouter un gardien
- `PUT /api/gardiens/<id>` - Modifier un gardien
- `DELETE /api/gardiens/<id>` - Supprimer un gardien

### Lieux
- `GET /api/reperages/<id>/lieux` - Liste des lieux
- `POST /api/reperages/<id>/lieux` - Ajouter un lieu
- `PUT /api/lieux/<id>` - Modifier un lieu
- `DELETE /api/lieux/<id>` - Supprimer un lieu

### Médias (Upload)
- `POST /api/reperages/<id>/medias` - Upload fichier
- `GET /api/reperages/<id>/medias` - Liste médias
- `DELETE /api/medias/<id>` - Supprimer média

### Traductions
- `GET /api/i18n/<lang>` - Récupérer traductions (FR/GB/ITAL/ESP)

---

## 🧪 TESTER LE FORMULAIRE

1. Démarrer le serveur : `python3 app.py`
2. Ouvrir dans un navigateur : http://localhost:5000
3. Choisir une langue (en haut à droite)
4. Remplir les différents onglets
5. Uploader des photos (drag & drop)
6. Cliquer sur "Enregistrer"
7. Les données sont sauvegardées automatiquement

---

## 💾 DONNÉES SAUVEGARDÉES

Toutes les données sont stockées dans :
- **Base de données** : `reperage.db`
- **Fichiers uploadés** : `static/uploads/`
- **Miniatures** : `static/uploads/thumbnails/`

---

## 🎨 PERSONNALISATION

### Couleurs (dans style.css)
```css
:root {
    --primary-color: #FF6B35;    /* Orange principal */
    --secondary-color: #FF8C5A;  /* Orange secondaire */
    --accent-color: #FF3B1F;     /* Rouge accent */
    --dark-color: #333333;       /* Gris foncé */
}
```

### Traductions (dans translations/i18n.json)
Vous pouvez modifier ou ajouter des traductions directement dans le fichier JSON.

---

## 🐛 EN CAS DE PROBLÈME

### Le serveur ne démarre pas
```bash
# Réinstaller les dépendances
pip install --break-system-packages -r requirements.txt
```

### Erreur base de données
```bash
# Supprimer et recréer la base
rm reperage.db
python3 app.py
```

### Les photos ne s'uploadent pas
```bash
# Vérifier que les dossiers existent
mkdir -p static/uploads/thumbnails
```

---

## 📝 PROCHAINES ÉTAPES

1. **Tester le prototype** ✓ Vous pouvez déjà tester
2. **Export PDF** → À implémenter
3. **Email notifications** → À configurer
4. **Dashboard admin** → À créer
5. **Migration PostgreSQL** → Pour la production
6. **Déploiement en ligne** → Quand vous êtes prêt

---

## 🎯 DIFFÉRENCES AVEC LA PRODUCTION

**Version actuelle (Prototype)** :
- SQLite (fichier local)
- Serveur de développement Flask
- Pas d'authentification
- Pas d'emails automatiques

**Version production (à venir)** :
- PostgreSQL (base professionnelle)
- Serveur production (Railway/Render)
- Authentification fixers
- Emails de notification
- Dashboard admin

---

## 📞 QUESTIONS ?

Cette version est un **prototype fonctionnel** pour que vous puissiez :
- Tester l'interface
- Voir comment fonctionne le multilingue
- Essayer l'upload de fichiers
- Comprendre le système

Testez-le et dites-moi ce que vous en pensez !

---

**Créé avec ❤️ pour Les Gardiens de la Tradition**
