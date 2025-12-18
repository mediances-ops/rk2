#!/usr/bin/env python3
"""
Migration : Ajouter colonne 'token' à la table reperages
"""
import secrets
from sqlalchemy import create_engine, Column, String, inspect, text
from sqlalchemy.orm import sessionmaker
from models import Reperage

# Configuration
DATABASE_URL = "sqlite:///reperage.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def generate_token():
    """Générer un token aléatoire sécurisé"""
    return secrets.token_urlsafe(16)  # 16 bytes = ~21 caractères

print("🔄 MIGRATION : Ajout colonne 'token' aux repérages")
print("=" * 70)

try:
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('reperages')]
    
    if 'token' in columns:
        print("✅ Colonne 'token' existe déjà !")
    else:
        print("📝 Ajout de la colonne 'token'...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE reperages ADD COLUMN token VARCHAR(32)"))
            conn.commit()
        print("✅ Colonne 'token' ajoutée !")
    
    # Générer tokens pour repérages existants
    print("\n🔐 Génération des tokens pour repérages existants...")
    reperages = session.query(Reperage).filter(
        (Reperage.token == None) | (Reperage.token == '')
    ).all()
    
    if len(reperages) == 0:
        print("✅ Tous les repérages ont déjà un token !")
    else:
        for rep in reperages:
            rep.token = generate_token()
            print(f"   ✅ Repérage #{rep.id} → {rep.token}")
        
        session.commit()
        print(f"\n✅ {len(reperages)} token(s) généré(s) avec succès !")
    
    print("\n" + "=" * 70)
    print("✅ MIGRATION TERMINÉE !")
    print("=" * 70)

except Exception as e:
    session.rollback()
    print(f"\n❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
