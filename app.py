import os, json, secrets, requests, io, re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from PIL import Image
from slugify import slugify # Indispensable pour les liens fixers

# Import des modèles
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

# =================================================================
# 1. INITIALISATION (LIGNE 16 : INDISPENSABLE EN HAUT)
# =================================================================
app = Flask(__name__)
CORS(app)

# Configuration dossiers
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Base de données
database_url = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

engine = init_db(database_url)

# --- FONCTIONS SYSTÈME ---
def send_to_docugen(reperage_dict):
    url = os.environ.get('DOCUGEN_API_URL')
    token = os.environ.get('BRIDGE_SECRET_TOKEN')
    if not url: return False
    headers = {"X-Bridge-Token": token, "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=reperage_dict, headers=headers, timeout=15)
        return response.status_code == 200
    except: return False

def linkify_text(text):
    if not text: return text
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)
app.jinja_env.filters['linkify'] = linkify_text

# =================================================================
# 2. ROUTES ADMINISTRATION (REPÉRAGES)
# =================================================================

@app.route('/')
def index_root():
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        query = session.query(Reperage)
        # Filtres
        s_f = request.args.get('statut')
        if s_f: query = query.filter(Reperage.statut == s_f)
        p_f = request.args.get('pays')
        if p_f: query = query.filter(Reperage.pays == p_f)
        
        reps_raw = query.order_by(Reperage.created_at.desc()).all()
        fixers_raw = session.query(Fixer).all()
        
        stats = {
            'total': session.query(Reperage).count(),
            'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(),
            'soumis': session.query(Reperage).filter_by(statut='soumis').count(),
            'valides': session.query(Reperage).filter_by(statut='validé').count()
        }

        reps_serialized = []
        for r in reps_raw:
            f_obj = next((f for f in fixers_raw if f.id == r.fixer_id), None)
            d = r.to_dict()
            d['created_at_display'] = r.created_at.strftime('%d/%m/%Y') if r.created_at else '-'
            d['created_time_display'] = r.created_at.strftime('%H:%M') if r.created_at else ''
            reps_serialized.append({'reperage': d, 'fixer': f_obj.to_dict() if f_obj else None})

        pays_list = [p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]]
        return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=[f.to_dict() for f in fixers_raw], stats=stats, pays_list=pays_list)
    finally: session.close()

@app.route('/admin/reperage/<int:id>')
def admin_reperage_detail(id):
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage: return "Repérage introuvable", 404
        t = json.loads(reperage.territoire_data) if reperage.territoire_data else {}
        e = json.loads(reperage.episode_data) if reperage.episode_data else {}
        fixer = session.get(Fixer, reperage.fixer_id) if reperage.fixer_id else None
        return render_template('admin_reperage_detail.html', reperage=reperage, territoire=t, episode=e, gardiens=reperage.gardiens, lieux=reperage.lieux, medias=reperage.medias, fixer=fixer)
    finally: session.close()

# =================================================================
# 3. ROUTES GESTION FIXERS (CORRESPONDANTS) - RESTAURÉES
# =================================================================

@app.route('/admin/fixers')
def admin_fixers():
    session = get_session(engine)
    try:
        fixers = session.query(Fixer).order_by(Fixer.nom.asc()).all()
        return render_template('admin_fixers.html', fixers=fixers)
    finally: session.close()

@app.route('/admin/fixer/new', methods=['GET', 'POST'])
def admin_create_fixer():
    if request.method == 'GET':
        return render_template('admin_fixer_edit.html', fixer=None)
    
    session = get_session(engine)
    try:
        prenom = request.form.get('prenom')
        nom = request.form.get('nom')
        token = secrets.token_urlsafe(6)[:8]
        slug = slugify(f"{prenom}-{nom}")
        
        fixer = Fixer(
            prenom=prenom, nom=nom, email=request.form.get('email'),
            telephone=request.form.get('telephone'), ville=request.form.get('ville'),
            pays=request.form.get('pays'), token_unique=token,
            lien_personnel=f"/fixer/{slug}-{token}", actif=True
        )
        session.add(fixer)
        session.commit()
        return redirect('/admin/fixers')
    finally: session.close()

@app.route('/admin/fixer/<int:id>')
def admin_fixer_detail(id):
    session = get_session(engine)
    try:
        fixer = session.get(Fixer, id)
        reperages = session.query(Reperage).filter_by(fixer_id=id).all()
        return render_template('admin_fixer_detail.html', fixer=fixer, reperages=reperages)
    finally: session.close()

@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_fixer(id):
    session = get_session(engine)
    try:
        fixer = session.get(Fixer, id)
        if request.method == 'POST':
            fixer.prenom = request.form.get('prenom')
            fixer.nom = request.form.get('nom')
            fixer.email = request.form.get('email')
            fixer.telephone = request.form.get('telephone')
            fixer.pays = request.form.get('pays')
            session.commit()
            return redirect('/admin/fixers')
        return render_template('admin_fixer_edit.html', fixer=fixer)
    finally: session.close()

# =================================================================
# 4. API & BRIDGE
# =================================================================

@app.route('/admin/reperages/create', methods=['POST'])
def admin_api_create_rep():
    session = get_session(engine)
    try:
        data = request.json
        new_rep = Reperage(
            token=secrets.token_urlsafe(16), region=data.get('region'),
            pays=data.get('pays'), fixer_id=data.get('fixer_id'),
            image_region=data.get('image_region'), statut='brouillon'
        )
        session.add(new_rep); session.commit()
        return jsonify({'status': 'success', 'id': new_rep.id})
    finally: session.close()

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage_api(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        for key in ['region', 'pays', 'statut', 'notes_admin', 'image_region']:
            if key in data: setattr(rep, key, data[key])
        session.commit()
        return jsonify({'status': 'ok'})
    finally: session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        rep.statut = 'soumis'
        session.commit()
        success = send_to_docugen(rep.to_dict())
        return jsonify({'status': 'success', 'bridge_sent': success})
    finally: session.close()

@app.route('/admin/reperage/<int:id>/supprimer', methods=['POST'])
def delete_reperage(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if rep: session.delete(rep); session.commit()
        return redirect('/admin')
    finally: session.close()

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
