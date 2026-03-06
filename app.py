# DOC-OS VERSION : V.76.2.5 SUPRÊME
# ÉTAT : MAINTENANCE CORRECTIVE - ALIGNEMENT MARGE ZÉRO
# DATE : 2026-03-06

import os, json, secrets, requests, io, zipfile, shutil, re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_file, send_from_directory, g, make_response
from flask_cors import CORS
from sqlalchemy import text, or_
from werkzeug.utils import secure_filename
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

def nocache(view):
    def no_cache_view(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    no_cache_view.__name__ = view.__name__
    return no_cache_view

def validate_url(url):
    if not url: return "https://destinationsetcuisines.com/doc/multilingue/bannerreperage.jpg"
    if url.startswith('http') or url.startswith('/'): return url
    return f"/{url}"

@app.route('/')
def index_root(): 
    return redirect('/admin')

@app.route('/admin')
@nocache
def admin_dashboard():
    session = get_db(); query = session.query(Reperage)
    reps = query.order_by(Reperage.id.desc()).all(); serialized = []
    for r in reps:
        f = session.get(Fixer, r.fixer_id) if r.fixer_id else None
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        serialized.append({'reperage': r.to_dict(), 'fixer': f.to_dict() if f else None, 'unread_count': unread})
    stats = {'total': len(reps), 'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(), 'soumis': session.query(Reperage).filter_by(statut='soumis').count(), 'valides': session.query(Reperage).filter_by(statut='validé').count()}
    return render_template('admin_dashboard.html', reperages=serialized, stats=stats, fixers=session.query(Fixer).all(), pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])

@app.route('/admin/fixers')
@nocache
def admin_fixers_list():
    session = get_db(); query = session.query(Fixer); search = request.args.get('search'); pays = request.args.get('pays')
    if search: query = query.filter(or_(Fixer.nom.ilike(f'%{search}%'), Fixer.prenom.ilike(f'%{search}%')))
    if pays: query = query.filter(Fixer.pays == pays)
    return render_template('admin_fixers.html', fixers=query.order_by(Fixer.nom.asc()).all(), pays_list=[p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]])

@app.route('/admin/reperage/<int:id>/print')
@nocache
def admin_print(id):
    session = get_db(); rep = session.get(Reperage, id); fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
    pairs = []
    for i in [1, 2, 3]:
        g_obj = session.query(Gardien).filter_by(reperage_id=id, index=i).first()
        l_obj = session.query(Lieu).filter_by(reperage_id=id, index=i).first()
        if g_obj or l_obj: pairs.append({'index': i, 'gardien': g_obj, 'lieu': l_obj})
    return render_template('print_reperage.html', rep=rep, fixer=fixer, pairs=pairs)

@app.route('/formulaire/<token>')
def route_form_fixer(token):
    session = get_db(); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    d = rep.to_dict(); d['image_region'] = validate_url(rep.image_region)
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=d)

@app.route('/admin/reperages/create', methods=['POST'])
@nocache
def admin_create_reperage():
    session = get_db(); data = request.json
    fixer_id = data.get('fixer_id'); fixer_nom = None
    if fixer_id and str(fixer_id).isdigit():
        f = session.get(Fixer, int(fixer_id))
        if f: fixer_nom = f"{f.prenom} {f.nom}"
    rep = Reperage(token=secrets.token_hex(16), region=str(data.get('region', '')).strip(), pays=str(data.get('pays', '')).strip(), fixer_id=int(fixer_id) if fixer_id and str(fixer_id).isdigit() else None, fixer_nom=fixer_nom, image_region=str(data.get('image_region', '')).strip(), notes_admin=str(data.get('notes_admin', '')).strip(), statut='brouillon')
    session.add(rep); session.commit()
    return jsonify({'status': 'success', 'id': rep.id})

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
@nocache
def admin_update_status(id):
    session = get_db(); rep = session.get(Reperage, id); data = request.json
    if not rep: abort(404)
    if 'statut' in data: rep.statut = data['statut']
    if 'notes_admin' in data: rep.notes_admin = data['notes_admin']
    if 'region' in data: rep.region = data['region']
    if 'pays' in data: rep.pays = data['pays']
    if 'image_region' in data: rep.image_region = data['image_region']
    if 'fixer_id' in data and str(data['fixer_id']).isdigit():
        f = session.get(Fixer, int(data['fixer_id']))
        if f: rep.fixer_id = f.id; rep.fixer_nom = f"{f.prenom} {f.nom}"
    session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/delete', methods=['DELETE'])
@nocache
def admin_delete_reperage(id):
    session = get_db(); rep = session.get(Reperage, id)
    if rep: session.delete(rep); session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
@nocache
def api_sync_engine(id):
    session = get_db(); rep = session.get(Reperage, id)
    if not rep: abort(404)
    if request.method == 'GET': return jsonify(rep.to_dict())
    data = request.json
    fields = ['villes', 'population', 'langues', 'climat', 'histoire', 'traditions', 'acces', 'hebergement', 'contraintes', 'arc', 'moments', 'sensibles', 'budget', 'notes', 'fete_nom', 'fete_date', 'fete_gps_lat', 'fete_gps_long', 'fete_origines', 'fete_visuel', 'fete_deroulement', 'fete_responsable', 'image_region', 'progression_pourcent']
    for f in fields:
        if f in data: 
            if f == 'progression_pourcent': setattr(rep, f, int(data[f]) if str(data[f]).isdigit() else 0)
            else: setattr(rep, f, str(data[f]).strip())
    for i in [1, 2, 3]:
        g_obj = session.query(Gardien).filter_by(reperage_id=rep.id, index=i).first() or Gardien(reperage_id=rep.id, index=i)
        if g_obj not in session: session.add(g_obj)
        for f in ['nom_prenom', 'age', 'fonction', 'savoir', 'histoire', 'psychologie', 'evaluation', 'langues', 'contact', 'intermediaire']:
            val = data.get(f"gardien{i}_{f}")
            if val is not None:
                if f == 'age': setattr(g_obj, f, int(val) if str(val).isdigit() else None)
                else: setattr(g_obj, f, str(val).strip())
        l_obj = session.query(Lieu).filter_by(reperage_id=rep.id, index=i).first() or Lieu(reperage_id=rep.id, index=i)
        if l_obj not in session: session.add(l_obj)
        for f in ['nom', 'type', 'gps_lat', 'gps_long', 'description', 'cinegenie', 'axes', 'points_vue', 'moments', 'son', 'acces', 'securite', 'elec', 'espace', 'meteo', 'permis']:
            val = data.get(f"lieu{i}_{f}")
            if val is not None: setattr(l_obj, f, str(val).strip())
    session.commit(); return jsonify({'status': 'success'})

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
@nocache
def api_submit(id):
    session = get_db(); rep = session.get(Reperage, id); rep.statut = 'soumis'; session.commit()
    if DOCUGEN_URL:
        try:
            p = rep.to_dict(); p['schema_id'] = p.get('id'); p['title'] = f"{rep.region} ({rep.pays})"
            requests.post(DOCUGEN_URL, json=p, headers={"X-Bridge-Token": BRIDGE_TOKEN}, timeout=10)
        except: pass
    return jsonify({'status': 'success'})

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    return send_from_directory(os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id))), secure_filename(filename))

@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
@nocache
def api_medias(id):
    session = get_db()
    if request.method == 'GET':
        ms = session.query(Media).filter_by(reperage_id=id).all()
        return jsonify([{'id': m.id, 'nom_fichier': m.nom_fichier, 'type': m.type} for m in ms])
    f = request.files['file']; ext = os.path.splitext(f.filename)[1].lower(); fn = secrets.token_hex(8) + "_" + secure_filename(f.filename); p = os.path.join(app.config['UPLOAD_FOLDER'], str(id)); os.makedirs(p, exist_ok=True); f.save(os.path.join(p, fn))
    session.add(Media(reperage_id=id, nom_original=f.filename, nom_fichier=fn, chemin_fichier=f"{id}/{fn}", type='pdf' if ext == '.pdf' else 'photo')); session.commit(); return jsonify({'status': 'success'})

@app.route('/api/medias/<int:media_id>', methods=['DELETE'])
@nocache
def api_delete_media(media_id):
    session = get_db(); m = session.get(Media, media_id); file_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], m.chemin_fichier))
    try: os.remove(file_path)
    except: pass
    session.delete(m); session.commit(); return jsonify({'status': 'success'})

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
@nocache
def api_chat(id):
    session = get_db()
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json; m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify({'status': 'success'}), 201

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
