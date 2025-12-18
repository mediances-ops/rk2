#!/usr/bin/env python3
"""
passenger_wsgi.py - Point d'entrée WSGI pour o2switch/Passenger
RootsKeepers - Application de repérage documentaire
"""

import sys
import os

# Ajouter le répertoire de l'application au path
INTERP = os.path.join(os.environ['HOME'], 'virtualenv', 'rootskeepers', '3.9', 'bin', 'python3')
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.insert(0, os.path.dirname(__file__))

# Importer l'application Flask
from app import app as application

# Configuration pour production
application.config['DEBUG'] = False

# IMPORTANT: o2switch utilise PostgreSQL, pas SQLite
# Les variables d'environnement seront définies dans .env
