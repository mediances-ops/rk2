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

# Configuration dossiers uploads (Compatible Railway Volumes)
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 # 500 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'thumbnails'), exist_ok=True)

# Configuration Base de données (PostgreSQL Railway ou SQLite Local)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

engine = init_db(database_url)

# =================================================================
# 2. FONCTIONS SYSTÈME & FILTRES JINJA
# =================================================================

def send_to_docugen(reperage_dict):
    """Envoie le dossier complet au cerveau IA Docu-Gen via le Bridge"""
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

        # --- SÉRIALISATION POUR LE JS (Anti-Apostrophe & Anti-Crash Date) ---
        reps_serialized = []
        for r in reperages_raw:
            f_obj = next((f for f in fixers_raw if f.id == r.fixer_id), None)
            d = r.to_dict()
            # On pré-formate les dates pour éviter l'erreur strftime dans le HTML
            d['created_at_display'] = r.created_at.strftime('%d/%m/%Y') if r.created_at else '-'
            d['created_time_display'] = r.created_at.strftime('%H:%M') if r.created_at else ''
            
            reps_serialized.append({
                'reperage': d,
                'fixer': f_obj.to_dict() if f_obj else None
            })

        # Liste des pays pour le menu déroulant
        pays_list = [p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]]

        return render_template('admin_dashboard.html', 
                             reperages=reps_serialized, 
                             fixers=[f.to_dict() for f in fixers_raw], 
                             stats=stats,
                             pays_list=pays_list)
    finally: session.close()

# =================================================================
# ACTION 1 : ROUTES DE CONSULTATION (ADMIN & DISTANT)
# =================================================================

@app.route('/admin/reperage/<int:id>')
def admin_reperage_detail(id):
    """Vue détaillée d'un repérage pour l'administrateur"""
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage:
            return "Repérage non trouvé", 404
        
        # Extraction sécurisée des données JSON
        try:
            territoire = json.loads(reperage.territoire_data) if reperage.territoire_data else {}
            episode = json.loads(reperage.episode_data) if reperage.episode_data else {}
        except Exception:
            territoire, episode = {}, {}

        # Récupération du fixer associé
        fixer = session.get(Fixer, reperage.fixer_id) if reperage.fixer_id else None
        
        return render_template('admin_reperage_detail.html',
                             reperage=reperage,
                             territoire=territoire,
                             episode=episode,
                             gardiens=reperage.gardiens,
                             lieux=reperage.lieux,
                             medias=reperage.medias,
                             fixer=fixer)
    finally:
        session.close()

@app.route('/formulaire/<token>')
def formulaire_reperage(token):
    """Accès au formulaire pour le correspondant (via token unique)"""
    session = get_session(engine)
    try:
        reperage = session.query(Reperage).filter_by(token=token).first()
        if not reperage:
            return "Lien de repérage invalide ou expiré", 404
        
        return render_template('index.html', 
                             reperage_id=reperage.id,
                             region=reperage.region,
                             pays=reperage.pays,
                             image_region=reperage.image_region)
    finally:
        session.close()

# =================================================================
# 4. API DE GESTION (CRÉATION, MODIFICATION, BRIDGE)
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
            fixer_nom=data.get('fixer_nom'),
            image_region=data.get('image_region'),
            statut='brouillon',
            territoire_data="{}", episode_data="{}"
        )
        session.add(new_rep)
        session.commit()
        return jsonify({'status': 'success', 'id': new_rep.id})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally: session.close()

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def update_reperage_api(id):
    """Mise à jour d'un dossier (utilisé par le bouton Modifier et le formulaire distant)"""
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': 'Non trouvé'}), 404
        
        # Liste des champs autorisés à la mise à jour
        for key in ['region', 'pays', 'statut', 'notes_admin', 'image_region', 'fixer_id', 'territoire_data', 'episode_data']:
            if key in data:
                # Si c'est un dictionnaire (JSON), on le convertit en texte
                if isinstance(data[key], dict):
                    setattr(rep, key, json.dumps(data[key]))
                else:
                    setattr(rep, key, data[key])
            
        session.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally: session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_to_ia(id):
    """Envoie le dossier vers Docu-Gen via la passerelle"""
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        rep.statut = 'soumis'
        session.commit()
        
        # Transmission au Bridge
        success = send_to_docugen(rep.to_dict())
        
        return jsonify({
            'status': 'success',
            'bridge_sent': success
        })
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
# 5. TECHNIQUES (UPLOADS & SERVE)
# =================================================================

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
