from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from models import init_db, get_session, Reperage, Gardien, Lieu, Media, Message
import os
import json
import secrets
from datetime import datetime
from PIL import Image
import io
import re

app = Flask(__name__)
CORS(app)

# Configuration
# ✅ Utiliser /data pour Railway volumes, fallback vers static/uploads en local
UPLOAD_FOLDER = os.environ.get('UPLOAD_PATH', '/data/uploads') if os.path.exists('/data') else 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'heic', 'webp', 'pdf', 'doc', 'docx', 'mp4', 'mov', 'avi'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB (pour les vidéos)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Créer les dossiers nécessaires
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'thumbnails'), exist_ok=True)


# ============= CONFIGURATION BASE DE DONNÉES =============
# ✅ Support PostgreSQL (Railway) et SQLite (Local)
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Production (Railway) : PostgreSQL
    # Remplacer postgres:// par postgresql:// (requis par SQLAlchemy 1.4+)
    database_url = database_url.replace('postgres://', 'postgresql://')
    print("📊 Base de données: PostgreSQL")
else:
    # Local : SQLite
    database_url = 'sqlite:///reperage.db'
    print("📊 Base de données: SQLite (reperage.db)")

# Initialiser la base de données avec l'URL appropriée
engine = init_db(database_url)

def generate_token():
    """Générer un token aléatoire sécurisé pour URLs"""
    return secrets.token_urlsafe(16)  # 16 bytes = ~21 caractères

def get_reperage_by_token_or_id(session, identifier):
    """Récupérer un repérage par token (préféré) ou ID (fallback)"""
    # D'abord essayer par token
    reperage = session.query(Reperage).filter_by(token=identifier).first()
    if reperage:
        return reperage
    
    # Si pas trouvé et que c'est un nombre, essayer par ID
    if identifier.isdigit():
        return session.query(Reperage).filter_by(id=int(identifier)).first()
    
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_thumbnail(image_path, thumbnail_path, size=(300, 300)):
    """Créer une miniature d'une image"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumbnail_path, quality=85, optimize=True)
            return True
    except Exception as e:
        print(f"Erreur création miniature: {e}")
        return False

def linkify_text(text):
    """Convertir les URLs en liens HTML cliquables"""
    if not text:
        return text
    
    # Pattern pour détecter les URLs
    url_pattern = r'(https?://[^\s]+)'
    
    # Remplacer les URLs par des liens HTML
    def replace_url(match):
        url = match.group(0)
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
    
    return re.sub(url_pattern, replace_url, text)

# Ajouter le filtre Jinja2
app.jinja_env.filters['linkify'] = linkify_text

# ============= ROUTES HTML =============

@app.route('/')
def index():
    return redirect('/admin')  # ✅ Rediriger vers admin par défaut


# ============= API TRADUCTIONS =============

@app.route('/api/i18n/<lang>')
def get_translations(lang):
    """Récupérer les traductions pour une langue"""
    try:
        with open('translations/i18n.json', 'r', encoding='utf-8') as f:
            translations = json.load(f)
        
        if lang in translations:
            return jsonify(translations[lang])
        else:
            return jsonify(translations['FR'])  # Français par défaut
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= API REPÉRAGES =============

@app.route('/api/reperages', methods=['GET'])
def get_reperages():
    """Récupérer tous les repérages"""
    session = get_session(engine)
    try:
        reperages = session.query(Reperage).all()
        return jsonify([r.to_dict() for r in reperages])
    finally:
        session.close()

@app.route('/api/reperages/<int:id>', methods=['GET'])
def get_reperage(id):
    """Récupérer un repérage spécifique"""
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if reperage:
            return jsonify(reperage.to_dict())
        return jsonify({'error': 'Repérage non trouvé'}), 404
    finally:
        session.close()

@app.route('/api/reperages', methods=['POST'])
def create_reperage():
    """Créer un nouveau repérage"""
    session = get_session(engine)
    try:
        data = request.json
        
        reperage = Reperage(
            token=generate_token(),  # ✅ Générer token sécurisé
            langue_interface=data.get('langue_interface', 'FR'),
            fixer_nom=data.get('fixer_nom'),
            fixer_email=data.get('fixer_email'),
            fixer_telephone=data.get('fixer_telephone'),
            pays=data.get('pays'),
            region=data.get('region'),
            territoire_data=json.dumps(data.get('territoire_data', {})),
            episode_data=json.dumps(data.get('episode_data', {}))
        )
        
        session.add(reperage)
        session.commit()
        
        return jsonify(reperage.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/reperages/<int:id>', methods=['PUT'])
def update_reperage(id):
    """Mettre à jour un repérage"""
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage:
            return jsonify({'error': 'Repérage non trouvé'}), 404
        
        data = request.json
        
        # Mise à jour des champs simples
        for field in ['langue_interface', 'fixer_nom', 'fixer_email', 'fixer_telephone', 
                      'pays', 'region', 'statut']:
            if field in data:
                setattr(reperage, field, data[field])
        
        # Mise à jour des données JSON
        if 'territoire_data' in data:
            reperage.territoire_data = json.dumps(data['territoire_data'])
        if 'episode_data' in data:
            reperage.episode_data = json.dumps(data['episode_data'])
        
        # ✅ NOUVEAU : Mise à jour des gardiens
        if 'gardiens' in data:
            # Supprimer les anciens gardiens
            session.query(Gardien).filter_by(reperage_id=id).delete()
            
            # Créer les nouveaux gardiens
            for gardien_data in data['gardiens']:
                gardien = Gardien(
                    reperage_id=id,
                    **gardien_data
                )
                session.add(gardien)
        
        # ✅ NOUVEAU : Mise à jour des lieux
        if 'lieux' in data:
            # Supprimer les anciens lieux
            session.query(Lieu).filter_by(reperage_id=id).delete()
            
            # Créer les nouveaux lieux
            for lieu_data in data['lieux']:
                lieu = Lieu(
                    reperage_id=id,
                    **lieu_data
                )
                session.add(lieu)
        
        reperage.updated_at = datetime.now()
        session.commit()
        
        return jsonify(reperage.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/reperages/<int:id>', methods=['DELETE'])
def delete_reperage(id):
    """Supprimer un repérage"""
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage:
            return jsonify({'error': 'Repérage non trouvé'}), 404
        
        session.delete(reperage)
        session.commit()
        
        return jsonify({'message': 'Repérage supprimé'}), 200
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/reperages/<int:id>/submit', methods=['POST'])
def submit_reperage(id):
    """Soumettre un repérage (changer statut de brouillon à soumis)"""
    session = get_session(engine)
    try:
        reperage = session.get(Reperage, id)
        if not reperage:
            return jsonify({'error': 'Repérage non trouvé'}), 404
        
        reperage.statut = 'soumis'
        reperage.updated_at = datetime.now()
        session.commit()
        
        return jsonify(reperage.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# ============= API GARDIENS =============

@app.route('/api/reperages/<int:reperage_id>/gardiens', methods=['GET'])
def get_gardiens(reperage_id):
    """Récupérer les gardiens d'un repérage"""
    session = get_session(engine)
    try:
        gardiens = session.query(Gardien).filter_by(reperage_id=reperage_id).order_by(Gardien.ordre).all()
        return jsonify([g.to_dict() for g in gardiens])
    finally:
        session.close()

@app.route('/api/reperages/<int:reperage_id>/gardiens', methods=['POST'])
def create_gardien(reperage_id):
    """Créer un gardien"""
    session = get_session(engine)
    try:
        data = request.json
        
        gardien = Gardien(
            reperage_id=reperage_id,
            ordre=data.get('ordre'),
            nom=data.get('nom'),
            prenom=data.get('prenom'),
            age=data.get('age'),
            genre=data.get('genre'),
            fonction=data.get('fonction'),
            savoir_transmis=data.get('savoir_transmis'),
            adresse=data.get('adresse'),
            telephone=data.get('telephone'),
            email=data.get('email'),
            contact_intermediaire=data.get('contact_intermediaire'),
            histoire_personnelle=data.get('histoire_personnelle'),
            evaluation_cinegenie=data.get('evaluation_cinegenie'),
            langues_parlees=data.get('langues_parlees'),
            photo_url=data.get('photo_url')
        )
        
        session.add(gardien)
        session.commit()
        
        return jsonify(gardien.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/gardiens/<int:id>', methods=['PUT'])
def update_gardien(id):
    """Mettre à jour un gardien"""
    session = get_session(engine)
    try:
        gardien = session.get(Gardien, id)
        if not gardien:
            return jsonify({'error': 'Gardien non trouvé'}), 404
        
        data = request.json
        
        for field in ['ordre', 'nom', 'prenom', 'age', 'genre', 'fonction', 'savoir_transmis',
                      'adresse', 'telephone', 'email', 'contact_intermediaire', 
                      'histoire_personnelle', 'evaluation_cinegenie', 'langues_parlees', 'photo_url']:
            if field in data:
                setattr(gardien, field, data[field])
        
        session.commit()
        return jsonify(gardien.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/gardiens/<int:id>', methods=['DELETE'])
def delete_gardien(id):
    """Supprimer un gardien"""
    session = get_session(engine)
    try:
        gardien = session.get(Gardien, id)
        if not gardien:
            return jsonify({'error': 'Gardien non trouvé'}), 404
        
        session.delete(gardien)
        session.commit()
        
        return jsonify({'message': 'Gardien supprimé'}), 200
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# ============= API LIEUX =============

@app.route('/api/reperages/<int:reperage_id>/lieux', methods=['GET'])
def get_lieux(reperage_id):
    """Récupérer les lieux d'un repérage"""
    session = get_session(engine)
    try:
        lieux = session.query(Lieu).filter_by(reperage_id=reperage_id).all()
        return jsonify([l.to_dict() for l in lieux])
    finally:
        session.close()

@app.route('/api/reperages/<int:reperage_id>/lieux', methods=['POST'])
def create_lieu(reperage_id):
    """Créer un lieu"""
    session = get_session(engine)
    try:
        data = request.json
        
        lieu = Lieu(
            reperage_id=reperage_id,
            numero_lieu=data.get('numero_lieu', 1),  # NOUVEAU: support des 3 lieux
            nom=data.get('nom'),
            type_environnement=data.get('type_environnement'),
            description_visuelle=data.get('description_visuelle'),
            elements_symboliques=data.get('elements_symboliques'),
            points_vue_remarquables=data.get('points_vue_remarquables'),
            cinegenie=data.get('cinegenie'),
            axes_camera=data.get('axes_camera'),
            moments_favorables=data.get('moments_favorables'),
            ambiance_sonore=data.get('ambiance_sonore'),
            adequation_narration=data.get('adequation_narration'),
            accessibilite=data.get('accessibilite'),
            securite=data.get('securite'),
            electricite=data.get('electricite'),
            espace_equipe=data.get('espace_equipe'),
            protection_meteo=data.get('protection_meteo'),
            contraintes_meteo=data.get('contraintes_meteo'),
            autorisations_necessaires=data.get('autorisations_necessaires'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude')
        )
        
        session.add(lieu)
        session.commit()
        
        return jsonify(lieu.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/lieux/<int:id>', methods=['PUT'])
def update_lieu(id):
    """Mettre à jour un lieu"""
    session = get_session(engine)
    try:
        lieu = session.get(Lieu, id)
        if not lieu:
            return jsonify({'error': 'Lieu non trouvé'}), 404
        
        data = request.json
        
        for field in ['nom', 'type_environnement', 'description_visuelle', 'elements_symboliques',
                      'points_vue_remarquables', 'cinegenie', 'axes_camera', 'moments_favorables',
                      'ambiance_sonore', 'adequation_narration', 'accessibilite', 'securite',
                      'electricite', 'espace_equipe', 'protection_meteo', 'contraintes_meteo',
                      'autorisations_necessaires', 'latitude', 'longitude']:
            if field in data:
                setattr(lieu, field, data[field])
        
        session.commit()
        return jsonify(lieu.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/lieux/<int:id>', methods=['DELETE'])
def delete_lieu(id):
    """Supprimer un lieu"""
    session = get_session(engine)
    try:
        lieu = session.get(Lieu, id)
        if not lieu:
            return jsonify({'error': 'Lieu non trouvé'}), 404
        
        session.delete(lieu)
        session.commit()
        
        return jsonify({'message': 'Lieu supprimé'}), 200
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# ============= API MÉDIAS (UPLOAD) =============

@app.route('/api/reperages/<int:reperage_id>/medias', methods=['POST'])
def upload_media(reperage_id):
    """Upload un fichier (photo, document)"""
    session = get_session(engine)
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Aucun fichier'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'Nom de fichier vide'}), 400
        
        if file and allowed_file(file.filename):
            # Sécuriser le nom de fichier
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{timestamp}_{filename}"
            
            # Créer le dossier du repérage
            reperage_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(reperage_id))
            os.makedirs(reperage_folder, exist_ok=True)
            
            # Sauvegarder le fichier
            filepath = os.path.join(reperage_folder, unique_filename)
            file.save(filepath)
            
            # Créer miniature si c'est une image
            is_image = filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'webp'}
            thumbnail_path = None
            
            if is_image:
                thumbnail_filename = f"thumb_{unique_filename}"
                thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', thumbnail_filename)
                create_thumbnail(filepath, thumbnail_path)
            
            # Enregistrer en base de données
            media = Media(
                reperage_id=reperage_id,
                type='photo' if is_image else 'document',
                categorie=request.form.get('categorie', 'autre'),
                nom_fichier=unique_filename,
                nom_original=filename,
                chemin_fichier=filepath,
                taille_octets=os.path.getsize(filepath),
                mime_type=file.content_type,
                legende=request.form.get('legende', ''),
                ordre_affichage=request.form.get('ordre_affichage', 0)
            )
            
            session.add(media)
            session.commit()
            
            return jsonify(media.to_dict()), 201
        
        return jsonify({'error': 'Type de fichier non autorisé'}), 400
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/reperages/<int:reperage_id>/medias', methods=['GET'])
def get_medias(reperage_id):
    """Récupérer les médias d'un repérage"""
    session = get_session(engine)
    try:
        medias = session.query(Media).filter_by(reperage_id=reperage_id).all()
        return jsonify([m.to_dict() for m in medias])
    finally:
        session.close()

@app.route('/api/medias/<int:id>', methods=['DELETE'])
def delete_media(id):
    """Supprimer un média"""
    session = get_session(engine)
    try:
        media = session.get(Media, id)
        if not media:
            return jsonify({'error': 'Média non trouvé'}), 404
        
        # Supprimer le fichier physique
        if os.path.exists(media.chemin_fichier):
            os.remove(media.chemin_fichier)
        
        session.delete(media)
        session.commit()
        
        return jsonify({'message': 'Média supprimé'}), 200
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# ============= API MESSAGES (CHAT) =============

@app.route('/api/reperages/<int:reperage_id>/messages', methods=['GET'])
def get_messages(reperage_id):
    """Récupérer tous les messages d'un repérage"""
    session = get_session(engine)
    try:
        messages = session.query(Message).filter_by(reperage_id=reperage_id).order_by(Message.created_at.asc()).all()
        return jsonify([msg.to_dict() for msg in messages])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/reperages/<int:reperage_id>/messages', methods=['POST'])
def create_message(reperage_id):
    """Créer un nouveau message"""
    session = get_session(engine)
    try:
        data = request.json
        
        # Vérifier que le repérage existe
        reperage = session.get(Reperage, reperage_id)
        if not reperage:
            return jsonify({'error': 'Repérage non trouvé'}), 404
        
        message = Message(
            reperage_id=reperage_id,
            auteur_type=data.get('auteur_type', 'fixer'),  # 'production' ou 'fixer'
            auteur_nom=data.get('auteur_nom', 'Anonyme'),
            contenu=data.get('contenu', ''),
            lu=False
        )
        
        session.add(message)
        session.commit()
        
        return jsonify(message.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/messages/<int:message_id>/read', methods=['PUT'])
def mark_message_read(message_id):
    """Marquer un message comme lu"""
    session = get_session(engine)
    try:
        message = session.get(Message, message_id)
        if not message:
            return jsonify({'error': 'Message non trouvé'}), 404
        
        message.lu = True
        session.commit()
        
        return jsonify(message.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/reperages/<int:reperage_id>/messages/unread-count', methods=['GET'])
def get_unread_count(reperage_id):
    """Compter les messages non lus d'un repérage"""
    session = get_session(engine)
    try:
        # Déterminer si c'est production ou fixer qui demande
        auteur_type = request.args.get('for', 'fixer')  # 'production' ou 'fixer'
        
        # Compter les messages non lus de l'autre partie
        if auteur_type == 'fixer':
            # Fixer voit les messages de la production non lus
            count = session.query(Message).filter_by(
                reperage_id=reperage_id,
                auteur_type='production',
                lu=False
            ).count()
        else:
            # Production voit les messages du fixer non lus
            count = session.query(Message).filter_by(
                reperage_id=reperage_id,
                auteur_type='fixer',
                lu=False
            ).count()
        
        return jsonify({'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# ============= FICHIERS STATIQUES =============

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Servir les fichiers uploadés"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ============= DASHBOARD ADMIN =============

@app.route('/admin')
def admin_dashboard():
    """Dashboard admin - liste des repérages"""
    session = get_session(engine)
    try:
        # Statistiques
        total = session.query(Reperage).count()
        brouillons = session.query(Reperage).filter_by(statut='brouillon').count()
        soumis = session.query(Reperage).filter_by(statut='soumis').count()
        valides = session.query(Reperage).filter_by(statut='validé').count()
        
        stats = {
            'total': total,
            'brouillons': brouillons,
            'soumis': soumis,
            'valides': valides
        }
        
        # Filtres avec jointure sur Fixer
        from models import Fixer
        query = session.query(Reperage, Fixer).outerjoin(Fixer, Reperage.fixer_id == Fixer.id)
        
        statut_filter = request.args.get('statut')
        if statut_filter:
            query = query.filter(Reperage.statut == statut_filter)
        
        pays_filter = request.args.get('pays')
        if pays_filter:
            query = query.filter(Reperage.pays == pays_filter)
        
        search = request.args.get('search')
        if search:
            query = query.filter(
                (Reperage.region.like(f'%{search}%')) |
                (Reperage.fixer_nom.like(f'%{search}%'))
            )
        
        results = query.order_by(Reperage.created_at.desc()).all()
        
        # Créer liste avec reperage + fixer
        reperages_with_fixer = []
        for reperage, fixer in results:
            rep_dict = {
                'reperage': reperage,
                'fixer': fixer,
                'lien_formulaire': fixer.lien_personnel if fixer else None
            }
            reperages_with_fixer.append(rep_dict)
        
        # Liste des pays pour le filtre
        pays_list = session.query(Reperage.pays).filter(Reperage.pays.isnot(None)).distinct().all()
        pays_list = [p[0] for p in pays_list]
        
        # Liste des fixers pour modal création
        from models import Fixer
        fixers = session.query(Fixer).order_by(Fixer.nom, Fixer.prenom).all()
        
        return render_template('admin_dashboard.html', 
                             reperages=reperages_with_fixer, 
                             stats=stats,
                             pays_list=pays_list,
                             fixers=fixers)
    finally:
        session.close()

@app.route('/admin/reperages/create', methods=['POST'])
def admin_create_reperage():
    """Créer un nouveau repérage depuis le dashboard admin"""
    session = get_session(engine)
    try:
        data = request.get_json()
        
        # Récupérer le fixer
        from models import Fixer
        fixer = session.query(Fixer).filter_by(id=data.get('fixer_id')).first()
        
        if not fixer:
            return jsonify({'error': 'Correspondant non trouvé'}), 404
        
        # Créer le repérage
        reperage = Reperage(
            token=generate_token(),  # ✅ Générer token sécurisé
            region=data.get('region'),
            pays=data.get('pays'),
            fixer_id=fixer.id,
            fixer_nom=fixer.nom,
            fixer_prenom=fixer.prenom,
            fixer_email=fixer.email,
            fixer_telephone=fixer.telephone,
            statut='brouillon',
            notes_admin=data.get('notes_admin'),
            image_region=data.get('image_region')
        )
        
        session.add(reperage)
        session.commit()
        
        return jsonify({
            'success': True,
            'reperage_id': reperage.id,
            'message': 'Repérage créé avec succès'
        }), 201
        
    except Exception as e:
        session.rollback()
        print(f"Erreur création repérage: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/admin/reperages/<int:reperage_id>/update', methods=['PUT'])
def admin_update_reperage(reperage_id):
    """Modifier un repérage depuis le dashboard admin"""
    session = get_session(engine)
    try:
        data = request.get_json()
        
        # Récupérer le repérage
        reperage = session.query(Reperage).filter_by(id=reperage_id).first()
        if not reperage:
            return jsonify({'error': 'Repérage non trouvé'}), 404
        
        # Récupérer le fixer
        from models import Fixer
        fixer = session.query(Fixer).filter_by(id=data.get('fixer_id')).first()
        if not fixer:
            return jsonify({'error': 'Correspondant non trouvé'}), 404
        
        # Mettre à jour le repérage
        reperage.region = data.get('region')
        reperage.pays = data.get('pays')
        reperage.fixer_id = fixer.id
        reperage.fixer_nom = fixer.nom
        reperage.fixer_prenom = fixer.prenom
        reperage.fixer_email = fixer.email
        reperage.fixer_telephone = fixer.telephone
        reperage.statut = data.get('statut', 'brouillon')
        reperage.notes_admin = data.get('notes_admin')
        reperage.image_region = data.get('image_region')
        
        session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Repérage modifié avec succès'
        }), 200
        
    except Exception as e:
        session.rollback()
        print(f"Erreur modification repérage: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/admin/reperage/<int:id>')
def admin_reperage_detail(id):
    """Vue détaillée d'un repérage"""
    from models import Fixer
    session = get_session(engine)
    try:
        reperage = session.query(Reperage).filter_by(id=id).first()
        if not reperage:
            return "Repérage non trouvé", 404
        
        # Parser les données JSON
        territoire = json.loads(reperage.territoire_data) if reperage.territoire_data else {}
        episode = json.loads(reperage.episode_data) if reperage.episode_data else {}
        
        gardiens = session.query(Gardien).filter_by(reperage_id=id).order_by(Gardien.ordre).all()
        lieux = session.query(Lieu).filter_by(reperage_id=id).all()
        medias = session.query(Media).filter_by(reperage_id=id).all()
        
        # Récupérer le fixer associé
        fixer = None
        if reperage.fixer_id:
            fixer = session.query(Fixer).filter_by(id=reperage.fixer_id).first()
        
        return render_template('admin_reperage_detail.html',
                             reperage=reperage,
                             territoire=territoire,
                             episode=episode,
                             gardiens=gardiens,
                             lieux=lieux,
                             medias=medias,
                             fixer=fixer)
    finally:
        session.close()

@app.route('/admin/reperage/<int:id>/valider', methods=['POST'])
def admin_valider_reperage(id):
    """Valider un repérage"""
    session = get_session(engine)
    try:
        reperage = session.query(Reperage).filter_by(id=id).first()
        if reperage:
            reperage.statut = 'validé'
            reperage.updated_at = datetime.now()
            session.commit()
        return redirect(f'/admin/reperage/{id}')
    finally:
        session.close()

@app.route('/admin/reperage/<int:id>/rouvrir', methods=['POST'])
def admin_rouvrir_reperage(id):
    """Rouvrir un repérage pour modifications (passe en brouillon)"""
    session = get_session(engine)
    try:
        reperage = session.query(Reperage).filter_by(id=id).first()
        if reperage:
            reperage.statut = 'brouillon'
            reperage.updated_at = datetime.now()
            session.commit()
        return redirect(f'/admin/reperage/{id}')
    finally:
        session.close()

@app.route('/admin/reperage/<int:id>/supprimer', methods=['POST'])
def admin_supprimer_reperage(id):
    """Supprimer un repérage et tous ses médias"""
    session = get_session(engine)
    try:
        reperage = session.query(Reperage).filter_by(id=id).first()
        if not reperage:
            return "Repérage non trouvé", 404
        
        print(f"🗑️ Suppression repérage ID {id}...")
        
        # 1. Supprimer tous les messages du chat
        try:
            messages = session.query(Message).filter_by(reperage_id=id).all()
            for message in messages:
                session.delete(message)
            print(f"   ✅ {len(messages)} messages supprimés")
        except Exception as e:
            print(f"   ⚠️ Erreur suppression messages: {e}")
        
        # 2. Supprimer tous les médias associés
        try:
            medias = session.query(Media).filter_by(reperage_id=id).all()
            for media in medias:
                # Supprimer le fichier physique
                try:
                    if os.path.exists(media.chemin_fichier):
                        os.remove(media.chemin_fichier)
                except:
                    pass
                session.delete(media)
            print(f"   ✅ {len(medias)} médias supprimés")
        except Exception as e:
            print(f"   ⚠️ Erreur suppression médias: {e}")
        
        # 3. Supprimer tous les gardiens
        try:
            gardiens = session.query(Gardien).filter_by(reperage_id=id).all()
            for gardien in gardiens:
                session.delete(gardien)
            print(f"   ✅ {len(gardiens)} gardiens supprimés")
        except Exception as e:
            print(f"   ⚠️ Erreur suppression gardiens: {e}")
        
        # 4. Supprimer tous les lieux
        try:
            lieux = session.query(Lieu).filter_by(reperage_id=id).all()
            for lieu in lieux:
                session.delete(lieu)
            print(f"   ✅ {len(lieux)} lieux supprimés")
        except Exception as e:
            print(f"   ⚠️ Erreur suppression lieux: {e}")
        
        # 5. Supprimer le dossier uploads du repérage
        try:
            reperage_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
            if os.path.exists(reperage_folder):
                import shutil
                shutil.rmtree(reperage_folder)
                print(f"   ✅ Dossier uploads supprimé")
        except Exception as e:
            print(f"   ⚠️ Erreur suppression dossier: {e}")
        
        # 6. Supprimer le repérage
        session.delete(reperage)
        session.commit()
        print(f"✅ Repérage ID {id} supprimé avec succès!")
        
        return redirect('/admin')
    except Exception as e:
        session.rollback()
        print(f"❌ ERREUR SUPPRESSION REPÉRAGE ID {id}: {e}")
        import traceback
        traceback.print_exc()
        return f"Erreur lors de la suppression: {e}", 500
    finally:
        session.close()

@app.route('/admin/reperage/<int:id>/pdf')
def admin_generate_pdf(id):
    """Générer un PDF du repérage - VERSION AMÉLIORÉE"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib.units import cm
        from reportlab.lib.enums import TA_CENTER
        from io import BytesIO
    except ImportError as e:
        print(f"❌ ERREUR: ReportLab non installé - {e}")
        return f"Erreur: ReportLab n'est pas installé. Exécutez: pip install reportlab --break-system-packages", 500
    
    session = get_session(engine)
    try:
        reperage = session.query(Reperage).filter_by(id=id).first()
        if not reperage:
            return "Repérage non trouvé", 404
        
        # Créer le PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm, leftMargin=2*cm, rightMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()
        
        # Styles personnalisés
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            textColor=colors.HexColor('#FF6B35'),
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#666666'),
            spaceAfter=30,
            alignment=TA_CENTER,
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#FF6B35'),
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubheading',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#FF8C5A'),
            spaceAfter=8,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        # TITRE PRINCIPAL
        story.append(Paragraph("ROOTSKEEPERS", title_style))
        story.append(Paragraph("Les Gardiens de la Tradition", subtitle_style))
        story.append(Spacer(1, 0.5*cm))
        
        # ORDRE CORRECT: RÉGION → PAYS → FIXER
        story.append(Paragraph("INFORMATIONS PRINCIPALES", heading_style))
        data = [
            ['Région:', reperage.region or '-'],
            ['Pays:', reperage.pays or '-'],
            ['Fixer:', reperage.fixer_nom or '-'],
            ['Email:', reperage.fixer_email or '-'],
            ['Téléphone:', reperage.fixer_telephone or '-'],
            ['Statut:', reperage.statut],
            ['Date:', reperage.created_at.strftime('%d/%m/%Y') if reperage.created_at else '-'],
        ]
        t = Table(data, colWidths=[4*cm, 12*cm])
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#FF6B35')),
            ('LINEBELOW', (0, -1), (-1, -1), 1, colors.HexColor('#FF6B35')),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.8*cm))
        
        # TERRITOIRE
        territoire = json.loads(reperage.territoire_data) if reperage.territoire_data else {}
        if territoire:
            story.append(Paragraph("TERRITOIRE", heading_style))
            for key, value in territoire.items():
                if value and key != 'id':
                    label = key.replace('_', ' ').title()
                    story.append(Paragraph(f"<b>{label}:</b> {value}", styles['Normal']))
                    story.append(Spacer(1, 0.2*cm))
            story.append(Spacer(1, 0.5*cm))
        
        # ÉPISODE
        episode = json.loads(reperage.episode_data) if reperage.episode_data else {}
        if episode:
            story.append(Paragraph("ÉPISODE", heading_style))
            for key, value in episode.items():
                if value and key != 'id':
                    label = key.replace('_', ' ').title()
                    story.append(Paragraph(f"<b>{label}:</b> {value}", styles['Normal']))
                    story.append(Spacer(1, 0.2*cm))
            story.append(Spacer(1, 0.5*cm))
        
        # GARDIENS
        gardiens = session.query(Gardien).filter_by(reperage_id=id).order_by(Gardien.ordre).all()
        if gardiens:
            story.append(Paragraph(f"LES 3 GARDIENS", heading_style))
            for g in gardiens:
                story.append(Paragraph(f"Gardien {g.ordre}", subheading_style))
                if g.prenom or g.nom:
                    story.append(Paragraph(f"<b>Nom:</b> {g.prenom or ''} {g.nom or ''}", styles['Normal']))
                if g.age:
                    story.append(Paragraph(f"<b>Âge:</b> {g.age} ans", styles['Normal']))
                if g.genre:
                    story.append(Paragraph(f"<b>Genre:</b> {g.genre}", styles['Normal']))
                if g.fonction:
                    story.append(Paragraph(f"<b>Fonction:</b> {g.fonction}", styles['Normal']))
                if g.savoir_transmis:
                    story.append(Paragraph(f"<b>Savoir transmis:</b> {g.savoir_transmis}", styles['Normal']))
                if g.telephone or g.email:
                    story.append(Paragraph(f"<b>Contact:</b> {g.telephone or ''} {g.email or ''}", styles['Normal']))
                story.append(Spacer(1, 0.5*cm))
        
        # LES 3 LIEUX
        lieux = session.query(Lieu).filter_by(reperage_id=id).order_by(Lieu.numero_lieu).all()
        if lieux:
            story.append(PageBreak())
            story.append(Paragraph(f"LIEUX DE TOURNAGE ({len(lieux)})", heading_style))
            
            for lieu in lieux:
                story.append(Paragraph(f"Lieu {lieu.numero_lieu}: {lieu.nom or 'Sans nom'}", subheading_style))
                
                if lieu.type_environnement:
                    story.append(Paragraph(f"<b>Type:</b> {lieu.type_environnement}", styles['Normal']))
                
                if lieu.description_visuelle:
                    story.append(Paragraph(f"<b>Description:</b> {lieu.description_visuelle}", styles['Normal']))
                
                if lieu.elements_symboliques:
                    story.append(Paragraph(f"<b>Éléments symboliques:</b> {lieu.elements_symboliques}", styles['Normal']))
                
                if lieu.cinegenie:
                    story.append(Paragraph(f"<b>Cinégénie:</b> {lieu.cinegenie}", styles['Normal']))
                
                if lieu.axes_camera:
                    story.append(Paragraph(f"<b>Axes caméra:</b> {lieu.axes_camera}", styles['Normal']))
                
                if lieu.accessibilite:
                    story.append(Paragraph(f"<b>Accessibilité:</b> {lieu.accessibilite}", styles['Normal']))
                
                if lieu.securite:
                    story.append(Paragraph(f"<b>Sécurité:</b> {lieu.securite}", styles['Normal']))
                
                if lieu.autorisations_necessaires:
                    story.append(Paragraph(f"<b>Autorisations:</b> {lieu.autorisations_necessaires}", styles['Normal']))
                
                story.append(Spacer(1, 0.7*cm))
        
        # Construire le PDF
        doc.build(story)
        buffer.seek(0)
        
        # Nom du fichier
        filename = f"RootsKeepers_{reperage.region or 'X'}_{reperage.pays or 'X'}_{datetime.now().strftime('%Y%m%d')}.pdf"
        filename = secure_filename(filename)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(f"❌ ERREUR GÉNÉRATION PDF: {e}")
        import traceback
        traceback.print_exc()
        return f"Erreur lors de la génération du PDF: {str(e)}", 500
    finally:
        session.close()

@app.route('/admin/reperage/<int:id>/photos')
def admin_download_photos(id):
    """Télécharger toutes les photos d'un repérage en ZIP"""
    import zipfile
    from io import BytesIO
    
    session = get_session(engine)
    try:
        reperage = session.query(Reperage).filter_by(id=id).first()
        if not reperage:
            return "Repérage non trouvé", 404
        
        medias = session.query(Media).filter_by(reperage_id=id, type='photo').all()
        
        if not medias:
            return "Aucune photo trouvée", 404
        
        # Créer le ZIP
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for media in medias:
                # Le chemin_fichier contient déjà le chemin complet
                file_path = media.chemin_fichier
                
                print(f"🔍 Tentative d'ajout: {file_path}")
                print(f"   Existe? {os.path.exists(file_path)}")
                
                if os.path.exists(file_path):
                    zip_file.write(file_path, media.nom_original)
                    print(f"   ✅ Ajouté au ZIP: {media.nom_original}")
                else:
                    print(f"   ❌ Fichier introuvable: {file_path}")
        
        zip_buffer.seek(0)
        
        # Nom du fichier ZIP
        filename = f"PHOTOS_REPERAGE_{id}_{datetime.now().strftime('%Y%m%d')}.zip"
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
    finally:
        session.close()

# ============= GESTION FIXERS =============

@app.route('/admin/fixers')
def admin_fixers():
    """Gestion des fixers avec filtres enrichis"""
    from models import Fixer
    session = get_session(engine)
    try:
        # Requête de base
        query = session.query(Fixer)
        
        # Filtre par recherche (nom, prénom, société)
        search = request.args.get('search')
        if search:
            query = query.filter(
                (Fixer.nom.like(f'%{search}%')) |
                (Fixer.prenom.like(f'%{search}%')) |
                (Fixer.societe.like(f'%{search}%'))
            )
        
        # Filtre par pays
        pays_filter = request.args.get('pays')
        if pays_filter:
            query = query.filter(Fixer.pays == pays_filter)
        
        # Filtre par langue
        langue_filter = request.args.get('langue')
        if langue_filter:
            query = query.filter(Fixer.langues_parlees.like(f'%{langue_filter}%'))
        
        # Filtre par statut
        statut_filter = request.args.get('statut')
        if statut_filter == 'actif':
            query = query.filter(Fixer.actif == True)
        elif statut_filter == 'inactif':
            query = query.filter(Fixer.actif == False)
        
        # Récupérer les fixers
        fixers = query.order_by(Fixer.created_at.desc()).all()
        
        # Liste des pays pour le filtre
        pays_list = session.query(Fixer.pays).filter(Fixer.pays.isnot(None)).distinct().all()
        pays_list = sorted([p[0] for p in pays_list if p[0]])
        
        return render_template('admin_fixers.html', fixers=fixers, pays_list=pays_list)
    finally:
        session.close()

@app.route('/admin/fixer/new', methods=['GET', 'POST'])
def admin_create_fixer():
    """Créer un nouveau fixer"""
    from models import Fixer
    from slugify import slugify
    import secrets
    
    # GET : Afficher le formulaire
    if request.method == 'GET':
        return render_template('admin_fixer_edit.html', fixer=None)
    
    # POST : Créer le fixer
    session = get_session(engine)
    try:
        # Récupérer les données de base
        prenom = request.form.get('prenom')
        nom = request.form.get('nom')
        email = request.form.get('email')
        telephone = request.form.get('telephone')
        
        # Générer le token unique
        token = secrets.token_urlsafe(6)[:8]
        
        # Créer le slug du nom
        slug = slugify(f"{prenom}-{nom}")
        
        # Créer le lien personnel
        lien = f"/fixer/{slug}-{token}"
        
        # Récupérer les langues parlées (checkboxes multiples)
        langues_parlees_list = request.form.getlist('langues_parlees')
        langues_parlees = ','.join(langues_parlees_list) if langues_parlees_list else None
        
        # Créer le fixer avec TOUS les champs
        fixer = Fixer(
            # Identité
            prenom=prenom,
            nom=nom,
            email=email,
            telephone=telephone,
            telephone_2=request.form.get('telephone_2'),
            
            # Professionnel
            societe=request.form.get('societe'),
            fonction=request.form.get('fonction'),
            site_web=request.form.get('site_web'),
            numero_siret=request.form.get('numero_siret'),
            
            # Adresse
            adresse_1=request.form.get('adresse_1'),
            adresse_2=request.form.get('adresse_2'),
            code_postal=request.form.get('code_postal'),
            ville=request.form.get('ville'),
            pays=request.form.get('pays'),
            region=request.form.get('region'),
            
            # Profil
            photo_profil_url=request.form.get('photo_profil_url'),
            bio=request.form.get('bio'),
            specialites=request.form.get('specialites'),
            
            # Langues
            langues_parlees=langues_parlees,
            langue_preferee=request.form.get('langue_preferee', 'FR'),
            
            # Système
            token_unique=token,
            lien_personnel=lien,
            actif=bool(request.form.get('actif')),
            notes_internes=request.form.get('notes_internes')
        )
        
        session.add(fixer)
        session.commit()
        
        return redirect('/admin/fixers')
    except Exception as e:
        session.rollback()
        print(f"Erreur création fixer: {e}")
        return f"Erreur: {e}", 500
    finally:
        session.close()

@app.route('/admin/fixer/<int:id>')
def admin_fixer_detail(id):
    """Page détail d'un fixer"""
    from models import Fixer
    
    session = get_session(engine)
    try:
        fixer = session.query(Fixer).filter_by(id=id).first()
        if not fixer:
            return "Fixer non trouvé", 404
        
        # Récupérer les repérages associés
        reperages = session.query(Reperage).filter_by(fixer_id=id).order_by(Reperage.created_at.desc()).all()
        
        return render_template('admin_fixer_detail.html', fixer=fixer, reperages=reperages)
    finally:
        session.close()

@app.route('/admin/fixer/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_fixer(id):
    """Modifier un fixer existant"""
    from models import Fixer
    
    session = get_session(engine)
    try:
        fixer = session.query(Fixer).filter_by(id=id).first()
        if not fixer:
            return "Fixer non trouvé", 404
        
        if request.method == 'POST':
            # Récupérer les langues parlées (checkboxes multiples)
            langues_parlees_list = request.form.getlist('langues_parlees')
            langues_parlees = ','.join(langues_parlees_list) if langues_parlees_list else None
            
            # Fonction helper pour convertir chaîne vide en None
            def empty_to_none(value):
                return value if value and value.strip() else None
            
            # Mettre à jour TOUS les champs
            # Identité
            fixer.prenom = request.form.get('prenom')
            fixer.nom = request.form.get('nom')
            fixer.email = request.form.get('email')
            fixer.telephone = request.form.get('telephone')
            fixer.telephone_2 = empty_to_none(request.form.get('telephone_2'))
            
            # Professionnel
            fixer.societe = empty_to_none(request.form.get('societe'))
            fixer.fonction = empty_to_none(request.form.get('fonction'))
            fixer.site_web = empty_to_none(request.form.get('site_web'))
            fixer.numero_siret = empty_to_none(request.form.get('numero_siret'))
            
            # Adresse
            fixer.adresse_1 = empty_to_none(request.form.get('adresse_1'))
            fixer.adresse_2 = empty_to_none(request.form.get('adresse_2'))
            fixer.code_postal = empty_to_none(request.form.get('code_postal'))
            fixer.ville = request.form.get('ville')
            fixer.pays = request.form.get('pays')
            fixer.region = empty_to_none(request.form.get('region'))
            
            # Profil
            fixer.photo_profil_url = empty_to_none(request.form.get('photo_profil_url'))
            fixer.bio = empty_to_none(request.form.get('bio'))
            fixer.specialites = empty_to_none(request.form.get('specialites'))
            
            # Langues
            fixer.langues_parlees = langues_parlees
            fixer.langue_preferee = request.form.get('langue_preferee', 'FR')
            
            # Système
            fixer.actif = bool(request.form.get('actif'))
            fixer.notes_internes = empty_to_none(request.form.get('notes_internes'))
            
            try:
                session.commit()
                return redirect('/admin/fixers')
            except Exception as e:
                session.rollback()
                print(f"❌ ERREUR SAUVEGARDE FIXER: {e}")
                return f"Erreur lors de la sauvegarde: {e}", 500
        
        # GET: afficher le formulaire
        return render_template('admin_fixer_edit.html', fixer=fixer)
    finally:
        session.close()

@app.route('/formulaire/<token>')
def formulaire_reperage(token):
    """Formulaire pour un repérage spécifique (sécurisé par token)"""
    from models import Fixer
    
    session = get_session(engine)
    try:
        # Récupérer le repérage par token
        reperage = get_reperage_by_token_or_id(session, token)
        if not reperage:
            return "Repérage non trouvé", 404
        
        # Récupérer le fixer associé
        fixer = session.query(Fixer).filter_by(id=reperage.fixer_id).first() if reperage.fixer_id else None
        
        if not fixer:
            return "Aucun correspondant affecté à ce repérage", 404
        
        # Préparer données FIXER_DATA (avec infos du REPÉRAGE, pas du fixer)
        FIXER_DATA = {
            'prenom': fixer.prenom,
            'nom': fixer.nom,
            'email': fixer.email,
            'telephone': fixer.telephone,
            'pays': reperage.pays,  # ← REPÉRAGE, pas fixer
            'region': reperage.region,  # ← REPÉRAGE, pas fixer
            'langue_preferee': fixer.langue_preferee or 'FR',
            'image_region': reperage.image_region if reperage.image_region else 'https://destinationsetcuisines.com/doc/multilingue/bannerreperage.jpg'
        }
        
        return render_template('index.html', FIXER_DATA=FIXER_DATA, REPERAGE_ID=reperage.id)
    finally:
        session.close()

@app.route('/fixer/<path:fixer_slug>')
def fixer_form(fixer_slug):
    """Formulaire pré-rempli pour un fixer spécifique"""
    from models import Fixer
    
    # Extraire le token du slug (les 8 derniers caractères)
    if len(fixer_slug) < 8:
        return "Lien invalide", 404
    
    token = fixer_slug[-8:]  # Les 8 derniers caractères
    
    session = get_session(engine)
    try:
        fixer = session.query(Fixer).filter_by(token_unique=token, actif=True).first()
        if not fixer:
            return "Fixer non trouvé ou inactif", 404
        
        # NOUVEAU : Chercher un repérage en brouillon existant pour ce fixer
        fixer_email = fixer.email
        reperage_existant = session.query(Reperage).filter_by(
            fixer_email=fixer_email,
            statut='brouillon'
        ).order_by(Reperage.updated_at.desc()).first()
        
        # Si un brouillon existe, passer son ID au template
        reperage_id = reperage_existant.id if reperage_existant else None
        
        # Préparer données FIXER_DATA avec image du repérage si disponible
        fixer_data = {
            'fixer_nom': fixer.nom,
            'fixer_prenom': fixer.prenom,
            'region': reperage_existant.region if reperage_existant else fixer.region,
            'pays': reperage_existant.pays if reperage_existant else fixer.pays,
            'image_region': reperage_existant.image_region if reperage_existant else None
        }
        
        # Renvoyer le formulaire avec données pré-remplies
        return render_template('index.html', 
                             fixer_id=fixer.id,
                             fixer_nom=f"{fixer.prenom} {fixer.nom}",
                             fixer_email=fixer.email,
                             fixer_telephone=fixer.telephone or '',
                             langue_default=fixer.langue_preferee,
                             reperage_id=reperage_id,
                             FIXER_DATA=fixer_data)
    finally:
        session.close()

@app.route('/admin/logout')
def admin_logout():
    """Déconnexion admin (placeholder)"""
    return redirect('/admin')

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🎬 SERVEUR DE REPÉRAGE - LES GARDIENS DE LA TRADITION")
    print("="*60)
    
    # Créer les tables au démarrage
    with app.app_context():
        from models import Base
        Base.metadata.create_all(engine)
        print("✅ Tables créées/vérifiées")
    
    port = int(os.environ.get('PORT', 5000))
    print(f"\n📍 URL: http://localhost:{port}")
    print("\n✅ Serveur démarré avec succès!\n")
    app.run(debug=False, host='0.0.0.0', port=port)

