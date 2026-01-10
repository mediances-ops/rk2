# DOC-OS VERSION : V.52 SUPRÊME RADICAL
import os, json, secrets, requests, io, zipfile
from flask import Flask, request, jsonify, render_template, redirect, abort, send_file, send_from_directory
from flask_cors import CORS
from sqlalchemy import text
from models import init_db, get_session, Reperage, Fixer, Media, Message

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

# MIGRATION VOLANTE RADICALE (Ajoute toutes les colonnes manquantes dans PostgreSQL)
with engine.connect() as conn:
    try:
        # Cette boucle parcourt toutes les colonnes définies dans Reperage et les force en base
        from models import Reperage as R
        for column in R.__table__.columns:
            try:
                conn.execute(text(f"ALTER TABLE reperages ADD COLUMN IF NOT EXISTS {column.name} {column.type}"))
            except: pass
        conn.commit()
        print("🛠️ DATABASE: Sync Radical V.52 OK")
    except Exception as e: print(f"ℹ️ Migration info: {e}")

# API SYNC RADICALE
@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_radical(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if not rep: return jsonify({'error': '404'}), 404
        if request.method == 'GET': return jsonify(rep.to_dict())
        
        data = request.json
        # MAPPAGE DIRECT COLONNE PAR COLONNE
        for key, value in data.items():
            if hasattr(rep, key):
                setattr(rep, key, value)
        
        session.commit()
        return jsonify({'status': 'success', 'progression': rep.progression_pourcent})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally: session.close()

# GESTION ADMIN
@app.route('/')
def index_root(): return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    reps = session.query(Reperage).order_by(Reperage.id.desc()).all()
    serialized = []
    for r in reps:
        f = session.query(Fixer).get(r.fixer_id)
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        d = r.to_dict(); d['unread_count'] = unread
        serialized.append({'reperage': d, 'fixer': f.to_dict() if f else None})
    stats = {'total': len(reps), 'brouillons': len([x for x in reps if x.statut == 'brouillon']), 'soumis': len([x for x in reps if x.statut == 'soumis']), 'valides': len([x for x in reps if x.statut == 'validé'])}
    return render_template('admin_dashboard.html', reperages=serialized, stats=stats, fixers=session.query(Fixer).all(), pays_list=[])

@app.route('/formulaire/<token>')
def route_form_dist(token):
    session = get_session(engine); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=rep.to_dict())

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def handle_chat(id):
    session = get_session(engine)
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.id.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json
    m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify(m.to_dict()), 201

@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
def api_medias(id):
    session = get_session(engine)
    if request.method == 'GET': return jsonify([m.to_dict() for m in session.query(Media).filter_by(reperage_id=id).all()])
    file = request.files['file']; filename = secrets.token_hex(8) + "_" + file.filename
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id)); os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, chemin_fichier=f"{id}/{filename}", type='photo')
    session.add(m); session.commit(); return jsonify(m.to_dict())

@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename): return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)), filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
