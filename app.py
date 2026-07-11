"""
Kaddu — Vote confidentiel pour associations, coopératives, tontines, syndicats, amicales.

Principe : chaque bulletin est CHIFFRÉ avant d'être stocké. Le décompte est calculé
directement sur les bulletins chiffrés (chiffrement homomorphe de Paillier), et seul
le TOTAL final est déchiffré. Personne — ni le serveur, ni l'organisateur — ne voit
les votes individuels. C'est la version « simple » de l'idée portée par la techno Zama.
"""
import os
import json
import time
import secrets
import sqlite3
from contextlib import closing

from flask import (
    Flask, request, redirect, url_for, render_template,
    make_response, abort, flash, send_from_directory
)
from phe import paillier

# --------------------------------------------------------------------------- #
#  Configuration
# --------------------------------------------------------------------------- #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("KADDU_DB", os.path.join(BASE_DIR, "kaddu.db"))
KEY_BITS = int(os.environ.get("KADDU_KEY_BITS", "1536"))  # clé Paillier (sécurité)

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", secrets.token_hex(16))
app.jinja_env.globals["ANNEE"] = time.strftime("%Y")


# --------------------------------------------------------------------------- #
#  Base de données
# --------------------------------------------------------------------------- #
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(db()) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id           TEXT PRIMARY KEY,
                admin_token  TEXT NOT NULL,
                title        TEXT NOT NULL,
                question     TEXT NOT NULL,
                options      TEXT NOT NULL,       -- JSON: ["Awa", "Modou", ...]
                pub_n        TEXT NOT NULL,       -- clé publique Paillier (n)
                priv_p       TEXT NOT NULL,       -- clé privée (p)
                priv_q       TEXT NOT NULL,       -- clé privée (q)
                created_at   INTEGER NOT NULL,
                closed       INTEGER NOT NULL DEFAULT 0,
                results      TEXT                 -- JSON: [nb, nb, ...] après clôture
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ballots (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id    TEXT NOT NULL,
                vector     TEXT NOT NULL,         -- JSON: [{c,e}, {c,e}, ...] chiffré
                created_at INTEGER NOT NULL
            )
        """)


# Initialise la base au CHARGEMENT du module — indispensable sous gunicorn.
init_db()


# --------------------------------------------------------------------------- #
#  Chiffrement homomorphe (Paillier)
# --------------------------------------------------------------------------- #
def new_keypair():
    pub, priv = paillier.generate_paillier_keypair(n_length=KEY_BITS)
    return pub, priv


def pub_from(n):
    return paillier.PaillierPublicKey(n=int(n))


def priv_from(pub, p, q):
    return paillier.PaillierPrivateKey(pub, int(p), int(q))


def enc_to_json(enc):
    return {"c": str(enc.ciphertext(be_secure=True)), "e": enc.exponent}


def json_to_enc(pub, d):
    return paillier.EncryptedNumber(pub, int(d["c"]), int(d["e"]))


def encrypt_vote(pub, n_options, choice):
    """Renvoie un vecteur chiffré : 1 pour l'option choisie, 0 pour les autres."""
    vec = []
    for i in range(n_options):
        vec.append(enc_to_json(pub.encrypt(1 if i == choice else 0)))
    return vec


def tally(pub, priv, ballots, n_options):
    """Additionne les bulletins CHIFFRÉS puis déchiffre seulement les totaux."""
    totals = []
    for i in range(n_options):
        acc = pub.encrypt(0)
        for b in ballots:
            acc = acc + json_to_enc(pub, b[i])
        totals.append(int(priv.decrypt(acc)))
    return totals


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def get_poll(poll_id):
    with closing(db()) as conn:
        row = conn.execute("SELECT * FROM polls WHERE id = ?", (poll_id,)).fetchone()
    return row


def count_ballots(poll_id):
    with closing(db()) as conn:
        r = conn.execute("SELECT COUNT(*) c FROM ballots WHERE poll_id = ?", (poll_id,)).fetchone()
    return r["c"]


def base_url():
    return request.url_root.rstrip("/")


# --------------------------------------------------------------------------- #
#  Routes
# --------------------------------------------------------------------------- #
@app.route("/ping")
def ping():
    return "ok", 200


@app.route("/sw.js")
def service_worker():
    # Servi à la racine pour couvrir toute l'app (scope "/").
    resp = make_response(send_from_directory(os.path.join(BASE_DIR, "static"), "sw.js"))
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/creer", methods=["GET", "POST"])
def creer():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        question = (request.form.get("question") or "").strip()
        options = [o.strip() for o in request.form.getlist("option") if o.strip()]
        if not title or not question or len(options) < 2:
            flash("Donne un titre, une question et au moins 2 choix.")
            return render_template("creer.html",
                                   title=title, question=question, options=options or ["", ""])
        if len(options) > 8:
            options = options[:8]

        poll_id = secrets.token_urlsafe(5).replace("-", "a").replace("_", "b")
        admin_token = secrets.token_urlsafe(16)
        pub, priv = new_keypair()
        with closing(db()) as conn, conn:
            conn.execute(
                "INSERT INTO polls (id, admin_token, title, question, options, "
                "pub_n, priv_p, priv_q, created_at, closed) "
                "VALUES (?,?,?,?,?,?,?,?,?,0)",
                (poll_id, admin_token, title, question, json.dumps(options),
                 str(pub.n), str(priv.p), str(priv.q), int(time.time())),
            )
        return redirect(url_for("partage", poll_id=poll_id, t=admin_token))

    return render_template("creer.html", title="", question="", options=["", ""])


@app.route("/partage/<poll_id>")
def partage(poll_id):
    poll = get_poll(poll_id)
    if not poll:
        abort(404)
    admin_token = request.args.get("t", "")
    if admin_token != poll["admin_token"]:
        # On n'affiche le lien admin que si le bon jeton est fourni.
        admin_token = ""
    vote_url = f"{base_url()}{url_for('voter', poll_id=poll_id)}"
    admin_url = (f"{base_url()}{url_for('admin', poll_id=poll_id, t=poll['admin_token'])}"
                 if admin_token else "")
    return render_template("partage.html", poll=poll, vote_url=vote_url, admin_url=admin_url)


@app.route("/v/<poll_id>", methods=["GET", "POST"])
def voter(poll_id):
    poll = get_poll(poll_id)
    if not poll:
        abort(404)
    options = json.loads(poll["options"])
    already = request.cookies.get(f"kv_{poll_id}") == "1"

    if poll["closed"]:
        return render_template("voter.html", poll=poll, options=options,
                               closed=True, already=already)

    if request.method == "POST":
        if already:
            return redirect(url_for("merci", poll_id=poll_id))
        try:
            choice = int(request.form.get("choice", "-1"))
        except ValueError:
            choice = -1
        if choice < 0 or choice >= len(options):
            flash("Choisis une option pour voter.")
            return render_template("voter.html", poll=poll, options=options,
                                   closed=False, already=False)
        pub = pub_from(poll["pub_n"])
        vector = encrypt_vote(pub, len(options), choice)
        with closing(db()) as conn, conn:
            conn.execute(
                "INSERT INTO ballots (poll_id, vector, created_at) VALUES (?,?,?)",
                (poll_id, json.dumps(vector), int(time.time())),
            )
        resp = make_response(redirect(url_for("merci", poll_id=poll_id)))
        resp.set_cookie(f"kv_{poll_id}", "1", max_age=60 * 60 * 24 * 365, samesite="Lax")
        return resp

    return render_template("voter.html", poll=poll, options=options,
                           closed=False, already=already)


@app.route("/v/<poll_id>/merci")
def merci(poll_id):
    poll = get_poll(poll_id)
    if not poll:
        abort(404)
    return render_template("merci.html", poll=poll)


@app.route("/r/<poll_id>")
def resultat(poll_id):
    poll = get_poll(poll_id)
    if not poll:
        abort(404)
    options = json.loads(poll["options"])
    if not poll["closed"]:
        return render_template("resultat.html", poll=poll, options=options,
                               ready=False, participants=count_ballots(poll_id))
    results = json.loads(poll["results"] or "[]")
    total = sum(results) if results else 0
    rows = []
    for i, opt in enumerate(options):
        n = results[i] if i < len(results) else 0
        pct = round(n / total * 100) if total else 0
        rows.append({"label": opt, "n": n, "pct": pct})
    rows_sorted = sorted(rows, key=lambda r: r["n"], reverse=True)
    win = rows_sorted[0]["label"] if rows_sorted and total else None
    return render_template("resultat.html", poll=poll, options=options, ready=True,
                           rows=rows, rows_sorted=rows_sorted, total=total, win=win)


@app.route("/admin/<poll_id>")
def admin(poll_id):
    poll = get_poll(poll_id)
    if not poll:
        abort(404)
    if request.args.get("t", "") != poll["admin_token"]:
        abort(403)
    options = json.loads(poll["options"])
    vote_url = f"{base_url()}{url_for('voter', poll_id=poll_id)}"
    return render_template("admin.html", poll=poll, options=options,
                           participants=count_ballots(poll_id), vote_url=vote_url,
                           token=poll["admin_token"])


@app.route("/admin/<poll_id>/clore", methods=["POST"])
def clore(poll_id):
    poll = get_poll(poll_id)
    if not poll:
        abort(404)
    if request.form.get("t", "") != poll["admin_token"]:
        abort(403)
    options = json.loads(poll["options"])
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT vector FROM ballots WHERE poll_id = ?", (poll_id,)
        ).fetchall()
    ballots = [json.loads(r["vector"]) for r in rows]
    pub = pub_from(poll["pub_n"])
    priv = priv_from(pub, poll["priv_p"], poll["priv_q"])
    results = tally(pub, priv, ballots, len(options)) if ballots else [0] * len(options)
    with closing(db()) as conn, conn:
        conn.execute("UPDATE polls SET closed = 1, results = ? WHERE id = ?",
                     (json.dumps(results), poll_id))
    return redirect(url_for("resultat", poll_id=poll_id))


@app.route("/rejoindre", methods=["GET", "POST"])
def rejoindre():
    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        # Autorise soit l'ID, soit une URL collée.
        if "/v/" in code:
            code = code.rsplit("/v/", 1)[-1].split("/")[0].split("?")[0]
        elif "/" in code:
            code = code.rstrip("/").rsplit("/", 1)[-1]
        if code and get_poll(code):
            return redirect(url_for("voter", poll_id=code))
        flash("Code introuvable. Vérifie et réessaie.")
    return render_template("rejoindre.html")


@app.errorhandler(404)
def not_found(e):
    return render_template("erreur.html", code=404,
                           msg="Ce vote n'existe pas ou a été supprimé."), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("erreur.html", code=403,
                           msg="Accès réservé à l'organisateur du vote."), 403


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
