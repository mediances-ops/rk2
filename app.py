# DOC-OS VERSION : V.75.1 SUPRÊME MISSION CONTROL
# ÉTAT : STABLE - SUBSTANCE ANALYSIS REPAQUAGE & BANNER FIX

import os, json, secrets, requests, io, zipfile, shutil, re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_file, send_from_directory, g, make_response
from flask_cors import CORS
from sqlalchemy import text, or_
from models import init_db, get_session, Reperage, Fixer, Media, Message, Gardien, Lieu

app = Flask(__name__)
CORS(app)

DB_URL = os.environ.get('DATABASE_URL').replace('postgres://', 'postgresql://', 1)
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')
engine = init_db(DB_URL)

@app.teardown_appcontext
def shutdown_session(exception=None):
    session = g.pop('db_session', None)
    if session is not None: session.close()

def get_db():
    if 'db_session' not in g: g.db_session = get_session(engine)
    return g.db_session

def validate_url(url):
    if not url: return "https://destinationsetcuisines.com/doc/multilingue/bannerreperage.jpg"
    if url.startswith('http') or url.startswith('/'): return url
    return f"/{url}"

@app.template_filter('linkify')
def linkify_filter(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, r'<a href="\1" target="_blank">\1</a>', text)

# --- NAVIGATION ---
@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_db(); query = session.query(Reperage)
    reps = query.order_by(Reperage.id.desc()).all(); serialized = []
    for r in reps:
        f = session.get(Fixer, r.fixer_id) if r.fixer_id else None
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        serialized.append({'reperage': r.to_dict(), 'fixer': f.to_dict() if f else None, 'unread_count': unread})
    stats = {'total': len(reps), 'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(), 'soumis': session.query(Reperage).filter_by(statut='soumis').count(), 'valides': session.query(Reperage).filter_by(statut='validé').count()}
    return render_template('admin_dashboard.html', reperages=serialized, stats=stats, fixers=session.query(Fixer).all(), pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])

# --- FICHE DE SUBSTANCE (REPAQUAGE V.75.1) ---
@app.route('/admin/reperage/<int:id>')
def admin_view_reperage(id):
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
    
    # SOUDURE : On valide l'URL pour le CSS inline
    banner_url = validate_url(rep.image_region)

    # REPAQUAGE SÉMANTIQUE POUR LES BOUCLES HTML
    territoire = {
        "Villes": rep.villes, "Population": rep.population, "Langues": rep.langues,
        "Climat": rep.climat, "Histoire": rep.histoire, "Traditions": rep.traditions,
        "Accès": rep.acces, "Hébergement": rep.hebergement
    }
    particularites = { "Contraintes": rep.contraintes, "Notes Production": rep.notes }
    episode = { "Arc Narratif": rep.arc, "Moments Clés": rep.moments, "Sensibles": rep.sensibles, "Budget": rep.budget }
    fete = {
        "Nom": rep.fete_nom, "Date": rep.fete_date, "Lat": rep.fete_gps_lat, "Long": rep.fete_gps_long,
        "Origines": rep.fete_origines, "Visuel": rep.fete_visuel, "Déroulement": rep.fete_deroulement, "Responsable": rep.fete_responsable
    }

    return render_template('admin_reperage_detail.html', 
                           reperage=rep, fixer=fixer, banner_url=banner_url,
                           territoire=territoire, particularites=particularites, 
                           episode=episode, fete=fete)

# --- SYNC ENGINE ---
@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_engine(id):
    session = get_db(); rep = session.get(Reperage, id)
    if not rep: abort(404)
    if request.method == 'GET': return jsonify(rep.to_dict())
    if rep.statut == 'validé': abort(403)
    data = request.json
    # Rail 100 champs
    fields = ['villes', 'population', 'langues', 'climat', 'histoire', 'traditions', 'acces', 'hebergement', 'contraintes', 'arc', 'moments', 'sensibles', 'budget', 'notes', 'fete_nom', 'fete_date', 'fete_gps_lat', 'fete_gps_long', 'fete_origines', 'fete_visuel', 'fete_deroulement', 'fete_responsable', 'image_region']
    for f in fields:
        if f in data: setattr(rep, f, str(data[f]).strip())
    # Rail Paires
    for i in [1, 2, 3]:
        g = session.query(Gardien).filter_by(reperage_id=rep.id, index=i).first() or Gardien(reperage_id=rep.id, index=i)
        if g not in session: session.add(g)
        for f in ['nom_prenom', 'age', 'fonction', 'savoir', 'histoire', 'psychologie', 'evaluation', 'langues', 'contact', 'intermediaire']:
            val = data.get(f"gardien{i}_{f}")
            if val is not None:
                if f == 'age': setattr(g, f, int(val) if str(val).isdigit() else None)
                else: setattr(g, f, str(val).strip())
        l = session.query(Lieu).filter_by(reperage_id=rep.id, index=i).first() or Lieu(reperage_id=rep.id, index=i)
        if l not in session: session.add(l)
        for f in ['nom', 'type', 'gps_lat', 'gps_long', 'description', 'cinegenie', 'axes', 'points_vue', 'moments', 'son', 'acces', 'securite', 'elec', 'espace', 'meteo', 'permis']:
            val = data.get(f"lieu{i}_{f}")
            if val is not None: setattr(l, f, str(val).strip())
    session.commit(); return jsonify({'status': 'success'})

# --- BRIDGE, MEDIAS, CHAT ---
@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def api_submit(id):
    session = get_db(); rep = session.get(Reperage, id); rep.statut = 'soumis'; session.commit()
    if DOCUGEN_URL:
        try: requests.post(DOCUGEN_URL, json=rep.to_dict(), headers={"X-Bridge-Token": BRIDGE_TOKEN}, timeout=10)
        except: pass
    return jsonify({'status': 'success'})

@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
def api_medias(id):
    session = get_db()
    if request.method == 'GET': return jsonify([{'id': m.id, 'nom_fichier': m.nom_fichier, 'type': m.type} for m in session.query(Media).filter_by(reperage_id=id).all()])
    f = request.files['file']; ext = os.path.splitext(f
