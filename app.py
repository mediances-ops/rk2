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

# ================= INITIALISATION =================
app = Flask(__name__)
CORS(app)

# Configuration dossiers
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'heic', 'webp', 'pdf', 'doc', 'docx', 'mp4', 'mov', 'avi'}
MAX_FILE_SIZE = 500 * 1024 * 1024

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'thumbnails'), exist_ok=True)

# Configuration Base de données
database_url = os.environ.get('DATABASE_URL')
if database_url:
    database_url = database_url.replace('postgres://', 'postgresql://')
else:
    database_url = 'sqlite:///reperage.db'

engine = init_db(database_url)

# ================= FONCTIONS UTILES =================

def send_to_docugen(reperage_dict):
    """Envoie les données vers Docu-Gen via la passerelle sécurisée"""
    url = os.environ.get('DOCUGEN_API_URL')
    token = os.environ.get('BRIDGE_SECRET_TOKEN')
    
    if not url:
        print("⚠️ Bridge annulé: DOCUGEN_API_URL non configuré.")
        return False
        
    headers = {
        "X-Bridge-Token": token,
        "Content-Type": "application/json"
    }
    
    try:
        print(f"🚀 Tentative d'envoi vers {url}...")
        response = requests.post(url, json=reperage_dict, headers=headers, timeout=15)
        if response.status_code == 200:
            print("✅ Transfert réussi !")
            return True
        else:
            print(f"❌ Erreur transfert: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"💥 Crash Bridge: {str(e)}")
        return False

def generate_token():
    return secrets.token_urlsafe(16)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ================= ROUTES API (BRIDGE INCLUS) =================

@app.route('/')
def index():
    return redirect('/admin')

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    """Verrouille le repérage et l'envoie à Docu-Gen"""
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage:
            return jsonify({'error': 'Repérage non trouvé'}), 404
        
        # 1. Mise à jour statut
        reperage.statut = 'soumis'
        reperage.updated_at = datetime.now()
        session.commit()
        
        # 2. Préparation du paquet de données
        data_to_send = reperage.to_dict()
        
        # 3. Appel du Bridge
        bridge_success = send_to_docugen(data_to_send)
        
        return jsonify({
            'status': 'success',
            'bridge_sent': bridge_success,
            'message': 'Dossier envoyé à Docu-Gen' if bridge_success else 'Statut mis à jour mais erreur Bridge'
        })
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# --- Les autres routes standards (simplifiées pour la clarté) ---

@app.route('/api/reperages', methods=['GET'])
def get_reperages():
    session = get_session(engine)
    try:
        items = session.query(Reperage).all()
        return jsonify([i.to_dict() for i in items])
    finally: session.close()

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        from models import Fixer
        results = session.query(Reperage, Fixer).outerjoin(Fixer, Reperage.fixer_id == Fixer.id).all()
        reperages_list = []
        for r, f in results:
            reperages_list.append({'reperage': r, 'fixer': f})
        return render_template('admin_dashboard.html', reperages=reperages_list, stats={})
    finally: session.close()

@app.route('/admin/reperage/<int:id>')
def admin_reperage_detail(id):
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage: return "Non trouvé", 404
        # Parsing JSON pour templates
        territoire = json.loads(reperage.territoire_data) if reperage.territoire_data else {}
        episode = json.loads(reperage.episode_data) if reperage.episode_data else {}
        return render_template('admin_reperage_detail.html', 
                             reperage=reperage, territoire=territoire, episode=episode,
                             gardiens=reperage.gardiens, lieux=reperage.lieux, medias=reperage.medias, fixer=None)
    finally: session.close()

# (Note: Tu devras garder tes autres routes API ici : lieux, gardiens, medias, messages...)
# Elles ne changent pas par rapport à ta version originale.

# ================= LANCEMENT =================
if __name__ == '__main__':
    with app.app_context():
        from models import Base
        Base.metadata.create_all(engine)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
