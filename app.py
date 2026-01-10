# DOC-OS VERSION : V.52 SUPRÊME
import os, json, secrets, requests, re, io, zipfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, abort, send_file
from flask_cors import CORS
from sqlalchemy import or_, text
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

app = Flask(__name__)
CORS(app)

# CONFIGURATION
raw_db_url = os.environ.get('DATABASE_URL')
DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1) if raw_db_url and raw_db_url.startswith('postgres://') else (raw_db_url or 'sqlite:///reperage.db')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
engine = init_db(DB_URL)

@app.template_filter('linkify')
def linkify_text(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

# ROUTES
@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    try:
        reps = session.query(Reperage).order_by(Reperage.created_at.desc()).all()
        serialized = []
        for r in reps:
            f = session.query(Fixer).get(r.fixer_id)
            unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
            last = session.query(Message).filter_by(reperage_id=r.id).order_by(Message.created_at.desc()).first()
            d = r.to_dict(); d['unread_count'] = unread; d['last_sender'] = last.auteur_nom if (last and unread > 0) else None
            serialized.append({'reperage': d, 'fixer': f.to_dict() if f else None})
        stats = {'total': len(reps), 'brouillons': len([x for x in reps if x.statut == 'brouillon']), 'soumis': len([x for x in reps if x.statut == 'soumis']), 'valides': len([x for x in reps if x.statut == 'validé'])}
        return render_template('admin_dashboard.html', reperages=serialized, stats=stats, fixers=session.query(Fixer).all(), pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])
    finally: session.close()

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_v52(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404
        if request.method == 'GET': return jsonify(rep.to_dict())
        
        data = request.json
        if 'progression' in data: rep.progression_pourcent = data['progression']
        for f in ['fixer_nom', 'pays', 'region', 'statut']:
            if f in data: setattr(rep, f, data[f])
            
        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'particularite_data' in data: rep.particularite_data = json.dumps(data['particularite_data'])
        if 'fete_data' in data: rep.fete_data = json.dumps(data['fete_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])

        if 'gardiens' in data:
            for g_data in data['gardiens']:
                obj = session.query(Gardien).filter_by(reperage_id=id, ordre=g_data.get('ordre')).first() or Gardien(reperage_id=id, ordre=g_data.get('ordre'))
                for k, v in g_data.items(): 
                    if hasattr(obj, k): setattr(obj, k, v)
                session.add(obj)
        if 'lieux' in data:
            for l_data in data['lieux']:
                obj = session.query(Lieu).filter_by(reperage_id=id, numero_lieu=l_data.get('numero_lieu')).first() or Lieu(reperage_id=id, numero_lieu=l_data.get('numero_lieu'))
                for k, v in l_data.items():
                    if hasattr(obj, k): setattr(obj, k, v)
                session.add(obj)
        session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally: session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def api_submit_v52(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        rep.statut = 'soumis'
        session.commit()
        if DOCUGEN_URL:
            requests.post(DOCUGEN_URL, json=rep.to_dict(), headers={"X-Bridge-Token": BRIDGE_TOKEN}, timeout=10)
        return jsonify({'status': 'success'})
    finally: session.close()

@app.route('/formulaire/<token>')
def route_form_v52(token):
    session = get_session(engine); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    f = session.get(Fixer, rep.fixer_id)
    f_data = {'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region, 'reperage_id': rep.id, 'nom': f.nom if f else '', 'prenom': f.prenom if f else '', 'langue_default': f.langue_preferee if f else 'FR'}
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=f_data)

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def handle_chat_v52(id):
    session = get_session(engine)
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.created_at.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json
    m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify(m.to_dict()), 201

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
