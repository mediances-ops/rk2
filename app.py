# DOC-OS VERSION : V.62 SUPRÊME MISSION CONTROL
import os, json, secrets, requests, io, zipfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_file, send_from_directory
from flask_cors import CORS
from sqlalchemy import text, or_
from models import init_db, get_session, Reperage, Fixer, Media, Message, Gardien, Lieu

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION RAILWAY ---
raw_db_url = os.environ.get('DATABASE_URL')
DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1) if raw_db_url and raw_db_url.startswith('postgres://') else (raw_db_url or 'sqlite:///reperage.db')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
engine = init_db(DB_URL)

# SOUDURE POSTGRES : MIGRATION AUTOMATIQUE DES 100 COLONNES
with engine.connect() as conn:
    from models import Reperage as R
    for col in R.__table__.columns:
        try: conn.execute(text(f"ALTER TABLE reperages ADD COLUMN IF NOT EXISTS {col.name} {col.type}"))
        except: pass
    conn.commit()

@app.template_filter('linkify')
def linkify_text(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

# =================================================================
# I. ADMINISTRATION HUB (7 COMMANDES)
# =================================================================

@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        query = session.query(Reperage)
        p_filter = request.args.get('pays'); s_filter = request.args.get('statut')
        if p_filter: query = query.filter(Reperage.pays == p_filter)
        if s_filter: query = query.filter(Reperage.statut == s_filter)
        
        reps = query.order_by(Reperage.id.desc()).all(); serialized = []
        for r in reps:
            f = session.query(Fixer).get(r.fixer_id)
            unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
            last_m = session.query(Message).filter_by(reperage_id=r.id).order_by(Message.id.desc()).first()
            d = r.to_dict(); d['unread_count'] = unread; d['last_sender'] = last_m.auteur_nom if (last_m and unread > 0) else None
            serialized.append({'reperage': d, 'fixer': f.to_dict() if f else None})
            
        pays_list = [p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]]
        stats = {'total': session.query(Reperage).count(), 'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(), 'soumis': session.query(Reperage).filter_by(statut='soumis').count(), 'valides': session.query(Reperage).filter_by(statut='validé').count()}
        return render_template('admin_dashboard.html', reperages=serialized, stats=stats, fixers=session.query(Fixer).all(), pays_list=pays_list)
    finally: session.close()

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_session(engine); fixers = session.query(Fixer).order_by(Fixer.nom.asc()).all()
    pays_list = [p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]]
    return render_template('admin_fixers.html', fixers=fixers, pays_list=pays_list)

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_rep():
    session = get_session(engine); data = request.json
    new_rep = Reperage(token=secrets.token_urlsafe(16), region=data.get('region'), pays=data.get('pays'), fixer_id=data.get('fixer_id'), fixer_nom=data.get('fixer_nom'), notes_admin=data.get('notes_admin'), statut='brouillon')
    session.add(new_rep); session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_update_cmd(id):
    session = get_session(engine); data = request.json; rep = session.get(Reperage, id)
    if not rep: abort(404)
    for f in ['region', 'pays', 'statut', 'notes_admin']:
        if f in data: setattr(rep, f, data[f])
    session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/delete', methods=['DELETE'])
def admin_delete_cmd(id):
    session = get_session(engine); rep = session.get(Reperage, id)
    if rep: session.delete(rep); session.commit()
    return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/print')
def admin_print_cmd(id):
    session = get_session(engine); rep = session.get(Reperage, id); fixer = session.query(Fixer).get(rep.fixer_id)
    return render_template('print_reperage.html', rep=rep, fixer=fixer)

@app.route('/admin/reperage/<int:id>/photos')
def admin_zip_cmd(id):
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
    if not os.path.exists(path): abort(404)
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for root, _, files in os.walk(path):
            for file in files: zf.write(os.path.join(root, file), file)
    memory_file.seek(0); return send_file(memory_file, download_name=f"Photos_Rep_{id}.zip", as_attachment=True)

# =================================================================
# II. API SOUDURE & CHAT (RADICAL FLAT-DATA)
# =================================================================

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_radical(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404
        if request.method == 'GET': return jsonify(rep.to_dict())
        data = request.json
        # MAPPAGE DIRECT 1:1 SUR LES 100 COLONNES
        for key, value in data.items():
            if hasattr(rep, key): setattr(rep, key, value)
        session.commit(); return jsonify({'status': 'success', 'synced_id': rep.id})
    finally: session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def api_submit_radical(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id); rep.statut = 'soumis'; session.commit()
        if DOCUGEN_URL: requests.post(DOCUGEN_URL, json=rep.to_dict(), headers={"X-Bridge-Token": BRIDGE_TOKEN}, timeout=10)
        return jsonify({'status': 'success'})
    finally: session.close()

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_chat(id):
    session = get_session(engine)
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json; m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify(m.to_dict()), 201

@app.route('/api/reperages/<int:id>/medias', methods=['POST'])
def api_medias(id):
    session = get_session(engine); file = request.files['file']; filename = secrets.token_hex(8) + "_" + file.filename; path = os.path.join(app.config['UPLOAD_FOLDER'], str(id)); os.makedirs(path, exist_ok=True); file.save(os.path.join(path, filename))
    m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, chemin_fichier=f"{id}/{filename}", type='photo'); session.add(m); session.commit(); return jsonify(m.to_dict())

@app.route('/formulaire/<token>')
def route_form_dist(token):
    session = get_session(engine); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=rep.to_dict())

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename): return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
