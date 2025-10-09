# init_db.py
from app import app, db

# Ce script sert uniquement à créer les tables dans la base de données PostgreSQL.
# Il faut l’exécuter une seule fois sur Render (via le shell).

with app.app_context():
    db.create_all()
    print("✅ Base de données initialisée avec succès sur PostgreSQL !")
