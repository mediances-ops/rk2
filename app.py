import os, json, secrets, requests, io, re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from PIL import Image
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

# =================================================================
# 1. INITIALISATION DE L'APP (IMPÉRATIF EN HAUT)
# =================================================================
app = Flask(__name__)
CORS(app)

# Configuration dossiers uploads
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configuration Base de données
database_url = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

engine = init_db(database_url)

# --- UTILITAIRES ---
def linkify_text(text):
    if not text: return text
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)
app.jinja_env.filters['linkify'] = linkify_text

def clean_dict(d):
    """Remplace tous les None par des chaînes vides pour forcer l'affichage dans app.js"""
    return {k: (v if v is not None else "") for k, v in d.items()}

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
# 2. ROUTES ADMINISTRATION (DASHBOARD)
# =================================================================

@app.route('/')
def index_root():
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        query = session.query(Reperage)
        s_f = request.args.get('statut')
        if s_f: query = query.filter(Reperage.statut == s_f)
        p_f = request.args.get('pays')
        if p_f: query = query.filter(Reperage.pays == p_f)
        
        reperages_raw = query.order_by(Reperage.created_at.desc()).all()
        fixers_raw = session.query(Fixer).all()
        
        stats = {
            'total': session.query(Reperage).count(),
            'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(),
            'soumis': session.query(Reperage).filter_by(statut='soumis').count(),
            'valides': session.query(Reperage).filter_by(statut='validé').count()
        }

        reps_serialized = []
        for r in reperages_raw:
            f_obj = next((f for f in fixers_raw if f.id == r.fixer_id), None)
            d = r.to_dict()
            d['created_at_display'] = r.created_at.strftime('%d/%m/%Y') if r.created_at else '-'
            d['created_time_display'] = r.created_at.strftime('%H:%M') if r.created_at else ''
            reps_serialized.append({'reperage': d, 'fixer': f_obj.to_dict() if f_obj else None})

        pays_list = [p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]]
        return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=[f.to_dict() for f in fixers_raw], stats=stats, pays_list=pays_list)
    finally: session.close()

# =================================================================
# 3. FORMULAIRE DISTANT (HARMONISATION TOTALE 3x3)
# =================================================================

@app.route('/formulaire/<token>')
def formulaire_reperage(token):
    session = get_session(engine)
    try:
        rep = session.query(Reperage).filter_by(token=token).first()
        if not rep: return "Lien invalide", 404
        
        fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        
        # --- GARDIENS : STRUCTURE HARMONISÉE ---
        g_list = []
        for i in range(1, 4):
            g_obj = next((g for g in rep.gardiens if g.ordre == i), None)
            if g_obj:
                g_list.append(clean_dict(g_obj.to_dict()))
            else:
                g_list.append({
                    'ordre': i, 'nom': '', 'prenom': '', 'age': '', 'genre': '',
                    'fonction': '', 'savoir_transmis': '', 'adresse': '', 'telephone': '',
                    'email': '', 'histoire_personnelle': '', 'evaluation_cinegenie': '', 'langues_parlees': ''
                })

        # --- LIEUX : STRUCTURE HARMONISÉE (INDISPENSABLE POUR APP.JS) ---
        l_list = []
        for i in range(1, 4):
            l_obj = next((l for l in rep.lieux if l.numero_lieu == i), None)
            if l_obj:
                l_list.append(clean_dict(l_obj.to_dict()))
            else:
                l_list.append({
                    'numero_lieu': i, 'nom': '', 'type_environnement': '', 'description_visuelle': '',
                    'elements_symboliques': '', 'points_vue_remarquables': '', 'cinegenie': '',
                    'axes_camera': '', 'moments_favorables': '', 'ambiance_sonore': '',
                    'adequation_narration': '', 'accessibilite': '', 'securite': '',
                    'electricite': '', 'espace_equipe': '', 'protection_meteo': '',
                    'contraintes_meteo': '', 'autorisations_necessaires': '',
                    'latitude': '', 'longitude': ''
                })

        fixer_data = {
            'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region,
            'prenom': fixer.prenom if fixer else '', 'nom': fixer.nom if fixer else '',
            'email': fixer.email if fixer else '', 'telephone': fixer.telephone if fixer else '',
            'langue_preferee': fixer.langue_preferee if fixer else 'FR',
            'territoire': clean_dict(json.loads(rep.territoire_data)) if rep.territoire_data else {},
            'episode': clean_dict(json.loads(rep.episode_data)) if rep.episode_data else {},
            'gardiens': g_list, 'lieux': l_list
        }
        
        return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=fixer_data, langue_default=fixer_data['langue_preferee'])
    finally: session.close()

# =================================================================
# 4. API SAUVEGARDE & CHAT
# =================================================================

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage_api(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': 'Dossier introuvable'}), 404

        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
        if 'gardiens' in data:
            for g_data in data['gardiens']:
                g_obj = session.query(Gardien).filter_by(reperage_id=id, ordre=g_data.get('ordre')).first()
                if not g_obj:
                    g_obj = Gardien(reperage_id=id, ordre=g_data.get('ordre'))
                    session.add(g_obj)
                for k, v in g_data.items():
                    if hasattr(g_obj, k): setattr(g_obj, k, v)

        if 'lieux' in data:
            for l_data in data['lieux']:
                l_obj = session.query(Lieu).filter_by(reperage_id=id, numero_lieu=l_data.get('numero_lieu')).first()
                if not l_obj:
                    l_obj = Lieu(reperage_id=id, numero_lieu=l_data.get('numero_lieu'))
                    session.add(l_obj)
                for k, v in l_data.items():
                    if hasattr(l_obj, k): setattr(l_obj, k, v)

        session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally: session.close()

@app.route('/api/reperages/<int:reperage_id>/messages', methods=['GET', 'POST'])
def handle_messages(reperage_id):
    session = get_session(engine)
    try:
        if request.method == 'GET':
            msgs = session.query(Message).filter_by(reperage_id=reperage_id).order_by(Message.created_at.asc()).all()
            return jsonify([m.to_dict() for m in msgs])
        data = request.json
        new_msg = Message(reperage_id=reperage_id, auteur_type=data.get('auteur_type', 'fixer'), auteur_nom=data.get('auteur_nom', 'Anonyme'), contenu=data.get('contenu', ''))
        session.add(new_msg); session.commit()
        return jsonify(new_msg.to_dict()), 201
    finally: session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_final_ia(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        rep.statut = 'soumis'
        session.commit()
        success = send_to_docugen(rep.to_dict())
        return jsonify({'status': 'success', 'bridge_sent': success})
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

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
