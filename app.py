import os, json, secrets, requests, re, io, zipfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, abort, send_file
from flask_cors import CORS
from sqlalchemy import or_, text
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

app = Flask(__name__)
CORS(app)

# =================================================================
# 1. CONFIGURATION ET CONNEXION (RAILWAY POSTGRESQL)
# =================================================================
raw_db_url = os.environ.get('DATABASE_URL')
if raw_db_url:
    if raw_db_url.startswith('postgres://'):
        DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1)
    else:
        DB_URL = raw_db_url
    print("✅ DATABASE: PostgreSQL Connectée")
else:
    DB_URL = 'sqlite:///reperage.db'
    print("⚠️ DATABASE: Fallback SQLite")

UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

engine = init_db(DB_URL)

# =================================================================
# PATCH DE MIGRATION SUPRÊME (RÉPARATION STRUCTURELLE POSTGRESQL)
# =================================================================
with engine.connect() as conn:
    try:
        # Table Reperages : Segments 5 Onglets
        conn.execute(text("ALTER TABLE reperages ADD COLUMN IF NOT EXISTS particularite_data TEXT DEFAULT '{}'"))
        conn.execute(text("ALTER TABLE reperages ADD COLUMN IF NOT EXISTS fete_data TEXT DEFAULT '{}'"))
        conn.execute(text("ALTER TABLE reperages ADD COLUMN IF NOT EXISTS progression_pourcent INTEGER DEFAULT 0"))
        
        # Table Gardiens : Les 10 champs de caractérisation
        conn.execute(text("ALTER TABLE gardiens ADD COLUMN IF NOT EXISTS nom_prenom VARCHAR(255)"))
        conn.execute(text("ALTER TABLE gardiens ADD COLUMN IF NOT EXISTS age INTEGER"))
        conn.execute(text("ALTER TABLE gardiens ADD COLUMN IF NOT EXISTS fonction VARCHAR(255)"))
        conn.execute(text("ALTER TABLE gardiens ADD COLUMN IF NOT EXISTS savoir TEXT"))
        conn.execute(text("ALTER TABLE gardiens ADD COLUMN IF NOT EXISTS histoire TEXT"))
        conn.execute(text("ALTER TABLE gardiens ADD COLUMN IF NOT EXISTS psychologie TEXT"))
        conn.execute(text("ALTER TABLE gardiens ADD COLUMN IF NOT EXISTS evaluation TEXT"))
        conn.execute(text("ALTER TABLE gardiens ADD COLUMN IF NOT EXISTS langues VARCHAR(255)"))
        conn.execute(text("ALTER TABLE gardiens ADD COLUMN IF NOT EXISTS contact TEXT"))
        conn.execute(text("ALTER TABLE gardiens ADD COLUMN IF NOT EXISTS intermediaire TEXT"))
        
        # Table Lieux : Les 15 champs techniques
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS type VARCHAR(255)"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS description TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS cinegenie TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS axes TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS points_vue TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS moments TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS son TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS adequation TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS acces TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS securite TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS elec TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS espace TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS meteo TEXT"))
        conn.execute(text("ALTER TABLE lieux ADD COLUMN IF NOT EXISTS permis TEXT"))
        
        conn.commit()
        print("🛠️ DATABASE: Migration structurelle Suprême OK")
    except Exception as e:
        print(f"ℹ️ DATABASE: Migration check : {e}")

@app.template_filter('linkify')
def linkify_text(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

# =================================================================
# I. ROUTES ADMINISTRATION (DASHBOARD & FIXERS)
# =================================================================

@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        query = session.query(Reperage)
        # Filtres actifs
        statut_f = request.args.get('statut')
        pays_f = request.args.get('pays')
        if statut_f: query = query.filter(Reperage.statut == statut_f)
        if pays_f: query = query.filter(Reperage.pays == pays_f)
        
        reps = query.order_by(Reperage.created_at.desc()).all()
        fixers = session.query(Fixer).all()
        
        stats = {
            'total': session.query(Reperage).count(),
            'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(),
            'soumis': session.query(Reperage).filter_by(statut='soumis').count(),
            'valides': session.query(Reperage).filter_by(statut='validé').count()
        }
        
        reps_serialized = []
        for r in reps:
            f = session.query(Fixer).get(r.fixer_id)
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

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_session(engine)
    try:
        query = session.query(Fixer)
        search = request.args.get('search')
        if search: query = query.filter(or_(Fixer.nom.like(f"%{search}%"), Fixer.societe.like(f"%{search}%")))
        fixers = query.order_by(Fixer.nom.asc()).all()
        pays_list = [p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]]
        return render_template('admin_fixers.html', fixers=fixers, pays_list=pays_list)
    finally: session.close()

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
            
            # Enregistrement intégral Fixer
            fields = ['nom', 'prenom', 'email', 'telephone', 'telephone_2', 'societe', 'fonction', 'site_web', 'numero_siret', 'adresse_1', 'adresse_2', 'code_postal', 'ville', 'pays', 'region', 'photo_profil_url', 'bio', 'specialites', 'langue_preferee', 'notes_internes']
            for k in fields:
                if k in request.form: setattr(fixer, k, request.form[k])
            
            fixer.actif = 'actif' in request.form
            fixer.langues_parlees = ", ".join(request.form.getlist('langues_parlees'))
            fixer.lien_personnel = f"{request.host_url}formulaire/{fixer.token_unique}"
            session.commit()
            return redirect('/admin/fixers')
        return render_template('admin_fixer_edit_v2.html', fixer=fixer)
    finally: session.close()

@app.route('/admin/fixer/<int:id>')
def admin_view_fixer(id):
    session = get_session(engine)
    try:
        f = session.get(Fixer, id)
        if not f: abort(404)
        reps = session.query(Reperage).filter_by(fixer_id=id).all()
        return render_template('admin_fixer_detail.html', fixer=f, reperages=reps)
    finally: session.close()

# =================================================================
# II. GESTION DES REPÉRAGES (HAUTE SUBSTANCE)
# =================================================================

@app.route('/admin/reperage/<int:id>')
def admin_view_reperage(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: abort(404)
        t = json.loads(rep.territoire_data or "{}")
        p = json.loads(rep.particularite_data or "{}")
        f_d = json.loads(rep.fete_data or "{}")
        e = json.loads(rep.episode_data or "{}")
        f = session.get(Fixer, rep.fixer_id)
        return render_template('admin_reperage_detail.html', 
            reperage=rep, territoire=t, particularites=p, fete=f_d, episode=e, fixer=f)
    finally: session.close()

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_high_sub(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404
        if request.method == 'GET': return jsonify(rep.to_dict())
        
        data = request.json
        if 'progression' in data: rep.progression_pourcent = data['progression']
        for f in ['fixer_nom', 'fixer_prenom', 'pays', 'region', 'statut']:
            if f in data: setattr(rep, f, data[f])
            
        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'particularite_data' in data: rep.particularite_data = json.dumps(data['particularite_data'])
        if 'fete_data' in data: rep.fete_data = json.dumps(data['fete_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
        # SOUDURE RELATIONNELLE : Déballage vers tables SQL
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
    finally: session.close()

# =================================================================
# III. MOTEURS DE SORTIE (PRINT & ZIP)
# =================================================================

@app.route('/admin/reperage/<int:id>/print')
def admin_print_high_sub(id):
    session = get_session(engine)
    rep = session.get(Reperage, id)
    t = json.loads(rep.territoire_data or "{}")
    p = json.loads(rep.particularite_data or "{}")
    f_d = json.loads(rep.fete_data or "{}")
    e = json.loads(rep.episode_data or "{}")
    pairs = [{'gardien': session.query(Gardien).filter_by(reperage_id=id, ordre=i).first(), 'lieu': session.query(Lieu).filter_by(reperage_id=id, numero_lieu=i).first(), 'index': i} for i in [1,2,3]]
    return render_template('print_reperage.html', rep=rep, territoire=t, particularites=p, fete=f_d, episode=e, pairs=pairs, fixer=session.get(Fixer, rep.fixer_id))

@app.route('/admin/reperage/<int:id>/photos')
def admin_zip_gen(id):
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    if not os.path.exists(path): return "Aucune photo", 404
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for root, _, files in os.walk(path):
            for file in files: zf.write(os.path.join(root, file), file)
    memory_file.seek(0)
    return send_file(memory_file, download_name=f"Photos_Rep_{id}.zip", as_attachment=True)

# =================================================================
# IV. SERVICES SYSTÈME (CHAT, UPLOAD, i18n)
# =================================================================

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_chat(id):
    session = get_session(engine)
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.created_at.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json
    m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify(m.to_dict()), 201

@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
def api_medias(id):
    session = get_session(engine)
    if request.method == 'GET': return jsonify([m.to_dict() for m in session.query(Media).filter_by(reperage_id=id).all()])
    file = request.files['file']; filename = secrets.token_hex(8) + "_" + secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id)); os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, chemin_fichier=f"{id}/{filename}", type='photo')
    session.add(m); session.commit(); return jsonify(m.to_dict())

@app.route('/api/i18n/<lang>')
def api_i18n(lang):
    try:
        path = os.path.join(app.root_path, 'translations', 'i18n.json')
        with open(path, 'r', encoding='utf-8') as f: return jsonify(json.load(f).get(lang, {}))
    except: return jsonify({}), 404

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_quick_up(id):
    session = get_session(engine); data = request.json; rep = session.get(Reperage, id)
    for f in ['region', 'pays', 'statut', 'notes_admin', 'image_region']:
        if f in data: setattr(rep, f, data[f])
    session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_rep():
    session = get_session(engine); data = request.json
    new_rep = Reperage(token=secrets.token_urlsafe(16), region=data.get('region'), pays=data.get('pays'), fixer_id=data.get('fixer_id'), fixer_nom=data.get('fixer_nom'), notes_admin=data.get('notes_admin'), statut='brouillon')
    session.add(new_rep); session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/delete', methods=['DELETE'])
def admin_del_rep(id):
    session = get_session(engine); rep = session.get(Reperage, id)
    if rep: session.delete(rep); session.commit()
    return jsonify({'status': 'success'})

@app.route('/formulaire/<token>')
def route_form_dist(token):
    session = get_session(engine); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    f = session.get(Fixer, rep.fixer_id); f_data = {'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region, 'reperage_id': rep.id, 'nom': f.nom if f else '', 'prenom': f.prenom if f else '', 'langue_default': f.langue_preferee if f else 'FR'}
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=f_data)

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
