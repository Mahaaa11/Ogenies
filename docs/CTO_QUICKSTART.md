# L&C Emailing — CTO Quickstart (Local Web App)

## What this is
This project is a **web application** (Frontend + API + MySQL).
It runs locally with **Docker Compose** and is accessed via your browser.

## Prerequisites
- **Docker Desktop** installed and running

## Start (recommended)
From the project root:

```bash
docker compose up -d --build
```

## URLs
- **Web app (UI)**: `http://localhost:3001`
- **API**: `http://localhost:8000/health`
- **phpMyAdmin** (MySQL UI): `http://localhost:8080`

## phpMyAdmin credentials (default)
- **Server/Host**: `mysql`
- **Port**: `3306`
- **User**: `lnc`
- **Password**: `lnc`
- **Database**: `lnc_emailing`

## Database (where it is / how it’s created)
- MySQL runs in the Docker container **`mysql`**
- Data persists in a Docker volume: **`mysql_data`**
- Tables + seed are created automatically on first start by:
  - `docker/mysql/01_schema.sql` (tables)
  - `docker/mysql/02_seed_prospects.sql` (P001..P100, agent1..agent100 @ogenies.com)

## Stop
```bash
docker compose down
```

## Reset everything (including DB)
WARNING: this deletes the MySQL data volume.

```bash
docker compose down -v
```
