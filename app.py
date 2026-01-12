# DOC-OS VERSION : V.66.1 SUPRÊME MISSION CONTROL
# ENGINE : FLASK + SQLALCHEMY SCOPED SESSIONS
# ÉTAT : STABLE - CORRECTIF ROUTE 404 CRÉATION FIXER

import os, json, secrets, requests, io, zipfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_file, send_from_directory, g
from flask_cors import CORS
from sqlalchemy import text, or_
from models import init_db, get_session, Reperage, Fixer, Media, Message, Gardien, Lieu

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ENVIRONNEMENT ---
raw_db_url = os.environ.get('DATABASE_URL')
DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1) if raw_db_url and raw_db_url.startswith('postgres://') else (raw_db_url or 'sqlite:///reperage.db')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialisation de l'Engine SQL
engine = init_db(DB_URL)

# --- GESTIONNAIRE DE SESSION (ANTI-TIMEOUT RAILWAY) ---
@app.teardown_appcontext
def shutdown_session(exception=None):
    """Ferme systématiquement la connexion DB à la fin de chaque requête."""
    session = g.pop('db_session', None)
    if session is not None:
        session.close()

def get_db():
    """Fournit une session unique par requête."""
    if 'db_session' not in g:
        g.db_session = get_session(engine)
    return g.db_session

# --- NAVIGATION ADMIN ---
@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_db()
    query = session.query(Reperage)
    
    # Filtrage dynamique
    p_f = request.args.get('pays')
    s_f = request.args.get('statut')
    if p_f: query = query.filter(Reperage.pays == p_f)
    if s_f: query = query.filter(Reperage.statut == s_f)
    
    reps = query.order_by(Reperage.id.desc()).all()
    serialized = []
    
    for r in reps:
        f = session.get(Fixer, r.fixer_id)
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        serialized.append({'reperage': r.to_dict(), 'fixer': f.to_dict() if f else None, 'unread_count': unread})
        
    stats = {
        'total': session.query(Reperage).count(),
        'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(),
        'soumis': session.query(Reperage).filter_by(statut='soumis').count(),
        'valides': session.query(Reperage).filter_by(statut='validé').count()
    }
    
    return render_template('admin_dashboard.html', 
                           reperages=serialized, 
                           stats=stats, 
                           fixers=session.query(Fixer).all(), 
                           pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_db()
    fixers = session.query(Fixer).order_by(Fixer.nom.asc()).all()
    pays_list = [p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]]
    return render_template('admin_fixers.html', fixers=fixers, pays_list=pays_list)

@app.route('/admin/fixer/new', methods=['POST'])
def admin_new_fixer():
    """Route de création de correspondant (FIX DU BUG 404)"""
    session = get_db()
    f = Fixer(
        token_unique=secrets.token_hex(6), # Génération du token unique 12 caractères
        created_at=datetime.utcnow()
    )
    # Mappage des champs du formulaire vers le modèle
    for key in ['nom', 'prenom', 'email', 'telephone', 'societe', 'fonction', 'pays', 'region', 'langue_preferee']:
        if key in request.form:
            setattr(f, key, request.form[key])
    
    session.add(f)
    session.commit()
    return redirect('/admin/fixers')

@app.route('/admin/fixer/<int:id>')
def admin_view_fixer(id):
    """Consultation profil correspondant."""
    session = get_db()
    fixer = session.get(Fixer, id)
    if not fixer: abort(404)
    return render_template('admin_fixer_edit_v2.html', fixer=fixer, readonly=True)

@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_fixer(id):
    session = get_db()
    fixer = session.get(Fixer, id)
    if request.method == 'POST':
        for key in request.form:
            if hasattr(fixer, key): setattr(fixer, key, request.form[key])
        session.commit()
        return redirect('/admin/fixers')
    return render_template('admin_fixer_edit_v2.html', fixer=fixer)

# --- MOTEUR DE SYNCHRONISATION DYNAMIQUE (100 CHAMPS) ---
@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_engine(id):
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    
    if request.method == 'GET':
        return jsonify(rep.to_dict())

    # SÉCURITÉ WORKFLOW
    if rep.statut != 'brouillon':
        return jsonify({'error': 'Dossier verrouillé'}), 403

    data = request.json
    
    # 1. Territoire & Fête
    for key, value in data.items():
        if hasattr(rep, key) and not isinstance(value, (list, dict)):
            setattr(rep, key, value)
    
    # 2. Gardiens Dynamiques (Index 1-3)
    for i in [1, 2, 3]:
        g_data = {k.replace(f'gardien{i}_', ''): v for k, v in data.items() if k.startswith(f'gardien{i}_')}
        if g_data:
            g = session.query(Gardien).filter_by(reperage_id=rep.id, index=i).first()
            if not g: 
                g = Gardien(reperage_id=rep.id, index=i)
                session.add(g)
            for k, v in g_data.items():
                if hasattr(g, k): setattr(g, k, v)

    # 3. Lieux Dynamiques (Index 1-3)
    for i in [1, 2, 3]:
        l_data = {k.replace(f'lieu{i}_', ''): v for k, v in data.items() if k.startswith(f'lieu{i}_')}
        if l_data:
            l = session.query(Lieu).filter_by(reperage_id=rep.id, index=i).first()
            if not l:
                l = Lieu(reperage_id=rep.id, index=i)
                session.add(l)
            for k, v in l_data.items():
                if hasattr(l, k): setattr(l, k, v)

    session.commit()
    return jsonify({'status': 'success', 'progression': rep.progression_pourcent})

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_rep():
    """Route de lancement d'une mission de repérage."""
    session = get_db()
    data = request.json
    f_id = data.get('fixer_id')
    fixer = session.get(Fixer, f_id)
    
    new_rep = Reperage(
        token=secrets.token_urlsafe(16),
        region=data.get('region'),
        pays=data.get('pays'),
        fixer_id=f_id,
        fixer_nom=f"{fixer.prenom} {fixer.nom}" if fixer else "Inconnu",
        notes_admin=data.get('notes_admin'),
        image_region=data.get('image_region'),
        statut='brouillon'
    )
    session.add(new_rep)
    session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def api_submit_to_prod(id):
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    rep.statut = 'soumis'
    session.commit()
    if DOCUGEN_URL:
        try: requests.post(DOCUGEN_URL, json=rep.to_dict(), headers={"X-Bridge-Token": BRIDGE_TOKEN}, timeout=15)
        except: pass
    return jsonify({'status': 'success'})

# --- CHAT & MÉDIAS ---
@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_chat(id):
    session = get_db()
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()
        if request.args.get('role') == 'admin':
            session.query(Message).filter_by(reperage_id=id, auteur_type='fixer').update({Message.lu: True})
            session.commit()
        return jsonify([m.to_dict() for m in msgs])
    
    data = request.json
    m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit()
    return jsonify({'status': 'success'}), 201

@app.route('/api/reperages/<int:id>/medias', methods=['POST'])
def api_upload_media(id):
    session = get_db()
    file = request.files['file']
    filename = secrets.token_hex(8) + "_" + file.filename
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, chemin_fichier=f"{id}/{filename}", type='photo')
    session.add(m); session.commit()
    return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_update_status(id):
    session = get_db(); rep = session.get(Reperage, id); data = request.json
    if 'statut' in data: rep.statut = data['statut']
    if 'notes_admin' in data: rep.notes_admin = data['notes_admin']
    session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/delete', methods=['DELETE'])
def admin_delete_rep(id):
    session = get_db(); rep = session.get(Reperage, id)
    if rep: session.delete(rep); session.commit()
    return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/print')
def admin_print(id):
    session = get_db(); rep = session.get(Reperage, id); fixer = session.get(Fixer, rep.fixer_id)
    pairs = []
    for i in [1, 2, 3]:
        g = session.query(Gardien).filter_by(reperage_id=id, index=i).first()
        l = session.query(Lieu).filter_by(reperage_id=id, index=i).first()
        if g or l: pairs.append({'index': i, 'gardien': g, 'lieu': l})
    return render_template('print_reperage.html', rep=rep, fixer=fixer, pairs=pairs)

@app.route('/formulaire/<token>')
def route_form_fixer(token):
    session = get_db(); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=rep.to_dict())

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
