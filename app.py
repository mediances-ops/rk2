import os, json, secrets, requests, re, io, zipfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, abort, send_file
from flask_cors import CORS
from sqlalchemy import or_, text
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION RAILWAY ---
raw_db_url = os.environ.get('DATABASE_URL')
DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1) if raw_db_url and raw_db_url.startswith('postgres://') else (raw_db_url or 'sqlite:///reperage.db')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_PATH', '/data/uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

engine = init_db(DB_URL)

@app.template_filter('linkify')
def linkify_text(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

# =================================================================
# I. ADMINISTRATION (DASHBOARD & FILTRES)
# =================================================================

@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        query = session.query(Reperage)
        if request.args.get('statut'): query = query.filter(Reperage.statut == request.args.get('statut'))
        if request.args.get('pays'): query = query.filter(Reperage.pays == request.args.get('pays'))
        
        reps = query.order_by(Reperage.created_at.desc()).all()
        fixers = session.query(Fixer).all()
        stats = {'total': session.query(Reperage).count(), 'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(), 'soumis': session.query(Reperage).filter_by(statut='soumis').count(), 'valides': session.query(Reperage).filter_by(statut='validé').count()}
        
        reps_serialized = []
        for r in reps:
            f = session.get(Fixer, r.fixer_id)
            unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
            last_m = session.query(Message).filter_by(reperage_id=r.id).order_by(Message.created_at.desc()).first()
            r_data = r.to_dict()
            r_data['unread_count'] = unread
            r_data['last_sender'] = last_m.auteur_nom if (last_m and unread > 0) else None
            r_data['prog_pourcent'] = r.progression_pourcent or 0
            reps_serialized.append({'reperage': r_data, 'fixer': f.to_dict() if f else None})
            
        pays_list = [p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]]
        return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=fixers, stats=stats, pays_list=pays_list)
    finally: session.close()

# FIX 10 : Filtres Fixers
@app.route('/admin/fixers')
def route_admin_fixers():
    session = get_session(engine)
    query = session.query(Fixer)
    if request.args.get('search'):
        s = f"%{request.args.get('search')}%"
        query = query.filter(or_(Fixer.nom.like(s), Fixer.prenom.like(s), Fixer.societe.like(s)))
    if request.args.get('pays'): query = query.filter(Fixer.pays == request.args.get('pays'))
    
    fixers = query.order_by(Fixer.nom.asc()).all()
    pays_list = [p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]]
    return render_template('admin_fixers.html', fixers=fixers, pays_list=pays_list)

@app.route('/admin/fixer/new', methods=['GET', 'POST'])
@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_fixer(id=None):
    session = get_session(engine)
    try:
        fixer = session.get(Fixer, id) if id else None
        if request.method == 'POST':
            if not fixer:
                fixer = Fixer(token_unique=secrets.token_hex(4), created_at=datetime.now())
                session.add(fixer)
            for k in ['nom', 'prenom', 'email', 'telephone', 'telephone_2', 'societe', 'fonction', 'site_web', 'numero_siret', 'adresse_1', 'adresse_2', 'code_postal', 'ville', 'pays', 'region', 'photo_profil_url', 'bio', 'specialites', 'langue_preferee', 'notes_internes']:
                if k in request.form: setattr(fixer, k, request.form[k])
            fixer.actif = 'actif' in request.form
            fixer.langues_parlees = ", ".join(request.form.getlist('langues_parlees'))
            fixer.lien_personnel = f"{request.host_url}formulaire/{fixer.token_unique}"
            session.commit()
            return redirect('/admin/fixers')
        return render_template('admin_fixer_edit_v2.html', fixer=fixer)
    finally: session.close()

# =================================================================
# II. SAUVEGARDE SEGMENTÉE (AUCUNE SIMPLIFICATION)
# =================================================================

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def api_segmented_sync(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404
        
        if 'progression' in data: rep.progression_pourcent = data['progression']
        for f in ['fixer_nom', 'fixer_prenom', 'pays', 'region', 'statut']:
            if f in data: setattr(rep, f, data[f])
            
        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
        # RESTAURATION LOGIQUE GARDIENS ET LIEUX (Soudure Fix 2)
        if 'gardiens' in data:
            for g in data['gardiens']:
                obj = session.query(Gardien).filter_by(reperage_id=id, ordre=g.get('ordre')).first() or Gardien(reperage_id=id, ordre=g.get('ordre'))
                for k, v in g.items(): 
                    if hasattr(obj, k): setattr(obj, k, v)
                session.add(obj)
        if 'lieux' in data:
            for l in data['lieux']:
                obj = session.query(Lieu).filter_by(reperage_id=id, numero_lieu=l.get('numero_lieu')).first() or Lieu(reperage_id=id, numero_lieu=l.get('numero_lieu'))
                for k, v in l.items():
                    if hasattr(obj, k): setattr(obj, k, v)
                session.add(obj)
        
        session.commit()
        return jsonify({'status': 'success'})
    finally: session.close()

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_quick_update(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        for f in ['region', 'pays', 'statut', 'notes_admin', 'image_region']:
            if f in data: setattr(rep, f, data[f])
        session.commit()
        return jsonify({'status': 'success'})
    finally: session.close()

# =================================================================
# III. DOWNLOADS & PRINT (FIX 3 & 5)
# =================================================================

@app.route('/admin/reperage/<int:id>/print')
def admin_haute_substance_print(id):
    session = get_session(engine)
    rep = session.get(Reperage, id)
    t = json.loads(rep.territoire_data) if rep.territoire_data else {}
    e = json.loads(rep.episode_data) if rep.episode_data else {}
    return render_template('print_reperage.html', rep=rep, territoire=t, episode=e, fixer=session.get(Fixer, rep.fixer_id))

@app.route('/admin/reperage/<int:id>/photos')
def admin_zip_gen(id):
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    if not os.path.exists(path): return "Aucune photo", 404
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for root, dirs, files in os.walk(path):
            for file in files: zf.write(os.path.join(root, file), file)
    memory_file.seek(0)
    return send_file(memory_file, download_name=f"Substance_Photos_{id}.zip", as_attachment=True)

# ... (Routes Chat, Medias, i18n, Formulaire maintenues) ...
@app.route('/api/i18n/<lang>')
def api_get_trans(lang):
    try:
        with open(os.path.join(app.root_path, 'translations', 'i18n.json'), 'r', encoding='utf-8') as f:
            return jsonify(json.load(f).get(lang, {}))
    except: return jsonify({}), 404

@app.route('/formulaire/<token>')
def route_form_fixer(token):
    session = get_session(engine); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    f = session.get(Fixer, rep.fixer_id)
    f_data = {'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region, 'reperage_id': rep.id, 'nom': f.nom if f else '', 'prenom': f.prenom if f else '', 'langue_default': f.langue_preferee if f else 'FR'}
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=f_data)

@app.route('/api/reperages/<int:id>', methods=['GET'])
def api_get_rep(id):
    session = get_session(engine); rep = session.get(Reperage, id)
    return jsonify(rep.to_dict())

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_messages(id):
    session = get_session(engine)
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.created_at.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json; m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify(m.to_dict()), 201

@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
def api_medias(id):
    session = get_session(engine)
    if request.method == 'GET':
        ms = session.query(Media).filter_by(reperage_id=id).all()
        return jsonify([m.to_dict() for m in ms])
    file = request.files['file']; filename = secrets.token_hex(8) + "_" + secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id)); os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, filename); file.save(file_path)
    m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, chemin_fichier=f"{id}/{filename}", type='photo')
    session.add(m); session.commit(); return jsonify(m.to_dict())

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
