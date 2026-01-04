import os, json, secrets, requests, io, re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

# =================================================================
# 1. INITIALISATION DE L'APP
# =================================================================
app = Flask(__name__)
CORS(app)

# Configuration dossiers
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'thumbnails'), exist_ok=True)

# Base de données
db_url = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db').replace('postgres://', 'postgresql://')
engine = init_db(db_url)

# =================================================================
# 2. FONCTIONS SYSTÈME
# =================================================================

def send_to_docugen(reperage_dict):
    url = os.environ.get('DOCUGEN_API_URL')
    token = os.environ.get('BRIDGE_SECRET_TOKEN')
    if not url: return False
    headers = {"X-Bridge-Token": token, "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=reperage_dict, headers=headers, timeout=15)
        return response.status_code == 200
    except: return False

# =================================================================
# 3. ROUTES ADMIN & BRIDGE
# =================================================================

@app.route('/')
def index_root():
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        query = session.query(Reperage, Fixer).outerjoin(Fixer, Reperage.fixer_id == Fixer.id)
        results = query.order_by(Reperage.created_at.desc()).all()
        reps = [{'reperage': r, 'fixer': f} for r, f in results]
        return render_template('admin_dashboard.html', reperages=reps, stats={})
    finally: session.close()

@app.route('/admin/reperage/<int:id>')
def admin_reperage_detail(id):
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage: return "Non trouvé", 404
        t = json.loads(reperage.territoire_data) if reperage.territoire_data else {}
        e = json.loads(reperage.episode_data) if reperage.episode_data else {}
        fixer = session.get(Fixer, reperage.fixer_id) if reperage.fixer_id else None
        return render_template('admin_reperage_detail.html', reperage=reperage, territoire=t, episode=e, gardiens=reperage.gardiens, lieux=reperage.lieux, medias=reperage.medias, fixer=fixer)
    finally: session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage: return jsonify({'error': 'Non trouvé'}), 404
        reperage.statut = 'soumis'
        session.commit()
        success = send_to_docugen(reperage.to_dict())
        return jsonify({'status': 'success', 'bridge_sent': success})
    except Exception as e: return jsonify({'error': str(e)}), 500
    finally: session.close()

# =================================================================
# 4. ROUTES CORRESPONDANTS (RÉTABLIES)
# =================================================================

@app.route('/fixer/<path:fixer_slug>')
def fixer_form(fixer_slug):
    """Lien personnel du correspondant"""
    token = fixer_slug[-8:] # Les 8 derniers caractères
    session = get_session(engine)
    try:
        fixer = session.query(Fixer).filter_by(token_unique=token, actif=True).first()
        if not fixer: return "Lien invalide ou inactif", 404
        
        # Chercher si un brouillon existe déjà pour ce fixer
        rep_existant = session.query(Reperage).filter_by(fixer_id=fixer.id, statut='brouillon').first()
        reperage_id = rep_existant.id if rep_existant else None
        
        return render_template('index.html', fixer_id=fixer.id, fixer_nom=f"{fixer.prenom} {fixer.nom}", fixer_email=fixer.email, reperage_id=reperage_id)
    finally: session.close()

@app.route('/formulaire/<token>')
def formulaire_reperage(token):
    """Accès direct à un formulaire par son token"""
    session = get_session(engine)
    try:
        reperage = session.query(Reperage).filter_by(token=token).first()
        if not reperage: return "Repérage non trouvé", 404
        fixer = session.query(Fixer).get(reperage.fixer_id)
        return render_template('index.html', REPERAGE_ID=reperage.id, FIXER_DATA={'prenom': fixer.prenom, 'nom': fixer.nom})
    finally: session.close()

# =================================================================
# 5. ROUTES TECHNIQUES (MESSAGES, UPLOADS)
# =================================================================

@app.route('/api/reperages/<int:reperage_id>/messages', methods=['GET'])
def get_messages(reperage_id):
    session = get_session(engine)
    try:
        msgs = session.query(Message).filter_by(reperage_id=reperage_id).order_by(Message.created_at.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    finally: session.close()

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
