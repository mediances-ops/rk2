import os, json, secrets, requests, io, re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from PIL import Image
from slugify import slugify # Nécessaire pour les liens fixers

# Import des modèles
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

# =================================================================
# 1. INITIALISATION DE L'APP (IMPÉRATIF EN HAUT)
# =================================================================
app = Flask(__name__)
CORS(app)

# Configuration dossiers uploads (Railway compatible)
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Base de données
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
    """Bridge vers Docu-Gen IA"""
    url = os.environ.get('DOCUGEN_API_URL')
    token = os.environ.get('BRIDGE_SECRET_TOKEN')
    if not url: return False
    headers = {"X-Bridge-Token": token, "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=reperage_dict, headers=headers, timeout=15)
        return response.status_code == 200
    except: return False

# =================================================================
# 2. ROUTES ADMINISTRATION (DASHBOARD & FILTRES)
# =================================================================

@app.route('/')
def index_root():
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        # --- FILTRES ---
        query = session.query(Reperage)
        statut_f = request.args.get('statut')
        if statut_f: query = query.filter(Reperage.statut == statut_f)
        pays_f = request.args.get('pays')
        if pays_f: query = query.filter(Reperage.pays == pays_f)
        
        reperages_raw = query.order_by(Reperage.created_at.desc()).all()
        fixers_raw = session.query(Fixer).all()
        
        # --- STATS RÉELLES ---
        stats = {
            'total': session.query(Reperage).count(),
            'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(),
            'soumis': session.query(Reperage).filter_by(statut='soumis').count(),
            'valides': session.query(Reperage).filter_by(statut='validé').count()
        }

        # --- SÉRIALISATION (Anti-Apostrophe) ---
        reps_serialized = []
        for r in reperages_raw:
            f_obj = next((f for f in fixers_raw if f.id == r.fixer_id), None)
            d = r.to_dict()
            d['created_at_display'] = r.created_at.strftime('%d/%m/%Y') if r.created_at else '-'
            reps_serialized.append({
                'reperage': d,
                'fixer': f_obj.to_dict() if f_obj else None
            })

        pays_list = [p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]]
        return render_template('admin_dashboard.html', 
                             reperages=reps_serialized, 
                             fixers=[f.to_dict() for f in fixers_raw], 
                             stats=stats, 
                             pays_list=pays_list)
    finally: session.close()

# =================================================================
# 3. GESTION DES FIXERS (RESTAURATION INTÉGRALE)
# =================================================================

@app.route('/admin/fixers')
def admin_fixers():
    session = get_session(engine)
    try:
        fixers = session.query(Fixer).order_by(Fixer.nom.asc()).all()
        return render_template('admin_fixers.html', fixers=fixers)
    finally: session.close()

@app.route('/admin/fixer/new', methods=['GET', 'POST'])
def admin_create_fixer():
    if request.method == 'GET':
        return render_template('admin_fixer_edit.html', fixer=None)
    
    session = get_session(engine)
    try:
        prenom, nom = request.form.get('prenom'), request.form.get('nom')
        token = secrets.token_urlsafe(6)[:8]
        fixer = Fixer(
            prenom=prenom, nom=nom, email=request.form.get('email'),
            telephone=request.form.get('telephone'), pays=request.form.get('pays'),
            token_unique=token, lien_personnel=f"/fixer/{slugify(prenom+'-'+nom)}-{token}", actif=True
        )
        session.add(fixer); session.commit()
        return redirect('/admin/fixers')
    finally: session.close()

@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_fixer(id):
    session = get_session(engine)
    try:
        fixer = session.get(Fixer, id)
        if request.method == 'POST':
            fixer.prenom, fixer.nom = request.form.get('prenom'), request.form.get('nom')
            fixer.email, fixer.telephone = request.form.get('email'), request.form.get('telephone')
            fixer.pays = request.form.get('pays')
            session.commit(); return redirect('/admin/fixers')
        return render_template('admin_fixer_edit.html', fixer=fixer)
    finally: session.close()

# =================================================================
# 4. FORMULAIRE DISTANT (HARMONISATION 3x3 FORCÉE)
# =================================================================

@app.route('/formulaire/<token>')
def formulaire_reperage(token):
    session = get_session(engine)
    try:
        rep = session.query(Reperage).filter_by(token=token).first()
        if not rep: return "Lien invalide", 404
        
        fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        
        # --- HARMONISATION : On remplit chaque tiroir vide ---
        g_list = []
        for i in range(1, 4):
            g_obj = next((g for g in rep.gardiens if g.ordre == i), None)
            g_list.append(clean_dict(g_obj.to_dict()) if g_obj else {'ordre': i, 'nom': '', 'prenom': '', 'fonction': '', 'savoir_transmis': '', 'histoire_personnelle': '', 'evaluation_cinegenie': ''})

        l_list = []
        for i in range(1, 4):
            l_obj = next((l for l in rep.lieux if l.numero_lieu == i), None)
            l_list.append(clean_dict(l_obj.to_dict()) if l_obj else {'numero_lieu': i, 'nom': '', 'type_environnement': '', 'description_visuelle': '', 'cinegenie': '', 'axes_camera': '', 'securite': '', 'accessibilite': ''})

        fixer_data = {
            'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region,
            'prenom': fixer.prenom if fixer else '', 'nom': fixer.nom if fixer else '',
            'territoire': clean_dict(json.loads(rep.territoire_data)) if rep.territoire_data else {},
            'episode': clean_dict(json.loads(rep.episode_data)) if rep.episode_data else {},
            'gardiens': g_list, 'lieux': l_list
        }
        return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=fixer_data)
    finally: session.close()

# =================================================================
# 5. API CRUD (CRÉATION, SAUVEGARDE, SUPPRESSION)
# =================================================================

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_reperage():
    """Rétablit la création avec image et token"""
    session = get_session(engine)
    try:
        data = request.json
        new_rep = Reperage(
            token=secrets.token_urlsafe(16), region=data.get('region'),
            pays=data.get('pays'), fixer_id=data.get('fixer_id'),
            fixer_nom=data.get('fixer_nom'), image_region=data.get('image_region'),
            statut='brouillon', territoire_data="{}", episode_data="{}"
        )
        session.add(new_rep); session.commit()
        return jsonify({'status': 'success', 'id': new_rep.id})
    finally: session.close()

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage_api(id):
    """Sauvegarde intégrale pour Dashboard et Formulaire Distant"""
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': 'Dossier introuvable'}), 404

        # Mise à jour des champs racine et notes
        for key in ['region', 'pays', 'statut', 'notes_admin', 'image_region', 'fixer_id']:
            if key in data: setattr(rep, key, data[key])

        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
        # Mise à jour profonde Gardiens
        if 'gardiens' in data:
            for g_data in data['gardiens']:
                g_obj = session.query(Gardien).filter_by(reperage_id=id, ordre=g_data.get('ordre')).first()
                if not g_obj:
                    g_obj = Gardien(reperage_id=id, ordre=g_data.get('ordre'))
                    session.add(g_obj)
                for k, v in g_data.items():
                    if hasattr(g_obj, k): setattr(g_obj, k, v)

        # Mise à jour profonde Lieux
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
        session.rollback(); return jsonify({'error': str(e)}), 500
    finally: session.close()

@app.route('/admin/reperage/<int:id>/supprimer', methods=['POST'])
def delete_reperage(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if rep: session.delete(rep); session.commit()
        return redirect('/admin')
    finally: session.close()

# =================================================================
# 6. BRIDGE & TECHNIQUES
# =================================================================

@app.route('/admin/reperage/<int:id>')
def admin_reperage_detail(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        t = json.loads(rep.territoire_data) if rep.territoire_data else {}
        e = json.loads(rep.episode_data) if rep.episode_data else {}
        fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        return render_template('admin_reperage_detail.html', reperage=rep, territoire=t, episode=e, gardiens=rep.gardiens, lieux=rep.lieux, medias=rep.medias, fixer=fixer)
    finally: session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_final_ia(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        rep.statut = 'soumis'; session.commit()
        success = send_to_docugen(rep.to_dict())
        return jsonify({'status': 'success', 'bridge_sent': success})
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

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
