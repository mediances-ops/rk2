@app.route('/formulaire/<token>')
def formulaire_reperage(token):
    """Action 1.1 : Charge le dossier intégral (3x3) avec tous les champs techniques"""
    session = get_session(engine)
    try:
        rep = session.query(Reperage).filter_by(token=token).first()
        if not rep: return "Lien invalide", 404
        
        fixer = session.get(Fixer, rep.fixer_id) if rep.fixer_id else None
        
        # --- STRUCTURE INTÉGRALE DES GARDIENS (Zéro omission) ---
        gardiens_list = []
        for i in range(1, 4):
            g_obj = next((g for g in rep.gardiens if g.ordre == i), None)
            if g_obj:
                gardiens_list.append(g_obj.to_dict())
            else:
                # Dictionnaire exhaustif pour forcer l'affichage des champs par app.js
                gardiens_list.append({
                    'ordre': i, 'nom': '', 'prenom': '', 'age': '', 'genre': '',
                    'fonction': '', 'savoir_transmis': '', 'adresse': '',
                    'telephone': '', 'email': '', 'histoire_personnelle': '',
                    'evaluation_cinegenie': '', 'langues_parlees': ''
                })

        # --- STRUCTURE INTÉGRALE DES LIEUX (Zéro omission) ---
        lieux_list = []
        for i in range(1, 4):
            l_obj = next((l for l in rep.lieux if l.numero_lieu == i), None)
            if l_obj:
                lieux_list.append(l_obj.to_dict())
            else:
                # Rétablissement de tous les tiroirs pour Lieux 2 et 3
                lieux_list.append({
                    'numero_lieu': i, 'nom': '', 'type_environnement': '',
                    'description_visuelle': '', 'elements_symboliques': '',
                    'points_vue_remarquables': '', 'cinegenie': '', 'axes_camera': '',
                    'moments_favorables': '', 'ambiance_sonore': '', 'adequation_narration': '',
                    'accessibilite': '', 'securite': '', 'electricite': '',
                    'espace_equipe': '', 'protection_meteo': '', 'contraintes_meteo': '',
                    'autorisations_necessaires': '', 'latitude': '', 'longitude': ''
                })

        # --- PAQUET DE DONNÉES COMPLET ---
        fixer_data = {
            'region': rep.region,
            'pays': rep.pays,
            'image_region': rep.image_region,
            'prenom': fixer.prenom if fixer else '',
            'nom': fixer.nom if fixer else '',
            'email': fixer.email if fixer else '',
            'telephone': fixer.telephone if fixer else '',
            'langue_preferee': fixer.langue_preferee if fixer else 'FR',
            'territoire': json.loads(rep.territoire_data) if rep.territoire_data else {},
            'episode': json.loads(rep.episode_data) if rep.episode_data else {},
            'gardiens': gardiens_list,
            'lieux': lieux_list
        }
        
        return render_template('index.html', 
                             REPERAGE_ID=rep.id, 
                             FIXER_DATA=fixer_data, 
                             langue_default=fixer_data['langue_preferee'])
    finally: session.close()
