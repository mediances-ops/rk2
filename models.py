from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import json
import os

Base = declarative_base()

# =================================================================
# 1. MODÈLE FIXER (CORRESPONDANT)
# =================================================================
class Fixer(Base):
    __tablename__ = 'fixers'
    
    id = Column(Integer, primary_key=True)
    # Identité
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
    
    # Adresse
    adresse_1 = Column(String(255))
    adresse_2 = Column(String(255))
    code_postal = Column(String(20))
    ville = Column(String(100))
    pays = Column(String(100))
    region = Column(String(200))
    
    # Profil & Bio
    photo_profil_url = Column(String(500))
    bio = Column(Text)
    specialites = Column(Text)
    
    # Langues
    langues_parlees = Column(String(255))
    langue_preferee = Column(String(10), default='FR')
    
    # Système
    token_unique = Column(String(12), unique=True)
    lien_personnel = Column(String(500))
    actif = Column(Boolean, default=True)
    notes_internes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relation vers repérages
    reperages = relationship("Reperage", backref="fixer_rel")

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        if d.get('created_at'): d['created_at'] = d['created_at'].isoformat()
        return d

# =================================================================
# 2. MODÈLE REPÉRAGE (PIVOT CENTRAL)
# =================================================================
class Reperage(Base):
    __tablename__ = 'reperages'
    
    id = Column(Integer, primary_key=True)
    token = Column(String(32), unique=True) # Token URL
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    langue_interface = Column(String(10), default='FR')
    statut = Column(String(20), default='brouillon')
    progression_pourcent = Column(Integer, default=0) # Pour la Jauge
    
    # Cache Fixer pour le Dashboard
    fixer_id = Column(Integer, ForeignKey('fixers.id'))
    fixer_nom = Column(String(255))
    fixer_prenom = Column(String(255))
    fixer_email = Column(String(255))
    fixer_telephone = Column(String(50))
    
    # Localisation
    pays = Column(String(100))
    region = Column(String(255))
    image_region = Column(String(500)) # Lien bannière
    
    # Données Segmentées JSON
    territoire_data = Column(Text, default="{}")
    episode_data = Column(Text, default="{}")
    notes_admin = Column(Text) # Notes privées production
    
    # Relations avec cascades intégrales
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
            'fixer_prenom': self.fixer_prenom,
            'pays': self.pays,
            'region': self.region,
            'image_region': self.image_region,
            'notes_admin': self.notes_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'territoire_data': json.loads(self.territoire_data) if self.territoire_data else {},
            'episode_data': json.loads(self.episode_data) if self.episode_data else {},
            'gardiens': [g.to_dict() for g in self.gardiens],
            'lieux': [l.to_dict() for l in self.lieux],
            'medias': [m.to_dict() for m in self.medias]
        }

# =================================================================
# 3. MODÈLE GARDIEN (TRIPTYQUE NARRATIF)
# =================================================================
class Gardien(Base):
    __tablename__ = 'gardiens'
    
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    ordre = Column(Integer) # 1, 2, 3
    
    nom = Column(String(255))
    prenom = Column(String(255))
    age = Column(Integer)
    genre = Column(String(50))
    fonction = Column(String(255))
    savoir_transmis = Column(Text)
    
    adresse = Column(Text)
    telephone = Column(String(50))
    email = Column(String(255))
    contact_intermediaire = Column(Text)
    
    histoire_personnelle = Column(Text)
    evaluation_cinegenie = Column(Text)
    langues_parlees = Column(String(255))
    photo_url = Column(String(500))
    
    reperage = relationship("Reperage", back_populates="gardiens")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# =================================================================
# 4. MODÈLE LIEU (TRIPTYQUE TECHNIQUE)
# =================================================================
class Lieu(Base):
    __tablename__ = 'lieux'
    
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    numero_lieu = Column(Integer, default=1) # 1, 2, 3
    
    nom = Column(String(255))
    type_environnement = Column(String(255))
    description_visuelle = Column(Text)
    points_vue_remarquables = Column(Text)
    
    cinegenie = Column(Text)
    axes_camera = Column(Text)
    moments_favorables = Column(Text)
    ambiance_sonore = Column(Text)
    adequation_narration = Column(Text)
    
    accessibilite = Column(Text)
    securite = Column(Text)
    electricite = Column(String(50))
    espace_equipe = Column(Text)
    protection_meteo = Column(Text)
    autorisations_necessaires = Column(Text)
    
    latitude = Column(Float)
    longitude = Column(Float)
    
    reperage = relationship("Reperage", back_populates="lieux")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# =================================================================
# 5. MODÈLES SYSTÈME (MÉDIAS & CHAT)
# =================================================================
class Media(Base):
    __tablename__ = 'medias'
    
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    type = Column(String(50)) # photo, document
    nom_fichier = Column(String(255))
    nom_original = Column(String(255))
    chemin_fichier = Column(String(500))
    taille_octets = Column(Integer)
    uploaded_at = Column(DateTime, default=datetime.now)
    
    reperage = relationship("Reperage", back_populates="medias")

    def to_dict(self):
        return {
            'id': self.id, 'type': self.type, 'nom_original': self.nom_original,
            'nom_fichier': self.nom_fichier, 'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    auteur_type = Column(String(20)) # production, fixer
    auteur_nom = Column(String(255))
    contenu = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    lu = Column(Boolean, default=False)
    
    reperage = relationship("Reperage", back_populates="messages")

    def to_dict(self):
        return {
            'id': self.id, 'auteur_type': self.auteur_type, 'auteur_nom': self.auteur_nom,
            'contenu': self.contenu, 'lu': self.lu, 
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# =================================================================
# 6. INITIALISATION MOTEUR
# =================================================================
def init_db(database_url):
    # Support PostgreSQL et SQLite
    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
