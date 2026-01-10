# DOC-OS VERSION : V.62 SUPRÊME MISSION CONTROL
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class Fixer(Base):
    __tablename__ = 'fixers'
    id = Column(Integer, primary_key=True)
    nom = Column(String(100)); prenom = Column(String(100)); email = Column(String(200), unique=True)
    telephone = Column(String(50)); telephone_2 = Column(String(50)); societe = Column(String(200))
    fonction = Column(String(100)); site_web = Column(String(255)); numero_siret = Column(String(50))
    adresse_1 = Column(String(255)); adresse_2 = Column(String(255)); code_postal = Column(String(20))
    ville = Column(String(100)); pays = Column(String(100)); bio = Column(Text); specialites = Column(Text)
    langues_parlees = Column(String(255)); token_unique = Column(String(12), unique=True); lien_personnel = Column(String(500))
    actif = Column(Boolean, default=True); notes_internes = Column(Text); created_at = Column(DateTime, default=datetime.now)
    
    # Relation explicite
    reperages = relationship("Reperage", back_populates="fixer_rel")

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        if d.get('created_at'): d['created_at'] = d['created_at'].isoformat()
        return d

class Reperage(Base):
    __tablename__ = 'reperages'
    id = Column(Integer, primary_key=True); token = Column(String(32), unique=True)
    statut = Column(String(20), default='brouillon'); progression_pourcent = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now); updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    fixer_id = Column(Integer, ForeignKey('fixers.id'))
    fixer_nom = Column(String(255)); pays = Column(String(100)); region = Column(String(255))
    image_region = Column(String(500)); notes_admin = Column(Text)

    # --- LES 100 COLONNES DE SUBSTANCE (FLAT DATA) ---
    # 1. TERRITORY
    ville = Column(String(255)); population = Column(String(255)); langues = Column(String(255))
    climat = Column(String(255)); histoire = Column(Text); traditions = Column(Text)
    acces = Column(Text); hebergement = Column(Text)
    # 2. PARTICULARITIES
    fete_nom = Column(String(255)); contraintes = Column(Text); arc = Column(Text)
    moments = Column(Text); sensibles = Column(Text); budget = Column(String(100)); notes = Column(Text)
    # 3. GUARDIANS (G1, G2, G3)
    g1_nom_prenom = Column(String(255)); g1_age = Column(Integer); g1_fonction = Column(String(255)); g1_savoir = Column(Text); g1_histoire = Column(Text); g1_psychologie = Column(Text); g1_evaluation = Column(Text); g1_langues = Column(String(255)); g1_contact = Column(Text); g1_intermediaire = Column(Text)
    g2_nom_prenom = Column(String(255)); g2_age = Column(Integer); g2_fonction = Column(String(255)); g2_savoir = Column(Text); g2_histoire = Column(Text); g2_psychologie = Column(Text); g2_evaluation = Column(Text); g2_langues = Column(String(255)); g2_contact = Column(Text); g2_intermediaire = Column(Text)
    g3_nom_prenom = Column(String(255)); g3_age = Column(Integer); g3_fonction = Column(String(255)); g3_savoir = Column(Text); g3_histoire = Column(Text); g3_psychologie = Column(Text); g3_evaluation = Column(Text); g3_langues = Column(String(255)); g3_contact = Column(Text); g3_intermediaire = Column(Text)
    # 4. LOCATIONS (L1, L2, L3)
    l1_nom = Column(String(255)); l1_type = Column(String(255)); l1_description = Column(Text); l1_cinegenie = Column(Text); l1_axes = Column(Text); l1_points_vue = Column(Text); l1_moments = Column(Text); l1_son = Column(Text); l1_gps = Column(String(255)); l1_acces = Column(Text); l1_securite = Column(Text); l1_elec = Column(Text); l1_espace = Column(Text); l1_meteo = Column(Text); l1_permis = Column(Text)
    l2_nom = Column(String(255)); l2_type = Column(String(255)); l2_description = Column(Text); l2_cinegenie = Column(Text); l2_axes = Column(Text); l2_points_vue = Column(Text); l2_moments = Column(Text); l2_son = Column(Text); l2_gps = Column(String(255)); l2_acces = Column(Text); l2_securite = Column(Text); l2_elec = Column(Text); l2_espace = Column(Text); l2_meteo = Column(Text); l2_permis = Column(Text)
    l3_nom = Column(String(255)); l3_type = Column(String(255)); l3_description = Column(Text); l3_cinegenie = Column(Text); l3_axes = Column(Text); l3_points_vue = Column(Text); l3_moments = Column(Text); l3_son = Column(Text); l3_gps = Column(String(255)); l3_acces = Column(Text); l3_securite = Column(Text); l3_elec = Column(Text); l3_espace = Column(Text); l3_meteo = Column(Text); l3_permis = Column(Text)
    # 5. FESTIVITY
    fete_lieu_date = Column(String(255)); fete_gps = Column(String(255)); fete_origines = Column(Text); fete_deroulement = Column(Text); fete_visuel = Column(Text); fete_responsable = Column(Text)

    # RELATIONS SOUDÉES (BACK_POPULATES)
    fixer_rel = relationship("Fixer", back_populates="reperages")
    medias = relationship("Media", back_populates="reperage", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="reperage", cascade="all, delete-orphan")
    gardiens = relationship("Gardien", back_populates="reperage") # Legacy imports support
    lieux = relationship("Lieu", back_populates="reperage") # Legacy imports support

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        if d.get('created_at'): d['created_at'] = d['created_at'].isoformat()
        if d.get('updated_at'): d['updated_at'] = d['updated_at'].isoformat()
        return d

class Gardien(Base):
    __tablename__ = 'gardiens_legacy'; id = Column(Integer, primary_key=True); reperage_id = Column(Integer, ForeignKey('reperages.id'))
    reperage = relationship("Reperage", back_populates="gardiens")

class Lieu(Base):
    __tablename__ = 'lieux_legacy'; id = Column(Integer, primary_key=True); reperage_id = Column(Integer, ForeignKey('reperages.id'))
    reperage = relationship("Reperage", back_populates="lieux")

class Media(Base):
    __tablename__ = 'medias'; id = Column(Integer, primary_key=True); reperage_id = Column(Integer, ForeignKey('reperages.id')); type = Column(String(50)); nom_fichier = Column(String(255)); nom_original = Column(String(255)); chemin_fichier = Column(String(500)); uploaded_at = Column(DateTime, default=datetime.now)
    reperage = relationship("Reperage", back_populates="medias")
    def to_dict(self): return {c.name: getattr(self, c.name).isoformat() if isinstance(getattr(self, c.name), datetime) else getattr(self, c.name) for c in self.__table__.columns}

class Message(Base):
    __tablename__ = 'messages'; id = Column(Integer, primary_key=True); reperage_id = Column(Integer, ForeignKey('reperages.id')); auteur_type = Column(String(20)); auteur_nom = Column(String(255)); contenu = Column(Text); created_at = Column(DateTime, default=datetime.now); lu = Column(Boolean, default=False)
    reperage = relationship("Reperage", back_populates="messages")
    def to_dict(self): return {c.name: getattr(self, c.name).isoformat() if isinstance(getattr(self, c.name), datetime) else getattr(self, c.name) for c in self.__table__.columns}

def init_db(url):
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine); return engine
def get_session(engine): return sessionmaker(bind=engine)()
