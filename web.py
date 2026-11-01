import sqlite3, hashlib, secrets, html, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, quote

DOM = "ember.nv"
SESS = {}
DOSS = [("recu", "📥 Réception"), ("favoris", "⭐ Favoris"), ("envoyes", "📤 Envoyés"),
        ("archives", "🗂 Archives"), ("corbeille", "🗑 Corbeille"), ("tous", "✉ Tous les mails")]
REQ = {"recu": ("a=? AND corb=0 AND arch=0", 1), "favoris": ("a=? AND etoile=1 AND corb=0", 1),
       "envoyes": ("de=? AND corb_exp=0", 1), "archives": ("a=? AND arch=1 AND corb=0", 1),
       "corbeille": ("((a=? AND corb=1) OR (de=? AND corb_exp=1))", 2),
       "tous": ("((a=? AND corb=0) OR (de=? AND corb_exp=0))", 2)}
CSS = """*{box-sizing:border-box}body{font-family:Roboto,system-ui,sans-serif;background:#fff;color:#202124;margin:0}
main{max-width:42rem;margin:0 auto;padding-bottom:6rem}
.bar{display:flex;gap:.6rem;align-items:center;margin:.6rem;background:#fff3e0;border-radius:28px;padding:.3rem .5rem;position:sticky;top:.4rem;z-index:3}
.bar form{flex:1;margin:0}.bar input{width:100%;border:0;background:transparent;font:inherit;padding:.6rem .2rem;outline:0}
.ic{background:none;border:0;font-size:1.4rem;color:#5f6368;padding:.3rem .6rem;cursor:pointer}
.av{width:2.4rem;height:2.4rem;border-radius:50%;background:#f57c00;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:500;flex:none}
.dr{position:fixed;top:0;left:0;bottom:0;width:17rem;background:#fff;transform:translateX(-100%);transition:.2s;z-index:10;overflow:auto;box-shadow:2px 0 10px rgba(0,0,0,.25);padding:1rem 0}
body.o .dr{transform:none}#ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:9}body.o #ov{display:block}
.dh{font-size:1.5rem;padding:0 1.2rem 1rem}.dh span{color:#f57c00}.em{padding:1rem 1.2rem;color:#5f6368;font-size:.85rem;word-break:break-all}
.lk{display:block;width:100%;text-align:left;background:none;border:0;font:inherit;padding:.8rem 1.2rem;color:#202124;text-decoration:none;cursor:pointer;border-radius:0 24px 24px 0;margin-right:.6rem}
.lk.on{background:#ffe0b2;color:#bf360c;font-weight:700}
.row{display:flex;gap:.8rem;align-items:center;padding:.7rem 1rem;border-bottom:1px solid #f1f1f1;background:#fafafa}
.row.nl{background:#fff}.row.nl .t,.row.nl .sj{font-weight:700}
.mid{flex:1;min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;color:#202124;text-decoration:none}
.sn{color:#5f6368}.rt{display:flex;flex-direction:column;align-items:flex-end;font-size:.75rem;color:#5f6368}
.rt form{margin:0}.st{background:none;border:0;font-size:1.2rem;color:#f57c00;padding:.1rem;cursor:pointer}
.fab{position:fixed;right:1rem;bottom:1rem;background:#ffe0b2;color:#bf360c;border-radius:16px;padding:1rem 1.3rem;font-weight:500;text-decoration:none;box-shadow:0 3px 8px rgba(0,0,0,.25)}
.pad{padding:1rem}.card{border:1px solid #ffe0b2;border-radius:8px;padding:1rem 1.2rem;margin:.8rem 0}
h1{font-size:2rem;font-weight:400;text-align:center;margin:1.5rem 0 .5rem}h1 span{color:#f57c00}h2{font-size:1.2rem;font-weight:500;margin:.2rem 0 .6rem}
input.c,textarea{font:inherit;padding:.85rem;border:1px solid #ddd;border-radius:4px;width:100%;margin:.35rem 0}
input.c:focus,textarea:focus{outline:2px solid #f57c00;border-color:#f57c00}
button.b,.btn{font:inherit;background:#f57c00;color:#fff;border:0;border-radius:20px;padding:.6rem 1.3rem;font-weight:500;text-decoration:none;display:inline-block;cursor:pointer;margin:.2rem}
.btn.g{background:#fff;color:#e65100;border:1px solid #ffcc80}
.info{background:#fff3e0;color:#bf360c;padding:.7rem 1rem;margin:0 .6rem;border-radius:8px}
.hd{display:flex;gap:.2rem;align-items:center;padding:.4rem .6rem;border-bottom:1px solid #eee}.hd form{margin:0}.sp{flex:1}
pre{white-space:pre-wrap;font:inherit;color:#3c4043;margin:1rem 0}small,.meta{color:#5f6368}"""

def db():
    c = sqlite3.connect("ember.db")
    c.execute("CREATE TABLE IF NOT EXISTS comptes(nom TEXT, mat TEXT, adresse TEXT UNIQUE)")
    c.execute("CREATE TABLE IF NOT EXISTS mails(id INTEGER PRIMARY KEY, a TEXT, de TEXT, sujet TEXT, corps TEXT, date TEXT)")
    if "mdp" not in [r[1] for r in c.execute("PRAGMA table_info(comptes)")]:
        c.execute("ALTER TABLE comptes ADD COLUMN mdp TEXT")
    mc = [r[1] for r in c.execute("PRAGMA table_info(mails)")]
    for col in ("lu", "etoile", "corb", "corb_exp", "arch"):
        if col not in mc:
            c.execute("ALTER TABLE mails ADD COLUMN " + col + " INTEGER DEFAULT 0")
    c.commit()
    return c

def hache(p, sel=None):
    sel = sel or secrets.token_hex(8)
    return sel + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), sel.encode(), 100000).hex()

def verifie(p, stock):
    return secrets.compare_digest(hache(p, stock.split("$")[0]), stock)

def creer(nom, mdp):
    nom = "".join(ch for ch in nom.lower() if ch.isalnum())
    if not nom:
        return None
    c = db()
    for _ in range(50):
        adr = f"{nom}.{secrets.randbelow(9998) + 2:04d}@{DOM}"
        try:
            c.execute("INSERT INTO comptes(nom,mat,adresse,mdp) VALUES(?,?,?,?)",
                      (nom, adr.split(".")[-1].split("@")[0], adr, hache(mdp)))
            c.commit(); c.close()
            return adr
        except sqlite3.IntegrityError:
            pass
    c.close()
    return None

def court(adr):
    return (adr or "?").split("@")[0]

def page(corps, user=None, info="", d="recu", q="", chrome=True):
    head = fab = ""
    if user:
        if chrome:
            c = db()
            n = c.execute("SELECT COUNT(*) FROM mails WHERE a=? AND lu=0 AND corb=0 AND arch=0", (user,)).fetchone()[0]
            c.close()
            liens = "".join('<a class="lk' + (" on" if k == d else "") + '" href="/d/' + k + '">' + nom +
                            (" (" + str(n) + ")" if k == "recu" and n else "") + '</a>' for k, nom in DOSS)
            head = ('<div class="bar"><button class="ic" onclick="T()">☰</button><form action="/d/' + d +
                    '"><input name="q" value="' + html.escape(q) + '" placeholder="Rechercher dans les mails"></form>'
                    '<div class="av">' + html.escape(user[:1].upper()) + '</div></div>'
                    '<div class="dr"><div class="dh">ember<span>.nv</span></div>' + liens +
                    '<form method="post" action="/sortir"><button class="lk">↪ Se déconnecter</button></form>'
                    '<div class="em">' + html.escape(user) + '</div></div><div id="ov" onclick="T()"></div>')
            fab = '<a class="fab" href="/ecrire">✎ Écrire</a>'
    box = '<p class="info">' + html.escape(info) + '</p>' if info else ""
    return ('<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1"><title>ember.nv</title>'
            '<link rel="manifest" href="/manifest.json"><meta name="theme-color" content="#f57c00"><style>' + CSS +
            '</style></head><body><main>' + head + box + corps + '</main>' + fab +
            '<script>function T(){document.body.classList.toggle("o")}</script></body></html>')

def accueil(info=""):
    return page("""<div class="pad"><h1>ember<span>.nv</span></h1>
<div class="card"><h2>Se connecter</h2><form method="post" action="/connexion">
<input class="c" name="adresse" placeholder="braise.0001@ember.nv" autocapitalize="none" required>
<input class="c" name="mdp" type="password" placeholder="Mot de passe" required>
<button class="b">Connexion</button></form>
<small>Compte créé avant le site : le premier mot de passe saisi devient le tien.</small></div>
<div class="card"><h2>Créer un compte</h2><form method="post" action="/creer">
<input class="c" name="nom" placeholder="Nom (ex : lena)" autocapitalize="none" required>
<input class="c" name="mdp" type="password" placeholder="Mot de passe (4 caractères min.)" required>
<button class="b">Créer</button></form></div></div>""", info=info, chrome=False)

def liste(user, d, q, info, ret):
    cond, n = REQ[d]
    args = [user] * n
    sql = "SELECT id,a,de,sujet,corps,date,lu,etoile FROM mails WHERE " + cond
    if q:
        sql += " AND (sujet LIKE ? OR corps LIKE ? OR de LIKE ? OR a LIKE ?)"
        args += ["%" + q + "%"] * 4
    c = db()
    rows = c.execute(sql + " ORDER BY id DESC", args).fetchall()
    c.close()
    out = ""
    for id_, a, de, sujet, corps, date, lu, etoile in rows:
        env = de == user and a != user
        qui = ("À : " + court(a)) if env else court(de)
        lettre = a if env else de
        nl = " nl" if (a == user and not lu) else ""
        snip = " ".join((corps or "").split())[:60]
        star = ('<form method="post" action="/action"><input type="hidden" name="id" value="' + str(id_) +
                '"><input type="hidden" name="act" value="etoile"><input type="hidden" name="r" value="' + html.escape(ret) +
                '"><button class="st">' + ("★" if etoile else "☆") + '</button></form>') if a == user else ""
        out += ('<div class="row' + nl + '"><div class="av">' + html.escape(lettre[:1].upper()) + '</div>'
                '<a class="mid" href="/m/' + str(id_) + '"><span class="t">' + html.escape(qui) + '</span><br><span class="sj">' +
                html.escape(sujet or "(sans sujet)") + '</span> <span class="sn">- ' + html.escape(snip) + '</span></a>'
                '<div class="rt"><span>' + html.escape(date or "") + '</span>' + star + '</div></div>')
    return page(out or '<p class="pad"><small>Aucun mail ici.</small></p>', user, info, d, q)

def vue(user, id_):
    c = db()
    r = c.execute("SELECT a,de,sujet,corps,date,etoile,corb,corb_exp FROM mails WHERE id=? AND (a=? OR de=?)", (id_, user, user)).fetchone()
    if not r:
        c.close()
        return None
    c.execute("UPDATE mails SET lu=1 WHERE id=? AND a=?", (id_, user))
    c.commit(); c.close()
    a, de, sujet, corps, date, etoile, corb, corb_exp = r
    dans_corb = (a == user and corb) or (de == user and corb_exp)
    def bt(act, txt):
        return ('<form method="post" action="/action"><input type="hidden" name="id" value="' + str(id_) +
                '"><input type="hidden" name="act" value="' + act + '"><button class="ic" title="' + act + '">' + txt + '</button></form>')
    barre = '<div class="hd"><a class="ic" href="/d/recu" style="text-decoration:none">←</a><span class="sp"></span>'
    if a == user:
        barre += bt("archiver", "🗂")
    barre += bt("restaurer", "♻") if dans_corb else bt("corbeille", "🗑")
    if a == user:
        barre += bt("nonlu", "✉") + bt("etoile", "★" if etoile else "☆")
    barre += '</div>'
    cit = "\n\n---------- Message transféré ----------\nDe : " + de + "\nObjet : " + (sujet or "") + "\n\n" + (corps or "")
    return page(barre + '<div class="pad"><h2>' + html.escape(sujet or "(sans sujet)") + '</h2><div style="display:flex;gap:.8rem">'
                '<div class="av">' + html.escape(de[:1].upper()) + '</div><div class="meta"><b style="color:#202124">' + html.escape(court(de)) +
                '</b><br>à ' + html.escape(a) + ' · ' + html.escape(date or "") + '</div></div><pre>' + html.escape(corps or "") + '</pre>'
                '<a class="btn g" href="/ecrire?a=' + quote(de) + '&s=' + quote("Re: " + (sujet or "")) + '">↩ Répondre</a>'
                '<a class="btn g" href="/ecrire?s=' + quote("Fwd: " + (sujet or "")) + '&c=' + quote(cit) + '">↪ Transférer</a></div>',
                user, chrome=False)

def ecrire(user, a="", s="", c=""):
    return page('<div class="hd"><a class="ic" href="/d/recu" style="text-decoration:none">✕</a><span class="sp"></span></div>'
                '<div class="pad"><h2>Nouveau message</h2><form method="post" action="/envoyer">'
                '<input class="c" name="a" value="' + html.escape(a) + '" placeholder="À (ex : lena.1679@ember.nv)" autocapitalize="none" required>'
                '<input class="c" name="sujet" value="' + html.escape(s) + '" placeholder="Objet">'
                '<textarea name="corps" rows="9" placeholder="Rédiger un message">' + html.escape(c) + '</textarea>'
                '<button class="b">Envoyer ➤</button></form></div>', user, chrome=False)

def agir(user, id_, act):
    c = db()
    r = c.execute("SELECT a,de FROM mails WHERE id=? AND (a=? OR de=?)", (id_, user, user)).fetchone()
    if r:
        a, de = r
        if act == "etoile" and a == user:
            c.execute("UPDATE mails SET etoile=1-COALESCE(etoile,0) WHERE id=?", (id_,))
        elif act == "nonlu" and a == user:
            c.execute("UPDATE mails SET lu=0 WHERE id=?", (id_,))
        elif act == "archiver" and a == user:
            c.execute("UPDATE mails SET arch=1 WHERE id=?", (id_,))
        elif act == "corbeille":
            if a == user: c.execute("UPDATE mails SET corb=1 WHERE id=?", (id_,))
            if de == user: c.execute("UPDATE mails SET corb_exp=1 WHERE id=?", (id_,))
        elif act == "restaurer":
            if a == user: c.execute("UPDATE mails SET corb=0, arch=0 WHERE id=?", (id_,))
            if de == user: c.execute("UPDATE mails SET corb_exp=0 WHERE id=?", (id_,))
        c.commit()
    c.close()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def user(self):
        for p in self.headers.get("Cookie", "").split(";"):
            k, _, v = p.strip().partition("=")
            if k == "sid":
                return SESS.get(v)

    def send(self, body, code=200, ctype="text/html; charset=utf-8"):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def go(self, url, extra=None):
        self.send_response(303)
        self.send_header("Location", url)
        for k, v in (extra or []):
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def form(self):
        n = int(self.headers.get("Content-Length", 0))
        return {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()}

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        qs = {k: v[0] for k, v in parse_qs(u.query).items()}
        if p == "/manifest.json":
            return self.send('{"name":"ember.nv","short_name":"ember","start_url":"/","display":"standalone","background_color":"#ffffff","theme_color":"#f57c00","icons":[{"src":"/icone.svg","sizes":"any","type":"image/svg+xml"}]}', 200, "application/manifest+json")
        if p == "/icone.svg":
            return self.send('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="22" fill="#f57c00"/><path d="M22 32h56v36H22z M22 32l28 22 28-22" fill="none" stroke="#fff" stroke-width="6" stroke-linejoin="round"/></svg>', 200, "image/svg+xml")
        user = self.user()
        if not user:
            return self.send(accueil(qs.get("m", "")))
        if p.startswith("/d/"):
            d = p[3:] if p[3:] in REQ else "recu"
            return self.send(liste(user, d, qs.get("q", "").strip(), qs.get("m", ""), self.path))
        if p.startswith("/m/") and p[3:].isdigit():
            v = vue(user, int(p[3:]))
            return self.send(v) if v else self.go("/d/recu")
        if p == "/ecrire":
            return self.send(ecrire(user, qs.get("a", ""), qs.get("s", ""), qs.get("c", "")))
        self.go("/d/recu")

    def do_POST(self):
        f = self.form()
        p = self.path
        user = self.user()
        if p == "/creer":
            if len(f.get("mdp", "")) < 4:
                return self.go("/?m=" + quote("Mot de passe trop court"))
            adr = creer(f.get("nom", ""), f["mdp"])
            if not adr:
                return self.go("/?m=" + quote("Nom invalide"))
            return self.send(accueil("Compte créé : " + adr + " (note-le bien)"))
        if p == "/connexion":
            adr = f.get("adresse", "").strip().lower()
            mdp = f.get("mdp", "")
            c = db()
            r = c.execute("SELECT mdp FROM comptes WHERE adresse=?", (adr,)).fetchone()
            if not r:
                c.close()
                return self.go("/?m=" + quote("Compte inconnu"))
            if r[0] is None:
                if len(mdp) < 4:
                    c.close()
                    return self.go("/?m=" + quote("Choisis un mot de passe de 4 caractères min."))
                c.execute("UPDATE comptes SET mdp=? WHERE adresse=?", (hache(mdp), adr))
                c.commit()
            elif not verifie(mdp, r[0]):
                c.close()
                return self.go("/?m=" + quote("Mot de passe incorrect"))
            c.close()
            sid = secrets.token_hex(16)
            SESS[sid] = adr
            return self.go("/d/recu", [("Set-Cookie", "sid=" + sid + "; HttpOnly; SameSite=Strict; Path=/")])
        if not user and p != "/sortir":
            return self.go("/")
        if p == "/envoyer":
            a = f.get("a", "").strip().lower()
            c = db()
            if not c.execute("SELECT 1 FROM comptes WHERE adresse=?", (a,)).fetchone():
                c.close()
                return self.go("/d/recu?m=" + quote("Destinataire inconnu : " + a))
            c.execute("INSERT INTO mails(a,de,sujet,corps,date) VALUES(?,?,?,?,?)",
                      (a, user, f.get("sujet", ""), f.get("corps", ""), time.strftime("%d/%m %H:%M")))
            c.commit(); c.close()
            return self.go("/d/envoyes?m=" + quote("Message envoyé"))
        if p == "/action":
            act = f.get("act", "")
            id_ = int(f["id"]) if f.get("id", "").isdigit() else 0
            agir(user, id_, act)
            r = f.get("r", "")
            if r.startswith("/") and not r.startswith("//"):
                return self.go(r)
            if act in ("corbeille", "archiver", "restaurer"):
                return self.go("/d/recu")
            return self.go("/m/" + str(id_))
        if p == "/sortir":
            for k, v in list(SESS.items()):
                if v == user:
                    del SESS[k]
            return self.go("/", [("Set-Cookie", "sid=; Max-Age=0; Path=/")])
        self.go("/")

print("Site ember.nv sur http://127.0.0.1:8080  (Ctrl+C pour arrêter)")
ThreadingHTTPServer(("127.0.0.1", 8080), H).serve_forever()