from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import json
import os

Base = declarative_base()

# =================================================================
# 1. MODÈLE FIXER (RÉSEAU INTERNATIONAL)
# =================================================================
class Fixer(Base):
    __tablename__ = 'fixers'
    
    id = Column(Integer, primary_key=True)
    # Identité & Contact
    nom = Column(String(100))
    prenom = Column(String(100))
    email = Column(String(200), unique=True)
    telephone = Column(String(50))
    telephone_2 = Column(String(50))
    
    # Professionnel
    societe = Column(String(200))
    fonction = Column(String(100))
    site_web = Column(String(255))
    numero_siret = Column(String(50))
    
    # Localisation
    adresse_1 = Column(String(255))
    adresse_2 = Column(String(255))
    code_postal = Column(String(20))
    ville = Column(String(100))
    pays = Column(String(100))
    region = Column(String(200))
    
    # Profil Substantiel
    photo_profil_url = Column(String(500))
    bio = Column(Text)
    specialites = Column(Text)
    langues_parlees = Column(String(255))
    langue_preferee = Column(String(10), default='FR')
    
    # Système
    token_unique = Column(String(12), unique=True)
    lien_personnel = Column(String(500))
    actif = Column(Boolean, default=True)
    notes_internes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    # Lien vers les repérages
    reperages = relationship("Reperage", backref="fixer_rel")

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        if d.get('created_at'): d['created_at'] = d['created_at'].isoformat()
        return d

# =================================================================
# 2. MODÈLE REPÉRAGE (CENTRE DE PILOTAGE - 5 ONGLETS)
# =================================================================
class Reperage(Base):
    __tablename__ = 'reperages'
    
    id = Column(Integer, primary_key=True)
    token = Column(String(32), unique=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    statut = Column(String(20), default='brouillon')
    progression_pourcent = Column(Integer, default=0) # Jauge synchronisée
    
    # Cache identité
    fixer_id = Column(Integer, ForeignKey('fixers.id'))
    fixer_nom = Column(String(255))
    pays = Column(String(100))
    region = Column(String(255))
    image_region = Column(String(500))
    
    # SEGMENTS HAUTE SUBSTANCE (JSON)
    territoire_data = Column(Text, default="{}")
    particularite_data = Column(Text, default="{}")
    fete_data = Column(Text, default="{}")
    episode_data = Column(Text, default="{}")
    notes_admin = Column(Text)
    
    # RELATIONS AVEC CASCADES INTÉGRALES
    gardiens = relationship("Gardien", back_populates="reperage", cascade="all, delete-orphan")
    lieux = relationship("Lieu", back_populates="reperage", cascade="all, delete-orphan")
    medias = relationship("Media", back_populates="reperage", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="reperage", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'token': self.token,
            'statut': self.statut,
            'progression_pourcent': self.progression_pourcent,
            'fixer_nom': self.fixer_nom,
            'pays': self.pays,
            'region': self.region,
            'image_region': self.image_region,
            'notes_admin': self.notes_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'territoire_data': json.loads(self.territoire_data or "{}"),
            'particularite_data': json.loads(self.particularite_data or "{}"),
            'fete_data': json.loads(self.fete_data or "{}"),
            'episode_data': json.loads(self.episode_data or "{}"),
            'gardiens': [g.to_dict() for g in self.gardiens],
            'lieux': [l.to_dict() for l in self.lieux],
            'medias': [m.to_dict() for m in self.medias]
        }

# =================================================================
# 3. MODÈLE GARDIEN (TRIPTYQUE HUMAIN - 10 CHAMPS)
# =================================================================
class Gardien(Base):
    __tablename__ = 'gardiens'
    
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    ordre = Column(Integer) # 1, 2 ou 3
    
    nom_prenom = Column(String(255))
    age = Column(Integer)
    fonction = Column(String(255))
    savoir = Column(Text)
    histoire = Column(Text)
    psychologie = Column(Text)
    evaluation = Column(Text)
    langues = Column(String(255))
    contact = Column(Text)
    intermediaire = Column(Text)
    
    reperage = relationship("Reperage", back_populates="gardiens")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# =================================================================
# 4. MODÈLE LIEU (TRIPTYQUE TECHNIQUE - 15 CHAMPS)
# =================================================================
class Lieu(Base):
    __tablename__ = 'lieux'
    
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    numero_lieu = Column(Integer) # 1, 2 ou 3
    
    nom = Column(String(255))
    type = Column(String(255))
    description = Column(Text)
    cinegenie = Column(Text)
    axes = Column(Text)
    points_vue = Column(Text)
    moments = Column(Text)
    son = Column(Text)
    adequation = Column(Text)
    acces = Column(Text)
    securite = Column(Text)
    elec = Column(Text)
    espace = Column(Text)
    meteo = Column(Text)
    permis = Column(Text)
    
    reperage = relationship("Reperage", back_populates="lieux")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# =================================================================
# 5. SYSTÈME MÉDIAS & CHAT COLLABORATIF
# =================================================================
class Media(Base):
    __tablename__ = 'medias'
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    type = Column(String(50))
    nom_fichier = Column(String(255))
    nom_original = Column(String(255))
    chemin_fichier = Column(String(500))
    uploaded_at = Column(DateTime, default=datetime.now)
    
    reperage = relationship("Reperage", back_populates="medias")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    auteur_type = Column(String(20)) # 'production' ou 'fixer'
    auteur_nom = Column(String(255))
    contenu = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    lu = Column(Boolean, default=False)
    
    reperage = relationship("Reperage", back_populates="messages")

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        if d.get('created_at'): d['created_at'] = d['created_at'].isoformat()
        return d

# =================================================================
# 6. INITIALISATION MOTEUR
# =================================================================
def init_db(database_url):
    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
