import os, json, secrets, requests, re, io
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

app = Flask(__name__)
CORS(app)

# CONFIGURATION ENVIRONNEMENT (PostgreSQL Railway)
DB_URL = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db').replace('postgres://', 'postgresql://')
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

engine = init_db(DB_URL)

@app.template_filter('linkify')
def linkify_text(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

# =================================================================
# I. ROUTES API (SOUDURES APP.JS)
# =================================================================

@app.route('/api/i18n/<lang>')
def get_translations(lang):
    try:
        with open('translations/i18n.json', 'r', encoding='utf-8') as f:
            all_trans = json.load(f)
        return jsonify(all_trans.get(lang, all_trans.get('FR', {})))
    except: return jsonify({'error': 'JSON not found'}), 404

@app.route('/api/reperages/<int:id>', methods=['GET'])
def get_reperage_api(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        return jsonify(rep.to_dict()) if rep else ({'error': '404'}, 404)
    finally: session.close()

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage_api(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404
        
        # Mise à jour Identité (Fixer, Pays, Région)
        for field in ['fixer_nom', 'fixer_prenom', 'fixer_email', 'fixer_telephone', 'pays', 'region', 'notes_admin', 'image_region', 'statut']:
            if field in data: setattr(rep, field, data[field])
        
        # JSON Data
        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
        # Gardiens (Profonde)
        if 'gardiens' in data:
            for g in data['gardiens']:
                obj = session.query(Gardien).filter_by(reperage_id=id, ordre=g.get('ordre')).first() or Gardien(reperage_id=id, ordre=g.get('ordre'))
                for k, v in g.items(): 
                    if hasattr(obj, k): setattr(obj, k, v)
                session.add(obj)

        # Lieux (Profonde)
        if 'lieux' in data:
            for l in data['lieux']:
                obj = session.query(Lieu).filter_by(reperage_id=id, numero_lieu=l.get('numero_lieu')).first() or Lieu(reperage_id=id, numero_lieu=l.get('numero_lieu'))
                for k, v in l.items():
                    if hasattr(obj, k): setattr(obj, k, v)
                session.add(obj)

        session.commit()
        return jsonify({'status': 'success'})
    except Exception as e: return jsonify({'error': str(e)}), 500
    finally: session.close()

@app.route('/api/reperages/<int:id>/medias', methods=['POST'])
def upload_media(id):
    if 'file' not in request.files: return "No file", 400
    file = request.files['file']
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    
    session = get_session(engine)
    try:
        m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, type='photo' if filename.lower().endswith(('.jpg','.png','.jpeg','.webp')) else 'document')
        session.add(m); session.commit()
        return jsonify(m.to_dict())
    finally: session.close()

# =================================================================
# II. GESTION ADMINISTRATIVE
# =================================================================

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
            reps_serialized.append({'reperage': r.to_dict(), 'fixer': f})
        return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=fixers, stats=stats)
    finally: session.close()

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_session(engine)
    try:
        fixers = session.query(Fixer).all()
        return render_template('admin_fixers.html', fixers=fixers)
    finally: session.close()

@app.route('/admin/fixer/new', methods=['GET', 'POST'])
@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def edit_fixer(id=None):
    session = get_session(engine)
    try:
        fixer = session.get(Fixer, id) if id else None
        if request.method == 'POST':
            if not fixer:
                fixer = Fixer(token_unique=secrets.token_hex(4), created_at=datetime.now())
                session.add(fixer)
            for k, v in request.form.items():
                if hasattr(fixer, k): setattr(fixer, k, v)
            fixer.actif = 'actif' in request.form
            fixer.langues_parlees = ", ".join(request.form.getlist('langues_parlees'))
            fixer.lien_personnel = f"{request.host_url}formulaire/{fixer.token_unique}"
            session.commit()
            return redirect(url_for('admin_fixers_list'))
        return render_template('admin_fixer_edit_v2.html', fixer=fixer)
    finally: session.close()

@app.route('/admin/reperages/create', methods=['POST'])
def create_reperage():
    session = get_session(engine)
    try:
        data = request.json
        new_rep = Reperage(
            token=secrets.token_urlsafe(16), region=data.get('region'), pays=data.get('pays'),
            fixer_id=data.get('fixer_id'), fixer_nom=data.get('fixer_nom'), image_region=data.get('image_region')
        )
        session.add(new_rep); session.commit()
        return jsonify({'id': new_rep.id})
    finally: session.close()

# =================================================================
# III. BRIDGE & FORMULAIRE DISTANT
# =================================================================

@app.route('/formulaire/<token>')
def formulaire_token(token):
    session = get_session(engine)
    try:
        rep = session.query(Reperage).filter_by(token=token).first_or_404()
        f = session.get(Fixer, rep.fixer_id)
        f_data = {
            'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region, 'reperage_id': rep.id,
            'nom': f.nom if f else '', 'prenom': f.prenom if f else '', 'email': f.email if f else '',
            'langue_default': f.langue_preferee if f else 'FR'
        }
        return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=f_data)
    finally: session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_to_docugen(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        rep.statut = 'soumis'
        session.commit()
        # Bridge IA
        url = os.environ.get('DOCUGEN_API_URL')
        token = os.environ.get('BRIDGE_SECRET_TOKEN')
        headers = {"X-Bridge-Token": token, "Content-Type": "application/json"}
        res = requests.post(url, json=rep.to_dict(), headers=headers, timeout=10)
        return jsonify({'status': 'success', 'bridge_sent': res.status_code == 200})
    except: return jsonify({'status': 'error'}), 500
    finally: session.close()

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_media(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
