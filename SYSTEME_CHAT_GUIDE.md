# SYSTÈME DE CHAT - GUIDE COMPLET

## FONCTIONNALITÉS

### Messagerie intégrée Production ↔ Fixer

✅ **Panneau latéral élégant**
- Slide depuis la droite
- Animation fluide
- Design moderne violet/bleu

✅ **Communication asynchrone**
- Messages Production (violet)
- Messages Fixer (bleu clair)
- Timestamp sur chaque message
- Identité claire de l'auteur

✅ **Expérience utilisateur optimale**
- Badge de notification (nombre non lus)
- Scroll automatique vers dernier message
- Envoi avec Entrée (Shift+Entrée = saut ligne)
- Indicateur "en train d'écrire..."
- Polling automatique (5 sec si ouvert, 10 sec si fermé)

✅ **Persistance en base de données**
- Tous les messages sauvegardés
- Statut lu/non lu
- Historique complet

---

## INSTALLATION

### 1. Arrêter le serveur
```bash
Ctrl + C
```

### 2. Remplacer les fichiers
Extraire le ZIP et remplacer tous les fichiers

### 3. Migration BDD
```bash
python migrate_add_chat.py
```

**Vous devriez voir :**
```
============================================================
MIGRATION: Ajout du système de chat
============================================================
🔄 Création de la table messages...
✅ Migration réussie !
   - Table messages créée
   - Index ajoutés pour les performances

💬 Le système de chat est maintenant opérationnel !
```

### 4. Redémarrer
```bash
python app.py
```

---

## UTILISATION

### **Pour les Fixers (Correspondants locaux)**

1. Ouvrir le formulaire de repérage
2. Voir le **bouton flottant 💬** en bas à droite
3. Cliquer pour ouvrir le panneau de chat
4. Écrire un message
5. Envoyer avec **Entrée** ou le bouton **Envoyer**

**Badge de notification :**
- Un chiffre rouge apparaît quand nouveaux messages de la Production
- Disparaît quand vous ouvrez le chat

### **Pour la Production (Admin)**

1. Aller sur `/admin/reperage/<id>`
2. Même bouton flottant 💬
3. Voir tous les messages du fixer
4. Répondre directement

---

## APERÇU VISUEL

```
┌─────────────────────────────────────────┐
│  [Formulaire]                    [💬 3] │ ← Badge (3 non lus)
│                                         │
│  Territoire: ...                        │
│  Épisode: ...                           │
│                                         │
└─────────────────────────────────────────┘

Clic sur 💬 →

┌─────────────────────┬───────────────────┐
│  [Formulaire]       │ 💬 Messages  [×]  │
│                     ├───────────────────┤
│  Territoire: ...    │ Production 14:30  │
│  Épisode: ...       │ ┌─────────────────┤
│                     │ │Besoin photo     │
│                     │ │atelier          │
│                     │ └─────────────────┤
│                     │                   │
│                     │ Vous 14:35        │
│                     │ ┌─────────────────┤
│                     │ │OK je fais ça    │
│                     │ │demain matin     │
│                     │ └─────────────────┤
│                     │                   │
│                     │ [Écrire message...│
│                     │              [▶]] │
└─────────────────────┴───────────────────┘
```

---

## CARACTÉRISTIQUES TECHNIQUES

### **Table BDD : messages**
```sql
- id (PK)
- reperage_id (FK)
- auteur_type (production/fixer)
- auteur_nom (nom affiché)
- contenu (texte du message)
- created_at (timestamp)
- lu (boolean)
```

### **API REST**
```
GET  /api/reperages/<id>/messages              → Liste messages
POST /api/reperages/<id>/messages              → Nouveau message
PUT  /api/messages/<id>/read                   → Marquer lu
GET  /api/reperages/<id>/messages/unread-count → Compteur non lus
```

### **Polling automatique**
- **Chat ouvert :** Recharge toutes les 5 secondes
- **Chat fermé :** Vérifie nouveaux messages toutes les 10 secondes

### **Statut lu/non lu**
- Messages Production → marqués lus quand Fixer ouvre chat
- Messages Fixer → marqués lus quand Production ouvre chat

---

## TESTS

### Test 1 : Envoi message fixer
```
1. Ouvrir formulaire fixer
2. Cliquer sur bouton 💬
3. Écrire "Test message fixer"
4. Appuyer sur Entrée
5. Message apparaît en bleu clair (droite)
```

### Test 2 : Badge notification
```
1. Admin envoie un message
2. Fixer voit badge rouge avec "1"
3. Fixer ouvre chat
4. Badge disparaît
```

### Test 3 : Historique
```
1. Envoyer plusieurs messages
2. Fermer le chat
3. Rouvrir le chat
4. Tous les messages sont là
```

### Test 4 : Envoi avec Entrée
```
1. Écrire message
2. Appuyer sur Entrée → Envoyé
3. Shift+Entrée → Saut de ligne (pas envoyé)
```

---

## AVANTAGES

✅ **Communication centralisée**
- Tout au même endroit
- Plus besoin d'emails/WhatsApp externes
- Contextuel (lié au repérage)

✅ **Traçabilité complète**
- Historique permanent
- Timestamp précis
- Identité claire

✅ **Expérience fluide**
- Pas de rechargement page
- Notifications visuelles
- Interface intuitive

✅ **Asynchrone**
- Chacun répond quand il peut
- Pas de pression temps réel
- Historique consultable

---

## ÉVOLUTIONS FUTURES POSSIBLES

### Version WebSocket (temps réel)
- Pas de polling (économie serveur)
- Notification instantanée
- Indicateur "en ligne"

### Pièces jointes
- Upload image dans chat
- Partage documents

### Édition/Suppression
- Modifier message envoyé
- Supprimer message

### Notifications email
- Email quand nouveau message
- Configurable par utilisateur

---

## FICHIERS MODIFIÉS

```
✅ models.py                     (modèle Message)
✅ app.py                        (4 routes API chat)
✅ templates/index.html          (panneau chat HTML)
✅ static/css/style.css          (styles chat)
✅ static/js/app.js              (logique chat JS)
✅ migrate_add_chat.py           (migration BDD)
```

---

## DÉPANNAGE

### Le bouton chat n'apparaît pas
- Vider cache navigateur (Ctrl + F5)
- Vérifier console JavaScript (F12)

### Les messages ne s'affichent pas
- Vérifier migration exécutée
- Vérifier logs serveur
- Tester API : `GET /api/reperages/1/messages`

### Badge ne se met pas à jour
- Attendre 10 secondes (polling)
- Recharger page

---

**Version :** 2.5
**Date :** 1er décembre 2025
**Fonctionnalité :** Chat Production ↔ Fixer
**Status :** ✅ OPÉRATIONNEL
