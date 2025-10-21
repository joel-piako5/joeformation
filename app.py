import sqlite3
import os
from sqlite3 import IntegrityError
from flask import (
    Flask, render_template, request, redirect, url_for, session,
    flash, send_from_directory, abort, Blueprint
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt
import calendar
from datetime import date, datetime
from questions import questions

app = Flask(__name__)
app.secret_key = 'joegoat532005mmaPK'
# Utilise PostgreSQL sur Render, sinon SQLite en local
if os.environ.get("RENDER"):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///etudiants.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_EMAIL = "joe@mail.mma"
ADMIN_CODE = "joe2005"

VIDEO_EXT = {"mp4", "webm", "ogg"}
PDF_EXT = {"pdf"}

# Modèle utilisateur
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(10), default='etudiant')  # 'admin' ou 'etudiant'

# Modèle résultats
class Resultat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    matricule = db.Column(db.String(50))
    matiere = db.Column(db.String(100))
    note = db.Column(db.Float)

# Route d'accueil
@app.route('/')
def index():
    return render_template('index.html')

# Route de contact
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        print(f"📩 Nouveau message de {name} ({email}) : {message}")
        flash("✅ Votre message a été envoyé avec succès !", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")

@app.route("/histoire")
def histoire():
    return render_template("histoire.html")

@app.route('/profile')
def profile():
    return render_template("profile.html")

# Inscription
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form['nom']
        email = request.form['email']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        user = User(nom=nom, email=email, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash('✅Compte créé avec succès.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# Connexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_nom'] = user.nom
            session['user_role'] = user.role
            flash('Connexion réussie.', 'success')
            return redirect(url_for('quiz')) if user.role == 'etudiant' else redirect(url_for('admin'))
        else:
            flash('Identifiants incorrects.', 'danger')
    return render_template('login.html')

# Dashboard
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# Déconnexion
@app.route('/logout')
def logout():
    session.clear()
    flash('Déconnexion réussie.', 'info')
    return redirect(url_for('login'))

# Liste des matières
@app.route("/liste_matieres")
def liste_matieres():
    matieres = [
        "Bases de l’informatique",
        "Traitement de texte avec Microsoft Word",
        "Introduction à Microsoft Excel (interface et concepts de base)",
        "Formules et fonctions de base (SOMME, MOYENNE, SI…)",
        "Automatisation simple avec Macros et introduction à VBA",
        "Introduction aux bases de données",
        "Découverte de Microsoft Access (tables, champs, enregistrements)",
        "Création de formulaires et requêtes simples",
        "Introduction à la programmation et à Python",
        "Variables, types de données et opérations de base",
        "Conditions, boucles et structures de contrôle",
        "Fonctions et organisation du code",
        "Projet pratique : Mini application Python (ex: calculatrice, gestion simple)"
    ]
    return render_template("liste_matieres.html", matieres=matieres)

# Résultats
@app.route('/resultats')
def resultats():
    return render_template('resultats.html')

@app.route('/utilisateurs')
def utilisateurs():
    if 'user_nom' not in session or session['user_nom'] != 'etudiant':
        flash("Accès refusé", "danger")
        return redirect(url_for('login'))
    users = User.query.all()
    return render_template('liste_etudiants.html', users=users)

@app.route('/etudiants')
def liste_etudiants():
    if "user_id" not in session:
        return redirect(url_for("logi"))
    etudiants = User.query.all()
    return render_template('liste_etudiants.html', etudiants=etudiants)

# Fichiers autorisés
def allowed_file(filename, filetype):
    ext = filename.rsplit(".", 1)[-1].lower()
    return (ext in VIDEO_EXT if filetype == "video" else ext in PDF_EXT)

# Page d'accueil des cours
@app.route("/homes")
def homes():
    return render_template("homes.html")

# Connexion admin
@app.route("/logi", methods=["GET", "POST"])
def logi():
    if request.method == "POST":
        email = request.form.get("email")
        code = request.form.get("code")
        if email == ADMIN_EMAIL and code == ADMIN_CODE:
            session["is_admin"] = True
            flash("Bienvenue l'administrateur joel !")
            return redirect(url_for("menu"))
        else:
            flash("Identifiants incorrects.")
    return render_template("logi.html")

# Déconnexion admin
@app.route("/logo")
def logo():
    session.pop("is_admin", None)
    flash("Déconnecté.")
    return redirect(url_for("homes"))

# Menu cours admin
@app.route("/menu")
def menu():
    if not session.get("is_admin"):
        flash("Accès refusé. Veuillez vous connecter.")
        return redirect(url_for("logi"))
    return render_template("menu.html")

# Ajouter une vidéo
@app.route("/Admin/add_video", methods=["GET", "POST"])
def add_video():
    if not session.get("is_admin"):
        return redirect(url_for("logi"))
    if request.method == "POST":
        file = request.files.get("file")
        if file and allowed_file(file.filename, "video"):
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)
            flash("Vidéo ajoutée !")
            return redirect(url_for("menu"))
        else:
            flash("Format vidéo invalide.")
    return render_template("add_video.html")

# Ajouter un PDF
@app.route("/Admin/add_pdf", methods=["GET", "POST"])
def add_pdf():
    if not session.get("is_admin"):
        return redirect(url_for("logi"))
    if request.method == "POST":
        file = request.files.get("file")
        if file and allowed_file(file.filename, "pdf"):
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)
            flash("PDF ajouté !")
            return redirect(url_for("menu"))
        else:
            flash("Format PDF invalide.")
    return render_template("add_pdf.html")

# Supprimer fichiers
@app.route("/admin/delete", methods=["GET", "POST"])
def delete_file():
    if not session.get("is_admin"):
        return redirect(url_for("logi"))
    if request.method == "POST":
        filename = request.form.get("filename")
        if filename:
            path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.exists(path):
                os.remove(path)
                flash(f"{filename} supprimé avec succès.")
            else:
                flash("Fichier introuvable.")
        return redirect(url_for("delete_file"))
    files = os.listdir(UPLOAD_FOLDER)
    return render_template("delete.html", files=files)

# Vidéos publiques
@app.route("/videos")
def videos():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.split(".")[-1].lower() in VIDEO_EXT]
    return render_template("videos.html", files=files)

# PDFs publics
@app.route("/pdfs")
def pdfs():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.split(".")[-1].lower() in PDF_EXT]
    return render_template("pdfs.html", files=files)

@app.route("/watch/<filename>")
def watch_video(filename):
    return render_template("watch_video.html", filename=filename)

@app.route("/view_pdf/<filename>")
def view_pdf(filename):
    return render_template("view_pdf.html", filename=filename)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# Calendrier
@app.route('/calendrier')
def calendrier():
    year = datetime.now().year
    month = datetime.now().month
    today = datetime.now().day
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)
    return render_template('calendrier.html', weeks=weeks, year=year, month=month, today=today)

# Questions du quiz
quiz_questions = [
    {"id": 1, "question": "Quel langage est utilisé pour le développement web côté serveur ?",
     "choices": ["HTML", "Python", "CSS", "Photoshop"], "answer": "Python"},
    {"id": 2, "question": "Quel protocole est utilisé pour naviguer sur le web ?",
     "choices": ["FTP", "HTTP", "SMTP", "SSH"], "answer": "HTTP"},
    {"id": 3, "question": "Quelle balise HTML est utilisée pour insérer une image ?",
     "choices": ["<div>", "<img>", "<link>", "<span>"], "answer": "<img>"},
    {"id": 4, "question": "Quel est le langage utilisé pour styliser une page web ?",
     "choices": ["Python", "CSS", "SQL", "PHP"], "answer": "CSS"},
    {"id": 5, "question": "Quel est le système de gestion de version le plus utilisé ?",
     "choices": ["Git", "SVN", "Mercurial", "Dropbox"], "answer": "Git"}
]

@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == "POST":
        score = 0
        for q in quiz_questions:
            user_answer = request.form.get(str(q["id"]))
            if user_answer == q["answer"]:
                score += 1
        return render_template("resul.html", score=score, total=len(quiz_questions))
    return render_template("quiz.html", questions=quiz_questions)

# Quiz d'entraînement
@app.route("/page")
def page():
    return render_template("page.html")

@app.route("/quizz", methods=["GET", "POST"])
def quizz():
    if request.method == "POST":
        score = 0
        for q in questions:
            user_answer = request.form.get(str(q["id"]))
            if user_answer == q["answer"]:
                score += 1
        return render_template("result.html", score=score, total=len(questions))
    return render_template("quizz.html", questions=questions)

# Lancement
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)


