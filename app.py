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
# 1. INITIALISATION ET SÉCURISATION (POSTGRESQL / VOLUMES)
# =================================================================
app = Flask(__name__)
CORS(app)

raw_db_url = os.environ.get('DATABASE_URL')
if raw_db_url:
    if raw_db_url.startswith('postgres://'):
        DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1)
    else:
        DB_URL = raw_db_url
    print("✅ DATABASE: PostgreSQL (Production) Connectée")
else:
    DB_URL = 'sqlite:///reperage.db'
    print("⚠️  DATABASE: Fallback SQLite")

UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

engine = init_db(DB_URL)

# Patch de migration auto pour la progression
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE reperages ADD COLUMN IF NOT EXISTS progression_pourcent INTEGER DEFAULT 0"))
        conn.commit()
    except Exception: pass

@app.template_filter('linkify')
def linkify_text(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

# =================================================================
# 2. ROUTES NAVIGATION & ADMIN
# =================================================================

@app.route('/')
def index_root():
    return redirect(url_for('admin_dashboard'))

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
            unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
            last_m = session.query(Message).filter_by(reperage_id=r.id).order_by(Message.created_at.desc()).first()
            r_data = r.to_dict()
            r_data['unread_count'] = unread
            r_data['last_sender'] = last_m.auteur_nom if (last_m and unread > 0) else None
            r_data['prog_pourcent'] = r.progression_pourcent or 0
            reps_serialized.append({'reperage': r_data, 'fixer': f.to_dict() if f else None})
        return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=fixers, stats=stats)
    finally: session.close()

@app.route('/admin/fixer/new', methods=['GET', 'POST'])
@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def edit_fixer(id=None):
    session = get_session(engine)
    try:
        fixer = session.get(Fixer, id) if id else None
        if request.method == 'POST':
            if not fixer:
                existing = session.query(Fixer).filter_by(email=request.form.get('email')).first()
                if existing: fixer = existing
                else:
                    fixer = Fixer(token_unique=secrets.token_hex(4), created_at=datetime.now())
                    session.add(fixer)
            for key in ['nom', 'prenom', 'email', 'telephone', 'telephone_2', 'societe', 'fonction', 'site_web', 'numero_siret', 'adresse_1', 'adresse_2', 'code_postal', 'ville', 'pays', 'region', 'photo_profil_url', 'bio', 'specialites', 'langue_preferee', 'notes_internes']:
                if key in request.form: setattr(fixer, key, request.form[key])
            fixer.actif = 'actif' in request.form
            fixer.langues_parlees = ", ".join(request.form.getlist('langues_parlees'))
            fixer.lien_personnel = f"{request.host_url}formulaire/{fixer.token_unique}"
            session.commit()
            return redirect('/admin/fixers')
        return render_template('admin_fixer_edit_v2.html', fixer=fixer)
    finally: session.close()

# =================================================================
# 3. API SOUDURE (POUR APP.JS)
# =================================================================

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage_api(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404

        # SYNCHRONISATION TOTALE AVEC LE JS
        if 'progression' in data:
            rep.progression_pourcent = data['progression']

        for f in ['fixer_nom', 'fixer_prenom', 'pays', 'region', 'notes_admin', 'image_region', 'statut']:
            if f in data: setattr(rep, f, data[f])

        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
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
        return jsonify({'status': 'success', 'synced': rep.progression_pourcent})
    finally: session.close()

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
        return jsonify(rep.to_dict()) if rep else ({'error': '404'}, 404)
    finally: session.close()

@app.route('/admin/reperage/<int:id>/pdf')
def generate_pdf(id):
    session = get_session(engine)
    rep = session.get(Reperage, id)
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.drawString(50, 800, f"DOC-OS : DOSSIER #{id}")
    p.drawString(50, 780, f"Region: {rep.region}")
    p.save(); buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Rep_{id}.pdf", mimetype='application/pdf')

# ============= FORMULAIRE & CHAT =============

@app.route('/formulaire/<token>')
def formulaire_token(token):
    session = get_session(engine)
    rep = session.query(Reperage).filter_by(token=token).first_or_404()
    f = session.get(Fixer, rep.fixer_id)
    f_data = {'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region, 'reperage_id': rep.id, 'nom': f.nom if f else '', 'prenom': f.prenom if f else '', 'langue_default': f.langue_preferee if f else 'FR'}
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=f_data)

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def handle_messages(id):
    session = get_session(engine)
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.created_at.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json
    m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify(m.to_dict()), 201

@app.route('/api/messages/<int:msg_id>/read', methods=['PUT'])
def mark_read(msg_id):
    session = get_session(engine); m = session.get(Message, msg_id)
    if m: m.lu = True
    session.commit(); return jsonify({'status': 'ok'})

@app.route('/admin/fixers')
def admin_fixers():
    session = get_session(engine); fixers = session.query(Fixer).all()
    return render_template('admin_fixers.html', fixers=fixers, pays_list=[])

@app.route('/api/reperages/<int:id>/medias', methods=['POST'])
def upload_media(id):
    file = request.files['file']; filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id)); os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    session = get_session(engine); m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, type='photo'); session.add(m); session.commit()
    return jsonify(m.to_dict())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
