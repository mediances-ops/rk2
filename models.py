# DOC-OS VERSION : V.72.0 SUPRÊME MISSION CONTROL
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class Fixer(Base):
    __tablename__ = 'fixers'
    id = Column(Integer, primary_key=True)
    nom = Column(String(100)); prenom = Column(String(100)); email = Column(String(200), unique=True)
    telephone = Column(String(50)); societe = Column(String(200)); fonction = Column(String(100))
    pays = Column(String(100)); region = Column(String(100)); bio = Column(Text); specialites = Column(Text)
    langues_parlees = Column(Text); langue_preferee = Column(String(10), default='FR')
    token_unique = Column(String(12), unique=True); actif = Column(Boolean, default=True)
    notes_internes = Column(Text); photo_profil_url = Column(Text); created_at = Column(DateTime, default=datetime.utcnow)
    reperages = relationship("Reperage", back_populates="fixer_rel")
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns if getattr(self, c.name) is not None}

class Reperage(Base):
    __tablename__ = 'reperages'
    id = Column(Integer, primary_key=True); token = Column(String(32), unique=True)
    statut = Column(String(20), default='brouillon'); progression_pourcent = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow); updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fixer_id = Column(Integer, ForeignKey('fixers.id')); fixer_nom = Column(String(255))
    pays = Column(String(100)); region = Column(String(255)); image_region = Column(Text); notes_admin = Column(Text)
    villes = Column(Text); population = Column(String(255)); langues = Column(String(255)); climat = Column(String(255)); histoire = Column(Text); traditions = Column(Text); acces = Column(Text); hebergement = Column(Text); contraintes = Column(Text); arc = Column(Text); moments = Column(Text); sensibles = Column(Text); budget = Column(String(255)); notes = Column(Text)
    fete_nom = Column(String(255)); fete_date = Column(String(255)); fete_gps_lat = Column(String(100)); fete_gps_long = Column(String(100)); fete_origines = Column(Text); fete_deroulement = Column(Text); fete_visuel = Column(Text); fete_responsable = Column(Text)
    fixer_rel = relationship("Fixer", back_populates="reperages")
    gardiens = relationship("Gardien", back_populates="reperage", cascade="all, delete-orphan")
    lieux = relationship("Lieu", back_populates="reperage", cascade="all, delete-orphan")
    medias = relationship("Media", back_populates="reperage", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="reperage", cascade="all, delete-orphan")

    def to_dict(self):
        def clean(d): return {k: v for k, v in d.items() if v not in [None, "", []]}
        pairs = {}
        for i in [1, 2, 3]:
            g = next((x for x in self.gardiens if x.index == i), None); l = next((x for x in self.lieux if x.index == i), None)
            pair_data = {}
            if g: pair_data.update(g.to_dict())
            if l: pair_data.update(l.to_dict())
            if pair_data: pairs[f"pair_{i}"] = clean(pair_data)
        return {
            "id": self.id, "token": self.token or "", "statut": self.statut, "region": self.region or "",
            "pays": self.pays or "", "fixer_nom": self.fixer_nom or "Inconnu", "fixer_id": self.fixer_id,
            "image_region": self.image_region or "", "notes_admin": self.notes_admin or "",
            "villes": self.villes or "", "progression_pourcent": self.progression_pourcent,
            "territory": clean({"population": self.population, "langues": self.langues, "climat": self.climat, "histoire": self.histoire, "traditions": self.traditions, "acces": self.acces, "hebergement": self.hebergement, "contraintes": self.contraintes, "arc": self.arc, "moments": self.moments, "sensibles": self.sensibles, "budget": self.budget, "notes": self.notes}),
            **pairs,
            "festivity": clean({"fete_nom": self.fete_nom, "fete_date": self.fete_date, "fete_gps_lat": self.fete_gps_lat, "fete_gps_long": self.fete_gps_long, "fete_origines": self.fete_origines, "fete_visuel": self.fete_visuel, "fete_deroulement": self.fete_deroulement, "fete_responsable": self.fete_responsable}),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class Gardien(Base):
    __tablename__ = 'gardiens'; id = Column(Integer, primary_key=True); reperage_id = Column(Integer, ForeignKey('reperages.id')); index = Column(Integer)
    nom_prenom = Column(String(255)); age = Column(Integer); fonction = Column(String(255)); savoir = Column(Text); histoire = Column(Text); psychologie = Column(Text); evaluation = Column(Text); langues = Column(String(255)); contact = Column(Text); intermediaire = Column(Text)
    reperage = relationship("Reperage", back_populates="gardiens")
    def to_dict(self): return {c.name: getattr(self, c.name) for c in self.__table__.columns if c.name not in ['id', 'reperage_id', 'index']}

class Lieu(Base):
    __tablename__ = 'lieux'; id = Column(Integer, primary_key=True); reperage_id = Column(Integer, ForeignKey('reperages.id')); index = Column(Integer)
    nom = Column(String(255)); type = Column(String(255)); description = Column(Text); cinegenie = Column(Text); axes = Column(Text); points_vue = Column(Text); moments = Column(Text); son = Column(Text); gps_lat = Column(String(100)); gps_long = Column(String(100)); acces = Column(Text); securite = Column(Text); elec = Column(Text); espace = Column(Text); meteo = Column(Text); permis = Column(Text)
    reperage = relationship("Reperage", back_populates="lieux")
    def to_dict(self): return {c.name: getattr(self, c.name) for c in self.__table__.columns if c.name not in ['id', 'reperage_id', 'index']}

class Media(Base):
    __tablename__ = 'medias'; id = Column(Integer, primary_key=True); reperage_id = Column(Integer, ForeignKey('reperages.id')); type = Column(String(50)); nom_fichier = Column(String(255)); nom_original = Column(String(255)); chemin_fichier = Column(String(500)); uploaded_at = Column(DateTime, default=datetime.utcnow)
    reperage = relationship("Reperage", back_populates="medias")
    def to_dict(self): return {c.name: getattr(self, c.name).isoformat() if isinstance(getattr(self, c.name), datetime) else getattr(self, c.name) for c in self.__table__.columns}

class Message(Base):
    __tablename__ = 'messages'; id = Column(Integer, primary_key=True); reperage_id = Column(Integer, ForeignKey('reperages.id')); auteur_type = Column(String(20)); auteur_nom = Column(String(255)); contenu = Column(Text); lu = Column(Boolean, default=False); created_at = Column(DateTime, default=datetime.utcnow)
    reperage = relationship("Reperage", back_populates="messages")
    def to_dict(self): return {c.name: getattr(self, c.name).isoformat() if isinstance(getattr(self, c.name), datetime) else getattr(self, c.name) for c in self.__table__.columns}

def init_db(url):
    engine = create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)
    Base.metadata.create_all(engine); return engine
def get_session(engine): return sessionmaker(bind=engine)()
