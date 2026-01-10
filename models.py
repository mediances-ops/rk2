# DOC-OS VERSION : V.62 SUPRÊME
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
    langues_parlees = Column(String(255)); langue_preferee = Column(String(10), default='EN')
    token_unique = Column(String(12), unique=True); lien_personnel = Column(String(500))
    actif = Column(Boolean, default=True); notes_internes = Column(Text); created_at = Column(DateTime, default=datetime.now)
    
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
    
    fixer_id = Column(Integer, ForeignKey('fixers.id')); fixer_nom = Column(String(255))
    pays = Column(String(100)); region = Column(String(255)); image_region = Column(String(500)); notes_admin = Column(Text)

    # --- MATRICE DES 100 COLONNES ---
    ville = Column(String(255)); population = Column(String(255)); langues = Column(String(255))
    climat = Column(String(255)); histoire = Column(Text); traditions = Column(Text)
    acces = Column(Text); hebergement = Column(Text); fete_nom = Column(String(255))
    contraintes = Column(Text); arc = Column(Text); moments = Column(Text); sensibles = Column(Text); budget = Column(String(100)); notes = Column(Text)
    
    # GUARDIANS (3x10)
    gardien1_nom_prenom = Column(String(255)); gardien1_age = Column(Integer); gardien1_fonction = Column(String(255)); gardien1_savoir = Column(Text); gardien1_histoire = Column(Text); gardien1_psychologie = Column(Text); gardien1_evaluation = Column(Text); gardien1_langues = Column(String(255)); gardien1_contact = Column(Text); gardien1_intermediaire = Column(Text)
    gardien2_nom_prenom = Column(String(255)); gardien2_age = Column(Integer); gardien2_fonction = Column(String(255)); gardien2_savoir = Column(Text); gardien2_histoire = Column(Text); gardien2_psychologie = Column(Text); gardien2_evaluation = Column(Text); gardien2_langues = Column(String(255)); gardien2_contact = Column(Text); gardien2_intermediaire = Column(Text)
    gardien3_nom_prenom = Column(String(255)); gardien3_age = Column(Integer); gardien3_fonction = Column(String(255)); gardien3_savoir = Column(Text); gardien3_histoire = Column(Text); gardien3_psychologie = Column(Text); gardien3_evaluation = Column(Text); gardien3_langues = Column(String(255)); gardien3_contact = Column(Text); gardien3_intermediaire = Column(Text)

    # LOCATIONS (3x15)
    lieu1_nom = Column(String(255)); lieu1_type = Column(String(255)); lieu1_description = Column(Text); lieu1_cinegenie = Column(Text); lieu1_axes = Column(Text); lieu1_points_vue = Column(Text); lieu1_moments = Column(Text); lieu1_son = Column(Text); lieu1_gps = Column(String(255)); lieu1_acces = Column(Text); lieu1_securite = Column(Text); lieu1_elec = Column(Text); lieu1_espace = Column(Text); lieu1_meteo = Column(Text); lieu1_permis = Column(Text)
    lieu2_nom = Column(String(255)); lieu2_type = Column(String(255)); lieu2_description = Column(Text); lieu2_cinegenie = Column(Text); lieu2_axes = Column(Text); lieu2_points_vue = Column(Text); lieu2_moments = Column(Text); lieu2_son = Column(Text); lieu2_gps = Column(String(255)); lieu2_acces = Column(Text); lieu2_securite = Column(Text); lieu2_elec = Column(Text); lieu2_espace = Column(Text); lieu2_meteo = Column(Text); lieu2_permis = Column(Text)
    lieu3_nom = Column(String(255)); lieu3_type = Column(String(255)); lieu3_description = Column(Text); lieu3_cinegenie = Column(Text); lieu3_axes = Column(Text); lieu3_points_vue = Column(Text); lieu3_moments = Column(Text); lieu3_son = Column(Text); lieu3_gps = Column(String(255)); lieu3_acces = Column(Text); lieu3_securite = Column(Text); lieu3_elec = Column(Text); lieu3_espace = Column(Text); lieu3_meteo = Column(Text); lieu3_permis = Column(Text)

    fete_lieu_date = Column(String(255)); fete_gps = Column(String(255)); fete_origines = Column(Text); fete_deroulement = Column(Text); fete_visuel = Column(Text); fete_responsable = Column(Text)

    fixer_rel = relationship("Fixer", back_populates="reperages")
    medias = relationship("Media", back_populates="reperage", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="reperage", cascade="all, delete-orphan")
    gardiens = relationship("Gardien", back_populates="reperage")
    lieux = relationship("Lieu", back_populates="reperage")

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        if d.get('created_at'): d['created_at'] = d['created_at'].isoformat()
        if d.get('updated_at'): d['updated_at'] = d['updated_at'].isoformat()
        return d

class Gardien(Base):
    __tablename__ = 'g_legacy'; id = Column(Integer, primary_key=True); reperage_id = Column(Integer, ForeignKey('reperages.id'))
    reperage = relationship("Reperage", back_populates="gardiens")

class Lieu(Base):
    __tablename__ = 'l_legacy'; id = Column(Integer, primary_key=True); reperage_id = Column(Integer, ForeignKey('reperages.id'))
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
