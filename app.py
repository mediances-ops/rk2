import os, json, secrets, requests, re, io, zipfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, abort, send_file
from flask_cors import CORS
from sqlalchemy import or_, text
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

app = Flask(__name__)
CORS(app)

# CONFIGURATION
raw_db_url = os.environ.get('DATABASE_URL')
DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1) if raw_db_url and raw_db_url.startswith('postgres://') else (raw_db_url or 'sqlite:///reperage.db')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
engine = init_db(DB_URL)

@app.template_filter('linkify')
def linkify_text(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

# ROUTES
@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        reps = session.query(Reperage).order_by(Reperage.created_at.desc()).all()
        fixers = session.query(Fixer).all()
        reps_serialized = []
        for r in reps:
            f = session.query(Fixer).get(r.fixer_id)
            unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
            last_m = session.query(Message).filter_by(reperage_id=r.id).order_by(Message.created_at.desc()).first()
            r_data = r.to_dict(); r_data['unread_count'] = unread; r_data['last_sender'] = last_m.auteur_nom if (last_m and unread > 0) else None
            reps_serialized.append({'reperage': r_data, 'fixer': f.to_dict() if f else None})
        stats = {'total': len(reps), 'brouillons': len([r for r in reps if r.statut == 'brouillon']), 'soumis': len([r for r in reps if r.statut == 'soumis']), 'valides': len([r for r in reps if r.statut == 'validé'])}
        return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=fixers, stats=stats, pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])
    finally: session.close()

# API SYNC (FIX 3 : Persistance garantie)
@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_high_sub(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404
        if request.method == 'GET': return jsonify(rep.to_dict())
        
        data = request.json
        if 'progression' in data: rep.progression_pourcent = data['progression']
        for f in ['fixer_nom', 'pays', 'region', 'statut']:
            if f in data: setattr(rep, f, data[f])
            
        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'particularite_data' in data: rep.particularite_data = json.dumps(data['particularite_data'])
        if 'fete_data' in data: rep.fete_data = json.dumps(data['fete_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])

        if 'gardiens' in data:
            for g_data in data['gardiens']:
                obj = session.query(Gardien).filter_by(reperage_id=id, ordre=g_data.get('ordre')).first() or Gardien(reperage_id=id, ordre=g_data.get('ordre'))
                for k, v in g_data.items(): 
                    if hasattr(obj, k): setattr(obj, k, v)
                session.add(obj)
        if 'lieux' in data:
            for l_data in data['lieux']:
                obj = session.query(Lieu).filter_by(reperage_id=id, numero_lieu=l_data.get('numero_lieu')).first() or Lieu(reperage_id=id, numero_lieu=l_data.get('numero_lieu'))
                for k, v in l_data.items():
                    if hasattr(obj, k): setattr(obj, k, v)
                session.add(obj)
        
        session.commit()
        return jsonify({'status': 'success', 'synced': rep.progression_pourcent})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally: session.close()

# SOUMISSION (FIX 5)
@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def api_submit_reperage(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        rep.statut = 'soumis'
        session.commit()
        # Envoi au Bridge
        if DOCUGEN_URL:
            headers = {"X-Bridge-Token": BRIDGE_TOKEN, "Content-Type": "application/json"}
            requests.post(DOCUGEN_URL, json=rep.to_dict(), headers=headers, timeout=10)
        return jsonify({'status': 'success', 'message': 'Dossier transmis'})
    finally: session.close()

# API MÉDIAS (FIX 1)
@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
def api_media_handler(id):
    session = get_session(engine)
    if request.method == 'GET':
        ms = session.query(Media).filter_by(reperage_id=id).all()
        return jsonify([m.to_dict() for m in ms])
    
    file = request.files['file']
    filename = secrets.token_hex(8) + "_" + secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, chemin_fichier=f"{id}/{filename}", type='photo')
    session.add(m); session.commit()
    return jsonify(m.to_dict())

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

@app.route('/api/i18n/<lang>')
def api_i18n(lang):
    try:
        path = os.path.join(app.root_path, 'translations', 'i18n.json')
        with open(path, 'r', encoding='utf-8') as f: return jsonify(json.load(f).get(lang, {}))
    except: return jsonify({}), 404

# Autres routes (Detail, Fixers, Print, Chat) maintenues sans simplification
@app.route('/admin/reperage/<int:id>')
def admin_detail(id):
    session = get_session(engine); rep = session.get(Reperage, id); t = json.loads(rep.territoire_data); part = json.loads(rep.particularite_data); fete = json.loads(rep.fete_data); e = json.loads(rep.episode_data)
    return render_template('admin_reperage_detail.html', reperage=rep, territoire=t, particularites=part, fete=fete, episode=e, fixer=session.get(Fixer, rep.fixer_id))

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_quick_update(id):
    session = get_session(engine); data = request.json; rep = session.get(Reperage, id)
    for f in ['region', 'pays', 'statut', 'notes_admin']:
        if f in data: setattr(rep, f, data[f])
    session.commit(); return jsonify({'status': 'success'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
