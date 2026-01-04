from flask import Flask, request, jsonify, send_from_directory, render_template, redirect
app = Flask(__name__) # LIGNE 2 : L'application est créée ICI

from flask_cors import CORS
from werkzeug.utils import secure_filename
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer
import os, json, secrets, requests, io, re
from datetime import datetime
from PIL import Image

CORS(app)

# Configuration dossiers
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'thumbnails'), exist_ok=True)

# Base de données
database_url = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db').replace('postgres://', 'postgresql://')
engine = init_db(database_url)

# --- FONCTION BRIDGE ---
def send_to_docugen(reperage_dict):
    url = os.environ.get('DOCUGEN_API_URL')
    token = os.environ.get('BRIDGE_SECRET_TOKEN')
    if not url: return False
    headers = {"X-Bridge-Token": token, "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=reperage_dict, headers=headers, timeout=15)
        return response.status_code == 200
    except: return False

# --- ROUTES ---
@app.route('/')
def index_root():
    return redirect('/admin')

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

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        query = session.query(Reperage, Fixer).outerjoin(Fixer, Reperage.fixer_id == Fixer.id)
        results = query.order_by(Reperage.created_at.desc()).all()
        reps_list = [{'reperage': r, 'fixer': f} for r, f in results]
        return render_template('admin_dashboard.html', reperages=reps_list, stats={})
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
