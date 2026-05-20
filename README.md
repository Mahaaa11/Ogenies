# L&C Emailing — AI Email Campaign Agent (Lead & Connect)

This is a beginner-friendly Python MVP for the agent described in the presentation:

- read prospect and email-event data
- calculate an interest score for each prospect
- decide the next action: priority call, follow-up, nurturing, or wait
- generate a personalized email draft
- create a small dashboard CSV

This repo now supports:

- **CSV mode** (original MVP)
- **MySQL mode** (read prospects/events from an existing MySQL database)
- **Twilio SendGrid events webhook** (ingest events and store them in MySQL)
- **Data & Intelligence KPIs** (open, click, unsubscribe, spam + score distribution)
- **SendGrid advanced KPIs (JSONL)** (deliverability, unique opens/clicks, CTOR/CTR, bounces, A/B, device/geo/hour, domain/provider)
- **A/B testing** (deterministic variant per prospect)
- **Timing optimization** (best send hour from historical engagement)

Sender identities for outbound drafts rotate deterministically across:
`agent1@ogenies.com` … `agent100@ogenies.com`.

Email generation follows a **SendGrid Dynamic Template** approach: the agent outputs
`template_id` plus `dynamic_template_data` (variables like `titre`, `contenu`, `lien`, `prenom`, `offre`)
to fill your SendGrid template.

Optionally, the agent can generate `titre/contenu/offre` with **OpenAI** (French-only, tone aligned to the provided campaign example) when:

- `OPENAI_API_KEY` is set
- `LNC_USE_OPENAI=true`

## Platform (Web App) — Recommended

This repository includes a **full local web platform**:

- **Frontend**: Next.js UI
- **Backend**: FastAPI API
- **Database**: MySQL (local Docker) + **phpMyAdmin**
- **Ingestion**: SendGrid Event Webhook → stored in MySQL (no JSON needed for production-like runs)

### Start the full app (Docker)

Prerequisite: **Docker Desktop** installed and running.

```bash
docker compose up -d --build
```

### URLs

- **Web UI**: `http://localhost:3001`
- **API health**: `http://localhost:8000/health`
- **phpMyAdmin**: `http://localhost:8080`

### Database (where it is / how it’s created)

- MySQL runs in the Docker container **`mysql`**
- Data persists in a Docker volume: **`mysql_data`**
- Tables + seed are created automatically on first start by:
  - `docker/mysql/01_schema.sql` (tables: `prospects`, `email_events`)
  - `docker/mysql/02_seed_prospects.sql` (P001..P100 / agent1..agent100 @ogenies.com)

### SendGrid webhook endpoint

Configure Twilio SendGrid Event Webhook to point to:

- `http://<your-host>/webhooks/sendgrid/events`

In local dev, if you use ngrok, it will look like:

- `https://<ngrok-subdomain>.ngrok.app/webhooks/sendgrid/events`

### Configure secrets (SendGrid)

Never commit `.env`. Use `.env.example` as a template.

Required for sending:

- `SENDGRID_API_KEY`
- `LNC_SENDGRID_TEMPLATE_ID`
- `LNC_SENDGRID_FROM_EMAIL`

### CTO quickstart (1 page)

See `docs/CTO_QUICKSTART.md`.

## MVP / CLI mode (optional)

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

### CSV mode (MVP)

```bash
python3 -m src.lnc_agent.cli run \
  --prospects data/prospects.csv \
  --events data/events.csv \
  --sendgrid-raw data/sendgrid_events.jsonl \
  --out output
```

### Send the generated emails via SendGrid

1) Set `SENDGRID_API_KEY` and `LNC_SENDGRID_TEMPLATE_ID` (see `.env.example`)
2) If your SendGrid account requires verified senders/domains, set `LNC_SENDGRID_FROM_EMAIL` to a verified sender.
3) Send **1 email max** as a safety check:

```bash
python3 -m src.lnc_agent.cli send-sendgrid \
  --prospects data/prospects.csv \
  --drafts output/email_drafts.csv \
  --limit 1
```

### Dashboard (tracking like the mock)

```bash
python3 -m pip install -r requirements.txt
streamlit run src/lnc_agent/dashboard_app.py
```

The dashboard reads:

- an `output_*/dashboard.csv` folder (configurable in the sidebar)
- `data/sendgrid_events.jsonl`
- `output_sendgrid_report/sendgrid_agent_report.csv`

## Platform (modern UI + API)

Backend API (dev):

```bash
. .venv/bin/activate
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Endpoints:

- `POST /api/run` (generate outputs)
- `POST /api/send` (send via SendGrid)
- `POST /api/report/sendgrid` (merge tracking + agent decisions)
- `GET /api/dashboard`
- `GET /api/recommendations`
- `GET /api/tracking`

Docker (local dev / cloud-ready):

```bash
docker compose up -d --build
```

You will get:

- `output/recommendations.csv`
- `output/email_drafts.csv`
- `output/dashboard.csv`

`output/email_drafts.csv` contains:

- `from_email` (one of `agent1..agent100@ogenies.com`)
- `template_id` (from env `LNC_SENDGRID_TEMPLATE_ID`)
- `dynamic_template_data` (JSON string for SendGrid)
  - includes `variant` (A/B) and `send_hour` (timing)

### MySQL mode (existing cloud database)

```bash
python3 -m src.lnc_agent.cli run-mysql \
  --mysql-host "<host>" \
  --mysql-user "<user>" \
  --mysql-password "<password>" \
  --mysql-database "<database>" \
  --prospects-table "prospects" \
  --events-table "email_events" \
  --out output
```

### Twilio SendGrid Event Webhook (store events in MySQL)

Set env vars (see `.env.example`), then run:

```bash
uvicorn src.lnc_agent.webhook_app:app --host 0.0.0.0 --port 8000
```

SendGrid endpoint:

- `POST /webhooks/sendgrid/events`

## What The Agent Does

The agent follows the slide logic:

1. **Data intelligence**
   It reads opens, clicks, click speed, engagement, and supplier/provider performance.

2. **Interest scoring**
   Each prospect gets a score from 0 to 100.

3. **Decision**
   - high score: personalized email plus priority call
   - medium score: follow-up
   - low score: nurturing newsletter
   - unsubscribed prospects: do not contact

4. **Automation**
   The agent chooses campaign steps like `J0`, `J+2`, or `J+5`.

5. **Email generation**
   This MVP uses templates. Later, we can replace the template generator with OpenAI.

## Learn The Code In This Order

1. [models.py](src/lnc_agent/models.py): the data objects.
2. [scoring.py](src/lnc_agent/scoring.py): how scores are calculated.
3. [decision.py](src/lnc_agent/decision.py): how the agent chooses actions.
4. [email_generator.py](src/lnc_agent/email_generator.py): how drafts are created.
5. [agent.py](src/lnc_agent/agent.py): how everything is connected.
6. [cli.py](src/lnc_agent/cli.py): how you run it from the terminal.

## Next Improvements

- connect to Sender API to import campaign stats
- connect to your CRM to import prospects
- add OpenAI email generation
- build a Streamlit or Flask dashboard
- add A/B testing message variants
