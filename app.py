import os, json, secrets, requests, re, io, zipfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, abort, send_file
from flask_cors import CORS
from sqlalchemy import or_, text
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

# PDF Moteur
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = Flask(__name__)
CORS(app)

# =================================================================
# 1. CONFIGURATION ENVIRONNEMENT (RAILWAY)
# =================================================================
raw_db_url = os.environ.get('DATABASE_URL')
if raw_db_url:
    # Correction automatique du protocole pour SQLAlchemy 2.0
    if raw_db_url.startswith('postgres://'):
        DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1)
    else:
        DB_URL = raw_db_url
    print("✅ DATABASE: PostgreSQL Connectée")
else:
    DB_URL = 'sqlite:///reperage.db'
    print("⚠️  DATABASE: Fallback SQLite")

UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

engine = init_db(DB_URL)

# Migration auto pour la progression si nécessaire
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE reperages ADD COLUMN IF NOT EXISTS progression_pourcent INTEGER DEFAULT 0"))
        conn.commit()
    except Exception:
        pass

@app.template_filter('linkify')
def linkify_text(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

# =================================================================
# 2. ROUTES ADMINISTRATION (DASHBOARD & FILTRES)
# =================================================================

@app.route('/')
def index_root():
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        query = session.query(Reperage)
        
        # Application des filtres demandés (FIX 10)
        statut_filter = request.args.get('statut')
        pays_filter = request.args.get('pays')
        
        if statut_filter:
            query = query.filter(Reperage.statut == statut_filter)
        if pays_filter:
            query = query.filter(Reperage.pays == pays_filter)
            
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
            f = session.get(Fixer, r.fixer_id)
            unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
            last_m = session.query(Message).filter_by(reperage_id=r.id).order_by(Message.created_at.desc()).first()
            
            r_data = r.to_dict()
            r_data['unread_count'] = unread
            r_data['last_sender'] = last_m.auteur_nom if (last_m and unread > 0) else None
            r_data['prog_pourcent'] = r.progression_pourcent or 0
            
            reps_serialized.append({
                'reperage': r_data,
                'fixer': f.to_dict() if f else None
            })
            
        pays_list = [p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]]
        return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=fixers, stats=stats, pays_list=pays_list)
    finally:
        session.close()

# =================================================================
# 3. GESTION DES FIXERS (CRUD COMPLET - FIX 1 & 3)
# =================================================================

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_session(engine)
    try:
        fixers = session.query(Fixer).order_by(Fixer.nom.asc()).all()
        pays_list = [p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]]
        return render_template('admin_fixers.html', fixers=fixers, pays_list=pays_list)
    finally:
        session.close()

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
            
            # Enregistrement intégral sans aucune simplification
            for k in ['nom', 'prenom', 'email', 'telephone', 'telephone_2', 'societe', 'fonction', 
                      'site_web', 'numero_siret', 'adresse_1', 'adresse_2', 'code_postal', 
                      'ville', 'pays', 'region', 'photo_profil_url', 'bio', 'specialites', 
                      'langue_preferee', 'notes_internes']:
                if k in request.form:
                    setattr(fixer, k, request.form[k])
            
            fixer.actif = 'actif' in request.form
            fixer.langues_parlees = ", ".join(request.form.getlist('langues_parlees'))
            fixer.lien_personnel = f"{request.host_url}formulaire/{fixer.token_unique}"
            
            session.commit()
            return redirect('/admin/fixers')
        return render_template('admin_fixer_edit_v2.html', fixer=fixer)
    finally:
        session.close()

@app.route('/admin/fixer/<int:id>')
def admin_fixer_detail_view(id):
    session = get_session(engine)
    try:
        f = session.get(Fixer, id)
        if not f: abort(404)
        reps = session.query(Reperage).filter_by(fixer_id=id).all()
        return render_template('admin_fixer_detail.html', fixer=f, reperages=reps)
    finally:
        session.close()

# =================================================================
# 4. GESTION DES REPÉRAGES & DOWNLOADS (FIX 5, 6 & 7)
# =================================================================

@app.route('/admin/reperage/<int:id>')
def admin_view_reperage_detail(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: abort(404)
        t = json.loads(rep.territoire_data) if rep.territoire_data else {}
        e = json.loads(rep.episode_data) if rep.episode_data else {}
        f = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        return render_template('admin_reperage_detail.html', reperage=rep, territoire=t, episode=e, fixer=f)
    finally:
        session.close()

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_quick_update_rep(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: abort(404)
        for f in ['region', 'pays', 'statut', 'notes_admin', 'image_region']:
            if f in data: setattr(rep, f, data[f])
        session.commit()
        return jsonify({'status': 'success'})
    finally:
        session.close()

@app.route('/admin/reperage/<int:id>/print')
def admin_print_handler(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: abort(404)
        t = json.loads(rep.territoire_data) if rep.territoire_data else {}
        e = json.loads(rep.episode_data) if rep.episode_data else {}
        f = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        return render_template('print_reperage.html', rep=rep, territoire=t, episode=e, fixer=f)
    finally:
        session.close()

@app.route('/admin/reperage/<int:id>/photos')
def admin_zip_handler(id):
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    if not os.path.exists(path): return "Aucune photo disponible", 404
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for root, dirs, files in os.walk(path):
            for file in files:
                zf.write(os.path.join(root, file), file)
    memory_file.seek(0)
    return send_file(memory_file, download_name=f"Photos_Rep_{id}.zip", as_attachment=True)

# =================================================================
# 5. API SOUDURE (FORMULAIRE & MÉDIAS)
# =================================================================

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_handler(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404
        if request.method == 'GET':
            return jsonify(rep.to_dict())
        
        data = request.json
        if 'progression' in data:
            rep.progression_pourcent = data['progression']
        
        for f in ['fixer_nom', 'fixer_prenom', 'pays', 'region', 'statut']:
            if f in data: setattr(rep, f, data[f])
            
        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
        session.commit()
        return jsonify({'status': 'success', 'synced': rep.progression_pourcent})
    finally:
        session.close()

@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
def api_media_handler(id):
    session = get_session(engine)
    try:
        if request.method == 'GET':
            ms = session.query(Media).filter_by(reperage_id=id).all()
            return jsonify([m.to_dict() for m in ms])
        
        file = request.files['file']
        filename = secrets.token_hex(8) + "_" + secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
        os.makedirs(path, exist_ok=True)
        file.save(os.path.join(path, filename))
        
        m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, chemin_fichier=f"{id}/{filename}", type='photo')
        session.add(m)
        session.commit()
        return jsonify(m.to_dict())
    finally:
        session.close()

@app.route('/api/i18n/<lang>')
def api_i18n_handler(lang):
    try:
        path = os.path.join(app.root_path, 'translations', 'i18n.json')
        with open(path, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        return jsonify(translations.get(lang, translations.get('FR')))
    except Exception:
        return jsonify({}), 404

# =================================================================
# 6. FORMULAIRE DISTANT & MESSAGES
# =================================================================

@app.route('/formulaire/<token>')
def route_form_viewer(token):
    session = get_session(engine)
    try:
        rep = session.query(Reperage).filter_by(token=token).first()
        if not rep: abort(404)
        f = session.get(Fixer, rep.fixer_id)
        f_data = {
            'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region, 
            'reperage_id': rep.id, 'nom': f.nom if f else '', 'prenom': f.prenom if f else '', 
            'langue_default': f.langue_preferee if f else 'FR'
        }
        return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=f_data)
    finally:
        session.close()

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_message_handler(id):
    session = get_session(engine)
    try:
        if request.method == 'GET':
            msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.created_at.asc()).all()
            return jsonify([m.to_dict() for m in msgs])
        data = request.json
        m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
        session.add(m)
        session.commit()
        return jsonify(m.to_dict()), 201
    finally:
        session.close()

@app.route('/uploads/<int:rep_id>/<filename>')
def route_serve_uploads(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
