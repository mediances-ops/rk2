# DOC-OS VERSION : V.74.2 FINALE
import os, json, secrets, requests, io, zipfile, shutil
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
    if not url: return ""
    if url.startswith('http') or url.startswith('/'): return url
    return f"/{url}"

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_engine(id):
    session = get_db(); rep = session.get(Reperage, id)
    if not rep: abort(404)
    if request.method == 'GET': return jsonify(rep.to_dict())
    
    data = request.json
    fields = ['villes', 'population', 'langues', 'climat', 'histoire', 'traditions', 'acces', 'hebergement', 'contraintes', 'arc', 'moments', 'sensibles', 'budget', 'notes', 'fete_nom', 'fete_date', 'fete_gps_lat', 'fete_gps_long', 'fete_origines', 'fete_visuel', 'fete_deroulement', 'fete_responsable', 'image_region']
    for f in fields:
        if f in data: setattr(rep, f, str(data[f]).strip())
    
    for i in [1, 2, 3]:
        g_obj = session.query(Gardien).filter_by(reperage_id=rep.id, index=i).first() or Gardien(reperage_id=rep.id, index=i)
        if g_obj not in session: session.add(g_obj)
        for f in ['nom_prenom', 'age', 'fonction', 'savoir', 'histoire', 'psychologie', 'evaluation', 'langues', 'contact', 'intermediaire']:
            val = data.get(f"gardien{i}_{f}")
            if val is not None:
                if f == 'age': setattr(g_obj, f, int(val) if (str(val).isdigit()) else None)
                else: setattr(g_obj, f, str(val).strip())
        l_obj = session.query(Lieu).filter_by(reperage_id=rep.id, index=i).first() or Lieu(reperage_id=rep.id, index=i)
        if l_obj not in session: session.add(l_obj)
        for f in ['nom', 'type', 'gps_lat', 'gps_long', 'description', 'cinegenie', 'axes', 'points_vue', 'moments', 'son', 'acces', 'securite', 'elec', 'espace', 'meteo', 'permis']:
            val = data.get(f"lieu{i}_{f}")
            if val is not None: setattr(l_obj, f, str(val).strip())
    session.commit(); return jsonify({'status': 'success'})

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    return send_from_directory(os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id))), filename)

# [AUTRES ROUTES ADMIN DASHBOARD, FIXERS ET BRIDGE MAINTENUES]
@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_db(); reps = session.query(Reperage).order_by(Reperage.id.desc()).all(); serialized = []
    for r in reps:
        f = session.get(Fixer, r.fixer_id) if r.fixer_id else None
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        serialized.append({'reperage': r.to_dict(), 'fixer': f.to_dict() if f else None, 'unread_count': unread})
    return render_template('admin_dashboard.html', reperages=serialized, stats={'total': len(reps), 'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(), 'soumis': session.query(Reperage).filter_by(statut='soumis').count(), 'valides': session.query(Reperage).filter_by(statut='validé').count()}, fixers=session.query(Fixer).all(), pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])

@app.route('/formulaire/<token>')
def route_form_fixer(token):
    session = get_db(); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    d = rep.to_dict(); d['image_region'] = validate_url(rep.image_region)
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=d)

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def api_submit(id):
    session = get_db(); rep = session.get(Reperage, id); rep.statut = 'soumis'; session.commit()
    if DOCUGEN_URL:
        try:
            p = rep.to_dict(); p['schema_id'] = p.get('id'); p['title'] = f"{rep.region} ({rep.pays})"
            requests.post(DOCUGEN_URL, json=p, headers={"X-Bridge-Token": BRIDGE_TOKEN}, timeout=10)
        except: pass
    return jsonify({'status': 'success'})

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_chat(id):
    session = get_db()
    if request.method == 'GET': return jsonify([m.to_dict() for m in session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()])
    data = request.json; m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify({'status': 'success'}), 201

@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
def api_medias(id):
    session = get_db()
    if request.method == 'GET': return jsonify([{'id': m.id, 'nom_fichier': m.nom_fichier, 'type': m.type} for m in session.query(Media).filter_by(reperage_id=id).all()])
    f = request.files['file']; fn = secrets.token_hex(8) + "_" + f.filename; p = os.path.join(app.config['UPLOAD_FOLDER'], str(id)); os.makedirs(p, exist_ok=True); f.save(os.path.join(p, fn))
    m = Media(reperage_id=id, nom_original=f.filename, nom_fichier=fn, chemin_fichier=f"{id}/{fn}", type='photo'); session.add(m); session.commit(); return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
