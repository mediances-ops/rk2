# 🚀 DÉPLOIEMENT O2SWITCH - GUIDE COMPLET

**Pour:** RootsKeepers Application  
**Hébergeur:** o2switch (cPanel + Python + PostgreSQL)  
**Durée estimée:** 2-3 heures

---

## ✅ PRÉREQUIS

- Compte o2switch actif
- Accès cPanel
- Domaine configuré (ex: rootskeepers.votredomaine.com)
- Fichiers application (ce ZIP)

---

## 📋 ÉTAPE 1 : CRÉER BASE DE DONNÉES POSTGRESQL

### **1.1 Accéder à PostgreSQL dans cPanel**
```
cPanel → Databases → PostgreSQL Database Wizard
```

### **1.2 Créer la base de données**
```
Nom: rootskeepers_db
```

### **1.3 Créer utilisateur**
```
Nom utilisateur: rootskeepers_user
Mot de passe: [GÉNÉRER MOT DE PASSE FORT]
```
**⚠️ NOTER ces informations !**

### **1.4 Associer utilisateur à la base**
```
Privilèges: ALL PRIVILEGES
```

### **1.5 Noter les informations de connexion**
```
Host: localhost
Port: 5432
Database: rootskeepers_db
User: rootskeepers_user
Password: [votre mot de passe]
```

---

## 📁 ÉTAPE 2 : UPLOADER LES FICHIERS

### **2.1 Via File Manager cPanel**
```
1. cPanel → File Manager
2. Naviguer vers /home/votrecompte/votredomaine.com/
3. Upload le ZIP complet
4. Extraire le ZIP
5. Déplacer le contenu de reperage-app-v2/ vers la racine
```

### **2.2 Structure finale**
```
/home/votrecompte/votredomaine.com/
├── passenger_wsgi.py  ⭐ IMPORTANT
├── app.py
├── models.py
├── requirements.txt
├── .env  (à créer)
├── static/
├── templates/
├── translations/
└── migrations/
```

---

## 🔧 ÉTAPE 3 : CONFIGURER PYTHON APP

### **3.1 Accéder à Setup Python App**
```
cPanel → Software → Setup Python App
```

### **3.2 Créer nouvelle application**
```
Python version: 3.9 (ou supérieur disponible)
Application root: /home/votrecompte/votredomaine.com
Application URL: votredomaine.com (ou sous-domaine)
Application startup file: passenger_wsgi.py
Application Entry point: application
```

### **3.3 Créer l'environnement virtuel**
```
Cliquer "Create"
Attendre création virtualenv (~2 minutes)
```

---

## 📦 ÉTAPE 4 : INSTALLER DÉPENDANCES

### **4.1 Accéder au Terminal SSH**
```
cPanel → Advanced → Terminal
```

### **4.2 Activer l'environnement virtuel**
```bash
source /home/votrecompte/virtualenv/rootskeepers/3.9/bin/activate
```

### **4.3 Naviguer vers l'application**
```bash
cd /home/votrecompte/votredomaine.com
```

### **4.4 Installer les dépendances**
```bash
pip install -r requirements.txt
```

### **4.5 Installer psycopg2 (PostgreSQL)**
```bash
pip install psycopg2-binary
```

---

## 🔐 ÉTAPE 5 : VARIABLES D'ENVIRONNEMENT

### **5.1 Créer fichier .env**
```bash
nano .env
```

### **5.2 Contenu du fichier .env**
```bash
# Base de données PostgreSQL
DATABASE_URL=postgresql://rootskeepers_user:VOTRE_MOT_DE_PASSE@localhost:5432/rootskeepers_db

# Clé secrète Flask (générer une nouvelle)
SECRET_KEY=votre-cle-secrete-aleatoire-longue

# Mode production
FLASK_ENV=production
DEBUG=False

# Upload
MAX_CONTENT_LENGTH=52428800
UPLOAD_FOLDER=/home/votrecompte/votredomaine.com/uploads

# URLs
BASE_URL=https://votredomaine.com
```

**💡 Générer SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### **5.3 Sauvegarder**
```
Ctrl+O (save)
Ctrl+X (exit)
```

---

## 🗄️ ÉTAPE 6 : ADAPTER app.py POUR POSTGRESQL

### **6.1 Modifier la connexion BDD**

**Remplacer cette ligne dans app.py:**
```python
# AVANT (SQLite local)
engine = init_db('sqlite:///reperage.db')
```

**Par:**
```python
# APRÈS (PostgreSQL production)
import os
from dotenv import load_dotenv

load_dotenv()  # Charger variables .env

database_url = os.getenv('DATABASE_URL', 'sqlite:///reperage.db')
engine = init_db(database_url)
```

### **6.2 Ajouter dans requirements.txt**
```
python-dotenv==1.0.0
psycopg2-binary==2.9.9
```

---

## 🔄 ÉTAPE 7 : INITIALISER LA BASE

### **7.1 Créer les tables**
```bash
python3 -c "from models import init_db; init_db('postgresql://rootskeepers_user:MOT_DE_PASSE@localhost:5432/rootskeepers_db')"
```

### **7.2 Exécuter migrations**
```bash
python3 migrate_add_numero_lieu.py
python3 migrate_add_chat.py
```

---

## 🚀 ÉTAPE 8 : REDÉMARRER L'APPLICATION

### **8.1 Dans Setup Python App**
```
Cliquer sur "Restart" ou "Stop/Start"
```

### **8.2 Créer fichier tmp/restart.txt**
```bash
mkdir -p tmp
touch tmp/restart.txt
```
**💡 À chaque modification, toucher ce fichier pour redémarrer**

---

## ✅ ÉTAPE 9 : TESTER

### **9.1 Accéder à l'URL**
```
https://votredomaine.com
```

### **9.2 Vérifier pages**
- ✅ Page d'accueil formulaire
- ✅ /admin (dashboard)
- ✅ Upload photos
- ✅ Chat fonctionnel
- ✅ Export PDF

### **9.3 Créer premier fixer**
```
/admin/fixers → Nouveau fixer
Tester le lien généré
```

---

## 🔒 ÉTAPE 10 : SÉCURITÉ

### **10.1 Permissions fichiers**
```bash
chmod 644 .env
chmod 755 uploads/
chmod 644 passenger_wsgi.py
```

### **10.2 Protéger .env**
Ajouter dans `.htaccess`:
```apache
<Files ".env">
    Order allow,deny
    Deny from all
</Files>
```

### **10.3 HTTPS**
```
cPanel → SSL/TLS → Let's Encrypt
Activer SSL pour le domaine
```

---

## 🐛 DÉPANNAGE

### **Erreur 500**
```bash
# Voir logs Passenger
tail -f /home/votrecompte/logs/rootskeepers_error.log
```

### **Module non trouvé**
```bash
# Réinstaller dépendances
source /home/votrecompte/virtualenv/rootskeepers/3.9/bin/activate
pip install -r requirements.txt
```

### **Base de données inaccessible**
```bash
# Vérifier connexion PostgreSQL
psql -h localhost -U rootskeepers_user -d rootskeepers_db
```

### **Redémarrer l'app**
```bash
touch tmp/restart.txt
```

---

## 📝 CHECKLIST FINALE

- [ ] Base PostgreSQL créée
- [ ] Fichiers uploadés
- [ ] Python App configurée
- [ ] Dépendances installées
- [ ] .env configuré
- [ ] app.py adapté pour PostgreSQL
- [ ] Tables BDD créées
- [ ] Migrations exécutées
- [ ] Application redémarrée
- [ ] HTTPS activé
- [ ] Tests OK
- [ ] Premier fixer créé

---

## 📞 SUPPORT O2SWITCH

**Si problème technique:**
```
Support o2switch: https://www.o2switch.fr/support
Ticket: depuis cPanel
Chat: disponible 24/7
```

---

**Version:** 1.0  
**Application:** RootsKeepers  
**Date:** Décembre 2025  
**Status:** Prêt pour déploiement
