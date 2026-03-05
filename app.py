# DOC-OS VERSION : V.71.0 SUPRÊME MISSION CONTROL
# ÉTAT : STABLE - FIXED FILENAME FOR SUBSTANCE VIEW

import os, json, secrets, requests, io, zipfile, shutil, re
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

# --- FILTRE LINKIFY ---
@app.template_filter('linkify')
def linkify_filter(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, r'<a href="\1" target="_blank">\1</a>', text)

# --- NAVIGATION ---
@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_db(); query = session.query(Reperage)
    reps = query.order_by(Reperage.id.desc()).all(); serialized = []
    for r in reps:
        f = session.get(Fixer, r.fixer_id)
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        serialized.append({'reperage': r.to_dict(), 'fixer': f.to_dict() if f else None, 'unread_count': unread})
    stats = {'total': len(reps), 'brouillons': session.query(Reperage).filter_by(statut='brouillon').count(), 'soumis': session.query(Reperage).filter_by(statut='soumis').count(), 'valides': session.query(Reperage).filter_by(statut='validé').count()}
    return render_template('admin_dashboard.html', reperages=serialized, stats=stats, fixers=session.query(Fixer).all(), pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])

# --- FICHE DE SUBSTANCE (SOUDURE V.71.0) ---
@app.route('/admin/reperage/<int:id>')
def admin_view_reperage(id):
    """SOUDURE V.71.0 : Utilisation du nom de fichier exact et des réservoirs."""
    session = get_db()
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    fixer = session.get(Fixer, rep.fixer_id)
    
    # Pack Reservoir 1 : Territoire
    territoire = {
        "villes": rep.villes, "population": rep.population, "langues": rep.langues,
        "climat": rep.climat, "histoire": rep.histoire, "acces": rep.acces, "hebergement": rep.hebergement
    }
    
    # Pack Reservoir 2 : Particularités
    particularites = { "contraintes": rep.contraintes, "notes_production": rep.notes }
    
    # Pack Reservoir 3 : Épisode
    episode = { "arc_narratif": rep.arc, "moments_cles": rep.moments, "sensibles": rep.sensibles, "budget_local": rep.budget }
    
    # Pack Reservoir 4 : Fête
    fete = {
        "nom": rep.fete_nom, "date": rep.fete_date, "gps_lat": rep.fete_gps_lat, "gps_long": rep.fete_gps_long,
        "origines": rep.fete_origines, "visuel": rep.fete_visuel, "deroulement": rep.fete_deroulement, "responsable": rep.fete_responsable
    }

    return render_template('admin_reperage_detail.html', # NOM CORRIGÉ ICI
                           reperage=rep, fixer=fixer, 
                           territoire=territoire, particularites=particularites, 
                           episode=episode, fete=fete)

# --- BRIDGE IA (FUSÉE) ---
@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    session = get_db(); rep = session.get(Reperage, id)
    if not rep: abort(404)
    rep.statut = 'soumis'; session.commit()
    if os.environ.get('DOCUGEN_API_URL'):
        try: requests.post(os.environ.get('DOCUGEN_API_URL'), json=rep.to_dict(), headers={"X-Bridge-Token": os.environ.get('BRIDGE_SECRET_TOKEN')}, timeout=30)
        except: pass
    return jsonify({'status': 'success'})

# --- IMPORT JSON ---
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
    except Exception as e: return jsonify({'error': str(e)}), 500

# --- SYNC ENGINE ---
@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_engine(id):
    session = get_db(); rep = session.get(Reperage, id)
    if not rep: abort(404)
    if request.method == 'GET': return jsonify(rep.to_dict())
    if rep.statut != 'brouillon': abort(403)
    data = request.json
    for k, v in data.items():
        if hasattr(rep, k) and k not in ['id', 'token']:
            if k == 'age': setattr(rep, k, int(v) if (v and str(v).isdigit()) else None)
            else: setattr(rep, k, v)
    session.commit(); return jsonify({'status': 'success'})

# --- MÉDIAS & CHAT ---
@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_chat(id):
    session = get_db()
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json; m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify({'status': 'success'}), 201

# --- CRÉATION MANUELLE ---
@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_rep():
    session = get_db(); data = request.json
    try:
        f_id = int(data.get('fixer_id')) if data.get('fixer_id') else None
        fixer = session.get(Fixer, f_id) if f_id else None
        new_rep = Reperage(token=secrets.token_urlsafe(16), region=data.get('region'), pays=data.get('pays'), fixer_id=f_id, fixer_nom=f"{fixer.prenom} {fixer.nom}" if fixer else "Inconnu", image_region=data.get('image_region'), notes_admin=data.get('notes_admin'), statut='brouillon')
        session.add(new_rep); session.commit()
        return jsonify({'status': 'success'})
    except Exception as e: return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000)); app.run(host='0.0.0.0', port=port)
