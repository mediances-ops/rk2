import os, json, secrets, requests, re, io
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, abort, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

# PDF Generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# =================================================================
# 1. INITIALISATION ET SÉCURISATION POSTGRESQL
# =================================================================
app = Flask(__name__)
CORS(app)

# Récupération et correction de l'URL Database
raw_db_url = os.environ.get('DATABASE_URL')
if raw_db_url:
    if raw_db_url.startswith('postgres://'):
        DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1)
    else:
        DB_URL = raw_db_url
    print("✅ DATABASE: PostgreSQL (Production) Connectée")
else:
    DB_URL = 'sqlite:///reperage.db'
    print("⚠️  DATABASE: SQLite (Fallback)")

# Configuration Volumes et Bridge
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialisation du moteur SQLAlchemy
engine = init_db(DB_URL)

# --- PATCH DE MIGRATION VOLANT (Répare l'Erreur 500 des colonnes manquantes) ---
with engine.connect() as conn:
    try:
        # Ajout de progression_pourcent si absent (Syntaxe PostgreSQL)
        conn.execute(text("ALTER TABLE reperages ADD COLUMN IF NOT EXISTS progression_pourcent INTEGER DEFAULT 0"))
        conn.commit()
        print("🛠️  DATABASE: Colonne progression_pourcent vérifiée/ajoutée")
    except Exception as e:
        print(f"ℹ️  DATABASE: Info migration : {e}")

# --- FILTRES JINJA ---
@app.template_filter('linkify')
def linkify_text(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

# =================================================================
# 2. ROUTES DE NAVIGATION RACINE
# =================================================================

@app.route('/')
def index_root():
    return redirect(url_for('admin_dashboard'))

# =================================================================
# 3. ADMINISTRATION DES FIXERS (CORRESPONDANTS)
# =================================================================

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_session(engine)
    try:
        query = session.query(Fixer)
        if request.args.get('search'):
            s = f"%{request.args.get('search')}%"
            query = query.filter(or_(Fixer.nom.like(s), Fixer.prenom.like(s), Fixer.societe.like(s)))
        if request.args.get('pays'):
            query = query.filter(Fixer.pays == request.args.get('pays'))
        
        fixers = query.order_by(Fixer.nom.asc()).all()
        pays_list = [p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]]
        return render_template('admin_fixers.html', fixers=fixers, pays_list=pays_list)
    finally: session.close()

@app.route('/admin/fixer/<int:id>')
def admin_fixer_detail(id):
    session = get_session(engine)
    try:
        fixer = session.get(Fixer, id)
        if not fixer: abort(404)
        reperages = session.query(Reperage).filter_by(fixer_id=id).all()
        return render_template('admin_fixer_detail.html', fixer=fixer, reperages=reperages)
    finally: session.close()

@app.route('/admin/fixer/new', methods=['GET', 'POST'])
@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def edit_fixer(id=None):
    session = get_session(engine)
    try:
        fixer = session.get(Fixer, id) if id else None
        if request.method == 'POST':
            if not fixer:
                # Sécurité email unique
                existing = session.query(Fixer).filter_by(email=request.form.get('email')).first()
                if existing:
                    fixer = existing
                else:
                    fixer = Fixer(token_unique=secrets.token_hex(4), created_at=datetime.now())
                    session.add(fixer)
            
            for key in ['nom', 'prenom', 'email', 'telephone', 'telephone_2', 'societe', 'fonction', 
                        'site_web', 'numero_siret', 'adresse_1', 'adresse_2', 'code_postal', 
                        'ville', 'pays', 'region', 'photo_profil_url', 'bio', 'specialites', 
                        'langue_preferee', 'notes_internes']:
                if key in request.form: setattr(fixer, key, request.form[key])
            
            fixer.actif = 'actif' in request.form
            fixer.langues_parlees = ", ".join(request.form.getlist('langues_parlees'))
            fixer.lien_personnel = f"{request.host_url}formulaire/{fixer.token_unique}"
            
            session.commit()
            return redirect(url_for('admin_fixers_list'))
        return render_template('admin_fixer_edit_v2.html', fixer=fixer)
    finally: session.close()

# =================================================================
# 4. ADMINISTRATION DES REPÉRAGES (TABLEAU DE BORD)
# =================================================================

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        reps = session.query(Reperage).order_by(Reperage.created_at.desc()).all()
        fixers = session.query(Fixer).all()
        stats = {
            'total': len(reps),
            'brouillons': len([r for r in reps if r.statut == 'brouillon']),
            'soumis': len([r for r in reps if r.statut == 'soumis']),
            'valides': len([r for r in reps if r.statut == 'validé'])
        }
        
        reps_serialized = []
        for r in reps:
            f = session.get(Fixer, r.fixer_id)
            # Notification Chat : Messages non lus du correspondant
            unread_count = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
            last_msg = session.query(Message).filter_by(reperage_id=r.id).order_by(Message.created_at.desc()).first()
            
            r_dict = r.to_dict()
            r_dict['unread_count'] = unread_count
            r_dict['last_sender'] = last_msg.auteur_nom if (last_msg and unread_count > 0) else None
            r_dict['prog_pourcent'] = r.progression_pourcent or 0

            reps_serialized.append({
                'reperage': r_dict, 
                'fixer': f.to_dict() if f else None
            })
            
        return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=fixers, stats=stats)
    finally: session.close()

@app.route('/admin/reperage/<int:id>')
def admin_reperage_detail(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: abort(404)
        t = json.loads(rep.territoire_data) if rep.territoire_data else {}
        e = json.loads(rep.episode_data) if rep.episode_data else {}
        fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        return render_template('admin_reperage_detail.html', reperage=rep, territoire=t, episode=e, gardiens=rep.gardiens, lieux=rep.lieux, medias=rep.medias, fixer=fixer)
    finally: session.close()

@app.route('/admin/reperage/<int:id>/pdf')
def generate_pdf(id):
    session = get_session(engine)
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 800, f"DOC-OS : DOSSIER DE REPÉRAGE #{rep.id}")
    p.setFont("Helvetica", 12)
    p.drawString(50, 780, f"Région : {rep.region}")
    p.drawString(50, 765, f"Fixer : {rep.fixer_nom}")
    p.line(50, 750, 550, 750)
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Reperage_{id}.pdf", mimetype='application/pdf')

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_reperage():
    session = get_session(engine)
    try:
        data = request.json
        new_rep = Reperage(
            token=secrets.token_urlsafe(16),
            region=data.get('region'), pays=data.get('pays'),
            fixer_id=data.get('fixer_id'), fixer_nom=data.get('fixer_nom'),
            image_region=data.get('image_region'), statut='brouillon'
        )
        session.add(new_rep); session.commit()
        return jsonify({'status': 'success', 'id': new_rep.id})
    finally: session.close()

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def update_reperage_admin(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: abort(404)
        for field in ['region', 'pays', 'statut', 'notes_admin', 'image_region']:
            if field in data: setattr(rep, field, data[field])
        session.commit()
        return jsonify({'status': 'success'})
    finally: session.close()

# =================================================================
# 5. API SOUDURE FRONT-END (APP.JS)
# =================================================================

@app.route('/api/i18n/<lang>')
def get_i18n(lang):
    try:
        path = os.path.join(app.root_path, 'translations', 'i18n.json')
        with open(path, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        return jsonify(translations.get(lang, translations.get('FR', {})))
    except: return jsonify({'error': 'Not found'}), 404

@app.route('/api/reperages/<int:id>', methods=['GET'])
def get_reperage_api(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404
        return jsonify(rep.to_dict())
    finally: session.close()

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage_api(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404

        # Identité
        for f in ['fixer_nom', 'fixer_prenom', 'pays', 'region', 'notes_admin', 'image_region', 'statut']:
            if f in data: setattr(rep, f, data[f])

        # JSON
        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
        # CALCUL DE PROGRESSION (JAUGE)
        filled = 0
        if 'territoire_data' in data:
            filled += len([v for v in data['territoire_data'].values() if v and len(str(v)) > 2])
        if 'episode_data' in data:
            filled += len([v for v in data['episode_data'].values() if v and len(str(v)) > 2])
        rep.progression_pourcent = min(100, int((filled / 18) * 100))

        # Gardiens et Lieux
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
        return jsonify({'status': 'success', 'progression': rep.progression_pourcent})
    finally: session.close()

@app.route('/api/reperages/<int:id>/medias', methods=['POST'])
def upload_media_api(id):
    if 'file' not in request.files: return "No file", 400
    file = request.files['file']
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    session = get_session(engine)
    try:
        m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, 
                  type='photo' if filename.lower().endswith(('.jpg','.png','.jpeg','.webp')) else 'document')
        session.add(m); session.commit()
        return jsonify(m.to_dict())
    finally: session.close()

# =================================================================
# 6. FORMULAIRE DISTANT ET CHAT
# =================================================================

@app.route('/formulaire/<token>')
def formulaire_token(token):
    session = get_session(engine)
    try:
        rep = session.query(Reperage).filter_by(token=token).first()
        if not rep: abort(404)
        fixer = session.get(Fixer, rep.fixer_id)
        fixer_data = {
            'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region, 'reperage_id': rep.id,
            'nom': fixer.nom if fixer else '', 'prenom': fixer.prenom if fixer else '',
            'langue_default': fixer.langue_preferee if fixer else 'FR'
        }
        return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=fixer_data)
    finally: session.close()

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def handle_messages_api(id):
    session = get_session(engine)
    try:
        if request.method == 'GET':
            msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.created_at.asc()).all()
            return jsonify([m.to_dict() for m in msgs])
        data = request.json
        new_msg = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
        session.add(new_msg); session.commit()
        return jsonify(new_msg.to_dict()), 201
    finally: session.close()

@app.route('/api/messages/<int:msg_id>/read', methods=['PUT'])
def mark_message_read(msg_id):
    session = get_session(engine)
    try:
        msg = session.get(Message, msg_id)
        if msg: msg.lu = True
        session.commit(); return jsonify({'status': 'ok'})
    finally: session.close()

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
