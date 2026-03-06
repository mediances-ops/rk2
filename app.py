# DOC-OS VERSION : V.77.0 SUPRÊME
# ÉTAT : ALIGNEMENT TOTAL DES RÉSERVOIRS - 2026

import os, json, secrets, requests, io
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, g, make_response
from flask_cors import CORS
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from models import init_db, get_session, Reperage, Fixer, Media, Message, Gardien, Lieu

app = Flask(__name__)
CORS(app)

# CONFIGURATION
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

def nocache(view):
    def no_cache_view(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    no_cache_view.__name__ = view.__name__
    return no_cache_view

# --- ROUTES DASHBOARD & ADMIN ---

@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
@nocache
def admin_dashboard():
    session = get_db()
    reps = session.query(Reperage).order_by(Reperage.id.desc()).all()
    serialized = []
    for r in reps:
        f = session.get(Fixer, int(r.fixer_id)) if r.fixer_id else None
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        serialized.append({'reperage': r.to_dict(), 'fixer': f.to_dict() if f else None, 'unread_count': unread})
    
    stats = {'total': len(reps), 
             'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(),
             'soumis': session.query(Reperage).filter_by(statut='soumis').count(),
             'valides': session.query(Reperage).filter_by(statut='validé').count()}
    return render_template('admin_dashboard.html', reperages=serialized, stats=stats, fixers=session.query(Fixer).all())

# --- MOTEUR DE SYNCHRONISATION (CORRIGÉ) ---

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
@nocache
def api_sync_engine(id):
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    
    if request.method == 'GET':
        return jsonify(rep.to_dict()) # Renvoie le JSON avec les tiroirs 'territory', etc.
    
    data = request.json
    
    # 1. Champs de la table principale (Territoire + Festivité)
    fields = ['villes', 'population', 'langues', 'climat', 'histoire', 'traditions', 'acces', 
              'hebergement', 'contraintes', 'arc', 'moments', 'sensibles', 'budget', 'notes', 
              'fete_nom', 'fete_date', 'fete_gps_lat', 'fete_gps_long', 'fete_origines', 
              'fete_visuel', 'fete_deroulement', 'fete_responsable', 'image_region', 'progression_pourcent']
    
    for f in fields:
        if f in data:
            val = data[f]
            if f == 'progression_pourcent':
                setattr(rep, f, int(val) if str(val).isdigit() else 0)
            else:
                # Sauvegarde brute du texte (histoire, traditions...)
                setattr(rep, f, str(val).strip() if val else "")

    # 2. Mise à jour des 3 PAIRES (Gardiens & Lieux)
    for i in [1, 2, 3]:
        # GARDIEN
        g_obj = session.query(Gardien).filter_by(reperage_id=rep.id, index=i).first() or Gardien(reperage_id=rep.id, index=i)
        if g_obj not in session: session.add(g_obj)
        for f in ['nom_prenom', 'age', 'fonction', 'savoir', 'histoire', 'psychologie', 'evaluation', 'langues', 'contact', 'intermediaire']:
            val = data.get(f"gardien{i}_{f}")
            if val is not None:
                if f == 'age': setattr(g_obj, f, int(val) if str(val).isdigit() else None)
                else: setattr(g_obj, f, str(val).strip())

        # LIEU
        l_obj = session.query(Lieu).filter_by(reperage_id=rep.id, index=i).first() or Lieu(reperage_id=rep.id, index=i)
        if l_obj not in session: session.add(l_obj)
        for f in ['nom', 'type', 'gps_lat', 'gps_long', 'description', 'cinegenie', 'axes', 'points_vue', 'moments', 'son', 'acces', 'securite', 'elec', 'espace', 'meteo', 'permis']:
            val = data.get(f"lieu{i}_{f}")
            if val is not None: setattr(l_obj, f, str(val).strip())

    session.commit()
    return jsonify({'status': 'success'})

# --- CHAT & MEDIAS (STABLES) ---

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
@nocache
def api_chat(id):
    session = get_db()
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json
    m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m)
    session.commit()
    return jsonify({'status': 'success'}), 201

@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
@nocache
def api_medias(id):
    session = get_db()
    if request.method == 'GET':
        ms = session.query(Media).filter_by(reperage_id=id).all()
        return jsonify([{'id': m.id, 'nom_fichier': m.nom_fichier, 'type': m.type} for m in ms])
    f = request.files['file']
    fn = secrets.token_hex(8) + "_" + secure_filename(f.filename)
    p = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    os.makedirs(p, exist_ok=True)
    f.save(os.path.join(p, fn))
    session.add(Media(reperage_id=id, nom_original=f.filename, nom_fichier=fn, chemin_fichier=f"{id}/{fn}", type='pdf' if f.filename.endswith('.pdf') else 'photo'))
    session.commit()
    return jsonify({'status': 'success'})

# --- ROUTE MANQUANTE 1 : MISE À JOUR DEPUIS LE DASHBOARD (BOUTON BLEU) ---
@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
@nocache
def admin_update_status(id):
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    data = request.json
    
    # Mise à jour des champs éditables dans le modal bleu
    if 'statut' in data: rep.statut = data['statut']
    if 'notes_admin' in data: rep.notes_admin = data['notes_admin']
    if 'region' in data: rep.region = data['region']
    if 'pays' in data: rep.pays = data['pays']
    if 'image_region' in data: rep.image_region = data['image_region']
    
    # Gestion de l'assignation du Fixer
    if 'fixer_id' in data:
        f_id = data['fixer_id']
        if f_id and str(f_id).isdigit():
            fixer = session.get(Fixer, int(f_id))
            if fixer:
                rep.fixer_id = fixer.id
                rep.fixer_nom = f"{fixer.prenom} {fixer.nom}"
    
    session.commit()
    return jsonify({'status': 'success'})

# --- ROUTE MANQUANTE 2 : SOUMISSION FINALE DU FIXER ---
@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
@nocache
def api_submit(id):
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    rep.statut = 'soumis'
    session.commit()
    
    # Envoi vers QuillOS (Bridge) si configuré
    if DOCUGEN_URL:
        try:
            p = rep.to_dict()
            p['schema_id'] = rep.id
            p['title'] = f"{rep.region} ({rep.pays})"
            requests.post(DOCUGEN_URL, json=p, headers={"X-Bridge-Token": BRIDGE_TOKEN}, timeout=5)
        except: pass
        
    return jsonify({'status': 'success'})

# --- ROUTE MANQUANTE 3 : CRÉATION DE DOSSIER ---
@app.route('/admin/reperages/create', methods=['POST'])
@nocache
def admin_create_reperage():
    session = get_db()
    data = request.json
    f_id = data.get('fixer_id')
    f_nom = None
    if f_id and str(f_id).isdigit():
        f = session.get(Fixer, int(f_id))
        if f: f_nom = f"{f.prenom} {f.nom}"
    
    rep = Reperage(
        token=secrets.token_hex(16),
        region=str(data.get('region', '')).strip(),
        pays=str(data.get('pays', '')).strip(),
        fixer_id=int(f_id) if f_id else None,
        fixer_nom=f_nom,
        statut='brouillon'
    )
    session.add(rep)
    session.commit()
    return jsonify({'status': 'success', 'id': rep.id})


# --- AUTRES ROUTES ---

@app.route('/formulaire/<token>')
def route_form_fixer(token):
    session = get_db()
    rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=rep.to_dict())

# ROUTE : MARQUER COMME LU (Dashboard Admin)
@app.route('/api/reperages/<int:id>/read', methods=['POST'])
@nocache
def api_mark_as_read(id):
    session = get_db()
    # On passe tous les messages non-lus du fixer à "True" pour ce repérage
    session.query(Message).filter_by(reperage_id=id, auteur_type='fixer', lu=False).update({Message.lu: True})
    session.commit()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
