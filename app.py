import os, json, secrets, requests, io, re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image

# Import des modèles
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

# =================================================================
# 1. INITIALISATION (Ligne 14 : Création de 'app')
# =================================================================
app = Flask(__name__)
CORS(app)

# Configuration dossiers
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'thumbnails'), exist_ok=True)

# Configuration Base de données
database_url = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

engine = init_db(database_url)

# =================================================================
# 2. FONCTIONS SYSTÈME
# =================================================================

def send_to_docugen(reperage_dict):
    """Envoie les données vers Docu-Gen via la passerelle"""
    url = os.environ.get('DOCUGEN_API_URL')
    token = os.environ.get('BRIDGE_SECRET_TOKEN')
    
    if not url:
        print("Erreur: URL Docu-Gen non configurée")
        return False
        
    headers = {
        "X-Bridge-Token": token,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=reperage_dict, headers=headers, timeout=15)
        return response.status_code == 200
    except Exception as e:
        print(f"Erreur Bridge: {e}")
        return False

# =================================================================
# 3. ROUTES API (Toutes les routes sont APRES l'initialisation de app)
# =================================================================

@app.route('/')
def index_root():
    return redirect('/admin')

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    """Route de soumission avec Bridge IA"""
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage:
            return jsonify({'error': 'Repérage non trouvé'}), 404
        
        # Marquer comme soumis
        reperage.statut = 'soumis'
        reperage.updated_at = datetime.now()
        session.commit()
        
        # Envoyer à Docu-Gen
        data = reperage.to_dict()
        bridge_success = send_to_docugen(data)
        
        return jsonify({
            'status': 'success',
            'bridge_sent': bridge_success
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/admin')
def admin_dashboard():
    """Vue Dashboard Admin"""
    session = get_session(engine)
    try:
        query = session.query(Reperage, Fixer).outerjoin(Fixer, Reperage.fixer_id == Fixer.id)
        results = query.order_by(Reperage.created_at.desc()).all()
        reps_list = [{'reperage': r, 'fixer': f} for r, f in results]
        return render_template('admin_dashboard.html', reperages=reps_list, stats={})
    finally:
        session.close()

@app.route('/admin/reperage/<int:id>')
def admin_reperage_detail(id):
    """Vue Détail Admin"""
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage: return "Non trouvé", 404
        
        territoire = json.loads(reperage.territoire_data) if reperage.territoire_data else {}
        episode = json.loads(reperage.episode_data) if reperage.episode_data else {}
        fixer = session.get(Fixer, reperage.fixer_id) if reperage.fixer_id else None
        
        return render_template('admin_reperage_detail.html', 
                             reperage=reperage, territoire=territoire, episode=episode,
                             gardiens=reperage.gardiens, lieux=reperage.lieux, 
                             medias=reperage.medias, fixer=fixer)
    finally:
        session.close()

@app.route('/api/reperages/<int:reperage_id>/messages', methods=['GET'])
def get_messages(reperage_id):
    session = get_session(engine)
    try:
        messages = session.query(Message).filter_by(reperage_id=reperage_id).order_by(Message.created_at.asc()).all()
        return jsonify([msg.to_dict() for msg in messages])
    finally:
        session.close()

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# =================================================================
# 4. LANCEMENT
# =================================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
