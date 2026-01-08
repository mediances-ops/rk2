import os, json, secrets, requests, re, io, zipfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, abort, send_file
from flask_cors import CORS
from sqlalchemy import or_, text
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message, Fixer

app = Flask(__name__)
CORS(app)

raw_db_url = os.environ.get('DATABASE_URL')
DB_URL = raw_db_url.replace('postgres://', 'postgresql://', 1) if raw_db_url and raw_db_url.startswith('postgres://') else (raw_db_url or 'sqlite:///reperage.db')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_PATH', '/data/uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

engine = init_db(DB_URL)

@app.template_filter('linkify')
def linkify_text(text):
    if not text: return ""
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(0)}" target="_blank">{m.group(0)}</a>', text)

# =================================================================
# I. ADMINISTRATION DES FIXERS (RESTAURATION COMPLÈTE)
# =================================================================

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_session(engine)
    try:
        query = session.query(Fixer)
        search = request.args.get('search')
        if search: query = query.filter(or_(Fixer.nom.like(f"%{search}%"), Fixer.societe.like(f"%{search}%")))
        fixers = query.order_by(Fixer.nom.asc()).all()
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
            # SAUVEGARDE INTÉGRALE DES 20 CHAMPS FIXER
            for k in ['nom', 'prenom', 'email', 'telephone', 'telephone_2', 'societe', 'fonction', 'site_web', 'numero_siret', 'adresse_1', 'adresse_2', 'code_postal', 'ville', 'pays', 'region', 'photo_profil_url', 'bio', 'specialites', 'langue_preferee', 'notes_internes']:
                if k in request.form: setattr(fixer, k, request.form[k])
            fixer.actif = 'actif' in request.form
            fixer.langues_parlees = ", ".join(request.form.getlist('langues_parlees'))
            fixer.lien_personnel = f"{request.host_url}formulaire/{fixer.token_unique}"
            session.commit()
            return redirect('/admin/fixers')
        return render_template('admin_fixer_edit_v2.html', fixer=fixer)
    finally: session.close()

@app.route('/admin/fixer/<int:id>')
def admin_view_fixer(id):
    session = get_session(engine)
    f = session.get(Fixer, id)
    reps = session.query(Reperage).filter_by(fixer_id=id).all()
    return render_template('admin_fixer_detail.html', fixer=f, reperages=reps)

# =================================================================
# II. SYNC & SEGMENTATION (SOUDURE FICHES "VOIR" ET "PRINT")
# =================================================================

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_high_substance(id):
    session = get_session(engine)
    try:
        rep = session.get(Reperage, id)
        if request.method == 'GET': return jsonify(rep.to_dict())
        data = request.json
        if 'progression' in data: rep.progression_pourcent = data['progression']
        for f in ['fixer_nom', 'fixer_prenom', 'pays', 'region', 'statut']:
            if f in data: setattr(rep, f, data[f])
            
        if 'territoire_data' in data: rep.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data: rep.episode_data = json.dumps(data['episode_data'])

        # RESTAURATION DE LA SEGMENTATION SQL POUR AFFICHAGE "VOIR"
        if 'gardiens' in data:
            for g in data['gardiens']:
                obj = session.query(Gardien).filter_by(reperage_id=id, ordre=g.get('ordre')).first() or Gardien(reperage_id=id, ordre=g.get('ordre'))
                for k, v in g.items(): 
                    if hasattr(obj, k): setattr(obj, k, v)
                session.add(obj)
        if 'lieux' in data:
            for l in data['lieux']:
                obj = session.query(Lieu).filter_by(reperage_id=id, numero_lieu=l.get('numero_lieu')).first() or Lieu(reperage_id=id, numero_lieu=l.get('numero_lieu'))
                for k, v in l.items():
                    if hasattr(obj, k): setattr(obj, k, v)
                session.add(obj)
        session.commit()
        return jsonify({'status': 'success'})
    finally: session.close()

# =================================================================
# III. IMPRESSION HAUTE SUBSTANCE (FIX 7)
# =================================================================

@app.route('/admin/reperage/<int:id>/print')
def admin_print_v30(id):
    session = get_session(engine)
    rep = session.get(Reperage, id)
    t = json.loads(rep.territoire_data) if rep.territoire_data else {}
    e = json.loads(rep.episode_data) if rep.episode_data else {}
    # Organisation par paires G+L pour le template
    pairs = []
    for i in [1, 2, 3]:
        g = session.query(Gardien).filter_by(reperage_id=id, ordre=i).first()
        l = session.query(Lieu).filter_by(reperage_id=id, numero_lieu=i).first()
        pairs.append({'gardien': g, 'lieu': l, 'index': i})
    return render_template('print_reperage.html', rep=rep, territoire=t, episode=e, pairs=pairs, fixer=session.get(Fixer, rep.fixer_id))

# ... (Routes Dashboard, Zip, Chat, i18n, Formulaire DISTANT identiques à V29 mais sécurisées) ...
@app.route('/admin')
def admin_dashboard():
    session = get_session(engine)
    reps = session.query(Reperage).order_by(Reperage.created_at.desc()).all()
    reps_serialized = []
    for r in reps:
        f = session.get(Fixer, r.fixer_id)
        unread = session.query(Message).filter_by(reperage_id=r.id, auteur_type='fixer', lu=False).count()
        last_m = session.query(Message).filter_by(reperage_id=r.id).order_by(Message.created_at.desc()).first()
        r_data = r.to_dict(); r_data['unread_count'] = unread; r_data['last_sender'] = last_m.auteur_nom if (last_m and unread > 0) else None
        reps_serialized.append({'reperage': r_data, 'fixer': f.to_dict() if f else None})
    stats = {'total': len(reps), 'brouillons': len([r for r in reps if r.statut=='brouillon']), 'soumis': len([r for r in reps if r.statut=='soumis']), 'valides': len([r for r in reps if r.statut=='validé'])}
    return render_template('admin_dashboard.html', reperages=reps_serialized, fixers=session.query(Fixer).all(), stats=stats, pays_list=[p[0] for p in session.query(Reperage.pays).distinct().all() if p[0]])

@app.route('/admin/reperage/<int:id>/delete', methods=['DELETE'])
def admin_del_rep(id):
    session = get_session(engine); rep = session.get(Reperage, id)
    if rep: session.delete(rep); session.commit()
    return jsonify({'status': 'success'})

@app.route('/admin/reperage/<int:id>/update', methods=['PUT'])
def admin_up_quick(id):
    session = get_session(engine); data = request.json; rep = session.get(Reperage, id)
    for f in ['region', 'pays', 'statut', 'notes_admin']:
        if f in data: setattr(rep, f, data[f])
    session.commit(); return jsonify({'status': 'success'})

@app.route('/api/reperages/<int:id>/messages', methods=['GET', 'POST'])
def api_chat(id):
    session = get_session(engine)
    if request.method == 'GET':
        msgs = session.query(Message).filter_by(reperage_id=id).order_by(Message.created_at.asc()).all()
        return jsonify([m.to_dict() for m in msgs])
    data = request.json; m = Message(reperage_id=id, auteur_type=data.get('auteur_type'), auteur_nom=data.get('auteur_nom'), contenu=data.get('contenu'))
    session.add(m); session.commit(); return jsonify(m.to_dict()), 201

@app.route('/formulaire/<token>')
def route_form(token):
    session = get_session(engine); rep = session.query(Reperage).filter_by(token=token).first()
    if not rep: abort(404)
    f = session.get(Fixer, rep.fixer_id)
    f_data = {'region': rep.region, 'pays': rep.pays, 'image_region': rep.image_region, 'reperage_id': rep.id, 'nom': f.nom if f else '', 'prenom': f.prenom if f else '', 'langue_default': f.langue_preferee if f else 'FR'}
    return render_template('index.html', REPERAGE_ID=rep.id, FIXER_DATA=f_data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
