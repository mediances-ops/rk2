# DOC-OS VERSION : V.72.2 SUPRÊME MISSION CONTROL
# ENGINE : FLASK + SQLALCHEMY SCOPED SESSIONS
# ÉTAT : CRITICAL STABILITY - SYNTAX FIX & FULL SYNC

import os
import json
import secrets
import requests
import io
import zipfile
import shutil
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_file, send_from_directory, g
from flask_cors import CORS
from sqlalchemy import text, or_
from models import init_db, get_session, Reperage, Fixer, Media, Message, Gardien, Lieu

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ENVIRONNEMENT ---
raw_db_url = os.environ.get('DATABASE_URL')
if raw_db_url and raw_db_url.startswith('postgres://'):
    DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1)
else:
    DB_URL = raw_db_url or 'sqlite:///reperage.db'

app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

engine = init_db(DB_URL)

# --- GESTIONNAIRE DE SESSION (ANTI-TIMEOUT RAILWAY) ---
@app.teardown_appcontext
def shutdown_session(exception=None):
    session = g.pop('db_session', None)
    if session is not None:
        session.close()

def get_db():
    if 'db_session' not in g:
        g.db_session = get_session(engine)
    return g.db_session

# --- FILTRES ET VALIDATIONS ---
def validate_image_url(url):
    if not url:
        return "https://destinationsetcuisines.com/doc/multilingue/bannerreperage.jpg"
    if url.startswith('http'):
        return url
    if url.startswith('uploads/'):
        return f"/{url}"
    return f"https://{url}"

@app.template_filter('linkify')
def linkify_filter(text):
    if not text:
        return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, r'<a href="\1" target="_blank">\1</a>', text)

# --- ROUTES NAVIGATION ---
@app.route('/')
def index_root():
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_db()
    query = session.query(Reperage)
    p_f = request.args.get('pays')
    s_f = request.args.get('statut')
    if p_f:
        query = query.filter(Reperage.pays == p_f)
    if s_f:
        query = query.filter(Reperage.statut == s_f)
    
    reps = query.order_by(Reperage.id.desc()).all()
    serialized = []
    for r in reps:
        f = session.get(Fixer, r.fixer_id) if r.fixer_id else None
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        serialized.append({
            'reperage': r.to_dict(),
            'fixer': f.to_dict() if f else None,
            'unread_count': unread
        })
    
    stats = {
        'total': len(reps),
        'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(),
        'soumis': session.query(Reperage).filter_by(statut='soumis').count(),
        'valides': session.query(Reperage).filter_by(statut='validé').count()
    }
    return render_template('admin_dashboard.html', 
                           reperages=serialized, 
                           stats=stats, 
                           fixers=session.query(Fixer).all(), 
                           pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_db()
    query = session.query(Fixer)
    search = request.args.get('search')
    pays = request.args.get('pays')
    if search:
        query = query.filter(or_(Fixer.nom.ilike(f'%{search}%'), Fixer.prenom.ilike(f'%{search}%')))
    if pays:
        query = query.filter(Fixer.pays == pays)
    
    fixers = query.order_by(Fixer.nom.asc()).all()
    pays_list = [p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]]
    return render_template('admin_fixers.html', fixers=fixers, pays_list=pays_list)

# --- MOTEUR DE SYNCHRONISATION ---
@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_engine(id):
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep:
        abort(404)
    if request.method == 'GET':
        return jsonify(rep.to_dict())
    
    if rep.statut != 'brouillon':
        return jsonify({'error': 'Locked'}), 403
    
    data = request.json
    for k, v in data.items():
        if hasattr(rep, k) and k not in ['token', 'id', 'fixer_id'] and not k.startswith(('gardien', 'lieu')):
            setattr(rep, k, v)
            
    for i in [1, 2, 3]:
        g_data = {key.replace(f'gardien{i}_', ''): val for key, val in data.items() if key.startswith(f'gardien{i}_')}
        if g_data:
            g_obj = session.query(Gardien).filter_by(reperage_id=rep.id, index=i).first()
            if not g_obj:
                g_obj = Gardien(reperage_id=rep.id, index=i)
                session.add(g_obj)
            for k, v in g_data.items():
                if hasattr(g_obj, k):
                    if k == 'age':
                        setattr(g_obj, k, int(v) if (v and str(v).isdigit()) else None)
                    else:
                        setattr(g_obj, k, v)
                        
        l_data = {key.replace(f'lieu{i}_', ''): val for key, val in data.items() if key.startswith(f'lieu{i}_')}
        if l_data:
            l_obj = session.query(Lieu).filter_by(reperage_id=rep.id, index=i).first()
            if not l_obj:
                l_obj = Lieu(reperage_id=rep.id, index=i)
                session.add(l_obj)
            for k, v in l_data.items():
                if hasattr(l_obj, k):
                    setattr(l_obj, k, v)
                    
    session.commit()
    return jsonify({'status': 'success'})

# --- MODULE IMPORT JSON ---
@app.route('/admin/reperages/import', methods=['POST'])
def admin_import_json():
    session = get_db()
    data = request.json
    try:
        new_rep = Reperage(
            token=secrets.token_urlsafe(16), 
            region=data.get('region'), 
            pays=data.get('pays'), 
            image_region=data.get('image_region'), 
            statut='brouillon', 
            villes=data.get('villes')
        )
        session.add(new_rep)
        session.flush()
        for i in [1, 2, 3]:
            pair = data.get(f'pair_{i}', {})
            if pair.get('gardien'):
                session.add(Gardien(reperage_id=new_rep.id, index=i, **pair['gardien']))
            if pair.get('location'):
                session.add(Lieu(reperage_id=new_rep.id, index=i, **pair['location']))
        session.commit()
        return jsonify({'status': 'success', 'id': new_rep.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- BRIDGE ET SOUMISSION ---
@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep:
        abort(404)
    rep.statut = 'soumis'
    session.commit()
    if DOCUGEN_URL:
        try:
            requests.post(DOCUGEN_URL, json=rep.to_dict(), headers={"X-Bridge-Token": BRIDGE_TOKEN}, timeout=30)
        except:
            pass
    return jsonify({'status': 'success'})

# --- GESTION MÉDIAS ET CHAT ---
@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
def api_medias(id):
    session = get_db()
    if request.method == 'GET':
        ms = session.query(Media).filter_by(reperage_id=id).all()
        return jsonify([{'id': m.id, 'nom_fichier': m.nom_fichier, 'type': m.type} for m in ms])
    
    file = request.files['file']
    ext = os.path.splitext(file.filename)[1].lower()
    filename = secrets.token_hex(8) + "_" + file.filename
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, chemin_fichier=f"{id}/{filename}", type='pdf' if ext == '.pdf' else 'photo')
    session.add(m)
    session.commit()
    return jsonify({'status': 'success'})

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    directory = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)))
    return send_from_directory(directory, filename)

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_chat(id):
    session = get_db()
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()
        if request.args.get('role') == 'admin':
            session.query(Message).filter_by(reperage_id=id, auteur_type='fixer').update({Message.lu: True})
            session.commit()
        return jsonify([m.to_dict() for m in msgs])
    
    data = request.json
    m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m)
    session.commit()
    return jsonify({'status': 'success'}), 201

# --- ROUTES ADMINISTRATION COMPLÉMENTAIRES ---
@app.route('/admin/fixer/new', methods=['POST'])
def admin_new_fixer():
    session = get_db()
    f = Fixer(token_unique=secrets.token_hex(6), created_at=datetime.utcnow())
    for k in request.form:
        if hasattr(f, k):
            setattr(f, k, request.form[k] == '1' if k == 'actif' else request.form[k])
    session.add(f)
    session.commit()
    return redirect('/admin/fixers')

@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_fixer(id):
    session = get_db()
    fixer = session.get(Fixer, id)
    if request.method == 'POST':
        for k in request.form:
            if hasattr(fixer, k):
                setattr(fixer, k, request.form[k] == '1' if k == 'actif' else request.form[k])
        session.commit()
        return redirect('/admin/fixers')
    return render_template('admin_fixer_edit_v2.html', fixer=fixer)

@app.route('/admin/reperage/<int:id>')
def admin_view_reperage(id):
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep:
        abort(404)
    fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
    image_final = validate_image_url(rep.image_region)
    territoire = {"villes": rep.villes, "population": rep.population, "langues": rep.langues, "climat": rep.climat, "histoire": rep.histoire, "acces": rep.acces, "hebergement": rep.hebergement}
    particularites = { "contraintes": rep.contraintes, "notes_production": rep.notes }
    episode = { "arc_narratif": rep.arc, "moments_cles": rep.moments, "sensibles": rep.sensibles, "budget_local": rep.budget }
    fete = {"nom": rep.fete_nom, "date": rep.fete_date, "gps_lat": rep.fete_gps_lat, "gps_long": rep.fete_gps_long, "origines": rep.fete_origines, "visuel": rep.fete_visuel, "deroulement": rep.fete_deroulement, "responsable": rep.fete_responsable}
    return render_template('admin_reperage_detail.html', reperage=rep, fixer=fixer, territoire=territoire, particularites=particularites, episode=episode, fete=fete, banner_url=image_final)

@app.route('/admin/reperage/<int:id>/print')
def admin_print(id):
    session = get_db()
    rep = session.get(Reperage, id)
    fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
    pairs = []
    for i in [1, 2, 3]:
        g_obj = session.query(Gardien).filter_by(reperage_id=id, index=i).first()
        l_obj = session.query(Lieu).filter_by(reperage_id=id, index=i).first()
        if g_obj or l_obj:
            pairs.append({'index': i, 'gardien': g_obj, 'lieu': l_obj})
    return render_template('print_reperage.html', rep=rep, fixer=fixer, pairs=pairs)

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_update_status(id):
    session = get_db()
    rep = session.get(Reperage, id)
    data = request.json
    if 'statut' in data:
        rep.statut = data['statut']
    if 'notes_admin' in data:
        rep.notes_admin = data['notes_admin']
    if 'image_region' in data:
        rep.image_region = data['image_region']
    if 'fixer_id' in data:
        f = session.get(Fixer, int(data['fixer_id']))
        if f:
            rep.fixer_id = f.id
            rep.fixer_nom = f"{f.prenom} {f.nom}"
    session.commit()
    return jsonify({'status': 'success'})

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_rep():
    session = get_db()
    data = request.json
    fixer = session.get(Fixer, int(data.get('fixer_id'))) if data.get('fixer_id') else None
    new_rep = Reperage(
        token=secrets.token_urlsafe(16), 
        region=data.get('region'), 
        pays=data.get('pays'), 
        fixer_id=fixer.id if fixer else None, 
        fixer_nom=f"{fixer.prenom} {fixer.nom}" if fixer else "Inconnu", 
        image_region=data.get('image_region'), 
        statut='brouillon'
    )
    session.add(new_rep)
    session.commit()
    return jsonify({'status': 'success'})

@app.route('/formulaire/<token>')
def route_form_fixer(token):
    session = get_db()
    rep = session.query(Reperage).filter_by(token=token).first()
    if not rep:
        abort(404)
    data = rep.to_dict()
    data['image_region'] = validate_image_url(data.get('image_region'))
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
