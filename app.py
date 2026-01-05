import os, json, secrets, requests, io, re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from sqlalchemy import or_
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
database_url = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db').replace('postgres://', 'postgresql://')
engine = init_db(database_url)

# =================================================================
# 2. FONCTIONS SYSTÈME & BRIDGE
# =================================================================

def send_to_docugen(reperage_dict):
    """Envoie le dossier complet au cerveau IA Docu-Gen"""
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
# 3. ROUTES ADMINISTRATION (DASHBOARD & FILTRES)
# =================================================================

@app.route('/')
def index_root():
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        # --- LOGIQUE DES FILTRES ---
        query = session.query(Reperage)
        
        statut_f = request.args.get('statut')
        if statut_f: query = query.filter(Reperage.statut == statut_f)
        
        pays_f = request.args.get('pays')
        if pays_f: query = query.filter(Reperage.pays == pays_f)
        
        search_f = request.args.get('search')
        if search_f: query = query.filter(or_(Reperage.region.like(f'%{search_f}%'), Reperage.fixer_nom.like(f'%{search_f}%')))

        reperages_raw = query.order_by(Reperage.created_at.desc()).all()
        fixers_raw = session.query(Fixer).all()

        # --- CALCUL DES STATS ---
        stats = {
            'total': session.query(Reperage).count(),
            'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(),
            'soumis': session.query(Reperage).filter_by(statut='soumis').count(),
            'valides': session.query(Reperage).filter_by(statut='validé').count()
        }

        # --- SÉRIALISATION POUR LE JS (Anti-Apostrophe) ---
        reps_serialized = []
        for r in reperages_raw:
            f_obj = next((f for f in fixers_raw if f.id == r.fixer_id), None)
            reps_serialized.append({
                'reperage': r.to_dict(),
                'fixer': f_obj.to_dict() if f_obj else None
            })

        pays_list = [p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]]

        return render_template('admin_dashboard.html', 
                             reperages=reps_serialized, 
                             fixers=[f.to_dict() for f in fixers_raw], 
                             stats=stats,
                             pays_list=pays_list)
    finally: session.close()

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_session(engine)
    try:
        fixers = session.query(Fixer).all()
        return render_template('admin_fixers.html', fixers=fixers)
    finally: session.close()

# =================================================================
# 4. ROUTES API CRUD (CRÉATION, MODIF, SUPPRESSION)
# =================================================================

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
            image_region=data.get('image_region'),
            statut='brouillon'
        )
        session.add(new_rep)
        session.commit()
        return jsonify({'status': 'success', 'id': new_rep.id})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally: session.close()

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': 'Non trouvé'}), 404
        
        for key in ['region', 'pays', 'statut', 'notes_admin', 'image_region']:
            if key in data: setattr(rep, key, data[key])
            
        session.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally: session.close()

@app.route('/admin/reperage/<int:id>/supprimer', methods=['POST'])
def delete_reperage(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if rep: 
            session.delete(rep)
            session.commit()
        return redirect('/admin')
    finally: session.close()

# =================================================================
# 5. VUES DÉTAILS & PDF
# =================================================================

@app.route('/admin/reperage/<int:id>')
def admin_reperage_detail(id):
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage: return "Non trouvé", 404
        t = json.loads(reperage.territoire_data) if reperage.territoire_data else {}
        e = json.loads(reperage.episode_data) if reperage.episode_data else {}
        fixer = session.get(Fixer, reperage.fixer_id) if reperage.fixer_id else None
        return render_template('admin_reperage_detail.html', 
                             reperage=reperage, territoire=t, episode=e, 
                             gardiens=reperage.gardiens, lieux=reperage.lieux, 
                             medias=reperage.medias, fixer=fixer)
    finally: session.close()

@app.route('/admin/reperage/<int:id>/pdf')
def admin_reperage_pdf(id):
    """Vue optimisée pour l'impression (utilisera window.print() côté client)"""
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        t = json.loads(reperage.territoire_data) if reperage.territoire_data else {}
        e = json.loads(reperage.episode_data) if reperage.episode_data else {}
        return render_template('admin_reperage_detail.html', reperage=reperage, territoire=t, episode=e, print_mode=True)
    finally: session.close()

# =================================================================
# 6. ROUTES CORRESPONDANTS & FORMULAIRES
# =================================================================

@app.route('/fixer/<path:fixer_slug>')
def fixer_form(fixer_slug):
    token = fixer_slug[-8:]
    session = get_session(engine)
    try:
        fixer = session.query(Fixer).filter_by(token_unique=token, actif=True).first()
        if not fixer: return "Lien invalide", 404
        rep = session.query(Reperage).filter_by(fixer_id=fixer.id, statut='brouillon').first()
        return render_template('index.html', fixer=fixer, reperage_id=rep.id if rep else None)
    finally: session.close()

@app.route('/formulaire/<token>')
def formulaire_reperage(token):
    session = get_session(engine)
    try:
        reperage = session.query(Reperage).filter_by(token=token).first()
        if not reperage: return "Repérage non trouvé", 404
        return render_template('index.html', reperage_id=reperage.id)
    finally: session.close()

# =================================================================
# 7. TECHNIQUES (MESSAGES & UPLOADS)
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
