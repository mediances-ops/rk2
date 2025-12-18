# 🚀 GUIDE D'UTILISATION - FICHIERS .BAT

**Date :** 12 décembre 2025  
**Application :** RootsKeepers v2 - Phase 1

---

## 📁 FICHIERS FOURNIS

Vous avez 3 fichiers .BAT pour gérer facilement le serveur :

1. **START_SERVER.bat** → Démarre le serveur
2. **STOP_SERVER.bat** → Arrête le serveur
3. **OPEN_APP.bat** → Ouvre l'application dans le navigateur

---

## 📦 INSTALLATION

### **1. Extraire le ZIP**

Extraire **reperage-production-PHASE1.zip** dans :
```
D:\Downloads\HTML Multilingues\reperage-production
```

### **2. Copier les fichiers .BAT**

Copier les 3 fichiers .BAT dans le même dossier :
```
D:\Downloads\HTML Multilingues\reperage-production\
├── START_SERVER.bat
├── STOP_SERVER.bat
├── OPEN_APP.bat
├── app.py
├── models.py
└── ...
```

---

## 🚀 UTILISATION

### **DÉMARRER LE SERVEUR**

**Double-cliquez sur :** `START_SERVER.bat`

**Ce qui se passe :**
1. Vérification du dossier ✅
2. Vérification Python ✅
3. Démarrage du serveur Flask

**Vous verrez :**
```
========================================
 SERVEUR DEMARRE !
 URL: http://127.0.0.1:5000
 
 Admin: http://127.0.0.1:5000/admin
 
 Pour ARRETER: Appuyez sur Ctrl+C
========================================

 * Running on http://127.0.0.1:5000
```

**⚠️ NE FERMEZ PAS CETTE FENÊTRE !**  
Elle doit rester ouverte tant que vous utilisez l'application.

---

### **OUVRIR L'APPLICATION**

**Double-cliquez sur :** `OPEN_APP.bat`

**Ce qui se passe :**
- Votre navigateur s'ouvre automatiquement sur l'admin
- http://127.0.0.1:5000/admin

**OU ouvrez manuellement dans votre navigateur :**
- Admin : http://127.0.0.1:5000/admin
- Fixer : http://127.0.0.1:5000/fixer/test-abc123

---

### **ARRÊTER LE SERVEUR**

**Méthode 1 (recommandée) :**
Dans la fenêtre où tourne le serveur, appuyez sur `Ctrl + C`

**Méthode 2 :**
Double-cliquez sur `STOP_SERVER.bat`  
(Tue tous les processus Python)

---

## 🔄 WORKFLOW COMPLET

### **Démarrage**
```
1. START_SERVER.bat (double-clic)
2. Attendre "Running on http://127.0.0.1:5000"
3. OPEN_APP.bat (double-clic)
4. Travailler dans l'application
```

### **Arrêt**
```
1. Ctrl+C dans la fenêtre serveur
   OU
   STOP_SERVER.bat (double-clic)
```

---

## ⚠️ RÉSOLUTION PROBLÈMES

### **"Python n'est pas reconnu..."**

**Solution :**
```bash
# Vérifier que Python est installé
python --version
```

Si ça ne marche pas, Python n'est pas dans le PATH.

**Correction temporaire :**
Modifier `START_SERVER.bat` ligne 29 :
```batch
:: Remplacer
python app.py

:: Par (avec votre chemin Python complet)
"C:\Users\VotreNom\AppData\Local\Programs\Python\Python311\python.exe" app.py
```

---

### **"app.py introuvable"**

**Solution :**
Vérifier que vous avez bien extrait le ZIP dans :
```
D:\Downloads\HTML Multilingues\reperage-production
```

Et que les fichiers .BAT sont bien dans ce dossier.

---

### **"Port 5000 already in use"**

**Solution :**
Un serveur tourne déjà !

1. Lancer `STOP_SERVER.bat`
2. Relancer `START_SERVER.bat`

---

### **Serveur démarre mais page blanche**

**Solution :**
1. Vérifier l'URL : http://127.0.0.1:5000/admin (avec /admin)
2. Vider le cache navigateur (Ctrl + F5)
3. Vérifier la console serveur (erreurs Python ?)

---

## 🎯 TESTS À FAIRE

Une fois le serveur démarré, suivre le guide :
**TEST_PHASE_1.md**

---

## 💡 ASTUCES

### **Créer des raccourcis sur le Bureau**

1. Clic-droit sur `START_SERVER.bat` → Créer un raccourci
2. Déplacer le raccourci sur le Bureau
3. Renommer en "🚀 Démarrer RootsKeepers"

Même chose pour `OPEN_APP.bat` :
- Renommer en "🌍 Ouvrir RootsKeepers"

---

### **Logs en temps réel**

Dans la fenêtre du serveur, vous verrez toutes les requêtes :
```
127.0.0.1 - - [12/Dec/2025 10:30:15] "GET /admin HTTP/1.1" 200 -
127.0.0.1 - - [12/Dec/2025 10:30:18] "POST /api/reperages HTTP/1.1" 201 -
```

C'est utile pour le debug ! 🔍

---

## ✅ CHECKLIST DÉMARRAGE

- [ ] ZIP extrait dans le bon dossier
- [ ] 3 fichiers .BAT copiés
- [ ] START_SERVER.bat lancé
- [ ] Message "Running on http://127.0.0.1:5000" affiché
- [ ] OPEN_APP.bat lancé OU URL ouverte manuellement
- [ ] Page admin s'affiche correctement

---

## 📞 BESOIN D'AIDE ?

Si problème, notez :
1. Quel fichier .BAT vous avez lancé
2. Le message d'erreur EXACT
3. Ce qui s'affiche dans la fenêtre du serveur

Et dites-le moi ! 💬

---

**BON DÉMARRAGE ! 🚀**
