import os, json, secrets, requests, io, re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from PIL import Image
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

# =================================================================
# 1. INITIALISATION
# =================================================================
app = Flask(__name__)
CORS(app)

# Configuration Railway / Volumes
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db_url = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db').replace('postgres://', 'postgresql://')
engine = init_db(db_url)

# --- FILTRES & UTILITAIRES ---
def linkify_text(text):
    if not text: return text
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

app.jinja_env.filters['linkify'] = linkify_text

def send_to_docugen(reperage_dict):
    """Envoie vers Docu-Gen IA via le Bridge"""
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
        statut_f = request.args.get('statut')
        if statut_f: query = query.filter(Reperage.statut == statut_f)
        pays_f = request.args.get('pays')
        if pays_f: query = query.filter(Reperage.pays == pays_f)
        
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

# =================================================================
# 3. ROUTES FORMULAIRE DISTANT (ACTION 1.1 : INJECTION TOTALE)
# =================================================================

@app.route('/formulaire/<token>')
def formulaire_reperage(token):
    """Action 1.1 : Charge l'intégralité du dossier pour le correspondant"""
    session = get_session(engine)
    try:
        rep = session.query(Reperage).filter_by(token=token).first()
        if not rep: return "Lien invalide", 404
        
        fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        
        # On prépare le paquet complet de données pour index.html
        fixer_data = {
            'region': rep.region,
            'pays': rep.pays,
            'image_region': rep.image_region,
            'prenom': fixer.prenom if fixer else '',
            'nom': fixer.nom if fixer else '',
            'email': fixer.email if fixer else '',
            'telephone': fixer.telephone if fixer else '',
            'langue_preferee': fixer.langue_preferee if fixer else 'FR',
            # On passe les données JSON décodées pour que le JS les distribue
            'territoire': json.loads(rep.territoire_data) if rep.territoire_data else {},
            'episode': json.loads(rep.episode_data) if rep.episode_data else {},
            'gardiens': [g.to_dict() for g in rep.gardiens],
            'lieux': [l.to_dict() for l in rep.lieux]
        }
        
        return render_template('index.html', 
                             REPERAGE_ID=rep.id, 
                             FIXER_DATA=fixer_data, 
                             langue_default=fixer_data['langue_preferee'])
    finally: session.close()

# =================================================================
# 4. API DE SAUVEGARDE ET CHAT (ACTION 1.6 : SAUVEGARDE INTEGRALE)
# =================================================================

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage_api(id):
    """Action 1.6 : Reçoit et range chaque donnée dans la bonne table"""
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': 'Dossier introuvable'}), 404

        # 1. Sauvegarde des blocs JSON principaux
        if 'territoire_data' in data:
            rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data:
            rep.episode_data = json.dumps(data['episode_data'])
        
        # 2. Mise à jour ou Création des Gardiens (G1, G2, G3)
        if 'gardiens' in data:
            for g_data in data['gardiens']:
                # On cherche si le gardien existe déjà pour ce repérage et cet ordre
                g_obj = session.query(Gardien).filter_by(reperage_id=id, ordre=g_data.get('ordre')).first()
                if not g_obj:
                    g_obj = Gardien(reperage_id=id, ordre=g_data.get('ordre'))
                    session.add(g_obj)
                
                g_obj.nom = g_data.get('nom')
                g_obj.fonction = g_data.get('fonction')
                g_obj.savoir_transmis = g_data.get('savoir_transmis')
                g_obj.histoire_personnelle = g_data.get('histoire_personnelle')
                g_obj.evaluation_cinegenie = g_data.get('evaluation_cinegenie')

        # 3. Mise à jour ou Création des Lieux (L1, L2, L3)
        if 'lieux' in data:
            for l_data in data['lieux']:
                l_obj = session.query(Lieu).filter_by(reperage_id=id, numero_lieu=l_data.get('numero_lieu')).first()
                if not l_obj:
                    l_obj = Lieu(reperage_id=id, numero_lieu=l_data.get('numero_lieu'))
                    session.add(l_obj)
                
                l_obj.nom = l_data.get('nom')
                l_obj.description_visuelle = l_data.get('description_visuelle')
                l_obj.ambiance_sonore = l_data.get('ambiance_sonore')
                l_obj.cinegenie = l_data.get('cinegenie')

        session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally: session.close()

@app.route('/api/reperages/<int:reperage_id>/messages', methods=['GET', 'POST'])
def handle_messages(reperage_id):
    """Action 1.5 : Rétablissement du Chat de production"""
    session = get_session(engine)
    try:
        if request.method == 'GET':
            msgs = session.query(Message).filter_by(reperage_id=reperage_id).order_by(Message.created_at.asc()).all()
            return jsonify([m.to_dict() for m in msgs])
        
        data = request.json
        new_msg = Message(
            reperage_id=reperage_id,
            auteur_type=data.get('auteur_type', 'fixer'),
            auteur_nom=data.get('auteur_nom', 'Anonyme'),
            contenu=data.get('contenu', '')
        )
        session.add(new_msg); session.commit()
        return jsonify(new_msg.to_dict()), 201
    finally: session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_final_ia(id):
    """Envoi définitif vers Docu-Gen IA"""
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        rep.statut = 'soumis'
        session.commit()
        success = send_to_docugen(rep.to_dict())
        return jsonify({'status': 'success', 'bridge_sent': success})
    finally: session.close()

# =================================================================
# 5. SERVEUR & UPLOADS
# =================================================================

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
