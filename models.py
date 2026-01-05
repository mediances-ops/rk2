from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import json
import os

Base = declarative_base()

class Reperage(Base):
    __tablename__ = 'reperages'
    
    id = Column(Integer, primary_key=True)
    token = Column(String(32), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    langue_interface = Column(String(4), default='FR')
    statut = Column(String(20), default='brouillon')
    
    fixer_id = Column(Integer, ForeignKey('fixers.id'), nullable=True)
    fixer_nom = Column(String(255))
    fixer_prenom = Column(String(255))
    fixer_email = Column(String(255))
    fixer_telephone = Column(String(50))
    
    pays = Column(String(100))
    region = Column(String(255))
    territoire_data = Column(Text)
    episode_data = Column(Text)
    
    notes_admin = Column(Text)
    image_region = Column(String(500))
    
    gardiens = relationship("Gardien", back_populates="reperage", cascade="all, delete-orphan")
    lieux = relationship("Lieu", back_populates="reperage", cascade="all, delete-orphan")
    medias = relationship("Media", back_populates="reperage", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'token': self.token,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'langue_interface': self.langue_interface,
            'statut': self.statut,
            'fixer_nom': self.fixer_nom,
            'fixer_prenom': self.fixer_prenom,
            'fixer_email': self.fixer_email,
            'fixer_telephone': self.fixer_telephone,
            'pays': self.pays,
            'region': self.region,
            'image_region': self.image_region,
            'territoire_data': json.loads(self.territoire_data) if self.territoire_data else {},
            'episode_data': json.loads(self.episode_data) if self.episode_data else {},
            'gardiens': [g.to_dict() for g in self.gardiens],
            'lieux': [l.to_dict() for l in self.lieux],
            'medias': [m.to_dict() for m in self.medias]
        }

class Gardien(Base):
    __tablename__ = 'gardiens'
    
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    ordre = Column(Integer)
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
        return {
            'id': self.id,
            'ordre': self.ordre,
            'nom': self.nom,
            'prenom': self.prenom,
            'age': self.age,
            'genre': self.genre,
            'fonction': self.fonction,
            'savoir_transmis': self.savoir_transmis,
            'adresse': self.adresse,
            'telephone': self.telephone,
            'email': self.email,
            'contact_intermediaire': self.contact_intermediaire,
            'histoire_personnelle': self.histoire_personnelle,
            'evaluation_cinegenie': self.evaluation_cinegenie,
            'langues_parlees': self.langues_parlees,
            'photo_url': self.photo_url
        }

class Lieu(Base):
    __tablename__ = 'lieux'
    
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    numero_lieu = Column(Integer, default=1)
    nom = Column(String(255))
    type_environnement = Column(String(255))
    description_visuelle = Column(Text)
    elements_symboliques = Column(Text)
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
    contraintes_meteo = Column(Text)
    autorisations_necessaires = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    
    reperage = relationship("Reperage", back_populates="lieux")
    
    def to_dict(self):
        return {
            'id': self.id,
            'numero_lieu': self.numero_lieu,
            'nom': self.nom,
            'type_environnement': self.type_environnement,
            'description_visuelle': self.description_visuelle,
            'elements_symboliques': self.elements_symboliques,
            'points_vue_remarquables': self.points_vue_remarquables,
            'cinegenie': self.cinegenie,
            'axes_camera': self.axes_camera,
            'moments_favorables': self.moments_favorables,
            'ambiance_sonore': self.ambiance_sonore,
            'adequation_narration': self.adequation_narration,
            'accessibilite': self.accessibilite,
            'securite': self.securite,
            'electricite': self.electricite,
            'espace_equipe': self.espace_equipe,
            'protection_meteo': self.protection_meteo,
            'contraintes_meteo': self.contraintes_meteo,
            'autorisations_necessaires': self.autorisations_necessaires,
            'latitude': self.latitude,
            'longitude': self.longitude
        }

class Media(Base):
    __tablename__ = 'medias'
    
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    type = Column(String(50))
    categorie = Column(String(100))
    nom_fichier = Column(String(255))
    nom_original = Column(String(255))
    chemin_fichier = Column(String(500))
    taille_octets = Column(Integer)
    mime_type = Column(String(100))
    legende = Column(Text)
    ordre_affichage = Column(Integer)
    uploaded_at = Column(DateTime, default=datetime.now)
    
    reperage = relationship("Reperage", back_populates="medias")
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'categorie': self.categorie,
            'nom_fichier': self.nom_fichier,
            'nom_original': self.nom_original,
            'chemin_fichier': self.chemin_fichier,
            'taille_octets': self.taille_octets,
            'mime_type': self.mime_type,
            'legende': self.legende,
            'ordre_affichage': self.ordre_affichage,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }

class Fixer(Base):
    __tablename__ = 'fixers'
    id = Column(Integer, primary_key=True)
    nom = Column(String(100))
    prenom = Column(String(100))
    email = Column(String(200), unique=True)
    telephone = Column(String(50))
    telephone_2 = Column(String(50))
    societe = Column(String(200))
    fonction = Column(String(100))
    site_web = Column(String(255))
    numero_siret = Column(String(50))
    adresse_1 = Column(String(255))
    adresse_2 = Column(String(255))
    code_postal = Column(String(20))
    ville = Column(String(100))
    pays = Column(String(100))
    region = Column(String(200))
    photo_profil_url = Column(String(500))
    bio = Column(Text)
    specialites = Column(Text)
    langues_parlees = Column(String(255))
    langue_preferee = Column(String(10), default='FR')
    token_unique = Column(String(8), unique=True)
    lien_personnel = Column(String(500))
    actif = Column(Boolean, default=True)
    notes_internes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nom': self.nom,
            'prenom': self.prenom,
            'email': self.email,
            'telephone': self.telephone,
            'token_unique': self.token_unique,
            'lien_personnel': self.lien_personnel,
            'actif': self.actif,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'), nullable=False)
    auteur_type = Column(String(20), nullable=False)
    auteur_nom = Column(String(255), nullable=False)
    contenu = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    lu = Column(Boolean, default=False)
    
    reperage = relationship("Reperage", backref="messages")
    
    def to_dict(self):
        return {
            'id': self.id,
            'auteur_type': self.auteur_type,
            'auteur_nom': self.auteur_nom,
            'contenu': self.contenu,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

def init_db(database_url):
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
