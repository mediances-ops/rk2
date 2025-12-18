"""
Migration : Ajouter colonnes notes_admin, image_region et fixer_prenom à la table reperages
"""
import sqlite3
import os

DB_PATH = 'reperage.db'

def migrate():
    print("🔧 Migration : Ajout de notes_admin, image_region et fixer_prenom")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Erreur : Base de données '{DB_PATH}' non trouvée")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Vérifier si les colonnes existent déjà
        cursor.execute("PRAGMA table_info(reperages)")
        columns = [col[1] for col in cursor.fetchall()]
        
        print(f"📋 Colonnes actuelles : {len(columns)}")
        
        # Ajouter notes_admin si elle n'existe pas
        if 'notes_admin' not in columns:
            print("➕ Ajout de la colonne 'notes_admin'...")
            cursor.execute("ALTER TABLE reperages ADD COLUMN notes_admin TEXT")
            print("✅ Colonne 'notes_admin' ajoutée")
        else:
            print("⏭️  Colonne 'notes_admin' existe déjà")
        
        # Ajouter image_region si elle n'existe pas
        if 'image_region' not in columns:
            print("➕ Ajout de la colonne 'image_region'...")
            cursor.execute("ALTER TABLE reperages ADD COLUMN image_region VARCHAR(500)")
            print("✅ Colonne 'image_region' ajoutée")
        else:
            print("⏭️  Colonne 'image_region' existe déjà")
        
        # Ajouter fixer_prenom si elle n'existe pas
        if 'fixer_prenom' not in columns:
            print("➕ Ajout de la colonne 'fixer_prenom'...")
            cursor.execute("ALTER TABLE reperages ADD COLUMN fixer_prenom VARCHAR(255)")
            print("✅ Colonne 'fixer_prenom' ajoutée")
        else:
            print("⏭️  Colonne 'fixer_prenom' existe déjà")
        
        conn.commit()
        
        # Vérification finale
        cursor.execute("PRAGMA table_info(reperages)")
        columns_after = [col[1] for col in cursor.fetchall()]
        
        print("=" * 60)
        print(f"✅ Migration terminée !")
        print(f"📊 Nombre de colonnes : {len(columns_after)}")
        print(f"📋 Nouvelles colonnes : notes_admin, image_region, fixer_prenom")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Erreur lors de la migration : {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
