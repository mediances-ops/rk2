# DOC-OS VERSION : V.70.4 SUPRÊME MISSION CONTROL
# ÉTAT : STABLE - MODULE IMPORT JSON AJOUTÉ (ZÉRO RISQUE)

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

# --- NAVIGATION & DASHBOARD ---
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

# --- MOTEUR D'IMPORTATION JSON (NOUVEAU MODULE V.70.4) ---
@app.route('/admin/reperages/import', methods=['POST'])
def admin_import_json():
    session = get_db()
    data = request.json
    if not data: return jsonify({'error': 'No data'}), 400

    try:
        # 1. Création de l'entité Maîtresse (R1 + R5)
        new_rep = Reperage(
            token=secrets.token_urlsafe(16),
            region=data.get('region', 'Imported Region'),
            pays=data.get('pays', 'Unknown'),
            image_region=data.get('image_region'),
            statut='brouillon',
            # Reservoir 1 : Territory
            villes=data.get('villes'),
            population=data.get('territory', {}).get('population'),
            langues=data.get('territory', {}).get('langues'),
            climat=data.get('territory', {}).get('climat'),
            histoire=data.get('territory', {}).get('histoire'),
            traditions=data.get('territory', {}).get('traditions'),
            acces=data.get('territory', {}).get('acces'),
            hebergement=data.get('territory', {}).get('hebergement'),
            notes=data.get('territory', {}).get('notes'),
            arc=data.get('territory', {}).get('arc'),
            moments=data.get('territory', {}).get('moments'),
            budget=data.get('territory', {}).get('budget'),
            # Reservoir 5 : Festivity
            fete_nom=data.get('festivity', {}).get('fete_nom'),
            fete_date=data.get('festivity', {}).get('fete_date'),
            fete_gps_lat=data.get('festivity', {}).get('fete_gps_lat'),
            fete_gps_long=data.get('festivity', {}).get('fete_gps_long'),
            fete_origines=data.get('festivity', {}).get('fete_origines'),
            fete_visuel=data.get('festivity', {}).get('fete_visuel'),
            fete_deroulement=data.get('festivity', {}).get('fete_deroulement'),
            fete_responsable=data.get('festivity', {}).get('fete_responsable')
        )
        session.add(new_rep)
        session.flush() # Récupère l'ID sans commiter

        # 2. Déballage des Paires (R2, R3, R4)
        for i in [1, 2, 3]:
            pair_key = f"pair_{i}"
            if pair_key in data:
                p = data[pair_key]
                # Partie Gardien
                g_data = p.get('gardien', {})
                if g_data:
                    new_g = Gardien(
                        reperage_id=new_rep.id,
                        index=i,
                        nom_prenom=g_data.get('nom_prenom'),
                        age=int(g_data.get('age')) if g_data.get('age') else None,
                        fonction=g_data.get('fonction'),
                        savoir=g_data.get('savoir'),
                        histoire=g_data.get('histoire'),
                        psychologie=g_data.get('psychologie'),
                        evaluation=g_data.get('evaluation'),
                        langues=g_data.get('langues'),
                        contact=g_data.get('contact'),
                        intermediaire=g_data.get('intermediaire')
                    )
                    session.add(new_g)
                # Partie Lieu
                l_data = p.get('location', {})
                if l_data:
                    new_l = Lieu(
                        reperage_id=new_rep.id,
                        index=i,
                        nom=l_data.get('nom'),
                        type=l_data.get('type'),
                        gps_lat=l_data.get('gps_lat'),
                        gps_long=l_data.get('gps_long'),
                        description=l_data.get('description'),
                        cinegenie=l_data.get('cinegenie'),
                        axes=l_data.get('axes'),
                        points_vue=l_data.get('points_vue'),
                        moments=l_data.get('moments'),
                        son=l_data.get('son'),
                        acces=l_data.get('acces'),
                        securite=l_data.get('securite'),
                        elec=l_data.get('elec'),
                        espace=l_data.get('espace'),
                        meteo=l_data.get('meteo'),
                        permis=l_data.get('permis')
                    )
                    session.add(new_l)

        session.commit()
        return jsonify({'status': 'success', 'id': new_rep.id})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500

# --- ROUTES EXISTANTES (SÉCURISÉES) ---
@app.route('/uploads/<int:rep_id>/<filename>')
def serve_uploads(rep_id, filename):
    directory = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], str(rep_id)))
    return send_from_directory(directory, filename)

@app.route('/api/reperages/<int:id>', methods=['GET', 'PUT'])
def api_sync_engine(id):
    session = get_db(); rep = session.get(Reperage, id)
    if not rep: abort(404)
    if request.method == 'GET': return jsonify(rep.to_dict())
    if rep.statut != 'brouillon': return jsonify({'error': 'Locked'}), 403
    data = request.json
    PROTECTED = ['token', 'id', 'fixer_id']
    for k, v in data.items():
        if hasattr(rep, k) and k not in PROTECTED and not isinstance(v, (list, dict)): setattr(rep, k, v)
    for i in [1, 2, 3]:
        g_data = {key.replace(f'gardien{i}_', ''): val for key, val in data.items() if key.startswith(f'gardien{i}_')}
        if g_data:
            g_obj = session.query(Gardien).filter_by(reperage_id=rep.id, index=i).first()
            if not g_obj: g_obj = Gardien(reperage_id=rep.id, index=i); session.add(g_obj)
            for k, v in g_data.items():
                if hasattr(g_obj, k):
                    if k == 'age': setattr(g_obj, k, int(v) if (v and str(v).isdigit()) else None)
                    else: setattr(g_obj, k, v)
        l_data = {key.replace(f'lieu{i}_', ''): val for key, val in data.items() if key.startswith(f'lieu{i}_')}
        if l_data:
            l_obj = session.query(Lieu).filter_by(reperage_id=rep.id, index=i).first()
            if not l_obj: l_obj = Lieu(reperage_id=rep.id, index=i); session.add(l_obj)
            for k, v in l_data.items():
                if hasattr(l_obj, k): setattr(l_obj, k, v)
    session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/fixer/new', methods=['POST'])
def admin_new_fixer():
    session = get_db(); f = Fixer(token_unique=secrets.token_hex(6), created_at=datetime.utcnow())
    for k in request.form:
        if hasattr(f, k):
            if k == 'actif': setattr(f, k, request.form[k] == '1')
            else: setattr(f, k, request.form[k])
    session.add(f); session.commit(); return redirect('/admin/fixers')

@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_fixer(id):
    session = get_db(); fixer = session.get(Fixer, id)
    if request.method == 'POST':
        for k in request.form:
            if hasattr(fixer, k):
                if k == 'actif': setattr(fixer, k, request.form[k] == '1')
                else: setattr(fixer, k, request.form[k])
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

@app.route('/api/reperages/<int:id>/medias', methods=['GET', 'POST'])
def api_medias(id):
    session = get_db()
    if request.method == 'GET':
        ms = session.query(Media).filter_by(reperage_id=id).all()
        return jsonify([{'id': m.id, 'nom_fichier': m.nom_fichier, 'type': m.type} for m in ms])
    file = request.files['file']; ext = os.path.splitext(file.filename)[1].lower()
    filename = secrets.token_hex(8) + "_" + file.filename
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(id)); os.makedirs(path, exist_ok=True)
    file.save(os.path.join(path, filename))
    m = Media(reperage_id=id, nom_original=file.filename, nom_fichier=filename, chemin_fichier=f"{id}/{filename}", type='pdf' if ext == '.pdf' else 'photo')
    session.add(m); session.commit(); return jsonify({'status': 'success'})

@app.route('/api/medias/<int:media_id>', methods=['DELETE'])
def api_delete_media(media_id):
    session = get_db(); m = session.get(Media, media_id); file_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], m.chemin_fichier))
    try: os.remove(file_path)
    except: pass
    session.delete(m); session.commit(); return jsonify({'status': 'success'})

@app.route('/admin/fixers')
def admin_fixers_list():
    session = get_db(); query = session.query(Fixer); search = request.args.get('search'); pays = request.args.get('pays')
    if search: query = query.filter(or_(Fixer.nom.ilike(f'%{search}%'), Fixer.prenom.ilike(f'%{search}%')))
    if pays: query = query.filter(Fixer.pays == pays)
    return render_template('admin_fixers.html', fixers=query.order_by(Fixer.nom.asc()).all(), pays_list=[p[0] for p in session.query(Fixer.pays).distinct().all() if p[0]])

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

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_rep():
    session = get_db(); data = request.json; fixer = session.get(Fixer, data.get('fixer_id'))
    new_rep = Reperage(token=secrets.token_urlsafe(16), region=data.get('region'), pays=data.get('pays'), fixer_id=data.get('fixer_id'), fixer_nom=f"{fixer.prenom} {fixer.nom}" if fixer else "Inconnu", image_region=data.get('image_region'), statut='brouillon')
    session.add(new_rep); session.commit(); return jsonify({'status': 'success'})



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000)); app.run(host='0.0.0.0', port=port)
