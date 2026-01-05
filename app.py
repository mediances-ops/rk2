import os, json, secrets, requests, io, re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect
from flask_cors import CORS
from werkzeug.utils import secure_filename
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

app = Flask(__name__)
CORS(app)

# Configuration Railway / Data
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db_url = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db').replace('postgres://', 'postgresql://')
engine = init_db(db_url)

def send_to_docugen(reperage_dict):
    url = os.environ.get('DOCUGEN_API_URL')
    token = os.environ.get('BRIDGE_SECRET_TOKEN')
    if not url: return False
    headers = {"X-Bridge-Token": token, "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=reperage_dict, headers=headers, timeout=15)
        return response.status_code == 200
    except: return False

# ================= ROUTES INDISPENSABLES =================

@app.route('/')
def index_root():
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        # On récupère les repérages ET la liste des fixers pour le bouton "Modifier"
        reperages = session.query(Reperage).order_by(Reperage.created_at.desc()).all()
        fixers = session.query(Fixer).all()
        reps_list = [{'reperage': r, 'fixer': session.get(Fixer, r.fixer_id) if r.fixer_id else None} for r in reperages]
        return render_template('admin_dashboard.html', reperages=reps_list, fixers=fixers, stats={})
    finally: session.close()

# ROUTE DU LIEN DISTANT (Celle qui ne s'ouvrait pas)
@app.route('/fixer/<path:fixer_slug>')
def fixer_form(fixer_slug):
    token = fixer_slug[-8:] # Extrait le token du lien
    session = get_session(engine)
    try:
        fixer = session.query(Fixer).filter_by(token_unique=token).first()
        if not fixer: return "Lien invalide", 404
        # Cherche un brouillon en cours
        rep = session.query(Reperage).filter_by(fixer_id=fixer.id, statut='brouillon').first()
        return render_template('index.html', fixer=fixer, reperage_id=rep.id if rep else None)
    finally: session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        reperage.statut = 'soumis'
        session.commit()
        success = send_to_docugen(reperage.to_dict())
        return jsonify({'status': 'success', 'bridge_sent': success})
    except Exception as e: return jsonify({'error': str(e)}), 500
    finally: session.close()

@app.route('/admin/reperage/<int:id>')
def admin_reperage_detail(id):
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        t = json.loads(reperage.territoire_data) if reperage.territoire_data else {}
        e = json.loads(reperage.episode_data) if reperage.episode_data else {}
        fixer = session.get(Fixer, reperage.fixer_id) if reperage.fixer_id else None
        return render_template('admin_reperage_detail.html', reperage=reperage, territoire=t, episode=e, gardiens=reperage.gardiens, lieux=reperage.lieux, medias=reperage.medias, fixer=fixer)
    finally: session.close()

# Route API pour que le bouton "Modifier" puisse sauvegarder
@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage_api(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if 'region' in data: rep.region = data['region']
        if 'pays' in data: rep.pays = data['pays']
        session.commit()
        return jsonify({'status': 'ok'})
    finally: session.close()

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
