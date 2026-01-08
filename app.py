import os, json, secrets, requests, re, io
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, abort, send_file
from flask_cors import CORS
from sqlalchemy import or_, text
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION RAILWAY ---
raw_db_url = os.environ.get('DATABASE_URL')
if raw_db_url:
    DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1) if raw_db_url.startswith('postgres://') else raw_db_url
else:
    DB_URL = 'sqlite:///reperage.db'

app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_PATH', '/data/uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

engine = init_db(DB_URL)

# Migration auto progression
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE reperages ADD COLUMN IF NOT EXISTS progression_pourcent INTEGER DEFAULT 0"))
        conn.commit()
    except Exception: pass

@app.template_filter('linkify')
def linkify_text(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

# =================================================================
# I. NAVIGATION & DASHBOARD (FIX 404 RACINE)
# =================================================================

@app.route('/')
def index_root():
    return redirect('/admin')

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
            unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
            last_m = session.query(Message).filter_by(reperage_id=r.id).order_by(Message.created_at.desc()).first()
            r_data = r.to_dict()
            r_data['unread_count'] = unread
            r_data['last_sender'] = last_m.auteur_nom if (last_m and unread > 0) else None
            r_data['prog_pourcent'] = r.progression_pourcent or 0
            reps_serialized.append({'reperage': r_data, 'fixer': f.to_dict() if f else None})
        return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=fixers, stats=stats)
    finally: session.close()

# =================================================================
# II. GESTION DES FIXERS (FIX 404 & ENREGISTREMENT)
# =================================================================

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_session(engine)
    try:
        fixers = session.query(Fixer).order_by(Fixer.nom.asc()).all()
        pays_list = [p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]]
        return render_template('admin_fixers.html', fixers=fixers, pays_list=pays_list)
    finally: session.close()

@app.route('/admin/fixer/new', methods=['GET', 'POST'])
@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_fixer(id=None):
    session = get_session(engine)
    try:
        fixer = session.get(Fixer, id) if id else None
        if request.method == 'POST':
            if not fixer:
                fixer = Fixer(token_unique=secrets.token_hex(4), created_at=datetime.now())
                session.add(fixer)
            
            # Sauvegarde exhaustive de tous les champs du formulaire
            for k in ['nom', 'prenom', 'email', 'telephone', 'telephone_2', 'societe', 'fonction', 
                      'site_web', 'numero_siret', 'adresse_1', 'adresse_2', 'code_postal', 
                      'ville', 'pays', 'region', 'photo_profil_url', 'bio', 'specialites', 
                      'langue_preferee', 'notes_internes']:
                if k in request.form: setattr(fixer, k, request.form[k])
            
            fixer.actif = 'actif' in request.form
            fixer.langues_parlees = ", ".join(request.form.getlist('langues_parlees'))
            fixer.lien_personnel = f"{request.host_url}formulaire/{fixer.token_unique}"
            
            session.commit()
            return redirect('/admin/fixers')
        return render_template('admin_fixer_edit_v2.html', fixer=fixer)
    finally: session.close()

@app.route('/admin/fixer/<int:id>')
def admin_fixer_view(id):
    session = get_session(engine)
    try:
        fixer = session.get(Fixer, id)
        if not fixer: abort(404)
        reps = session.query(Reperage).filter_by(fixer_id=id).all()
        return render_template('admin_fixer_detail.html', fixer=fixer, reperages=reps)
    finally: session.close()

# =================================================================
# III. GESTION DES REPÉRAGES & IMPRESSION
# =================================================================

@app.route('/admin/reperage/<int:id>')
def admin_view_reperage(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: abort(404)
        t = json.loads(rep.territoire_data) if rep.territoire_data else {}
        e = json.loads(rep.episode_data) if rep.episode_data else {}
        fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        return render_template('admin_reperage_detail.html', reperage=rep, territoire=t, episode=e, fixer=fixer)
    finally: session.close()

@app.route('/admin/reperage/<int:id>/print')
def admin_print_reperage(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: abort(404)
        t = json.loads(rep.territoire_data) if rep.territoire_data else {}
        e = json.loads(rep.episode_data) if rep.episode_data else {}
        fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        # Template Print Haute Substance (@media print)
        return render_template('print_reperage.html', rep=rep, territoire=t, episode=e, fixer=fixer)
    finally: session.close()

# =================================================================
# IV. API CORE (SOUDURE TOTALE JS)
# =================================================================

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_rep_sync(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404
        
        if request.method == 'GET':
            return jsonify(rep.to_dict())
        
        data = request.json
        # Synchronisation forcée du pourcentage (JS vers Base)
        if 'progression' in data:
            rep.progression_pourcent = data['progression']
        
        for f in ['fixer_nom', 'fixer_prenom', 'pays', 'region', 'statut']:
            if f in data: setattr(rep, f, data[f])
            
        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])
        
        session.commit()
        return jsonify({'status': 'success', 'synced': rep.progression_pourcent})
    finally: session.close()

@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
def api_rep_medias(id):
    session = get_session(engine)
    if request.method == 'GET':
        ms = session.query(Media).filter_by(reperage_id=id).all()
        return jsonify([m.to_dict() for m in ms])
    
    file = request.files['file']
    filename = secrets.token_hex(8) + "_" + secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, chemin_fichier=f"{id}/{filename}", type='photo')
    session.add(m); session.commit()
    return jsonify(m.to_dict())

@app.route('/api/i18n/<lang>')
def api_get_translations(lang):
    try:
        with open(os.path.join(app.root_path, 'translations', 'i18n.json'), 'r', encoding='utf-8') as f:
            return jsonify(json.load(f).get(lang, {}))
    except: return jsonify({}), 404

# =================================================================
# V. FORMULAIRE DISTANT & CHAT
# =================================================================

@app.route('/formulaire/<token>')
def route_external_form(token):
    session = get_session(engine)
    try:
        rep = session.query(Reperage).filter_by(token=token).first()
        if not rep: abort(404)
        f = session.get(Fixer, rep.fixer_id)
        f_data = {
            'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region, 
            'reperage_id': rep.id, 'nom': f.nom if f else '', 'prenom': f.prenom if f else '', 
            'langue_default': f.langue_preferee if f else 'FR'
        }
        return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=f_data)
    finally: session.close()

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_rep_messages(id):
    session = get_session(engine)
    try:
        if request.method == 'GET':
            msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.created_at.asc()).all()
            return jsonify([m.to_dict() for m in msgs])
        data = request.json
        m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
        session.add(m); session.commit()
        return jsonify(m.to_dict()), 201
    finally: session.close()

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_static_uploads(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_quick_update(id):
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        for f in ['region', 'pays', 'statut', 'notes_admin']:
            if f in data: setattr(rep, f, data[f])
        session.commit()
        return jsonify({'status': 'success'})
    finally: session.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
