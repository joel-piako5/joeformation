import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt
from datetime import datetime
import calendar
import boto3
from questions import questions  # ton fichier questions.py

# --- CONFIGURATION FLASK ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "joegoat532005mmaPK")

# --- DATABASE POSTGRESQL ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///etudiants.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

bcrypt = Bcrypt(app)

# --- S3 CONFIG ---
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
S3_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
S3_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
s3 = boto3.client(
    's3',
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY
)

VIDEO_EXT = {"mp4", "webm", "ogg"}
PDF_EXT = {"pdf"}

# --- ADMIN ---
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "joe@mail.mma")
ADMIN_CODE = os.environ.get("ADMIN_CODE", "joe2005")

# --- MODELES ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(10), default='etudiant')  # admin ou etudiant

class Resultat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    matricule = db.Column(db.String(50))
    matiere = db.Column(db.String(100))
    note = db.Column(db.Float)

# --- FONCTIONS UTILITAIRES ---
def allowed_file(filename, filetype):
    ext = filename.rsplit(".", 1)[-1].lower()
    return (ext in VIDEO_EXT if filetype == "video" else ext in PDF_EXT)

def upload_to_s3(file, filename):
    s3.upload_fileobj(file, S3_BUCKET, filename)
    return f"https://{S3_BUCKET}.s3.amazonaws.com/{filename}"

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

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

@pp.route('/dashboard')
def dashboard():
    return render_template("dashboard.html")

# --- INSCRIPTION ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form['nom']
        email = request.form['email']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        user = User(nom=nom, email=email, password=hashed_pw)
        try:
            db.session.add(user)
            db.session.commit()
            flash('✅ Compte créé avec succès.', 'success')
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('❌ Cet email existe déjà.', 'danger')
    return render_template('register.html')

# --- CONNEXION ---
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
            return redirect(url_for('quiz')) if user.role == 'etudiant' else redirect(url_for('menu'))
        else:
            flash('Identifiants incorrects.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Déconnexion réussie.', 'info')
    return redirect(url_for('login'))

# --- DASHBOARD / MENU ADMIN ---
@app.route("/menu")
def menu():
    if not session.get("is_admin"):
        flash("Accès refusé. Veuillez vous connecter.")
        return redirect(url_for("logi"))
    return render_template("menu.html")

@app.route("/logi", methods=["GET", "POST"])
def logi():
    if request.method == "POST":
        email = request.form.get("email")
        code = request.form.get("code")
        if email == ADMIN_EMAIL and code == ADMIN_CODE:
            session["is_admin"] = True
            flash("Bienvenue l'administrateur !")
            return redirect(url_for("menu"))
        else:
            flash("Identifiants incorrects.")
    return render_template("logi.html")

@app.route("/logo")
def logo():
    session.pop("is_admin", None)
    flash("Déconnecté.")
    return redirect(url_for("index"))

# --- UPLOAD VIDEO / PDF ---
@app.route("/Admin/add_video", methods=["GET", "POST"])
def add_video():
    if not session.get("is_admin"):
        return redirect(url_for("logi"))
    if request.method == "POST":
        file = request.files.get("file")
        if file and allowed_file(file.filename, "video"):
            filename = secure_filename(file.filename)
            file_url = upload_to_s3(file, filename)
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
            filename = secure_filename(file.filename)
            file_url = upload_to_s3(file, filename)
            flash("PDF ajouté !")
            return redirect(url_for("menu"))
        else:
            flash("Format PDF invalide.")
    return render_template("add_pdf.html")

# --- LISTES / UTILISATEURS ---
@app.route('/utilisateurs')
def utilisateurs():
    if 'user_nom' not in session or session['user_role'] != 'admin':
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

# --- VIDEOS / PDF PUBLIC ---
@app.route("/videos")
def videos():
    # Ici, si tu veux, tu peux lister les fichiers depuis S3
    # Pour simplifier, on met juste un lien vide ou tu peux stocker les URLs dans la DB
    return render_template("videos.html", files=[])

@app.route("/pdfs")
def pdfs():
    return render_template("pdfs.html", files=[])

# --- QUIZ ---
quiz_questions = [
    {"id": 1, "question": "Quel langage est utilisé pour le développement web côté serveur ?", "choices": ["HTML", "Python", "CSS", "Photoshop"], "answer": "Python"},
    {"id": 2, "question": "Quel protocole est utilisé pour naviguer sur le web ?", "choices": ["FTP", "HTTP", "SMTP", "SSH"], "answer": "HTTP"},
    {"id": 3, "question": "Quelle balise HTML est utilisée pour insérer une image ?", "choices": ["<div>", "<img>", "<link>", "<span>"], "answer": "<img>"},
    {"id": 4, "question": "Quel est le langage utilisé pour styliser une page web ?", "choices": ["Python", "CSS", "SQL", "PHP"], "answer": "CSS"},
    {"id": 5, "question": "Quel est le système de gestion de version le plus utilisé ?", "choices": ["Git", "SVN", "Mercurial", "Dropbox"], "answer": "Git"}
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

# --- CALENDRIER ---
@app.route('/calendrier')
def calendrier():
    year = datetime.now().year
    month = datetime.now().month
    today = datetime.now().day
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)
    return render_template('calendrier.html', weeks=weeks, year=year, month=month, today=today)

# --- LANCEMENT ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

