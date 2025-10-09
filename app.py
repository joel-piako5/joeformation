import os
import calendar
from datetime import date, datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from questions import questions
from models import db, User


db.init_app(app)

# --- Configuration de base ---
app = Flask(__name__)
app.secret_key = 'joegoat532005mmaPK'

# --- Configuration base de données ---
# Si Render fournit DATABASE_URL → PostgreSQL
# Sinon (local) → SQLite
database_url = os.environ.get("DATABASE_URL", "sqlite:///etudiants.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# --- Configuration des fichiers upload ---
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
VIDEO_EXT = {"mp4", "webm", "ogg"}
PDF_EXT = {"pdf"}

# --- Informations administrateur ---
ADMIN_EMAIL = "joe@mail.mma"
ADMIN_CODE = "joe2005"

# ------------------ MODELES ------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(10), default="etudiant")  # admin ou etudiant

class Resultat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    matricule = db.Column(db.String(50))
    matiere = db.Column(db.String(100))
    note = db.Column(db.Float)

# ------------------ ROUTES ------------------
@app.route("/")
def index():
    return render_template("index.html")

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

@app.route("/profile")
def profile():
    return render_template("profile.html")

# --- Inscription ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nom = request.form["nom"]
        email = request.form["email"]
        password = request.form["password"]

        # Vérifie si email déjà utilisé
        if User.query.filter_by(email=email).first():
            flash("⚠️ Cet email est déjà utilisé.", "warning")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        user = User(nom=nom, email=email, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash("✅ Compte créé avec succès.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

# --- Connexion utilisateur ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["user_nom"] = user.nom
            session["user_role"] = user.role
            flash("Connexion réussie.", "success")
            if user.role == "etudiant":
                return redirect(url_for("quiz"))
            else:
                return redirect(url_for("menu"))
        else:
            flash("Identifiants incorrects.", "danger")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Déconnexion réussie.", "info")
    return redirect(url_for("login"))

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
        "Projet pratique : Mini application Python"
    ]
    return render_template("liste_matieres.html", matieres=matieres)

@app.route("/resultats")
def resultats():
    return render_template("resultats.html")

@app.route("/etudiants")
def liste_etudiants():
    if "user_id" not in session:
        return redirect(url_for("login"))
    etudiants = User.query.all()
    return render_template("liste_etudiants.html", etudiants=etudiants)

# ------------------ ADMIN ------------------

@app.route("/logi", methods=["GET", "POST"])
def logi():
    if request.method == "POST":
        email = request.form.get("email")
        code = request.form.get("code")
        if email == ADMIN_EMAIL and code == ADMIN_CODE:
            session["is_admin"] = True
            flash("Bienvenue administrateur Joel !")
            return redirect(url_for("menu"))
        else:
            flash("Identifiants incorrects.")
    return render_template("logi.html")

@app.route("/logo")
def logo():
    session.pop("is_admin", None)
    flash("Déconnecté.")
    return redirect(url_for("homes"))

@app.route("/menu")
def menu():
    if not session.get("is_admin"):
        flash("Accès refusé.")
        return redirect(url_for("logi"))
    return render_template("menu.html")

# --- Ajout fichiers ---
def allowed_file(filename, filetype):
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in (VIDEO_EXT if filetype == "video" else PDF_EXT)

@app.route("/Admin/add_video", methods=["GET", "POST"])
def add_video():
    if not session.get("is_admin"):
        return redirect(url_for("logi"))
    if request.method == "POST":
        file = request.files.get("file")
        if file and allowed_file(file.filename, "video"):
            filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
            file.save(filepath)
            flash("Vidéo ajoutée !")
            return redirect(url_for("menu"))
        else:
            flash("Format vidéo invalide.")
    return render_template("add_video.html")

@app.route("/Admin/add_pdf", methods=["GET", "POST"])
def add_pdf():
    if not session.get("is_admin"):
        return redirect(url_for("logi"))
    if request.method == "POST":
        file = request.files.get("file")
        if file and allowed_file(file.filename, "pdf"):
            filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
            file.save(filepath)
            flash("PDF ajouté !")
            return redirect(url_for("menu"))
        else:
            flash("Format PDF invalide.")
    return render_template("add_pdf.html")

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

# --- Pages publiques ---
@app.route("/homes")
def homes():
    return render_template("homes.html")

@app.route("/videos")
def videos():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.split(".")[-1].lower() in VIDEO_EXT]
    return render_template("videos.html", files=files)

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

# --- Calendrier ---
@app.route("/calendrier")
def calendrier():
    year = datetime.now().year
    month = datetime.now().month
    today = datetime.now().day
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)
    return render_template("calendrier.html", weeks=weeks, year=year, month=month, today=today)

# --- Quiz ---
quiz_questions = [
    {"id": 1, "question": "Quel langage est utilisé pour le développement web côté serveur ?", "choices": ["HTML", "Python", "CSS", "Photoshop"], "answer": "Python"},
    {"id": 2, "question": "Quel protocole est utilisé pour naviguer sur le web ?", "choices": ["FTP", "HTTP", "SMTP", "SSH"], "answer": "HTTP"},
    {"id": 3, "question": "Quelle balise HTML est utilisée pour insérer une image ?", "choices": ["<div>", "<img>", "<link>", "<span>"], "answer": "<img>"},
    {"id": 4, "question": "Quel est le langage utilisé pour styliser une page web ?", "choices": ["Python", "CSS", "SQL", "PHP"], "answer": "CSS"},
    {"id": 5, "question": "Quel est le système de gestion de version le plus utilisé ?", "choices": ["Git", "SVN", "Mercurial", "Dropbox"], "answer": "Git"},
]

@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        score = 0
        for q in quiz_questions:
            user_answer = request.form.get(str(q["id"]))
            if user_answer == q["answer"]:
                score += 1
        return render_template("resul.html", score=score, total=len(quiz_questions))
    return render_template("quiz.html", questions=quiz_questions)

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

# --- Lancement ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)





