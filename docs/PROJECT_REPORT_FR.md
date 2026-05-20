# Rapport projet — Plateforme L&C Emailing (Lead & Connect) (A→Z)

## 1) Objectif du projet
Construire une **plateforme web** qui permet de piloter une campagne email (acquisition, puis autres campagnes) en connectant :
- une **base de prospects** (MySQL existante / ou MySQL local en dev),
- l’**envoi d’emails via Twilio SendGrid** (Dynamic Templates),
- l’**ingestion d’événements SendGrid** (webhook),
- un **agent** qui calcule un **score**, une **décision** (next action), et fournit du **tracking + KPIs**.

Le projet doit fonctionner :
- en **local** (dev) avec MySQL + phpMyAdmin via Docker,
- avec une architecture **production-like** (web + API + DB), et non un simple script.

---

## 2) Périmètre fonctionnel (ce que la plateforme fait)

### 2.1 Prospects
- Source principale : **MySQL** (mode recommandé).
- Identités utilisées pour tests : `agent1@ogenies.com … agent100@ogenies.com`.
- Données attendues (minimum) : `id`, `email`, + champs optionnels (`first_name`, `company`, etc.).

### 2.2 Envoi d’emails (SendGrid Dynamic Templates)
- Les emails sont envoyés avec un **template SendGrid** via :
  - `template_id`
  - `dynamic_template_data` contenant notamment :
    - `titre`, `contenu`, `lien`, `prenom`, `offre`
    - `variant` (A/B)
    - `campaign_id`
    - `send_batch_id` (phase/envoi de masse)
    - `send_hour` / `send_weekday` (timing)

### 2.3 Ingestion d’événements (SendGrid webhook)
- Endpoint : `POST /webhooks/sendgrid/events`
- Événements attendus : `processed`, `delivered`, `open`, `click`, `bounce`, `dropped`, `spam`, `unsubscribe`, etc.
- Champs clés utilisés :
  - `timestamp`
  - `sg_event_id` (déduplication)
  - `sg_message_id` (identifiant d’envoi par destinataire)
  - `email`
  - `url` (pour `click`)
  - `custom_args` (ex: `send_batch_id`, `campaign_id`)

### 2.4 Tracking + KPIs + Campagnes
La plateforme fournit :
- **Dashboard** : KPIs principaux (deliverability, open rate unique, CTR unique, rapid click, etc.) + graph “par jour” + graph “par phase”.
- **Tracking** : vue par prospect (opens/clicks, urls cliquées, rapid click, score, décision, best time).
- **Campagnes** : une campagne (ex: acquisition) contient des **phases** (`phase-1`, `phase-2`…), chaque phase représentant un **envoi de masse**.

### 2.5 Décisions modifiables + validation/exécution
Dans la section “Actions recommandées” :
- On voit la **décision IA** par prospect.
- On peut **modifier** l’action.
- On peut définir **jour/heure de renvoi**.
- On peut **valider** un groupe de prospects.
- La validation peut **exécuter** l’action : envoi SendGrid immédiat pour les prospects sélectionnés.

---

## 3) Architecture technique

### 3.1 Composants
- **Frontend** : Next.js (UI)
- **Backend** : FastAPI (API)
- **DB** : MySQL
- **Admin DB** : phpMyAdmin

### 3.2 Ports locaux (Docker)
- Web UI : `http://localhost:3001`
- API : `http://localhost:8000`
- phpMyAdmin : `http://localhost:8080`
- MySQL : `localhost:3306`

### 3.3 Stockage (local dev)
- Données MySQL : volume Docker **`mysql_data`** (persistant)
- Schéma + seed : `docker/mysql/*.sql`
- Overrides décisions : `output_platform/decisions.json`

---

## 4) Base de données (MySQL)

### 4.1 Tables principales (local dev)
- `prospects` : liste prospects
- `email_events` : événements SendGrid (raw) avec déduplication par `sg_event_id`

### 4.2 Création automatique
Au premier démarrage MySQL Docker exécute :
- `docker/mysql/01_schema.sql` (schema)
- `docker/mysql/02_seed_prospects.sql` (seed P001..P100)

---

## 5) Flux “A→Z” (fonctionnement global)

### 5.1 Démarrage
1) `docker compose up -d --build`
2) UI accessible sur `http://localhost:3001`

### 5.2 Pipeline de données
1) **Prospects** disponibles dans MySQL.
2) **Envoi** : l’API envoie via SendGrid avec `custom_args` (campaign/phase).
3) **Webhook** : SendGrid pousse les events vers `/webhooks/sendgrid/events`.
4) **Stockage events** : insertion dans MySQL `email_events` (dédup par `sg_event_id`).
5) **Analyse** : l’agent calcule score/segments/décisions + best time.
6) **KPIs** : calcul agrégé (dashboard/campagnes/trend).
7) **UI** : lecture des endpoints API pour afficher résultats.

---

## 6) Logique agent (score, segment, décision)

### 6.1 Scoring (0–100)
Le score combine :
- signaux positifs : open/click, engagement,
- signaux négatifs : unsubscribe/spam (pénalités).

### 6.2 Segmentation
- `high`, `medium`, `low` (en fonction du score)

### 6.3 Next action (exemples)
- `high` → `personalized_email_and_priority_call`
- `medium` → `follow_up_email`
- `low` → `nurturing_newsletter`
- `unsubscribed` → `do_not_contact`

### 6.4 Rapid click
KPI & signal d’intérêt : clic “rapide” dans une fenêtre **≤ 1 heure** (définition projet).

---

## 7) KPIs (principes de calcul)
Objectif : éviter les valeurs “fausses” dues aux retries/duplicats.

### 7.1 Déduplication
- `sg_event_id` : identifiant unique d’événement (à privilégier).

### 7.2 Delivered / Processed
Au niveau KPI global :
- Delivered est calculé en **unique** par \((email, sg_message_id)\).

### 7.3 Open rate / CTR
Les taux officiels sont basés sur des **comptes uniques** (et non “total events”).

---

## 8) Scope (Tout / Dernière phase / 24h)
Pour éviter des chiffres incohérents entre pages, un scope a été introduit :
- **Tout** : historique complet (emails prospects connus)
- **Dernière phase** : dernière phase (`send_batch_id`) uniquement
- **24h** : événements des dernières 24h

Ce scope est sélectionnable dans l’UI et réutilisé pour régénérer des artefacts cohérents.

---

## 9) Livrables (ce qu’on a ajouté au repo)
- `docker-compose.yml` (web + api + mysql + phpmyadmin)
- `docker/mysql/01_schema.sql` + `docker/mysql/02_seed_prospects.sql`
- `docs/CTO_QUICKSTART.md`
- `scripts/start-local.sh` et `scripts/start-local.ps1`
- mise à jour `README.md` (plateforme complète)

---

## 10) Limites / points à améliorer (prochaines étapes)
- “Valider actions” exécute **immédiatement**. Si besoin : ajouter un **scheduler** (exécution au jour/heure choisis).
- Stockage DB : aujourd’hui events en MySQL, mais certaines sorties restent en fichiers `output_platform/*` (possible de migrer 100% DB).
- Ajouter audit/traçabilité : historique des validations/exécutions par user.
- Ajouter authentification (si usage interne/production).

---

## 11) Conclusion
Le projet a évolué d’un MVP fichier (JSON/CSV) vers une **plateforme web complète** avec **MySQL local via Docker**, une ingestion SendGrid robuste (dédup), un agent de scoring/décision, du tracking, des KPIs, une notion de campagnes/phases, et un workflow “décision → validation → exécution”.

