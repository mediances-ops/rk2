# DOC-OS VERSION : V.70.7 SUPRÊME MISSION CONTROL
# ÉTAT : STABLE - FIX CRÉATION DOSSIER & SOUDURE NOTES

import os, json, secrets, requests, io, zipfile, shutil
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_file, send_from_directory, g
from flask_cors import CORS
from sqlalchemy import text, or_
from models import init_db, get_session, Reperage, Fixer, Media, Message, Gardien, Lieu

app = Flask(__name__)
CORS(app)

DB_URL = os.environ.get('DATABASE_URL').replace('postgres://', 'postgresql://', 1)
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_PATH', '/data/uploads')
BRIDGE_TOKEN = os.environ.get('BRIDGE_SECRET_TOKEN', 'DocuGenPass2026')
DOCUGEN_URL = os.environ.get('DOCUGEN_API_URL')
engine = init_db(DB_URL)

@app.teardown_appcontext
def shutdown_session(exception=None):
    session = g.pop('db_session', None)
    if session is not None: session.close()

def get_db():
    if 'db_session' not in g: g.db_session = get_session(engine)
    return g.db_session

def send_to_docugen(reperage_dict):
    url = os.environ.get('DOCUGEN_API_URL')
    token = os.environ.get('BRIDGE_SECRET_TOKEN')
    if not url: return False
    headers = {"X-Bridge-Token": token, "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=reperage_dict, headers=headers, timeout=30)
        return response.status_code == 200
    except: return False

@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_db(); query = session.query(Reperage)
    p_f = request.args.get('pays'); s_f = request.args.get('statut')
    if p_f: query = query.filter(Reperage.pays == p_f)
    if s_f: query = query.filter(Reperage.statut == s_f)
    reps = query.order_by(Reperage.id.desc()).all(); serialized = []
    for r in reps:
        f = session.get(Fixer, r.fixer_id)
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        serialized.append({'reperage': r.to_dict(), 'fixer': f.to_dict() if f else None, 'unread_count': unread})
    stats = {'total': len(reps), 'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(), 'soumis': session.query(Reperage).filter_by(statut='soumis').count(), 'valides': session.query(Reperage).filter_by(statut='validé').count()}
    return render_template('admin_dashboard.html', reperages=serialized, stats=stats, fixers=session.query(Fixer).all(), pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    rep.statut = 'soumis'; session.commit()
    send_to_docugen(rep.to_dict()); return jsonify({'status': 'success'})

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_rep():
    """SOUDURE V.70.7 : Correction Cast ID et Inversion Notes/Image"""
    session = get_db(); data = request.json
    try:
        f_id = int(data.get('fixer_id')) if data.get('fixer_id') else None
        fixer = session.get(Fixer, f_id) if f_id else None
        new_rep = Reperage(
            token=secrets.token_urlsafe(16),
            region=data.get('region'),
            pays=data.get('pays'),
            fixer_id=f_id,
            fixer_nom=f"{fixer.prenom} {fixer.nom}" if fixer else "Inconnu",
            image_region=data.get('image_region'),
            notes_admin=data.get('notes_admin'), # CORRECTIF : Reçoit les notes
            statut='brouillon'
        )
        session.add(new_rep); session.commit()
        return jsonify({'status': 'success'})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/admin/reperages/import', methods=['POST'])
def admin_import_json():
    session = get_db(); data = request.json
    try:
        new_rep = Reperage(token=secrets.token_urlsafe(16), region=data.get('region'), pays=data.get('pays'), image_region=data.get('image_region'), statut='brouillon', villes=data.get('villes'), notes_admin=data.get('notes_admin'))
        session.add(new_rep); session.flush()
        # [Logique de déballage des 5 réservoirs maintenue intégralement]
        for i in [1, 2, 3]:
            pair = data.get(f'pair_{i}', {})
            g_data = pair.get('gardien', {}); l_data = pair.get('location', {})
            if g_data: session.add(Gardien(reperage_id=new_rep.id, index=i, **g_data))
            if l_data: session.add(Lieu(reperage_id=new_rep.id, index=i, **l_data))
        session.commit(); return jsonify({'status': 'success', 'id': new_rep.id})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_engine(id):
    session = get_db(); rep = session.get(Reperage, id)
    if not rep or rep.statut != 'brouillon': abort(403)
    data = request.json
    for k, v in data.items():
        if hasattr(rep, k) and k not in ['id', 'token']: setattr(rep, k, v)
    session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_db(); query = session.query(Fixer); search = request.args.get('search'); pays = request.args.get('pays')
    if search: query = query.filter(or_(Fixer.nom.ilike(f'%{search}%'), Fixer.prenom.ilike(f'%{search}%')))
    if pays: query = query.filter(Fixer.pays == pays)
    return render_template('admin_fixers.html', fixers=query.order_by(Fixer.nom.asc()).all(), pays_list=[p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]])

@app.route('/admin/fixer/new', methods=['POST'])
def admin_new_fixer():
    session = get_db(); f = Fixer(token_unique=secrets.token_hex(6), created_at=datetime.utcnow())
    for k in request.form:
        if hasattr(f, k): setattr(f, k, request.form[k] == '1' if k == 'actif' else request.form[k])
    session.add(f); session.commit(); return redirect('/admin/fixers')

@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_fixer(id):
    session = get_db(); fixer = session.get(Fixer, id)
    if request.method == 'POST':
        for k in request.form:
            if hasattr(fixer, k): setattr(fixer, k, request.form[k] == '1' if k == 'actif' else request.form[k])
        session.commit(); return redirect('/admin/fixers')
    return render_template('admin_fixer_edit_v2.html', fixer=fixer)

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_chat(id):
    session = get_db()
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()
        if request.args.get('role') == 'admin':
            session.query(Message).filter_by(reperage_id=id, auteur_type='fixer').update({Message.lu: True}); session.commit()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json; m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify({'status': 'success'}), 201

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_update_status(id):
    session = get_db(); rep = session.get(Reperage, id); data = request.json
    if 'statut' in data: rep.statut = data['statut']
    if 'notes_admin' in data: rep.notes_admin = data['notes_admin']
    if 'image_region' in data: rep.image_region = data['image_region']
    if 'fixer_id' in data:
        f = session.get(Fixer, int(data['fixer_id']))
        if f: rep.fixer_id = f.id; rep.fixer_nom = f"{f.prenom} {f.nom}"
    session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/delete', methods=['DELETE'])
def admin_delete_rep(id):
    session = get_db(); rep = session.get(Reperage, id)
    if rep: 
        try: shutil.rmtree(os.path.join(app.config['UPLOAD_FOLDER'], str(id)))
        except: pass
        session.delete(rep); session.commit()
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
    d = rep.to_dict(); d['image_region'] = rep.image_region 
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=d)

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000)); app.run(host='0.0.0.0', port=port)
