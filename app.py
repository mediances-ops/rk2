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

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION RAILWAY ---
raw_db_url = os.environ.get('DATABASE_URL')
if raw_db_url:
    DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1) if raw_db_url.startswith('postgres://') else raw_db_url
    print("✅ DATABASE: PostgreSQL Connectée")
else:
    DB_URL = 'sqlite:///reperage.db'

UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

engine = init_db(DB_URL)

# Migration volante pour la jauge
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
# I. ROUTES ADMINISTRATION (FIXERS & DASHBOARD)
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

@app.route('/admin/reperage/<int:id>')
def route_admin_detail(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: abort(404)
        t = json.loads(rep.territoire_data) if rep.territoire_data else {}
        e = json.loads(rep.episode_data) if rep.episode_data else {}
        fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        return render_template('admin_reperage_detail.html', reperage=rep, territoire=t, episode=e, gardiens=rep.gardiens, lieux=rep.lieux, medias=rep.medias, fixer=fixer)
    finally: session.close()

@app.route('/admin/fixers')
def route_admin_fixers():
    session = get_session(engine)
    try:
        fixers = session.query(Fixer).all()
        return render_template('admin_fixers.html', fixers=fixers, pays_list=[])
    finally: session.close()

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def route_admin_update(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: abort(404)
        for f in ['region', 'pays', 'statut', 'notes_admin']:
            if f in data: setattr(rep, f, data[f])
        session.commit()
        return jsonify({'status': 'success'})
    finally: session.close()

# =================================================================
# II. API SOUDURE (UTILISÉE PAR LE FORMULAIRE JS)
# =================================================================

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def api_update_reperage(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404

        # SYNC PROGRESSION
        if 'progression' in data:
            rep.progression_pourcent = data['progression']

        # Identité
        for f in ['fixer_nom', 'fixer_prenom', 'pays', 'region', 'statut']:
            if f in data: setattr(rep, f, data[f])

        # Datas
        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
        # Deep Save Gardiens/Lieux
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

@app.route('/api/reperages/<int:id>', methods=['GET'])
def api_get_reperage(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        return jsonify(rep.to_dict()) if rep else ({'error': '404'}, 404)
    finally: session.close()

@app.route('/api/i18n/<lang>')
def api_get_i18n(lang):
    try:
        path = os.path.join(app.root_path, 'translations', 'i18n.json')
        with open(path, 'r', encoding='utf-8') as f:
            trans = json.load(f)
        return jsonify(trans.get(lang, trans.get('FR')))
    except: return jsonify({}), 404

# =================================================================
# III. MÉDIAS, PDF ET CHAT
# =================================================================

@app.route('/admin/reperage/<int:id>/pdf')
def route_generate_pdf(id):
    session = get_session(engine)
    rep = session.get(Reperage, id)
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.drawString(50, 800, f"DOC-OS Dossier #{id}")
    p.drawString(50, 780, f"Région: {rep.region}")
    p.save(); buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Rep_{id}.pdf", mimetype='application/pdf')

@app.route('/api/reperages/<int:id>/medias', methods=['POST'])
def api_upload_media(id):
    file = request.files['file']
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    session = get_session(engine)
    m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, type='photo')
    session.add(m); session.commit()
    return jsonify(m.to_dict())

@app.route('/formulaire/<token>')
def route_formulaire_fixer(token):
    session = get_session(engine)
    rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    f = session.get(Fixer, rep.fixer_id)
    f_data = {'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region, 'reperage_id': rep.id, 'nom': f.nom if f else '', 'prenom': f.prenom if f else '', 'langue_default': f.langue_preferee if f else 'FR'}
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=f_data)

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_handle_messages(id):
    session = get_session(engine)
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.created_at.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json
    m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify(m.to_dict()), 201

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_file(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
