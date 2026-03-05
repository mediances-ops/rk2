# DOC-OS VERSION : V.73.1 SUPRÊME MISSION CONTROL
# ENGINE : FLASK + SQLALCHEMY SCOPED SESSIONS
# ÉTAT : CRITICAL STABILITY - ZERO BRICOLAGE - ROOT FIXED

import os, json, secrets, requests, io, zipfile, shutil, re
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

engine = init_db(DB_URL)

# --- GESTIONNAIRE DE SESSION (ANTI-TIMEOUT RAILWAY) ---
@app.teardown_appcontext
def shutdown_session(exception=None):
    session = g.pop('db_session', None)
    if session is not None:
        session.close()

def get_db():
    if 'db_session' not in g:
        g.db_session = get_session(engine)
    return g.db_session

# --- FILTRES JINJA2 ---
@app.template_filter('linkify')
def linkify_filter(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, r'<a href="\1" target="_blank">\1</a>', text)

# =================================================================
# 1. NAVIGATION PRINCIPALE (PRIORITAIRE)
# =================================================================

@app.route('/')
def index_root():
    """Rétablit la redirection automatique (Fix 404)."""
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    """Tour de contrôle de la production."""
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
        f = session.get(Fixer, r.fixer_id) if r.fixer_id else None
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        # Traçabilité : unread_count à la racine pour le HTML
        serialized.append({
            'reperage': r.to_dict(), 
            'fixer': f.to_dict() if f else None,
            'unread_count': unread
        })
        
    stats = {
        'total': len(reps),
        'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(),
        'soumis': session.query(Reperage).filter_by(statut='soumis').count(),
        'valides': session.query(Reperage).filter_by(statut='validé').count()
    }
    return render_template('admin_dashboard.html', 
                           reperages=serialized, stats=stats, 
                           fixers=session.query(Fixer).all(),
                           pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])

# =================================================================
# 2. MOTEUR DE SOUDURE DÉTERMINISTE (LES 100 RAILS)
# =================================================================

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_engine(id):
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    
    if request.method == 'GET':
        return jsonify(rep.to_dict())

    if rep.statut != 'brouillon':
        return jsonify({'error': 'Dossier verrouillé'}), 403

    data = request.json
    
    # Rail A : Territoire (14 champs)
    rail_territory = ['villes', 'population', 'langues', 'climat', 'histoire', 'traditions', 
                      'acces', 'hebergement', 'contraintes', 'arc', 'moments', 'sensibles', 'budget', 'notes']
    for field in rail_territory:
        if field in data:
            setattr(rep, field, str(data[field]).strip())

    # Rail B : Festivité (8 champs)
    rail_fete = ['fete_nom', 'fete_date', 'fete_gps_lat', 'fete_gps_long', 'fete_origines', 
                 'fete_visuel', 'fete_deroulement', 'fete_responsable']
    for field in rail_fete:
        if field in data:
            setattr(rep, field, str(data[field]).strip())

    # Rail C : Gardiens et Lieux (30 + 48 champs)
    for i in [1, 2, 3]:
        # Gardien i
        g_obj = session.query(Gardien).filter_by(reperage_id=rep.id, index=i).first()
        if not g_obj: 
            g_obj = Gardien(reperage_id=rep.id, index=i)
            session.add(g_obj)
        
        g_map = ['nom_prenom', 'age', 'fonction', 'savoir', 'histoire', 'psychologie', 'evaluation', 'langues', 'contact', 'intermediaire']
        for field in g_map:
            val = data.get(f"gardien{i}_{field}")
            if val is not None:
                if field == 'age':
                    setattr(g_obj, field, int(val) if (str(val).isdigit()) else None)
                else:
                    setattr(g_obj, field, str(val).strip())

        # Lieu i
        l_obj = session.query(Lieu).filter_by(reperage_id=rep.id, index=i).first()
        if not l_obj:
            l_obj = Lieu(reperage_id=rep.id, index=i)
            session.add(l_obj)
        
        l_map = ['nom', 'type', 'gps_lat', 'gps_long', 'description', 'cinegenie', 'axes', 'points_vue', 
                 'moments', 'son', 'acces', 'securite', 'elec', 'espace', 'meteo', 'permis']
        for field in l_map:
            val = data.get(f"lieu{i}_{field}")
            if val is not None:
                setattr(l_obj, field, str(val).strip())

    if 'progression_pourcent' in data:
        rep.progression_pourcent = int(data['progression_pourcent'])

    session.commit()
    return jsonify({'status': 'success'})

# =================================================================
# 3. GESTION DES MÉDIAS (DÉSTOCKAGE PHYSIQUE)
# =================================================================

@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
def api_medias(id):
    session = get_db()
    if request.method == 'GET':
        ms = session.query(Media).filter_by(reperage_id=id).all()
        return jsonify([{'id': m.id, 'nom_fichier': m.nom_fichier, 'type': m.type} for m in ms])
    
    file = request.files['file']
    ext = os.path.splitext(file.filename)[1].lower()
    filename = secrets.token_hex(8) + "_" + file.filename
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, 
              chemin_fichier=f"{id}/{filename}", type='pdf' if ext == '.pdf' else 'photo')
    session.add(m); session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/medias/<int:media_id>', methods=['DELETE'])
def api_delete_media(media_id):
    """Suppression physique et logique du média (Fix test n°24)."""
    session = get_db()
    m = session.get(Media, media_id)
    if not m: abort(404)
    try:
        file_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], m.chemin_fichier))
        if os.path.exists(file_path): os.remove(file_path)
    except: pass
    session.delete(m); session.commit()
    return jsonify({'status': 'success'})

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    directory = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)))
    return send_from_directory(directory, filename)

# =================================================================
# 4. MODULES COMPLÉMENTAIRES (IMPORT, BRIDGE, CHAT)
# =================================================================

@app.route('/admin/reperages/import', methods=['POST'])
def admin_import_json():
    session = get_db(); data = request.json
    try:
        new_rep = Reperage(token=secrets.token_urlsafe(16), region=data.get('region'), 
                           pays=data.get('pays'), image_region=data.get('image_region'), 
                           statut='brouillon', villes=data.get('villes'))
        session.add(new_rep); session.flush()
        for i in [1, 2, 3]:
            pair = data.get(f'pair_{i}', {})
            if pair.get('gardien'): session.add(Gardien(reperage_id=new_rep.id, index=i, **pair['gardien']))
            if pair.get('location'): session.add(Lieu(reperage_id=new_rep.id, index=i, **pair['location']))
        session.commit(); return jsonify({'status': 'success', 'id': new_rep.id})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    session = get_db(); rep = session.get(Reperage, id)
    if not rep: abort(404)
    rep.statut = 'soumis'; session.commit()
    if DOCUGEN_URL:
        try: requests.post(DOCUGEN_URL, json=rep.to_dict(), headers={"X-Bridge-Token": BRIDGE_TOKEN}, timeout=30)
        except: pass
    return jsonify({'status': 'success'})

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_chat(id):
    session = get_db()
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()
        if request.args.get('role') == 'admin':
            session.query(Message).filter_by(reperage_id=id, auteur_type='fixer').update({Message.lu: True}); session.commit()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json
    m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify({'status': 'success'}), 201

# =================================================================
# 5. ADMINISTRATION (FIXERS & DETAILS)
# =================================================================

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_db(); query = session.query(Fixer); search = request.args.get('search'); pays = request.args.get('pays')
    if search: query = query.filter(or_(Fixer.nom.ilike(f'%{search}%'), Fixer.prenom.ilike(f'%{search}%')))
    if pays: query = query.filter(Fixer.pays == pays)
    return render_template('admin_fixers.html', fixers=query.order_by(Fixer.nom.asc()).all(), 
                           pays_list=[p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]])

@app.route('/admin/fixer/new', methods=['POST'])
def admin_new_fixer():
    session = get_db(); f = Fixer(token_unique=secrets.token_hex(6), created_at=datetime.utcnow())
    for k in request.form:
        if hasattr(f, k): setattr(f, k, request.form[k] == '1' if k == 'actif' else request.form[k])
    session.add(f); session.commit(); return redirect('/admin/fixers')

@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_fixer(id):
    session = get_db(); fixer = session.get(Fixer, id)
    if not fixer: abort(404)
    if request.method == 'POST':
        for k in request.form:
            if hasattr(fixer, k): setattr(fixer, k, request.form[k] == '1' if k == 'actif' else request.form[k])
        session.commit(); return redirect('/admin/fixers')
    return render_template('admin_fixer_edit_v2.html', fixer=fixer)

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_update_status(id):
    session = get_db(); rep = session.get(Reperage, id); data = request.json
    if 'statut' in data: rep.statut = data['statut']
    if 'notes_admin' in data: rep.notes_admin = data['notes_admin']
    if 'fixer_id' in data:
        f = session.get(Fixer, int(data['fixer_id']))
        if f: rep.fixer_id = f.id; rep.fixer_nom = f"{f.prenom} {f.nom}"
    session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/print')
def admin_print(id):
    session = get_db(); rep = session.get(Reperage, id); fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
    pairs = []
    for i in [1, 2, 3]:
        g_obj = session.query(Gardien).filter_by(reperage_id=id, index=i).first()
        l_obj = session.query(Lieu).filter_by(reperage_id=id, index=i).first()
        if g_obj or l_obj: pairs.append({'index': i, 'gardien': g_obj, 'lieu': l_obj})
    return render_template('print_reperage.html', rep=rep, fixer=fixer, pairs=pairs)

@app.route('/formulaire/<token>')
def route_form_fixer(token):
    session = get_db(); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=rep.to_dict())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
