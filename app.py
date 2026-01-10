# DOC-OS VERSION : V.58 SUPRÊME RADICAL
import os, json, secrets, requests, io, zipfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_file, send_from_directory
from flask_cors import CORS
from sqlalchemy import or_, text
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

# MIGRATION VOLANTE 100 COLONNES (SOUDURE POSTGRES)
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
# I. ADMINISTRATION & FILTRES (FIX 10)
# =================================================================

@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        query = session.query(Reperage)
        # SOUDURE FILTRES
        p_filter = request.args.get('pays')
        s_filter = request.args.get('statut')
        if p_filter: query = query.filter(Reperage.pays == p_filter)
        if s_filter: query = query.filter(Reperage.statut == s_filter)
        
        reps = query.order_by(Reperage.id.desc()).all()
        serialized = []
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

# ROUTE FIXER (FIX 404 NAVIGATION)
@app.route('/admin/fixers')
def admin_fixers():
    session = get_session(engine)
    fixers = session.query(Fixer).order_by(Fixer.nom.asc()).all()
    pays_list = [p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]]
    return render_template('admin_fixers.html', fixers=fixers, pays_list=pays_list)

# =================================================================
# II. MODALS & SAUVEGARDE (SOUDURE RELATIONNELLE)
# =================================================================

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_update_quick(id):
    """Soudure Modal : Informations de bases & Statut"""
    session = get_session(engine)
    try:
        data = request.json
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404
        for f in ['region', 'pays', 'statut', 'notes_admin']:
            if f in data: setattr(rep, f, data[f])
        session.commit()
        return jsonify({'status': 'success'})
    finally: session.close()

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_flat(id):
    """Moteur de Sync 100 Points (Miroir Terrain)"""
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if request.method == 'GET': return jsonify(rep.to_dict())
        data = request.json
        for key, value in data.items():
            if hasattr(rep, key): setattr(rep, key, value)
        session.commit()
        return jsonify({'status': 'success', 'progression': rep.progression_pourcent})
    except Exception as e:
        session.rollback(); return jsonify({'error': str(e)}), 500
    finally: session.close()

# =================================================================
# III. CHAT, MÉDIAS & SORTIE
# =================================================================

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_chat_handler(id):
    session = get_session(engine)
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json
    m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify(m.to_dict()), 201

@app.route('/admin/reperage/<int:id>/delete', methods=['DELETE'])
def admin_delete_rep(id):
    session = get_session(engine); rep = session.get(Reperage, id)
    if rep: session.delete(rep); session.commit()
    return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/print')
def admin_print_view(id):
    session = get_session(engine); rep = session.get(Reperage, id)
    return render_template('print_reperage.html', rep=rep, fixer=session.get(Fixer, rep.fixer_id))

@app.route('/formulaire/<token>')
def route_form_dist(token):
    session = get_session(engine); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=rep.to_dict())

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
