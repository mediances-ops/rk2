from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer
import os
import json
import secrets
import requests
from datetime import datetime
from PIL import Image
import io
import re

# =================================================================
# 1. INITIALISATION DE L'APP (DOIT ÊTRE AU DÉBUT)
# =================================================================
app = Flask(__name__)
CORS(app)

# Configuration dossiers
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'heic', 'webp', 'pdf', 'doc', 'docx', 'mp4', 'mov', 'avi'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 # 500 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'thumbnails'), exist_ok=True)

# Configuration Base de données
database_url = os.environ.get('DATABASE_URL')
if database_url:
    database_url = database_url.replace('postgres://', 'postgresql://')
else:
    database_url = 'sqlite:///reperage.db'

engine = init_db(database_url)

# =================================================================
# 2. FONCTIONS SYSTÈME & BRIDGE
# =================================================================

def send_to_docugen(reperage_dict):
    """Envoie les données vers Docu-Gen"""
    url = os.environ.get('DOCUGEN_API_URL')
    token = os.environ.get('BRIDGE_SECRET_TOKEN')
    if not url: return False
    
    headers = {"X-Bridge-Token": token, "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=reperage_dict, headers=headers, timeout=15)
        return response.status_code == 200
    except: return False

def generate_token(): return secrets.token_urlsafe(16)
def allowed_file(filename): return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =================================================================
# 3. ROUTES API (TOUT APRÈS APP = FLASK)
# =================================================================

@app.route('/')
def index():
    return redirect('/admin')

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage: return jsonify({'error': 'Non trouvé'}), 404
        
        reperage.statut = 'soumis'
        reperage.updated_at = datetime.now()
        session.commit()
        
        # Envoi Bridge
        success = send_to_docugen(reperage.to_dict())
        return jsonify({'status': 'success', 'bridge_sent': success})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# Vos autres routes (Gardiens, Lieux, etc.)
@app.route('/api/reperages', methods=['GET'])
def get_reperages():
    session = get_session(engine)
    try:
        reperages = session.query(Reperage).all()
        return jsonify([r.to_dict() for r in reperages])
    finally: session.close()

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        from models import Fixer
        query = session.query(Reperage, Fixer).outerjoin(Fixer, Reperage.fixer_id == Fixer.id)
        results = query.order_by(Reperage.created_at.desc()).all()
        reperages_list = [{'reperage': r, 'fixer': f} for r, f in results]
        return render_template('admin_dashboard.html', reperages=reperages_list, stats={})
    finally: session.close()

@app.route('/admin/reperage/<int:id>')
def admin_reperage_detail(id):
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage: return "Non trouvé", 404
        territoire = json.loads(reperage.territoire_data) if reperage.territoire_data else {}
        episode = json.loads(reperage.episode_data) if reperage.episode_data else {}
        from models import Fixer
        fixer = session.get(Fixer, reperage.fixer_id) if reperage.fixer_id else None
        return render_template('admin_reperage_detail.html', 
                             reperage=reperage, territoire=territoire, episode=episode,
                             gardiens=reperage.gardiens, lieux=reperage.lieux, 
                             medias=reperage.medias, fixer=fixer)
    finally: session.close()

# API MESSAGES
@app.route('/api/reperages/<int:reperage_id>/messages', methods=['GET'])
def get_messages(reperage_id):
    session = get_session(engine)
    try:
        msgs = session.query(Message).filter_by(reperage_id=reperage_id).order_by(Message.created_at.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    finally: session.close()

@app.route('/api/reperages/<int:reperage_id>/messages', methods=['POST'])
def create_message(reperage_id):
    session = get_session(engine)
    try:
        data = request.json
        msg = Message(reperage_id=reperage_id, auteur_type=data.get('auteur_type'), 
                      auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
        session.add(msg)
        session.commit()
        return jsonify(msg.to_dict()), 201
    finally: session.close()

# ROUTE POUR LES FICHIERS UPLOADÉS
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# =================================================================
# 4. LANCEMENT
# =================================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
