"""
Migration : Ajouter champs enrichis à la table fixers
"""
import sqlite3
import os

DB_PATH = 'reperage.db'

def migrate():
    print("🔧 Migration : Enrichissement table Fixers")
    print("=" * 80)
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Erreur : Base de données '{DB_PATH}' non trouvée")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Vérifier colonnes existantes
        cursor.execute("PRAGMA table_info(fixers)")
        columns = [col[1] for col in cursor.fetchall()]
        
        print(f"📋 Colonnes actuelles : {len(columns)}")
        
        nouveaux_champs = [
            ('societe', 'VARCHAR(200)', 'Société/Agence'),
            ('fonction', 'VARCHAR(100)', 'Fonction/Poste'),
            ('adresse_1', 'VARCHAR(255)', 'Adresse ligne 1'),
            ('adresse_2', 'VARCHAR(255)', 'Adresse ligne 2'),
            ('code_postal', 'VARCHAR(20)', 'Code postal'),
            ('ville', 'VARCHAR(100)', 'Ville'),
            ('telephone_2', 'VARCHAR(50)', 'Téléphone secondaire'),
            ('site_web', 'VARCHAR(255)', 'Site internet'),
            ('photo_profil_url', 'VARCHAR(500)', 'URL photo profil'),
            ('bio', 'TEXT', 'Biographie'),
            ('specialites', 'TEXT', 'Spécialités/Expertises'),
            ('langues_parlees', 'VARCHAR(255)', 'Langues parlées'),
            ('numero_siret', 'VARCHAR(50)', 'Numéro SIRET'),
            ('notes_internes', 'TEXT', 'Notes privées admin')
        ]
        
        champs_ajoutes = 0
        
        for nom_champ, type_sql, description in nouveaux_champs:
            if nom_champ not in columns:
                print(f"➕ Ajout '{nom_champ}' ({description})...")
                cursor.execute(f"ALTER TABLE fixers ADD COLUMN {nom_champ} {type_sql}")
                champs_ajoutes += 1
                print(f"   ✅ Colonne '{nom_champ}' ajoutée")
            else:
                print(f"⏭️  '{nom_champ}' existe déjà")
        
        conn.commit()
        
        # Vérification finale
        cursor.execute("PRAGMA table_info(fixers)")
        columns_after = [col[1] for col in cursor.fetchall()]
        
        print("=" * 80)
        print(f"✅ Migration terminée !")
        print(f"📊 Colonnes avant : {len(columns)}")
        print(f"📊 Colonnes après : {len(columns_after)}")
        print(f"➕ Nouveaux champs : {champs_ajoutes}")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Erreur lors de la migration : {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
