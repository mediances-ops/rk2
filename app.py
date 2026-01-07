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

# Configuration dossiers (Railway Volume /data)
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db_url = os.environ.get('DATABASE_URL', 'sqlite:///reperage.db').replace('postgres://', 'postgresql://')
engine = init_db(db_url)

# --- FILTRES JINJA ---
def linkify_text(text):
    if not text: return text
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)
app.jinja_env.filters['linkify'] = linkify_text

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
        # Gestion des filtres
        query = session.query(Reperage)
        if request.args.get('statut'): query = query.filter(Reperage.statut == request.args.get('statut'))
        if request.args.get('pays'): query = query.filter(Reperage.pays == request.args.get('pays'))
        if request.args.get('search'):
            s = request.args.get('search')
            query = query.filter(or_(Reperage.region.like(f'%{s}%'), Reperage.fixer_nom.like(f'%{s}%')))

        reperages_raw = query.order_by(Reperage.created_at.desc()).all()
        fixers_raw = session.query(Fixer).all()
        
        # Stats
        stats = {
            'total': session.query(Reperage).count(),
            'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(),
            'soumis': session.query(Reperage).filter_by(statut='soumis').count(),
            'valides': session.query(Reperage).filter_by(statut='validé').count()
        }

        # Sérialisation safe pour éviter strftime error dans le HTML
        reps_serialized = []
        for r in reperages_raw:
            f_obj = next((f for f in fixers_raw if f.id == r.fixer_id), None)
            d = r.to_dict()
            d['created_at_display'] = r.created_at.strftime('%d/%m/%Y') if r.created_at else '-'
            d['created_time_display'] = r.created_at.strftime('%H:%M') if r.created_at else ''
            reps_serialized.append({'reperage': d, 'fixer': f_obj.to_dict() if f_obj else None})

        pays_list = [p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]]
        return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=fixers_raw, stats=stats, pays_list=pays_list)
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
# 3. ROUTES FIXERS (CORRESPONDANTS)
# =================================================================

@app.route('/admin/fixers')
def admin_fixers():
    session = get_session(engine)
    try:
        fixers = session.query(Fixer).all()
        return render_template('admin_fixers.html', fixers=fixers)
    finally: session.close()

# =================================================================
# 4. API SAUVEGARDE ET CRÉATION (COMMUNIQUE AVEC LE JS)
# =================================================================

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_reperage():
    """Rétablit la route de création qui manquait (Génère le Token Vital)"""
    session = get_session(engine)
    try:
        data = request.json
        new_rep = Reperage(
            token=secrets.token_urlsafe(16), # Génération du token pour le lien distant
            region=data.get('region'),
            pays=data.get('pays'),
            fixer_id=data.get('fixer_id'),
            fixer_nom=data.get('fixer_nom'),
            image_region=data.get('image_region'),
            statut='brouillon',
            territoire_data="{}", 
            episode_data="{}"
        )
        session.add(new_rep)
        session.commit()
        return jsonify({'status': 'success', 'id': new_rep.id})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage_api(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': 'Introuvable'}), 404

        # Sauvegarde Territoire et Episode
        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
        # Sauvegarde profonde Gardiens
        if 'gardiens' in data:
            for g_data in data['gardiens']:
                g_obj = session.query(Gardien).filter_by(reperage_id=id, ordre=g_data.get('ordre')).first()
                if not g_obj:
                    g_obj = Gardien(reperage_id=id, ordre=g_data.get('ordre'))
                    session.add(g_obj)
                for k, v in g_data.items():
                    if hasattr(g_obj, k): setattr(g_obj, k, v)

        # Sauvegarde profonde Lieux
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

# =================================================================
# 5. FORMULAIRE DISTANT
# =================================================================

@app.route('/formulaire/<token>')
def formulaire_token(token):
    session = get_session(engine)
    try:
        rep = session.query(Reperage).filter_by(token=token).first()
        if not rep: return "Repérage non trouvé", 404
        fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        
        fixer_data = {
            'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region,
            'prenom': fixer.prenom if fixer else '', 'nom': fixer.nom if fixer else '',
            'territoire': json.loads(rep.territoire_data) if rep.territoire_data else {},
            'episode': json.loads(rep.episode_data) if rep.episode_data else {},
            'gardiens': [g.to_dict() for g in rep.gardiens],
            'lieux': [l.to_dict() for l in rep.lieux]
        }
        return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=fixer_data)
    finally: session.close()

@app.route('/api/reperages/<int:reperage_id>/messages', methods=['GET', 'POST'])
def handle_messages(reperage_id):
    session = get_session(engine)
    try:
        if request.method == 'GET':
            msgs = session.query(Message).filter_by(reperage_id=reperage_id).order_by(Message.created_at.asc()).all()
            return jsonify([m.to_dict() for m in msgs])
        data = request.json
        new_msg = Message(reperage_id=reperage_id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
        session.add(new_msg); session.commit(); return jsonify(new_msg.to_dict()), 201
    finally: session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': 'Non trouvé'}), 404
        rep.statut = 'soumis'
        session.commit()
        success = send_to_docugen(rep.to_dict())
        return jsonify({'status': 'success', 'bridge_sent': success})
    except Exception as e: return jsonify({'error': str(e)}), 500
    finally: session.close()

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
