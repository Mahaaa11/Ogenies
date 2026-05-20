# Déployer **L&C Emailing** sur PlanetHoster N0C

Ce guide te dit, **étape par étape**, comment mettre l'application en ligne sur
ton hébergement PlanetHoster (offre **N0C / Hybride / The World**) — celui où ton
CTO a déjà un compte. À la fin, tu auras :

- `https://mailing.ogeniesrgpd.com` → l'**interface web** (Next.js, en statique)
- `https://apimailing.ogeniesrgpd.com` → l'**API FastAPI** (Python + Passenger)
- Le **webhook SendGrid** qui pousse les events dans MySQL automatiquement
- La base **MySQL** managée par PlanetHoster (visible dans phpMyAdmin du panel)

> **Important** : sur N0C, le runtime "Application Manager" ne parle que
> **WSGI**. Or FastAPI est **ASGI**. On utilise donc un petit adaptateur
> `a2wsgi` (déjà ajouté à `requirements.txt`) et un `passenger_wsgi.py` à la
> racine du projet, qui sert de point d'entrée pour Passenger. Tu n'as rien
> à coder, juste à pointer Passenger sur ce fichier.

---

## Étape 0 — Avant de commencer (5 minutes)

1. **Récupère** auprès de ton CTO :
   - login N0C (Panel PlanetHoster)
   - login SSH (souvent identique au panel)
   - login MySQL (host, user, password) — ou bien la permission de créer la base toi-même via le panel
2. **Sous-domaines** que tu vas utiliser (tu peux changer les noms) :
   - `mailing.ogeniesrgpd.com` → front
   - `apimailing.ogeniesrgpd.com` → backend

Si le domaine `ogeniesrgpd.com` n'est pas encore configuré chez PlanetHoster,
demande à ton CTO de l'ajouter au compte avant d'aller plus loin.

3. **Révoque la clé SendGrid** qui était en clair dans `.env.example` du repo
   (côté SendGrid → API Keys → "Delete"), puis crée-en **une nouvelle**. C'est
   cette nouvelle clé que tu mettras dans `.env` en production.

---

## Étape 1 — Préparer les sous-domaines + la base MySQL côté N0C

### 1.1 Créer les deux sous-domaines

Dans le panel N0C :

1. `Domaines` → `Sous-domaines` → **Ajouter**
   - `mailing` sur `ogeniesrgpd.com` → tu pointeras sa **racine documents** vers
     un dossier qui contiendra le **build statique** du front (étape 4).
   - `apimailing` sur `ogeniesrgpd.com` → ce sous-domaine sera attaché à
     l'**Application Python** que tu vas créer à l'étape 3.

2. Active le **SSL Let's Encrypt** sur les deux : `Domaines` → cocher le SSL,
   `Activer`. C'est gratuit et ça donne automatiquement le `https://`.

### 1.2 Créer la base MySQL

Dans le panel N0C :

1. `Bases de données` → `MySQL` → **Créer une base**
   - nom suggéré : `lncemail_prod` (le préfixe utilisateur est ajouté
     automatiquement par PlanetHoster, ex : `tonuser_lncemail_prod`)
2. **Créer un utilisateur** MySQL (ex : `tonuser_lncapi`) avec un mot de passe
   fort, puis **rattache-le** à la base avec **tous les droits**.
3. Note tout dans un coin (tu en auras besoin à l'étape 3.4) :
   - host : presque toujours `localhost`
   - port : `3306`
   - database : `tonuser_lncemail_prod`
   - user : `tonuser_lncapi`
   - password : `…`

### 1.3 Importer le schéma + le seed

1. Ouvre **phpMyAdmin** depuis le panel (`Bases de données` → ton lien phpMyAdmin).
2. Sélectionne la base que tu viens de créer.
3. Onglet **Importer** → **Choisir un fichier** :
   - upload `docker/mysql/01_schema.sql` (crée les tables `prospects` et `email_events`)
   - **Exécuter**, puis recommence avec `docker/mysql/02_seed_prospects.sql`
     (insère les 100 prospects de test `agent1@ogenies.com..agent100@ogenies.com`)

---

## Étape 2 — Pousser le code sur le serveur

Deux options. **L'option SSH+git est de loin la plus propre.**

### Option A (recommandée) : SSH + git

```bash
# Sur ta machine :
ssh tonuser@tonserveur.n0c.com

# Une fois connecté :
cd ~
git clone https://github.com/<ton-org>/lnc-emailing.git   # ou ton repo privé
# Si privé, utilise un deploy key (clé SSH) ou un token Personal Access Token.
```

> Pas de Git installé sur le serveur ? Demande-le à ton CTO ou utilise l'option B.

### Option B : upload manuel (zip / SFTP)

1. Sur ta machine, fais un zip du projet en excluant les dossiers inutiles :

```bash
cd "/Users/macbookpro/Documents/New project"
zip -r lnc-emailing.zip . -x \
  ".venv/*" "frontend/node_modules/*" "frontend/.next/*" "frontend/out/*" \
  "output_*/*" ".git/*" "*.DS_Store"
```

2. Dans le panel N0C → **Gestionnaire de fichiers** (ou via SFTP), upload
   `lnc-emailing.zip` dans `~/` et décompresse-le dans un dossier
   `~/lnc-emailing/`.

---

## Étape 3 — Créer l'application Python (backend FastAPI)

C'est l'étape la plus dense du guide. Ne saute aucune sous-étape, et lis bien
les encadrés explicatifs : tout est conçu pour que tu comprennes **pourquoi**
tu fais chaque action.

### Comprendre l'architecture en 30 secondes

Sur PlanetHoster N0C mutualisé, tu n'as **pas** de droit `root`, donc tu ne
peux pas installer Docker, ni faire tourner `uvicorn` à la main en permanence.
À la place, N0C te propose un outil qui s'appelle **"Setup Python App"** :

- Tu lui dis "voici un dossier, voici une version de Python, et voici le
  fichier qui décrit comment lancer mon app".
- Lui se charge :
  1. de créer un **virtualenv** dédié (`~/virtualenv/lnc-emailing/3.12/`),
  2. de configurer **Apache + Passenger** pour qu'à chaque requête HTTP qui
     arrive sur `apimailing.ogeniesrgpd.com`, Apache passe la balle à Passenger
     qui appelle ton code Python.

**Petit problème** : Passenger ne sait dialoguer qu'avec des apps **WSGI** (un
vieux protocole synchrone). Or FastAPI/Starlette parle **ASGI** (async). On
résout ça avec une seule ligne de code dans `passenger_wsgi.py` (déjà
préparée pour toi) : on enveloppe l'app FastAPI dans un adaptateur `a2wsgi`
(déjà déclaré dans `requirements.txt`). Tu n'as rien à coder.

```
Internet → Apache N0C → Passenger (WSGI) → a2wsgi → FastAPI (ASGI) → ton code
```

---

### 3.1 Créer l'application Python dans N0C

1. Connecte-toi au **panel N0C** (https://my.planethoster.net puis ton hébergement).
2. Dans le menu principal cherche **"Hébergement Web"** (ou **"Sites web"** /
   **"My N0C"** selon la version du panel).
3. Trouve la rubrique **"Setup Python App"** (parfois listée sous "Apps Manager"
   ou directement "Python").
4. Tu arrives sur une liste vide (si c'est la première fois) → clique
   **Create Application**.

Un formulaire s'ouvre avec ces champs **dans cet ordre** :

| Champ | Valeur à mettre | À quoi ça sert |
|---|---|---|
| **Python version** | `3.12.x` (la plus récente disponible) | Version de l'interpréteur. Ne descend pas en dessous de `3.11`, sinon FastAPI moderne ne marchera pas. |
| **Application root** | `lnc-emailing` | C'est **uniquement le nom du dossier** sous ton `$HOME`, pas un chemin complet. N0C va créer/utiliser `/home/tonuser/lnc-emailing/`. Si tu as déjà décompressé le zip dedans (étape 2), c'est bon. |
| **Application URL** | `apimailing.ogeniesrgpd.com` (et **rien** dans le champ "/path" à côté, laisse-le vide) | C'est le sous-domaine sur lequel l'app sera exposée. Tu l'as créé à l'étape 1.1. |
| **Application startup file** | `passenger_wsgi.py` | Le fichier que Passenger va importer. **Doit être à la racine de `Application root`**. C'est déjà le cas dans notre repo. |
| **Application Entry point** | `application` | Le nom de la variable Python (dans `passenger_wsgi.py`) qui contient l'app WSGI. Si tu mets autre chose, Passenger ne trouvera pas l'app et renverra `502 Bad Gateway`. |
| **Passenger log file** *(optionnel)* | `passenger.log` | Où écrire les logs d'erreur Passenger. Laisse la valeur par défaut, tu pourras y accéder depuis le panel. |

5. Clique **Create**.

**Ce qui se passe en coulisses** (utile pour debug plus tard) :

- N0C crée `/home/tonuser/virtualenv/lnc-emailing/3.12/` → c'est le venv dédié.
- N0C crée un fichier `.htaccess` (ou équivalent) dans le dossier du sous-domaine
  `apimailing.ogeniesrgpd.com` pour rediriger toutes les requêtes vers Passenger.
- N0C ajoute des règles Apache pour invoquer Passenger sur ce sous-domaine.

> ⚠️ Si tu te trompes de version Python ou de URL, tu peux supprimer l'app et la
> recréer (rien de cassé), ou utiliser le bouton **Edit** ensuite.

---

### 3.2 Activer le virtualenv via SSH et installer les dépendances

En haut de la page de ton application Python, N0C affiche un encart bleu
intitulé typiquement **"Run the following command to enter the virtual
environment"** avec une commande prête à copier. Ça ressemble à :

```bash
source /home/tonuser/virtualenv/lnc-emailing/3.12/bin/activate && cd /home/tonuser/lnc-emailing
```

(le `tonuser` sera **ton vrai nom d'utilisateur** N0C, pas le mot "tonuser")

#### Te connecter en SSH

1. **Récupère tes infos SSH** dans le panel : `Avancé` → `SSH Access` (ou
   `Activer SSH`). Souvent l'host est `<tonuser>@<tonuser>.n0c.com` ou un IP
   numérique. Le port peut être `22` ou `5022` selon l'offre.
2. Ouvre un terminal sur ta machine et lance :

```bash
ssh -p 22 tonuser@tonuser.n0c.com
```

(Remplace par les valeurs réelles. PlanetHoster te demandera le mot de passe
de ton compte hébergement, **pas** ton mot de passe `my.planethoster.net`.)

#### Activer le venv et installer les deps

Une fois en SSH, **colle** la commande de l'encart bleu :

```bash
source /home/tonuser/virtualenv/lnc-emailing/3.12/bin/activate && cd /home/tonuser/lnc-emailing
```

Tu sais que ça a marché si ton prompt change : il devrait commencer par
`(lnc-emailing:3.12) $` ou `(3.12) $`. Tu es maintenant **dans le venv** :
toute commande `pip` ou `python` que tu lances va dans ce venv isolé.

Installe les dépendances du projet :

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

La 2e commande va prendre 1-2 minutes. Tu verras défiler `Downloading...` /
`Installing...` pour `fastapi`, `uvicorn`, `pymysql`, `a2wsgi`, `pandas`, etc.

**Vérifie que ça s'est bien passé** :

```bash
pip list | grep -Ei "fastapi|a2wsgi|pymysql|uvicorn"
```

Tu dois voir les 4 packages avec leur version. Si l'un manque, relance
`pip install -r requirements.txt` (parfois un timeout réseau).

> ⚠️ **Si tu vois `error: command 'gcc' failed`** sur un package qui compile du
> C (rare avec nos deps), c'est que la version de Python choisie ne dispose
> pas du build kit. Solution : passer à une version Python plus récente, ou
> contacter le support N0C.

---

### 3.3 Vérifier `passenger_wsgi.py` (5 secondes, lecture rapide)

Le fichier est **déjà** à la racine de ton projet, et fait exactement ça :

```python
import os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from a2wsgi import ASGIMiddleware
from backend.app.main import app as _asgi_app

application = ASGIMiddleware(_asgi_app)
```

**Ce que ça fait, ligne par ligne** :

1. `ROOT = ...` + `sys.path.insert` : ajoute la racine du projet au PYTHONPATH
   pour que Python puisse trouver `backend.app.main` et `src.lnc_agent.*`.
2. `from backend.app.main import app` : récupère l'app FastAPI (ASGI).
3. `application = ASGIMiddleware(_asgi_app)` : enveloppe l'ASGI dans un wrapper
   WSGI que Passenger peut appeler.

La **variable** que Passenger cherche s'appelle `application` (c'est ce que tu
as mis dans le champ "Application Entry point" à l'étape 3.1). **Ne renomme pas
cette variable** sinon Passenger te renverra une 502.

**Comment vérifier que tout est bien en place** (depuis le SSH dans le venv) :

```bash
python -c "import passenger_wsgi; print('OK:', type(passenger_wsgi.application).__name__)"
```

Tu dois voir `OK: ASGIMiddleware`. Si tu vois un `ImportError`, c'est qu'un
package manque (retourne en 3.2) ou que le `cd` n'est pas dans le bon dossier.

---

### 3.4 Renseigner les variables d'environnement (LE point critique)

C'est ici que ça plante le plus souvent en prod. Sois minutieux.

#### Où les mettre

Sur la page de ton app Python dans le panel N0C, tu vas trouver une section
**Environment variables** (parfois cachée sous "Show variables" ou "+ Add
variable"). C'est un tableau à deux colonnes : `Name` et `Value`.

#### Les variables à ajouter, une par une

| Name | Value | Explication |
|---|---|---|
| `SENDGRID_API_KEY` | `SG.xxx...` (ta **nouvelle** clé après révocation de l'ancienne) | Clé d'API SendGrid pour envoyer les emails. **Ne mets PAS de guillemets** autour. |
| `LNC_SENDGRID_TEMPLATE_ID` | `d-dd610c9721b54305bead1e7028eec11f` | ID du Dynamic Template SendGrid (créé côté SendGrid → Email API → Dynamic Templates). |
| `LNC_SENDGRID_FROM_EMAIL` | `contact@ogenies.com` (ou autre sender **vérifié** dans SendGrid) | L'adresse expéditeur. Doit être validée côté SendGrid (Single Sender Verification ou Domain Authentication), sinon SendGrid renvoie `403`. |
| `LNC_CORS_ORIGINS` | `https://mailing.ogeniesrgpd.com` | Origines autorisées à appeler l'API. **Sans slash final** (`/`), **exactement** le sous-domaine du front. Tu peux mettre plusieurs origines séparées par des virgules. |
| `LNC_EVENT_STORE` | `mysql` | Dit au backend de lire/écrire les events SendGrid dans MySQL (plutôt que dans des fichiers locaux). |
| `LNC_PROSPECT_SOURCE` | `mysql` | Idem pour les prospects. |
| `LNC_MYSQL_HOST` | `localhost` | Sur N0C mutualisé, la base MySQL est sur le même serveur que ton app. Quasi-toujours `localhost`. |
| `LNC_MYSQL_PORT` | `3306` | Port standard MySQL. |
| `LNC_MYSQL_USER` | `tonuser_lncapi` (celui de l'étape 1.2) | Utilisateur que tu as créé dans le panel. |
| `LNC_MYSQL_PASSWORD` | le password de cet utilisateur | Tu l'as choisi à l'étape 1.2. |
| `LNC_MYSQL_DATABASE` | `tonuser_lncemail_prod` | Le nom complet de la base (avec le préfixe de ton utilisateur). |
| `LNC_MYSQL_PROSPECTS_TABLE` | `prospects` | Nom de la table. Laisse la valeur par défaut. |
| `LNC_MYSQL_EVENTS_TABLE` | `email_events` | Idem. |

> ⚠️ **Trois pièges classiques** :
> 1. **Ne mets pas de guillemets** (`"..."`) autour des valeurs dans le panel ;
>    tout ce qui est entre guillemets serait inclus dans la valeur littéralement.
> 2. **Pas d'espace** avant ou après le `=` ni dans le nom de la variable.
> 3. Si ton mot de passe MySQL contient des caractères spéciaux (`$`, `#`,
>    espace, `&`), c'est OK dans le panel (c'est juste un champ texte), mais
>    pas OK dans un fichier `.env` sans guillemets. Préfère le panel.

#### Faut-il aussi créer un fichier `.env` sur le serveur ?

**Non**, et c'est même déconseillé. Notre code lit les variables avec
`os.environ.get(...)`, donc tant qu'elles sont **dans l'environnement du
processus Passenger** (ce que fait le panel N0C automatiquement), pas besoin
de fichier. Avantages du panel :

- Tu peux changer une variable et **Restart** sans toucher au code.
- Les variables ne fuient pas si quelqu'un récupère un dump du dossier.
- Tu vois tout en un coup d'œil.

#### Vérifier que les variables sont bien chargées

Une fois sauvegardées, **redémarre l'app** (bouton **Restart** en haut de la
page), puis depuis ta machine :

```bash
curl -s https://apimailing.ogeniesrgpd.com/health
```

→ tu dois voir `{"status":"ok"}`. Ensuite teste un endpoint qui dépend des
variables MySQL :

```bash
curl -s -i https://apimailing.ogeniesrgpd.com/api/dashboard
```

- `HTTP 200` + du JSON → les vars sont bien chargées, MySQL est joignable.
- `HTTP 404 ... dashboard.csv not found` → c'est normal au premier appel, il
  faut d'abord `POST /api/report/sendgrid?scope=all` pour générer le rapport.
- `HTTP 500 ... LNC_MYSQL_DATABASE is required` → la variable est mal nommée
  ou pas sauvegardée. Retourne dans le panel.
- `HTTP 500 ... Access denied for user` → le user/password MySQL est faux,
  ou l'utilisateur n'a pas été rattaché à la base avec les droits.

---

### 3.5 Démarrer / redémarrer l'app + tests de bout en bout

#### Restart

En haut de la page de l'app Python il y a un bouton **Restart** (parfois
**Restart Application**). À chaque fois que tu modifies :

- une variable d'environnement,
- le code Python (après un `git pull` ou un upload SFTP),
- les dépendances (`pip install ...`),

tu **dois cliquer Restart**, sinon Passenger continue d'utiliser l'ancienne
version en mémoire.

#### Les 3 tests à faire dans l'ordre

```bash
# Test 1 — l'app répond
curl -i https://apimailing.ogeniesrgpd.com/health
# attendu: HTTP/1.1 200 OK + {"status":"ok"}

# Test 2 — le pipeline complet (génère les KPIs depuis MySQL)
curl -i -X POST "https://apimailing.ogeniesrgpd.com/api/report/sendgrid?scope=all"
# attendu: HTTP/1.1 200 OK + {"ok":true,"out_csv":"...","scope":{...}}

# Test 3 — CORS depuis le front
curl -i -H "Origin: https://mailing.ogeniesrgpd.com" \
  https://apimailing.ogeniesrgpd.com/api/dashboard
# attendu: header "access-control-allow-origin: https://mailing.ogeniesrgpd.com"
```

#### Si tu vois `HTTP 500` ou `HTTP 502`

C'est presque toujours une de ces 4 raisons. Diagnostic dans cet ordre :

1. **Logs de l'app** : panel N0C → page de ton app Python → onglet/section
   **Application Logs** (ou fichier `~/lnc-emailing/passenger.log` via SSH).
   Le traceback Python s'y trouve.
2. **Variable manquante** : relis `Étape 3.4`, cherche la variable mentionnée
   dans le traceback.
3. **MySQL pas joignable** : `mysql -h localhost -u tonuser_lncapi -p
   tonuser_lncemail_prod` depuis le SSH, si ça ne marche pas, le user/db est
   mal configuré côté panel.
4. **`a2wsgi` ou `fastapi` manquant** : retourne en `Étape 3.2` et relance
   `pip install -r requirements.txt` **dans le venv** (vérifie ton prompt
   commence bien par `(lnc-emailing:3.12)`).

#### Mini check-list "tout est bon en étape 3"

- [ ] L'app apparaît avec status **Started** dans le panel
- [ ] `curl /health` répond `200 OK`
- [ ] `curl -X POST /api/report/sendgrid?scope=all` répond `200 OK`
- [ ] L'en-tête `access-control-allow-origin` correspond à `mailing.ogeniesrgpd.com`
- [ ] `pip list` dans le venv montre `fastapi`, `a2wsgi`, `pymysql`, `uvicorn`

Quand les 5 cases sont cochées, tu peux passer à l'**Étape 4** (déploiement
du front).

---

## Étape 4 — Déployer le frontend (Next.js en statique)

L'idée : on **builde** le front sur ta machine (ou via SSH) en mode **export
statique**, puis on copie le résultat dans le dossier servi par le sous-domaine
`mailing.ogeniesrgpd.com`.

### 4.1 Configurer l'URL du backend

Sur ta machine, dans le dossier `frontend/`, crée un fichier
`.env.production` (basé sur `.env.production.example`) :

```bash
NEXT_PUBLIC_API_BASE=https://apimailing.ogeniesrgpd.com
```

### 4.2 Builder le front en statique

```bash
cd frontend
npm install
npm run build:static
```

Ça produit un dossier `frontend/out/` qui contient des fichiers HTML/CSS/JS
purs (pas de Node nécessaire en prod).

### 4.3 Pousser le dossier `out/` vers le serveur

```bash
# Depuis le dossier "frontend" sur ta machine :
scp -r out/* tonuser@tonserveur.n0c.com:~/public_html/app/
```

(remplace `~/public_html/app/` par la **racine documents** que tu as choisie
pour le sous-domaine `mailing.ogeniesrgpd.com` à l'étape 1.1)

Ou via le **Gestionnaire de fichiers** du panel : upload le contenu de `out/`
dans le dossier du sous-domaine.

### 4.4 Tester

Ouvre `https://mailing.ogeniesrgpd.com` dans ton navigateur. Tu dois voir le
dashboard. Si tu vois un bandeau rouge "Backend non prêt", retourne à
l'étape 3.4 et vérifie `LNC_CORS_ORIGINS`.

---

## Étape 5 — Brancher le webhook SendGrid

Côté SendGrid (`Settings` → `Mail Settings` → `Event Webhook`) :

- **HTTP Post URL** : `https://apimailing.ogeniesrgpd.com/webhooks/sendgrid/events`
- Coche les events que tu veux ingérer : `delivered`, `open`, `click`,
  `bounce`, `dropped`, `spam`, `unsubscribe`, `processed`.
- **Test Your Integration** → vérifie qu'il reçoit `200 OK`.
- **Enable** → sauvegarde.

À partir de là, chaque event SendGrid arrive automatiquement dans la table
`email_events` de ta base MySQL.

---

## Étape 6 — Mettre à jour l'app plus tard

Quand tu veux pousser une nouvelle version :

```bash
ssh tonuser@tonserveur.n0c.com
cd ~/lnc-emailing
git pull
source ~/virtualenv/lnc-emailing/3.12/bin/activate
pip install -r requirements.txt   # si tu as ajouté des deps
# Restart l'app via le panel (bouton "Restart")
```

Pour le front, refais `npm run build:static` localement puis `scp -r out/*` vers
le serveur.

---

## Limitations à connaître (et comment les contourner)

- **Pas de jobs cron longs** : pour des batchs (ex: relancer la génération de
  drafts toutes les heures), utilise les **cron jobs N0C** (5 min minimum) qui
  lancent `python -m src.lnc_agent.cli ...`.
- **Pas de WebSockets sur Passenger mutualisé** : pas grave, on n'en utilise
  pas dans cette app.
- **SendGrid From email** : doit être **vérifié** dans ton compte SendGrid
  (Single Sender Verification ou Domain Authentication), sinon les envois
  partent en `403`.

---

## Récap des URLs en prod

| Composant | URL |
|---|---|
| Front (dashboard) | `https://mailing.ogeniesrgpd.com` |
| API FastAPI | `https://apimailing.ogeniesrgpd.com` |
| Health-check API | `https://apimailing.ogeniesrgpd.com/health` |
| Webhook SendGrid | `https://apimailing.ogeniesrgpd.com/webhooks/sendgrid/events` |
| phpMyAdmin | depuis le panel N0C |

Si tu vois le bandeau rouge "Backend non prêt" : c'est que le CORS du backend
n'autorise pas ce sous-domaine. Retourne en `Étape 3.4`, vérifie que
`LNC_CORS_ORIGINS=https://mailing.ogeniesrgpd.com` (sans slash final, exactement
ce sous-domaine), puis **Restart** l'app Python.
