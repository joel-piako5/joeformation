# app.py
import os
import calendar
from datetime import datetime, date
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError
from uuid import uuid4
from questions import questions  # tu avais déjà ce fichier

# ---------- Configuration ----------
app = Flask(__name__)
# secret via env for prod ; fallback temporaire
app.secret_key = os.environ.get("SECRET_KEY", "joegoat532005mmaPK")

# DATABASE: sur Render définis DATABASE_URL (Postgres). Fallback sqlite pour dev local.
database_url = os.environ.get("DATABASE_URL", "sqlite:///etudiants.db")
# Render fournit parfois DATABASE_URL qui commence par postgres:// --> SQLAlchemy attend postgresql://
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Uploads
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# Allowed extensions
VIDEO_EXT = {"mp4", "webm", "ogg"}
PDF_EXT = {"pdf"}

# S3 optional (recommended for Render production)
USE_S3 = bool(os.environ.get("S3_BUCKET"))  # si S3_BUCKET est present on utilise S3
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")  # optionnel

# ---------- Extensions ----------
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# ---------- Modèles ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='etudiant')  # 'admin' ou 'etudiant'

class Resultat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    matricule = db.Column(db.String(50))
    matiere = db.Column(db.String(100))
    note = db.Column(db.Float)

# ---------- Helpers ----------
def allowed_file(filename, filetype):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower()
    if filetype == "video":
        return ext in VIDEO_EXT
    elif filetype == "pdf":
        return ext in PDF_EXT
    return False

def unique_filename(filename):
    name = secure_filename(filename)
    uid = uuid4().hex[:8]
    return f"{uid}_{name}"

# S3 upload helper (optionel)
def upload_file_to_s3(file_stream, filename, content_type):
    if not USE_S3:
        raise RuntimeError("S3 non configuré")
    s3 = boto3.client(
        "s3",
        region_name=S3_REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
    )
    try:
        s3.upload_fileobj(
            Fileobj=file_stream,
            Bucket=S3_BUCKET,
            Key=filename,
            ExtraArgs={"ContentType": content_type, "ACL": "private"}
        )
        # retour le chemin ou key
        return filename
    except (BotoCoreError, NoCredentialsError) as e:
        app.logger.error(f"S3 upload error: {e}")
        raise

def s3_file_url(key):
    # URL privée/ publique selon configuration ; ici on renvoie la key pour que l'app sache quoi demander
    return f"s3://{S3_BUCKET}/{key}"

# Admin credentials (pour ton mécanisme simple)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "joe@mail.mma")
ADMIN_CODE = os.environ.get("ADMIN_CODE", "joe2005")

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")
        # ici tu peux envoyer un email ou stocker dans DB
        app.logger.info(f"📩 Nouveau message de {name} ({email}) : {message}")
        flash("✅ Votre message a été envoyé avec succès !", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html")

@app.route("/histoire")
def histoire():
    return render_template("histoire.html")

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("profile.html")

# Inscription
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form.get('nom')
        email = request.form.get('email')
        password = request.form.get('password')
        if not nom or not email or not password:
            flash("Veuillez remplir tous les champs.", "warning")
            return redirect(url_for('register'))
        # Vérifier si email existe
        if User.query.filter_by(email=email).first():
            flash("Cet email est déjà utilisé.", "warning")
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(password)
        new_user = User(nom=nom, email=email, password=hashed_pw)
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('✅ Compte créé avec succès.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            app.logger.error(f"Erreur création utilisateur: {e}")
            db.session.rollback()
            flash("Erreur lors de la création du compte.", "danger")
            return redirect(url_for('register'))
    return render_template('register.html')

# Connexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_nom'] = user.nom
            session['user_role'] = user.role
            flash('Connexion réussie.', 'success')
            if user.role == 'etudiant':
                return redirect(url_for('quiz'))
            else:
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Identifiants incorrects.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

# Dashboard (exemple)
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Déconnexion réussie.', 'info')
    return redirect(url_for('login'))

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

@app.route('/resultats')
def resultats():
    return render_template('resultats.html')

# Utilisateurs - vue admin (protégée)
@app.route('/utilisateurs')
def utilisateurs():
    if session.get('user_role') != 'admin' and not session.get('is_admin'):
        flash("Accès refusé", "danger")
        return redirect(url_for('login'))
    users = User.query.all()
    return render_template('liste_etudiants.html', users=users)

@app.route('/etudiants')
def liste_etudiants():
    if "user_id" not in session:
        return redirect(url_for("login"))
    etudiants = User.query.all()
    return render_template('liste_etudiants.html', etudiants=etudiants)

# Pages d'accueil des cours
@app.route("/homes")
def homes():
    return render_template("homes.html")

# Connexion admin simple (ton système)
@app.route("/logi", methods=["GET", "POST"])
def logi():
    if request.method == "POST":
        email = request.form.get("email")
        code = request.form.get("code")
        if email == ADMIN_EMAIL and code == ADMIN_CODE:
            session["is_admin"] = True
            flash("Bienvenue l'administrateur joel !", "success")
            return redirect(url_for("menu"))
        else:
            flash("Identifiants incorrects.", "danger")
            return redirect(url_for("logi"))
    return render_template("logi.html")

# Déconnexion admin
@app.route("/logo")
def logo():
    session.pop("is_admin", None)
    flash("Déconnecté.", "info")
    return redirect(url_for("homes"))

@app.route("/menu")
def menu():
    if not session.get("is_admin"):
        flash("Accès refusé. Veuillez vous connecter.", "danger")
        return redirect(url_for("logi"))
    return render_template("menu.html")

# Ajouter vidéo (admin)
@app.route("/Admin/add_video", methods=["GET", "POST"])
def add_video():
    if not session.get("is_admin"):
        return redirect(url_for("logi"))
    if request.method == "POST":
        file = request.files.get("file")
        if file and allowed_file(file.filename, "video"):
            filename = unique_filename(file.filename)
            if USE_S3:
                try:
                    upload_file_to_s3(file, filename, file.content_type)
                    flash("Vidéo ajoutée sur S3 !", "success")
                except Exception:
                    flash("Erreur upload vidéo sur S3.", "danger")
                    return redirect(url_for("add_video"))
            else:
                path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(path)
                flash("Vidéo ajoutée (stockage local) !", "success")
            return redirect(url_for("menu"))
        else:
            flash("Format vidéo invalide.", "danger")
            return redirect(url_for("add_video"))
    return render_template("add_video.html")

# Ajouter PDF (admin)
@app.route("/Admin/add_pdf", methods=["GET", "POST"])
def add_pdf():
    if not session.get("is_admin"):
        return redirect(url_for("logi"))
    if request.method == "POST":
        file = request.files.get("file")
        if file and allowed_file(file.filename, "pdf"):
            filename = unique_filename(file.filename)
            if USE_S3:
                try:
                    upload_file_to_s3(file, filename, file.content_type)
                    flash("PDF ajouté sur S3 !", "success")
                except Exception:
                    flash("Erreur upload PDF sur S3.", "danger")
                    return redirect(url_for("add_pdf"))
            else:
                path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(path)
                flash("PDF ajouté (stockage local) !", "success")
            return redirect(url_for("menu"))
        else:
            flash("Format PDF invalide.", "danger")
            return redirect(url_for("add_pdf"))
    return render_template("add_pdf.html")

# Suppression (admin)
@app.route("/admin/delete", methods=["GET", "POST"])
def delete_file():
    if not session.get("is_admin"):
        return redirect(url_for("logi"))
    if request.method == "POST":
        filename = request.form.get("filename")
        if not filename:
            flash("Nom fichier manquant.", "warning")
            return redirect(url_for("delete_file"))
        if USE_S3:
            # suppression sur S3
            s3 = boto3.client(
                "s3",
                region_name=S3_REGION,
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
            )
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=filename)
                flash(f"{filename} supprimé de S3.", "success")
            except Exception as e:
                app.logger.error(f"S3 delete error: {e}")
                flash("Erreur suppression sur S3.", "danger")
        else:
            path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.exists(path):
                os.remove(path)
                flash(f"{filename} supprimé avec succès.", "success")
            else:
                flash("Fichier introuvable.", "warning")
        return redirect(url_for("delete_file"))

    # GET -> lister les fichiers
    if USE_S3:
        # liste rudimentaire : on retourne uniquement clé S3 (nécessite pagination si beaucoup)
        s3 = boto3.client(
            "s3",
            region_name=S3_REGION,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
        )
        try:
            resp = s3.list_objects_v2(Bucket=S3_BUCKET, MaxKeys=100)
            files = [obj['Key'] for obj in resp.get('Contents', [])]
        except Exception:
            files = []
    else:
        files = os.listdir(UPLOAD_FOLDER)
    return render_template("delete.html", files=files)

# VIDEOS PUBLIC
@app.route("/videos")
def videos():
    if USE_S3:
        s3 = boto3.client(
            "s3",
            region_name=S3_REGION,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
        )
        try:
            resp = s3.list_objects_v2(Bucket=S3_BUCKET, MaxKeys=100)
            files = [obj['Key'] for obj in resp.get('Contents', []) if obj['Key'].split(".")[-1].lower() in VIDEO_EXT]
        except Exception:
            files = []
    else:
        files = [f for f in os.listdir(UPLOAD_FOLDER) if f.split(".")[-1].lower() in VIDEO_EXT]
    return render_template("videos.html", files=files)

# PDFS PUBLIC
@app.route("/pdfs")
def pdfs():
    if USE_S3:
        s3 = boto3.client(
            "s3",
            region_name=S3_REGION,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
        )
        try:
            resp = s3.list_objects_v2(Bucket=S3_BUCKET, MaxKeys=100)
            files = [obj['Key'] for obj in resp.get('Contents', []) if obj['Key'].split(".")[-1].lower() in PDF_EXT]
        except Exception:
            files = []
    else:
        files = [f for f in os.listdir(UPLOAD_FOLDER) if f.split(".")[-1].lower() in PDF_EXT]
    return render_template("pdfs.html", files=files)

@app.route("/watch/<path:filename>")
def watch_video(filename):
    # si S3, ici tu pourrais générer un lien signé pour le streaming
    return render_template("watch_video.html", filename=filename)

@app.route("/view_pdf/<path:filename>")
def view_pdf(filename):
    return render_template("view_pdf.html", filename=filename)

# servir les fichiers locaux
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    if USE_S3:
        # si S3, soit tu génères un lien signé, soit tu empêches l'accès direct
        # pour l'instant on retourne 404 si on est en S3 (tu peux implémenter signed_url)
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=False)

# Calendrier
@app.route('/calendrier')
def calendrier():
    year = datetime.now().year
    month = datetime.now().month
    today = datetime.now().day
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)
    return render_template('calendrier.html', weeks=weeks, year=year, month=month, today=today)

# Quiz principal (ton code)
quiz_questions = [
    {
        "id": 1,
        "question": "Quel langage est utilisé pour le développement web côté serveur ?",
        "choices": ["HTML", "Python", "CSS", "Photoshop"],
        "answer": "Python"
    },
    {
        "id": 2,
        "question": "Quel protocole est utilisé pour naviguer sur le web ?",
        "choices": ["FTP", "HTTP", "SMTP", "SSH"],
        "answer": "HTTP"
    },
    {
        "id": 3,
        "question": "Quelle balise HTML est utilisée pour insérer une image ?",
        "choices": ["<div>", "<img>", "<link>", "<span>"],
        "answer": "<img>"
    },
    {
        "id": 4,
        "question": "Quel est le langage utilisé pour styliser une page web ?",
        "choices": ["Python", "CSS", "SQL", "PHP"],
        "answer": "CSS"
    },
    {
        "id": 5,
        "question": "Quel est le système de gestion de version le plus utilisé ?",
        "choices": ["Git", "SVN", "Mercurial", "Dropbox"],
        "answer": "Git"
    }
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

# Quiz d'entraînement (questions venant de questions.py)
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

# Route admin dashboard placeholder
@app.route("/admin")
def admin_dashboard():
    if not (session.get("is_admin") or session.get("user_role") == "admin"):
        flash("Accès admin requis.", "danger")
        return redirect(url_for("logi"))
    return render_template("admin_dashboard.html")

# ---------- Initialisation DB & run ----------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=(os.environ.get("FLASK_DEBUG") == "1"))
