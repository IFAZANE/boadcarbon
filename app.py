from flask import Flask, render_template, jsonify, redirect, url_for, request, session, flash
import psycopg2
import psycopg2.extras
import json
from flask_sqlalchemy import SQLAlchemy
import random



app = Flask(__name__)
app.secret_key = 'supersecretkey'  # pour gérer les sessions

# Config PostgreSQL
DB_HOST = "localhost"
DB_NAME = "BOAD_Carbone"
DB_USER = "postgres"
DB_PASS = "baba"

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ➕ Modèle pour les statistiques
class Statistique(db.Model):
    __tablename__ = 'statistiques'
    id = db.Column(db.Integer, primary_key=True)
    nb_projets = db.Column(db.Integer, nullable=False)
    co2_reduit = db.Column(db.Float, nullable=False)
    gain_financier = db.Column(db.Float, nullable=False)

# 🔐 Identifiants de connexion admin
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password"


# 🔁 Connexion DB psycopg2
def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )



def table_exists(cur, table_name):
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = %s
        );
    """, (table_name,))
    return cur.fetchone()[0]




def get_transport_data():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    base_donnees = {}

    # Tables classées par scope, type de transport, et mode (routier, aérien, etc.)
    tables_info = {
        "scope_1": {
            "personne": {
                "routier": "transportroutierpersonnes1"
                # "aérien": "transportaerienpersonnes1",
                # "maritime": "transportmaritimepersonnes1",
                # "ferroviaire": "transportferroviairepersonnes1"
            },
            "marchandise": {
                "routier": "transportroutiermarchandise1"
                # "aérien": "transportaerienmarchandise1",
                # "maritime": "transportmaritimemarchandise1",
                # "ferroviaire": "transportferroviairemarchandise1"
            }
        },
        "scope_2": {
            "personne": {
                "routier": "transportroutierpersonnes2"
                # "aérien": "transportaerienpersonnes2",
                # "maritime": "transportmaritimepersonnes2",
                # "ferroviaire": "transportferroviairepersonnes2"
            },
            "marchandise": {
                "routier": "transportroutiermarchandise2"
                # "aérien": "transportaerienmarchandise2"
                # "maritime": "transportmaritimemarchandise2",
                # "ferroviaire": "transportferroviairemarchandise2"
            }
        },
        "scope_3": {
            "personne": {
                "routier": "transportroutierpersonnes3",
                "aérien": "transportaerienpersonnes3",
                 "maritime": "transportmaritimepersonnes3",
                "ferroviaire": "transportferroviairepersonnes3"
            },
            "marchandise": {
                "routier": "transportroutiermarchandise3",
                "aérien": "transportaerienmarchandise3",
                "maritime": "transportmaritimemarchandise3",
                "ferroviaire": "transportferroviairemarchandise3"
            }
        }
    }

    for scope, types in tables_info.items():
        base_donnees[scope] = {}
        for type_transport, modes in types.items():
            base_donnees[scope][type_transport] = {}
            for mode, table in modes.items():
                base_donnees[scope][type_transport][mode] = []
                if table is not None:
                    cur.execute(f"SELECT id, nom, description, emission FROM {table};")
                    lignes = cur.fetchall()
                    for ligne in lignes:
                        base_donnees[scope][type_transport][mode].append({
                            "id": ligne["id"],
                            "nom": ligne["nom"],
                            "facteur": float(ligne["emission"]),
                            "description": ligne["description"]
                        })

    cur.close()
    conn.close()
    return base_donnees



@app.route("/transport")
def transport():
    data = get_transport_data()
    return render_template("transport.html", engins_json=json.dumps(data))





def get_energie_data():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Récupère les scopes
    cur.execute("SELECT id, nom FROM scope ORDER BY id;")
    scopes = cur.fetchall()

    data = {}

    for scope in scopes:
        scope_nom = scope['nom'].lower().replace(" ", "_")
        data[scope_nom] = {}

        # 🔹 Énergies bioénergies classiques
        cur.execute("""
            SELECT nom, emission, description
            FROM energiebioenergie
            WHERE scope_id = %s;
        """, (scope['id'],))
        rows = cur.fetchall()

        for row in rows:
            if row['emission'] is not None:
                data[scope_nom].setdefault("Énergie", []).append({
                    "nom": row['nom'],
                    "facteur": float(row['emission']),
                    "description": row['description'],
                    "unite": "U"
                })

        # 🔸 Électricité UEMOA – uniquement pour scope 2
        if scope['id'] == 2:
            cur.execute("""
                SELECT nom, emission, description
                FROM electriciteuemoa2
                WHERE scope_id = %s;
            """, (scope['id'],))
            rows = cur.fetchall()

            for row in rows:
                if row['emission'] is not None:
                    data[scope_nom].setdefault("Électricité UEMOA", []).append({
                        "nom": row['nom'],
                        "facteur": float(row['emission']),
                        "description": row['description'],
                        "unite": "kWh"
                    })

        # 🔸 Électricité Scope 3 – table electricite3
        if scope['id'] == 3:
            cur.execute("""
                SELECT nom, emission, description
                FROM electricite3
                WHERE scope_id = %s;
            """, (scope['id'],))
            rows = cur.fetchall()

            for row in rows:
                if row['emission'] is not None:
                    data[scope_nom].setdefault("Électricité", []).append({
                        "nom": row['nom'],
                        "facteur": float(row['emission']),
                        "description": row['description'],
                        "unite": "kWh"
                    })

    cur.close()
    conn.close()

    return data




@app.route('/energie')
def energie():
    base_donnees_energie = get_energie_data()
    return render_template('energie.html', engins_energie=base_donnees_energie)









def safe_value(val, default=""):
    if val is None:
        return default
    try:
        if isinstance(val, (str, int, float)):
            return val
        return str(val)
    except Exception:
        return default



def get_equipements_data():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT id, nom FROM scope ORDER BY id;")
    scopes = cur.fetchall()

    categories = {
        "Agriculture": "equipementsagriculture3",
        "Construction(BTP & Meubles)": "equipementsconstruction3",
        "Électrique/IT": "equipementselectriqueit3",
        "Plastique": "equipementsplastique3",
        "Papier/Carton": "equipementspapiercarton3",
        "Autre": "equipementsautre3",
        "Santé": "equipementssante3",
        "Déchets": "equipementsdechet3"

    }

    data = {}

    for scope in scopes:
        scope_nom = scope['nom'].lower().replace(" ", "_")
        data[scope_nom] = {}

        for categorie_nom, table in categories.items():
            try:
                cur.execute(f"""
                    SELECT nom, emission, description
                    FROM {table}
                    WHERE scope_id = %s;
                """, (scope['id'],))
                rows = cur.fetchall()
            except psycopg2.Error as e:
                conn.rollback()
                print(f"Erreur SQL sur la table {table} : {e}")
                rows = []

            data[scope_nom][categorie_nom] = []
            for row in rows:
                data[scope_nom][categorie_nom].append({
                    "nom": safe_value(row['nom']),
                    "facteur": float(row['emission']) if row['emission'] is not None else 0.0,
                    "description": safe_value(row['description']),
                    "unite": "U"
                })

    cur.close()
    conn.close()
    return data

@app.route('/equipements')
def equipements():
    base_donnees_equipements = get_equipements_data()

    try:
        base_donnees_json = json.dumps(base_donnees_equipements)
    except TypeError as e:
        print("Erreur JSON:", e)
        base_donnees_json = "{}"

    return render_template('equipements.html', engins_equipements=get_equipements_data())







@app.route("/resultat", methods=["GET", "POST"])
def resultat():
    user_info = {
        "prenom": session.get("prenom", ""),
        "nom": session.get("nom", ""),
        "email": session.get("email", ""),
        "telephone": session.get("telephone", ""),
        "nom_projet": session.get("nom_projet", ""),
        "duree_projet": session.get("duree_projet", "")
    }
    return render_template("resultat.html", user_info=user_info)









@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USERNAME and request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            flash("Identifiant ou mot de passe incorrect", "error")
    return render_template("login.html")


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        nb_projets = int(request.form['nb_projets'])
        co2_reduit = float(request.form['co2_reduit'])
        gain_financier = float(request.form['gain_financier'])

        new_stat = Statistique(
            nb_projets=nb_projets,
            co2_reduit=co2_reduit,
            gain_financier=gain_financier
        )
        db.session.add(new_stat)
        db.session.commit()
        flash("Statistiques enregistrées avec succès.")
        return redirect(url_for('index'))

    return render_template("admin.html")


@app.route('/')
def index():
    # Récupérer la dernière stat admin
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT nb_projets, co2_reduit, gain_financier FROM statistiques ORDER BY id DESC LIMIT 1")
        stat = cur.fetchone()
    except:
        stat = None

    cur.close()
    conn.close()

    return render_template('index.html', stat=stat)



def get_arbres_data():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    arbres = {}

    cur.execute("SELECT nom_arbre, type_stock, valeur FROM arbres_stock_c;")
    rows = cur.fetchall()

    for row in rows:
        nom = row["nom_arbre"]
        type_stock = row["type_stock"]
        valeur = row["valeur"]

        if nom not in arbres:
            arbres[nom] = {}

        arbres[nom][type_stock] = {
            "facteur": float(valeur),
            "unite": "u",  # unité par défaut
            "description": ""  # tu peux remplir si tu as un champ description
        }

    cur.close()
    conn.close()

    # On transforme en liste d'objets pour correspondre à l'ancien format
    arbres_list = [{"nom": nom, "maturites": maturites} for nom, maturites in arbres.items()]
    return arbres_list


@app.route('/arbres')
def arbres():
    arbres = get_arbres_data()
    return render_template('arbres.html', arbres=arbres)





@app.route('/apropos')
def apropos():
    return render_template('apropos.html')


@app.route('/aide')
def aide():
    return render_template('aide.html')




from datetime import datetime
app.secret_key = "secret123"  # pour les messages flash

@app.context_processor
def inject_now():
    return {'current_year': datetime.now().year}

@app.route('/contact', methods=['GET'])
def contact():
    return render_template('contact.html')

@app.route('/envoyer_contact', methods=['POST'])
def envoyer_contact():
    nom = request.form['nom']
    email = request.form['email']
    message = request.form['message']

    # TODO : ajouter en base de données ou envoyer par mail ici

    flash("Votre message a bien été envoyé. Merci !", "success")
    return redirect(url_for('contact'))








# @app.route("/inscription", methods=["GET", "POST"])
# def inscription():
#     if request.method == "POST":
#         session["prenom"] = request.form["prenom"]
#         session["nom"] = request.form["nom"]
#         session["email"] = request.form["email"]
#         session["password"] = request.form["password"]
#         session["projet"] = request.form["projet"]
#
#         # Génère le code et le stocke
#         code = str(random.randint(100000, 999999))
#         session["code"] = code
#
#         # Redirige vers la page d'affichage du code
#         return redirect("/code")
#     return render_template("inscription.html")


import re

@app.route("/inscriptionclient", methods=["GET", "POST"])
def inscriptionclient():
    errors = {}
    if request.method == "POST":
        form_data = request.form
        errors = valider_formulaire(form_data)

        if not errors:
            # Sauvegarder en session (ou en base si besoin)
            session["prenom"] = form_data.get("prenom", "").strip()
            session["nom"] = form_data.get("nom", "").strip()
            session["email"] = form_data.get("email", "").strip()
            session["telephone"] = form_data.get("telephone", "").strip()
            session["nom_projet"] = form_data.get("nom_projet", "").strip()
            session["duree_projet"] = form_data.get("duree_projet", "").strip()
            session["password"] = form_data.get("password", "").strip()

            # --- Réinitialisation des données précédentes ---
            keys_to_clear = ["transport", "energie", "equipements", "arbres"]
            for key in keys_to_clear:
                session.pop(key, None)

            # Redirection directe vers la page transport (plus de code de vérification)
            return redirect(url_for("transport"))

    return render_template("inscriptionclient.html", errors=errors)





@app.route("/verification", methods=["GET", "POST"])
def verification():
    if request.method == "POST":
        code_saisi = request.form.get("code", "")
        if code_saisi == session.get("code"):
            return redirect(url_for("transport"))
        else:
            flash("Code invalide. Veuillez réessayer.", "error")
            return render_template("verification.html"), 403
    return render_template("verification.html")

# Fonction de validation du formulaire (inchangée)
def valider_formulaire(data):
    erreurs = {}

    nom = data.get('nom', '').strip()
    email = data.get('email', '').strip()
    telephone = data.get('telephone', '').strip()
    nom_projet = data.get('nom_projet', '').strip()

    if not nom:
        erreurs['nom'] = "Le nom est obligatoire."
    elif not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ \-']{2,50}$", nom):
        erreurs['nom'] = "Nom invalide (lettres, espaces, '-' et apostrophes autorisés)."

    if not email:
        erreurs['email'] = "L'adresse e-mail est obligatoire."
    elif not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        erreurs['email'] = "Adresse e-mail invalide."

    if not telephone:
        erreurs['telephone'] = "Le numéro de téléphone est obligatoire."
    elif not re.match(r"^\+?[0-9\s\-]{6,20}$", telephone):
        erreurs['telephone'] = "Numéro de téléphone invalide."

    if not nom_projet:
        erreurs['nom_projet'] = "Le nom du projet est obligatoire."
    elif len(nom_projet) < 2 or len(nom_projet) > 80:
        erreurs['nom_projet'] = "Le nom du projet doit comporter entre 2 et 80 caractères."

    return erreurs




if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Créera la table 'statistiques' si elle n'existe pas
    app.run(debug=True)
