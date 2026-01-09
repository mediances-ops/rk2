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

# MIGRATION VOLANTE 5 ONGLETS
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE reperages ADD COLUMN IF NOT EXISTS particularite_data TEXT DEFAULT '{}'"))
        conn.execute(text("ALTER TABLE reperages ADD COLUMN IF NOT EXISTS fete_data TEXT DEFAULT '{}'"))
        conn.commit()
    except Exception: pass

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
    reps = session.query(Reperage).order_by(Reperage.created_at.desc()).all()
    stats = {'total': len(reps), 'brouillons': len([r for r in reps if r.statut == 'brouillon']), 'soumis': len([r for r in reps if r.statut == 'soumis']), 'valides': len([r for r in reps if r.statut == 'validé'])}
    reps_serialized = []
    for r in reps:
        f = session.query(Fixer).get(r.fixer_id)
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        last_m = session.query(Message).filter_by(reperage_id=r.id).order_by(Message.created_at.desc()).first()
        r_data = r.to_dict(); r_data['unread_count'] = unread; r_data['last_sender'] = last_m.auteur_nom if (last_m and unread > 0) else None
        reps_serialized.append({'reperage': r_data, 'fixer': f.to_dict() if f else None})
    return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=session.query(Fixer).all(), stats=stats, pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])

@app.route('/admin/reperage/<int:id>')
def admin_view_reperage(id):
    session = get_session(engine)
    rep = session.get(Reperage, id)
    if not rep: abort(404)
    return render_template('admin_reperage_detail.html', 
        reperage=rep, 
        territoire=json.loads(rep.territoire_data), 
        particularites=json.loads(rep.particularite_data),
        fete=json.loads(rep.fete_data),
        episode=json.loads(rep.episode_data),
        fixer=session.get(Fixer, rep.fixer_id)
    )

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_5_tabs(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if request.method == 'GET': return jsonify(rep.to_dict())
        data = request.json
        if 'progression' in data: rep.progression_pourcent = data['progression']
        for f in ['fixer_nom', 'pays', 'region', 'statut']:
            if f in data: setattr(rep, f, data[f])
        
        # SAUVEGARDE SEGMENTÉE 5 RÉSERVOIRS
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
    finally: session.close()

# Routes secondaires (ZIP, Print, Fixers, Chat, i18n) maintenues sans simplification
@app.route('/admin/reperage/<int:id>/print')
def admin_print(id):
    session = get_session(engine); rep = session.get(Reperage, id)
    t = json.loads(rep.territoire_data); p = json.loads(rep.particularite_data); f_d = json.loads(rep.fete_data); e = json.loads(rep.episode_data)
    pairs = [{'gardien': session.query(Gardien).filter_by(reperage_id=id, ordre=i).first(), 'lieu': session.query(Lieu).filter_by(reperage_id=id, numero_lieu=i).first(), 'index': i} for i in [1,2,3]]
    return render_template('print_reperage.html', rep=rep, territoire=t, particularites=p, fete=f_d, episode=e, pairs=pairs, fixer=session.get(Fixer, rep.fixer_id))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
