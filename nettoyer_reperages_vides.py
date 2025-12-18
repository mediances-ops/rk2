#!/usr/bin/env python3
"""
Script de nettoyage : Supprimer les repérages vides/anonymes
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Reperage, Gardien, Lieu, Media, Message

# Configuration
DATABASE_URL = "sqlite:///reperage.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

print("🧹 NETTOYAGE DES REPÉRAGES VIDES")
print("=" * 70)

try:
    # Trouver tous les repérages vides
    reperages_vides = session.query(Reperage).filter(
        (Reperage.region == None) | (Reperage.region == '') | (Reperage.region == 'Non renseignée'),
        (Reperage.fixer_id == None)
    ).all()
    
    print(f"\n📋 {len(reperages_vides)} repérage(s) vide(s) trouvé(s)")
    
    if len(reperages_vides) == 0:
        print("✅ Aucun repérage à supprimer !")
        session.close()
        exit(0)
    
    # Afficher les repérages à supprimer
    for rep in reperages_vides:
        print(f"   - ID {rep.id}: {rep.region or 'Non renseignée'} / {rep.fixer_nom or 'Anonyme'} (créé le {rep.created_at})")
    
    # Demander confirmation
    print("\n⚠️  ATTENTION : Ces repérages vont être supprimés définitivement !")
    reponse = input("Continuer ? (oui/non) : ").strip().lower()
    
    if reponse not in ['oui', 'o', 'yes', 'y']:
        print("❌ Nettoyage annulé.")
        session.close()
        exit(0)
    
    # Supprimer
    compteur = 0
    for rep in reperages_vides:
        print(f"\n🗑️  Suppression repérage ID {rep.id}...")
        
        # Supprimer messages
        messages = session.query(Message).filter_by(reperage_id=rep.id).all()
        for msg in messages:
            session.delete(msg)
        
        # Supprimer gardiens
        gardiens = session.query(Gardien).filter_by(reperage_id=rep.id).all()
        for gardien in gardiens:
            session.delete(gardien)
        
        # Supprimer lieux
        lieux = session.query(Lieu).filter_by(reperage_id=rep.id).all()
        for lieu in lieux:
            session.delete(lieu)
        
        # Supprimer médias
        medias = session.query(Media).filter_by(reperage_id=rep.id).all()
        for media in medias:
            session.delete(media)
        
        # Supprimer repérage
        session.delete(rep)
        compteur += 1
        print(f"   ✅ Repérage ID {rep.id} supprimé")
    
    session.commit()
    print("\n" + "=" * 70)
    print(f"✅ NETTOYAGE TERMINÉ ! {compteur} repérage(s) supprimé(s)")
    print("=" * 70)

except Exception as e:
    session.rollback()
    print(f"\n❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
