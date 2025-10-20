import os
import calendar
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory
)

# --- Configuration de base ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "joegoat532005mmaPK")

# --- Base de données SQLite locale ---
DB_PATH = "etudiants.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table utilisateur
    c.execute("""
        CREATE TABLE IF NOT EXISTS utilisateur (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'etudiant'
        )
    """)

    # Table résultats
    c.execute("""
        CREATE TABLE IF NOT EXISTS resultat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT,
            matricule TEXT,
            matiere TEXT,
            note REAL
        )
    """)

    conn.commit()
    conn.close()

init_db()

# --- Dossiers upload ---
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
VIDEO_EXT = {"mp4", "webm", "ogg"}
PDF_EXT = {"pdf"}

# --- Informations administrateur ---
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "joe@mail.mma")
ADMIN_CODE = os.environ.get("ADMIN_CODE", "joe2005")


# ------------------ PAGES PUBLIQUES ------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/homes")
def homes():
    return render_template("homes.html")

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


# ------------------ INSCRIPTION ------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email et mot de passe requis.", "warning")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO utilisateur (nom, email, password) VALUES (?, ?, ?)", (nom, email, hashed_pw))
            conn.commit()
            flash("✅ Compte créé avec succès.", "success")
        except sqlite3.IntegrityError:
            flash("⚠ Cet email est déjà utilisé.", "warning")
        finally:
            conn.close()

        return redirect(url_for("login"))
    return render_template("register.html")


# ------------------ CONNEXION ------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, nom, password, role FROM utilisateur WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["user_nom"] = user[1]
            session["user_role"] = user[3]
            flash("Connexion réussie.", "success")
            return redirect(url_for("quiz")) if user[3] == "etudiant" else redirect(url_for("index"))
        else:
            flash("Identifiants incorrects.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Déconnexion réussie.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ------------------ LISTE MATIERES ------------------

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


# ------------------ LISTE DES ÉTUDIANTS ------------------

@app.route("/etudiants")
def liste_etudiants():
    if "user_id" not in session:
        return redirect(url_for("logi"))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nom, email, role FROM utilisateur")
    users = c.fetchall()
    conn.close()
    return render_template("liste_etudiants.html", users=users)


# ------------------ ADMIN ------------------

@app.route("/logi", methods=["GET", "POST"])
def logi():
    if request.method == "POST":
        email = request.form.get("email")
        code = request.form.get("code")
        if email == ADMIN_EMAIL and code == ADMIN_CODE:
            session["is_admin"] = True
            flash("Bienvenue administrateur !")
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


# ------------------ GESTION FICHIERS ------------------

def allowed_file(filename, filetype):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return (ext in VIDEO_EXT) if filetype == "video" else (ext in PDF_EXT)


@app.route("/Admin/add_video", methods=["GET", "POST"])
def add_video():
    if not session.get("is_admin"):
        return redirect(url_for("logi"))
    if request.method == "POST":
        file = request.files.get("file")
        if file and allowed_file(file.filename, "video"):
            safe_name = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, safe_name)
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
            safe_name = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, safe_name)
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


# ------------------ VIDEOS / PDF ------------------

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


# ------------------ CALENDRIER ------------------

@app.route("/calendrier")
def calendrier():
    year = datetime.now().year
    month = datetime.now().month
    today = datetime.now().day
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)
    return render_template("calendrier.html", weeks=weeks, year=year, month=month, today=today)


# ------------------ QUIZ ------------------

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
     "choices": ["Git", "SVN", "Mercurial", "Dropbox"], "answer": "Git"},
]

@app.route("/page")
def page():
    return render_template("page.html")
    
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


@app.route("/quizz", methods=["GET", "POST"])
def quizz():
    if request.method == "POST":
        questions_list = external_questions or []
        score = 0
        for q in questions_list:
            user_answer = request.form.get(str(q["id"]))
            if user_answer == q["answer"]:
                score += 1
        return render_template("result.html", score=score, total=len(questions_list))
    return render_template("quizz.html", questions=external_questions)

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)


