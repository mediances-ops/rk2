import os, json, secrets, requests, re, io
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, abort, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from sqlalchemy import or_, text
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

# PDF Moteur
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# =================================================================
# 1. INITIALISATION ET SÉCURISATION
# =================================================================
app = Flask(__name__)
CORS(app)

raw_db_url = os.environ.get('DATABASE_URL')
if raw_db_url:
    DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1) if raw_db_url.startswith('postgres://') else raw_db_url
else:
    DB_URL = 'sqlite:///reperage.db'

UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

engine = init_db(DB_URL)

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

# =================================================================
# 3. PDF HAUTE SUBSTANCE (CORRIGÉ)
# =================================================================

@app.route('/admin/reperage/<int:id>/pdf')
def generate_pdf(id):
    session = get_session(engine)
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # En-tête
    p.setFont("Helvetica-Bold", 20)
    p.drawString(50, height - 50, "DOC-OS | DOSSIER DE REPÉRAGE")
    p.setFont("Helvetica", 12)
    p.drawString(50, height - 70, f"Région : {rep.region or 'N/A'} | Pays : {rep.pays or 'N/A'}")
    p.line(50, height - 80, width - 50, height - 80)

    # Contenu
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, height - 110, "INFORMATIONS GÉNÉRALES")
    p.setFont("Helvetica", 11)
    p.drawString(60, height - 130, f"Fixer : {rep.fixer_nom or 'N/A'}")
    p.drawString(60, height - 145, f"Date de création : {rep.created_at.strftime('%d/%m/%Y')}")
    p.drawString(60, height - 160, f"Niveau de complétion : {rep.progression_pourcent}%")

    # Section Territoire
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, height - 200, "1. LE TERRITOIRE")
    t_data = json.loads(rep.territoire_data) if rep.territoire_data else {}
    y = height - 220
    for key, val in t_data.items():
        if val and y > 50:
            p.setFont("Helvetica-Bold", 10)
            p.drawString(60, y, f"{key.capitalize()} :")
            p.setFont("Helvetica", 10)
            p.drawString(150, y, f"{str(val)[:80]}")
            y -= 15

    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"DOC_OS_{rep.region}_{id}.pdf", mimetype='application/pdf')

# =================================================================
# 4. FORMULAIRE DISTANT (FIX ATTRIBUT ERROR)
# =================================================================

@app.route('/formulaire/<token>')
def formulaire_token(token):
    session = get_session(engine)
    try:
        # CORRECTION : Utilisation de first() car first_or_404 n'existe pas en standard
        rep = session.query(Reperage).filter_by(token=token).first()
        if not rep: 
            abort(404)
        
        fixer = session.get(Fixer, rep.fixer_id)
        f_data = {
            'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region, 'reperage_id': rep.id,
            'nom': fixer.nom if fixer else '', 'prenom': fixer.prenom if fixer else '',
            'langue_default': fixer.langue_preferee if fixer else 'FR'
        }
        return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=f_data)
    finally: session.close()

# =================================================================
# 5. API SOUDURE (SYNCHRONISATION)
# =================================================================

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage_api(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404

        if 'progression' in data: rep.progression_pourcent = data['progression']

        for f in ['fixer_nom', 'fixer_prenom', 'pays', 'region', 'notes_admin', 'image_region', 'statut']:
            if f in data: setattr(rep, f, data[f])

        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
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
        return jsonify({'status': 'success'})
    finally: session.close()

@app.route('/api/reperages/<int:id>/medias', methods=['POST'])
def upload_media_api(id):
    if 'file' not in request.files: return "Aucun fichier", 400
    file = request.files['file']
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, filename)
    file.save(file_path)
    
    session = get_session(engine)
    try:
        m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, 
                  chemin_fichier=f"{id}/{filename}", type='photo' if filename.lower().endswith(('.jpg','.png','.jpeg')) else 'document')
        session.add(m); session.commit()
        return jsonify(m.to_dict())
    finally: session.close()

# --- AUTRES ROUTES (Identiques V18) ---
@app.route('/api/i18n/<lang>')
def get_i18n(lang):
    try:
        path = os.path.join(app.root_path, 'translations', 'i18n.json')
        with open(path, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        return jsonify(translations.get(lang, translations.get('FR', {})))
    except: return jsonify({'error': 'Not found'}), 404

@app.route('/api/reperages/<int:id>', methods=['GET'])
def get_reperage_api_v2(id):
    session = get_session(engine)
    rep = session.get(Reperage, id)
    return jsonify(rep.to_dict()) if rep else ({'error': '404'}, 404)

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def handle_messages(id):
    session = get_session(engine)
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.created_at.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json
    m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify(m.to_dict()), 201

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
