#!/usr/bin/env python3
"""
Migration: Ajout de la table messages pour le chat Production <-> Fixer
"""

import sqlite3
import os

def migrate():
    db_path = 'reperage.db'
    
    if not os.path.exists(db_path):
        print("❌ Base de données non trouvée.")
        print("   Exécutez d'abord 'python app.py' pour créer la BDD.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Vérifier si la table existe déjà
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if cursor.fetchone():
            print("✅ La table messages existe déjà. Migration annulée.")
            return
        
        print("🔄 Création de la table messages...")
        
        # Créer la table messages
        cursor.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reperage_id INTEGER NOT NULL,
                auteur_type VARCHAR(20) NOT NULL,
                auteur_nom VARCHAR(255) NOT NULL,
                contenu TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                lu BOOLEAN DEFAULT 0,
                FOREIGN KEY (reperage_id) REFERENCES reperages(id) ON DELETE CASCADE
            )
        """)
        
        # Créer des index pour optimiser les requêtes
        cursor.execute("""
            CREATE INDEX idx_messages_reperage 
            ON messages(reperage_id)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_messages_lu 
            ON messages(reperage_id, auteur_type, lu)
        """)
        
        conn.commit()
        print("✅ Migration réussie !")
        print("   - Table messages créée")
        print("   - Index ajoutés pour les performances")
        print("\n💬 Le système de chat est maintenant opérationnel !")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Erreur lors de la migration : {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("MIGRATION: Ajout du système de chat")
    print("=" * 60)
    migrate()
