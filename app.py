import os, json, secrets, requests, io, re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image

# Import des modèles (Assure-toi que models.py est celui que je t'ai donné avec to_dict complet)
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db_url = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db').replace('postgres://', 'postgresql://')
engine = init_db(db_url)

# --- FONCTION BRIDGE IA ---
def send_to_docugen(reperage_dict):
    url = os.environ.get('DOCUGEN_API_URL')
    token = os.environ.get('BRIDGE_SECRET_TOKEN')
    if not url: return False
    headers = {"X-Bridge-Token": token, "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=reperage_dict, headers=headers, timeout=15)
        return response.status_code == 200
    except: return False

# --- ROUTES ADMIN ---

@app.route('/')
def index_root():
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        reps_raw = session.query(Reperage).order_by(Reperage.created_at.desc()).all()
        fixers_raw = session.query(Fixer).all()
        
        # Stats
        stats = {
            'total': session.query(Reperage).count(),
            'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(),
            'soumis': session.query(Reperage).filter_by(statut='soumis').count(),
            'valides': session.query(Reperage).filter_by(statut='validé').count()
        }

        # Sérialisation pour le JS (Apostrophes safe)
        reps_serialized = []
        for r in reps_raw:
            f_obj = next((f for f in fixers_raw if f.id == r.fixer_id), None)
            reps_serialized.append({
                'reperage': r.to_dict(),
                'fixer': f_obj.to_dict() if f_obj else None
            })

        return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=[f.to_dict() for f in fixers_raw], stats=stats)
    finally: session.close()

@app.route('/admin/fixers')
def admin_fixers():
    session = get_session(engine)
    try:
        fixers = session.query(Fixer).all()
        return render_template('admin_fixers.html', fixers=fixers)
    finally: session.close()

# --- ROUTES API CRUD ---

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_reperage():
    session = get_session(engine)
    try:
        data = request.json
        new_rep = Reperage(
            token=secrets.token_urlsafe(16),
            region=data.get('region'),
            pays=data.get('pays'),
            fixer_id=data.get('fixer_id'),
            image_region=data.get('image_region'), # RESTAURATION IMAGE
            statut='brouillon'
        )
        session.add(new_rep)
        session.commit()
        return jsonify({'status': 'success', 'id': new_rep.id})
    finally: session.close()

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        for key in ['region', 'pays', 'statut', 'notes_admin', 'image_region']:
            if key in data: setattr(rep, key, data[key])
        session.commit()
        return jsonify({'status': 'ok'})
    finally: session.close()

@app.route('/admin/reperage/<int:id>/supprimer', methods=['POST'])
def delete_reperage(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        session.delete(rep)
        session.commit()
        return redirect('/admin')
    finally: session.close()

# --- FORMULAIRE DISTANT ---
@app.route('/formulaire/<token>')
def formulaire_token(token):
    session = get_session(engine)
    try:
        rep = session.query(Reperage).filter_by(token=token).first()
        if not rep: return "Lien invalide", 404
        return render_template('index.html', reperage_id=rep.id)
    finally: session.close()

@app.route('/fixer/<path:fixer_slug>')
def fixer_form(fixer_slug):
    token = fixer_slug[-8:]
    session = get_session(engine)
    try:
        fixer = session.query(Fixer).filter_by(token_unique=token).first()
        if not fixer: return "Correspondant inconnu", 404
        return render_template('index.html', fixer_id=fixer.id, fixer_nom=f"{fixer.prenom} {fixer.nom}")
    finally: session.close()

# --- BRIDGE & PDF ---
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

@app.route('/admin/reperage/<int:id>/pdf')
def generate_pdf(id):
    # Logique PDF Reportlab simplifiée pour l'exemple
    return f"Génération PDF pour ID {id} en cours..."

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
