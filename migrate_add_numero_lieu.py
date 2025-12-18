#!/usr/bin/env python3
"""
Migration: Ajout du champ numero_lieu à la table lieux
Permet de gérer 3 lieux distincts par repérage (Lieu 1, Lieu 2, Lieu 3)
"""

import sqlite3
import os

def migrate():
    db_path = 'reperage.db'
    
    if not os.path.exists(db_path):
        print("❌ Base de données non trouvée. Rien à migrer.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Vérifier si la colonne existe déjà
        cursor.execute("PRAGMA table_info(lieux)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'numero_lieu' in columns:
            print("✅ La colonne numero_lieu existe déjà. Migration annulée.")
            return
        
        print("🔄 Ajout de la colonne numero_lieu...")
        
        # Ajouter la colonne
        cursor.execute("""
            ALTER TABLE lieux 
            ADD COLUMN numero_lieu INTEGER DEFAULT 1
        """)
        
        # Mettre à jour tous les lieux existants avec numero_lieu = 1
        cursor.execute("""
            UPDATE lieux 
            SET numero_lieu = 1 
            WHERE numero_lieu IS NULL
        """)
        
        conn.commit()
        print("✅ Migration réussie !")
        print("   - Colonne numero_lieu ajoutée")
        print("   - Tous les lieux existants définis à numero_lieu = 1")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Erreur lors de la migration : {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("MIGRATION: Ajout du champ numero_lieu")
    print("=" * 60)
    migrate()
