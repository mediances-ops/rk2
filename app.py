import os, json, secrets, requests, io, zipfile, shutil, re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_file, send_from_directory, g, make_response
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

def nocache(view):
    def no_cache_view(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    no_cache_view.__name__ = view.__name__
    return no_cache_view

@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_db(); query = session.query(Reperage)
    reps = query.order_by(Reperage.id.desc()).all(); serialized = []
    for r in reps:
        f = session.get(Fixer, r.fixer_id) if r.fixer_id else None
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        serialized.append({'reperage': r.to_dict(), 'fixer': f.to_dict() if f else None, 'unread_count': unread})
    return render_template('admin_dashboard.html', reperages=serialized, stats={'total': len(reps), 'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(), 'soumis': session.query(Reperage).filter_by(statut='soumis').count(), 'valides': session.query(Reperage).filter_by(statut='validé').count()}, fixers=session.query(Fixer).all(), pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
@nocache
def api_sync_engine(id):
    session = get_db(); rep = session.get(Reperage, id)
    if not rep: abort(404)
    if request.method == 'GET': return jsonify(rep.to_dict())
    
    data = request.json
    # RAIL TERRITOIRE & FÊTE
    fields = ['villes', 'population', 'langues', 'climat', 'histoire', 'traditions', 'acces', 'hebergement', 'contraintes', 'arc', 'moments', 'sensibles', 'budget', 'notes', 'fete_nom', 'fete_date', 'fete_gps_lat', 'fete_gps_long', 'fete_origines', 'fete_visuel', 'fete_deroulement', 'fete_responsable', 'image_region']
    for f in fields:
        if f in data: setattr(rep, f, str(data[f]).strip())
    
    # RAIL PAIRES
    for i in [1, 2, 3]:
        g_obj = session.query(Gardien).filter_by(reperage_id=rep.id, index=i).first() or Gardien(reperage_id=rep.id, index=i)
        if g_obj not in session: session.add(g_obj)
        for f in ['nom_prenom', 'age', 'fonction', 'savoir', 'histoire', 'psychologie', 'evaluation', 'langues', 'contact', 'intermediaire']:
            val = data.get(f"gardien{i}_{f}")
            if val is not None:
                if f == 'age': setattr(g_obj, f, int(val) if str(val).isdigit() else None)
                else: setattr(g_obj, f, str(val).strip())
        
        l_obj = session.query(Lieu).filter_by(reperage_id=rep.id, index=i).first() or Lieu(reperage_id=rep.id, index=i)
        if l_obj not in session: session.add(l_obj)
        for f in ['nom', 'type', 'gps_lat', 'gps_long', 'description', 'cinegenie', 'axes', 'points_vue', 'moments', 'son', 'acces', 'securite', 'elec', 'espace', 'meteo', 'permis']:
            val = data.get(f"lieu{i}_{f}")
            if val is not None: setattr(l_obj, f, str(val).strip())
            
    if 'progression_pourcent' in data: rep.progression_pourcent = int(data['progression_pourcent'])
    session.commit(); return jsonify({'status': 'success'})

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def api_submit(id):
    session = get_db(); rep = session.get(Reperage, id); rep.statut = 'soumis'; session.commit()
    if DOCUGEN_URL:
        try: requests.post(DOCUGEN_URL, json=rep.to_dict(), headers={"X-Bridge-Token": BRIDGE_TOKEN}, timeout=10)
        except: pass
    return jsonify({'status': 'success'})

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    return send_from_directory(os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id))), filename)

@app.route('/formulaire/<token>')
def route_form_fixer(token):
    session = get_db(); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=rep.to_dict())

# ... [Routes Admin et Médias maintenues à 100%] ...
@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_db(); query = session.query(Fixer); search = request.args.get('search'); pays = request.args.get('pays')
    if search: query = query.filter(or_(Fixer.nom.ilike(f'%{search}%'), Fixer.prenom.ilike(f'%{search}%')))
    if pays: query = query.filter(Fixer.pays == pays)
    return render_template('admin_fixers.html', fixers=query.order_by(Fixer.nom.asc()).all(), pays_list=[p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]])

@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_fixer(id):
    session = get_db(); fixer = session.get(Fixer, id)
    if request.method == 'POST':
        for k in request.form:
            if hasattr(fixer, k): setattr(fixer, k, request.form[k] == '1' if k == 'actif' else request.form[k])
        session.commit(); return redirect('/admin/fixers')
    return render_template('admin_fixer_edit_v2.html', fixer=fixer)

@app.route('/admin/reperage/<int:id>/print')
def admin_print(id):
    session = get_db(); rep = session.get(Reperage, id); fixer = session.get(Fixer, rep.fixer_id)
    pairs = []
    for i in [1, 2, 3]:
        g = session.query(Gardien).filter_by(reperage_id=id, index=i).first()
        l = session.query(Lieu).filter_by(reperage_id=id, index=i).first()
        if g or l: pairs.append({'index': i, 'gardien': g, 'lieu': l})
    return render_template('print_reperage.html', rep=rep, fixer=fixer, pairs=pairs)

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
@nocache
def api_chat(id):
    session = get_db()
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json; m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify({'status': 'success'}), 201

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_rep():
    session = get_db(); data = request.json; f_id = int(data.get('fixer_id')) if data.get('fixer_id') else None; fixer = session.get(Fixer, f_id)
    new_rep = Reperage(token=secrets.token_urlsafe(16), region=data.get('region'), pays=data.get('pays'), fixer_id=f_id, fixer_nom=f"{fixer.prenom} {fixer.nom}" if fixer else "Inconnu", image_region=data.get('image_region'), notes_admin=data.get('notes_admin'), statut='brouillon')
    session.add(new_rep); session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/reperages/import', methods=['POST'])
def admin_import_json():
    session = get_db(); data = request.json
    try:
        new_rep = Reperage(token=secrets.token_urlsafe(16), region=data.get('region'), pays=data.get('pays'), image_region=data.get('image_region'), statut='brouillon', villes=data.get('villes'))
        session.add(new_rep); session.flush()
        for i in [1, 2, 3]:
            pair = data.get(f'pair_{i}', {})
            if pair.get('gardien'): session.add(Gardien(reperage_id=new_rep.id, index=i, **pair['gardien']))
            if pair.get('location'): session.add(Lieu(reperage_id=new_rep.id, index=i, **pair['location']))
        session.commit(); return jsonify({'status': 'success', 'id': new_rep.id})
    except: return jsonify({'error': 'Import failed'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
