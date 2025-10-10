from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    _tablename_ = "user"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True, index=True)
    password = db.Column(db.String(255))
    role = db.Column(db.String(50), default="etudiant")  # admin ou etudiant

class Resultat(db.Model):
    _tablename_ = "resultat"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255))
    matricule = db.Column(db.String(100))
    matiere = db.Column(db.String(200))
    note = db.Column(db.Float)

