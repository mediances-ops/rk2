# DOC-OS VERSION : V.66 SUPRÊME MISSION CONTROL
# ARCHITECTURE : RELATIONNELLE NORMALISÉE (5 RÉSERVOIRS)
# ÉTAT : STABLE - SÉCURISÉ POUR RAILWAY / POSTGRESQL

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class Fixer(Base):
    """
    RÉSERVOIR RH : GESTION DES CORRESPONDANTS
    """
    __tablename__ = 'fixers'
    id = Column(Integer, primary_key=True)
    nom = Column(String(100))
    prenom = Column(String(100))
    email = Column(String(200), unique=True)
    telephone = Column(String(50))
    societe = Column(String(200))
    fonction = Column(String(100))
    pays = Column(String(100))
    region = Column(String(100))
    bio = Column(Text)
    specialites = Column(Text)
    langues_parlees = Column(Text)
    langue_preferee = Column(String(10), default='FR')
    token_unique = Column(String(12), unique=True)
    actif = Column(Boolean, default=True)
    notes_internes = Column(Text)
    photo_profil_url = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    reperages = relationship("Reperage", back_populates="fixer_rel")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns if getattr(self, c.name) is not None}

class Reperage(Base):
    """
    TABLE MAÎTRESSE : PORTE LES RÉSERVOIRS 1 (TERRITOIRE) ET 5 (FÊTE)
    """
    __tablename__ = 'reperages'
    id = Column(Integer, primary_key=True)
    token = Column(String(32), unique=True)
    statut = Column(String(20), default='brouillon')
    progression_pourcent = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # LIAISON FIXER
    fixer_id = Column(Integer, ForeignKey('fixers.id'))
    fixer_nom = Column(String(255))
    pays = Column(String(100))
    region = Column(String(255))
    image_region = Column(Text)
    notes_admin = Column(Text)

    # --- RÉSERVOIR 1 : TERRITOIRE (14 CHAMPS) ---
    villes = Column(Text) # Pluriel validé
    population = Column(String(255))
    langues = Column(String(255))
    climat = Column(String(255))
    histoire = Column(Text)
    traditions = Column(Text)
    acces = Column(Text)
    hebergement = Column(Text)
    contraintes = Column(Text)
    arc = Column(Text)
    moments = Column(Text)
    sensibles = Column(Text)
    budget = Column(String(255))
    notes = Column(Text)

    # --- RÉSERVOIR 5 : LA FÊTE (8 CHAMPS) ---
    fete_nom = Column(String(255))
    fete_date = Column(String(255))
    fete_gps_lat = Column(String(100))
    fete_gps_long = Column(String(100))
    fete_origines = Column(Text)
    fete_deroulement = Column(Text)
    fete_visuel = Column(Text)
    fete_responsable = Column(Text)

    # RELATIONS
    fixer_rel = relationship("Fixer", back_populates="reperages")
    gardiens = relationship("Gardien", back_populates="reperage", cascade="all, delete-orphan")
    lieux = relationship("Lieu", back_populates="reperage", cascade="all, delete-orphan")
    medias = relationship("Media", back_populates="reperage", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="reperage", cascade="all, delete-orphan")

    def to_dict(self):
        """
        CONSTRUCTION DE L'EXPORT JSON EN 5 RÉSERVOIRS (CONTRAT APP 2)
        """
        # Nettoyage récursif des valeurs None ou vides
        def clean(d):
            return {k: v for k, v in d.items() if v not in [None, "", []]}

        # R1 : Territoire
        territory = clean({
            "villes": self.villes, "population": self.population, "langues": self.langues,
            "climat": self.climat, "histoire": self.histoire, "traditions": self.traditions,
            "acces": self.acces, "hebergement": self.hebergement, "contraintes": self.contraintes,
            "arc": self.arc, "moments": self.moments, "sensibles": self.sensibles,
            "budget": self.budget, "notes": self.notes
        })

        # R5 : La Fête
        festivity = clean({
            "fete_nom": self.fete_nom, "fete_date": self.fete_date,
            "fete_gps_lat": self.fete_gps_lat, "fete_gps_long": self.fete_gps_long,
            "fete_origines": self.fete_origines, "fete_deroulement": self.fete_deroulement,
            "fete_visuel": self.fete_visuel, "fete_responsable": self.fete_responsable
        })

        # R2, R3, R4 : Paires Gardiens / Lieux
        pairs = {}
        for i in [1, 2, 3]:
            g = next((x for x in self.gardiens if x.index == i), None)
            l = next((x for x in self.lieux if x.index == i), None)
            pair_data = {}
            if g: pair_data.update(g.to_dict())
            if l: pair_data.update(l.to_dict())
            if pair_data:
                pairs[f"pair_{i}"] = clean(pair_data)

        return clean({
            "id": self.id,
            "token": self.token,
            "statut": self.statut,
            "region": self.region,
            "pays": self.pays,
            "territory": territory,
            **pairs,
            "festivity": festivity,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        })

class Gardien(Base):
    """
    RÉSERVOIRS 2-4 (PARTIE PERSONNAGE) : 10 CHAMPS
    """
    __tablename__ = 'gardiens'
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    index = Column(Integer) # 1, 2 ou 3
    
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
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns if c.name not in ['id', 'reperage_id', 'index']}
        return d

class Lieu(Base):
    """
    RÉSERVOIRS 2-4 (PARTIE DÉCOR) : 16 CHAMPS
    """
    __tablename__ = 'lieux'
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    index = Column(Integer) # 1, 2 ou 3

    nom = Column(String(255))
    type = Column(String(255))
    description = Column(Text)
    cinegenie = Column(Text)
    axes = Column(Text)
    points_vue = Column(Text)
    moments = Column(Text)
    son = Column(Text)
    gps_lat = Column(String(100))
    gps_long = Column(String(100))
    acces = Column(Text)
    securite = Column(Text)
    elec = Column(Text)
    espace = Column(Text)
    meteo = Column(Text)
    permis = Column(Text)

    reperage = relationship("Reperage", back_populates="lieux")

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns if c.name not in ['id', 'reperage_id', 'index']}
        return d

class Media(Base):
    __tablename__ = 'medias'
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    type = Column(String(50))
    nom_fichier = Column(String(255))
    nom_original = Column(String(255))
    chemin_fichier = Column(String(500))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    reperage = relationship("Reperage", back_populates="medias")

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    reperage_id = Column(Integer, ForeignKey('reperages.id'))
    auteur_type = Column(String(20)) # 'production' ou 'fixer'
    auteur_nom = Column(String(255))
    contenu = Column(Text)
    lu = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    reperage = relationship("Reperage", back_populates="messages")

def init_db(url):
    engine = create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    return sessionmaker(bind=engine)()
