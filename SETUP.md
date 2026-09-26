# Apple ID Store Bot — Server Setup Guide

## Quick Overview

| Component | Details |
|---|---|
| **Python** | 3.12+ |
| **Database** | PostgreSQL 16+ |
| **Cache** | Redis 7+ |
| **Container** | Docker + Docker Compose (optional but recommended) |
| **ORM** | SQLAlchemy 2.0 + asyncpg |
| **Migrations** | Alembic |

---

## Option 1: Docker Compose (Recommended)

### Step 1 — Install prerequisites

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose

# Enable and start Docker
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

### Step 2 — Clone the repo

```bash
git clone <repo-url> appleid-bot
cd appleid-bot
```

### Step 3 — Create `.env` file

```bash
cp .env.example .env
nano .env
```

**Edit these required values:**

```env
BOT_TOKEN=your_telegram_bot_token_here
DB_PASSWORD=your_strong_database_password
ENCRYPTION_KEY=generate_with: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
ADMIN_IDS=your_telegram_chat_id
```

Optional but recommended:

```env
DB_HOST=postgres          # inside Docker network
DB_PORT=5432
DB_NAME=apple_store
DB_USER=apple_bot
REDIS_URL=redis://redis:6379/0
```

> Generate `ENCRYPTION_KEY` once and keep it safe — you'll need it to decrypt inventory data.

### Step 4 — Run the full setup

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

This will:
1. Start PostgreSQL + Redis containers
2. Create the database and user
3. Run all Alembic migrations
4. Start the bot

### Step 5 — Verify

```bash
docker-compose ps
docker-compose logs -f bot
```

---

## Option 2: Bare Metal (No Docker)

### Step 1 — Install system packages

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip \
    postgresql postgresql-contrib redis-server \
    libpq-dev gcc

# Start services
sudo systemctl enable postgresql redis-server
sudo systemctl start postgresql redis-server
```

### Step 2 — Create PostgreSQL user and database

```bash
sudo -u postgres psql <<'EOF'
CREATE USER apple_bot WITH PASSWORD 'your_strong_password';
CREATE DATABASE apple_store OWNER apple_bot;
GRANT ALL PRIVILEGES ON DATABASE apple_store TO apple_bot;
\q
EOF
```

### Step 3 — Clone repo and set up virtual environment

```bash
git clone <repo-url> appleid-bot
cd appleid-bot
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 4 — Create `.env`

```bash
cp .env.example .env
nano .env
```

Set:
```env
BOT_TOKEN=your_telegram_bot_token
DB_HOST=localhost
DB_PORT=5432
DB_NAME=apple_store
DB_USER=apple_bot
DB_PASSWORD=your_strong_password
REDIS_URL=redis://localhost:6379/0
ENCRYPTION_KEY=your_generated_key
```

### Step 5 — Initialize the database

```bash
# Using the provided script (recommended)
python scripts/setup_database.py
```

Or manually with Alembic:
```bash
alembic upgrade head
```

### Step 6 — Run the bot

```bash
python -m app.main
```

Or as a systemd service (included):
```bash
sudo cp systemd/apple-store-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable apple-store-bot
sudo systemctl start apple-store-bot
sudo systemctl status apple-store-bot
```

---

## Docker Compose — Manual Steps (if setup.sh doesn't work)

```bash
# Build and start the stack
docker-compose up -d --build

# Initialize database (one-time)
docker-compose run --rm bot python scripts/setup_database.py

# Start the bot service
docker-compose up -d bot

# View logs
docker-compose logs -f bot

# Stop everything
docker-compose down
```

---

## Maintenance Commands

| Command | Description |
|---|---|
| `docker-compose logs -f bot` | Watch bot logs |
| `docker-compose restart bot` | Restart bot |
| `./scripts/backup.sh` | Backup PostgreSQL database |
| `./scripts/restore.sh <file>` | Restore from backup |
| `docker-compose down -v` | Stop and remove all volumes (⚠️ deletes DB) |

---

## Verification Checklist

- [ ] `docker-compose ps` shows all services as `Up`
- [ ] `docker-compose logs bot` shows bot connecting to Telegram
- [ ] Bot responds to `/start` in Telegram
- [ ] Admin panel accessible with your `ADMIN_IDS`

---

## Troubleshooting

**Bot won't start?**
```bash
docker-compose logs bot
```
Common cause: missing `BOT_TOKEN` or `ENCRYPTION_KEY` in `.env`.

**Database connection errors?**
```bash
docker-compose exec postgres pg_isready -U apple_bot -d apple_store
```

**Migrations fail?**
```bash
docker-compose run --rm bot alembic upgrade head
```

---

## Key Files Reference

| File | Purpose |
|---|---|
| `.env` | All configuration (never commit this!) |
| `docker-compose.yml` | Docker orchestration |
| `Dockerfile` | Container image |
| `alembic.ini` + `alembic/` | Database migrations |
| `app/config.py` | Settings loaded from `.env` |
| `app/database/models/` | SQLAlchemy ORM models |
| `scripts/setup_database.py` | DB creation + migration runner |
| `systemd/apple-store-bot.service` | Systemd service unit |
| `scripts/backup.sh` | PostgreSQL backup |
| `scripts/restore.sh` | PostgreSQL restore |
