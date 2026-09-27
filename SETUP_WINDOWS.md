# Apple ID Store Bot — Windows Manual Setup

## Prerequisites

| Tool | Version | Install Link |
|---|---|---|
| Python | 3.12+ | <https://python.org/downloads> |
| PostgreSQL | 16+ | <https://www.postgresql.org/download/windows/> |
| Redis | 7+ | <https://github.com/microsoftarchive/redis/releases> (or use WSL2) |
| Git | latest | <https://git-scm.com/download/win> |

> **Note:** Redis on Windows is not officially supported. Best option: install via **WSL2** (`wsl --install`, then `sudo apt install redis-server`) or use a Docker container for Redis only.

---

## Step 1 — Install PostgreSQL

1. Run the PostgreSQL installer
2. Remember the **superuser password** you set (default user: `postgres`)
3. Default port: `5432`
4. Add PostgreSQL `bin` folder to PATH (e.g., `C:\Program Files\PostgreSQL\16\bin`)

---

## Step 2 — Install Redis (via WSL2 - Recommended)

```powershell
# In PowerShell as Administrator
wsl --install
# Restart computer, then:
wsl sudo apt update && sudo apt install -y redis-server
wsl sudo service redis-server start
```

Redis will run on `localhost:6379` from Windows.

**Alternative:** Use Docker for Redis only:
```powershell
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

---

## Step 3 — Clone & Setup Project

```powershell
# In PowerShell or Command Prompt
cd D:\
git clone <your-repo-url> appleid-bot
cd appleid-bot
```

---

## Step 4 — Create Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 5 — Create Database & User

Open **Command Prompt** (or `psql` if in PATH):

```cmd
psql -U postgres
```

Then in psql shell:

```sql
CREATE USER apple_bot WITH PASSWORD 'your_strong_password';
CREATE DATABASE apple_store OWNER apple_bot;
GRANT ALL PRIVILEGES ON DATABASE apple_store TO apple_bot;
\q
```

---

## Step 6 — Configure `.env`

```powershell
copy .env.example .env
notepad .env
```

**Required values to edit:**

```env
BOT_TOKEN=123456789:ABC-DEF-your-bot-token
DB_HOST=localhost
DB_PORT=5432
DB_NAME=apple_store
DB_USER=apple_bot
DB_PASSWORD=your_strong_password
REDIS_URL=redis://localhost:6379/0
ENCRYPTION_KEY=generate-with-python-below
ADMIN_IDS=123456789
```

**Generate ENCRYPTION_KEY:**
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output into `.env`.

---

## Step 7 — Run Database Setup

```powershell
.\.venv\Scripts\activate
python scripts\setup_database.py
```

Expected output:
```
============================================================
Apple ID Store Bot - Database Setup
============================================================
Host: localhost
Port: 5432
Database: apple_store
User: apple_bot
============================================================
Creating database 'apple_store'...
Database 'apple_store' already exists.
Creating user 'apple_bot'...
User 'apple_bot' already exists.
Granting privileges on database 'apple_store' to user 'apple_bot'...
Privileges granted!
Running database migrations...
Migrations completed successfully!

Created tables (22):
  - admin_users
  - audit_logs
  - broadcast_receipts
  - broadcasts
  - coupons
  - coupon_usages
  - inventory
  - orders
  - payments
  - products
  - referrals
  - settings
  - support_messages
  - support_tickets
  - unlock_inquiries
  - unlock_requests
  - users
  - wallet_transactions
  - wallets
  ...

============================================================
Database setup completed successfully!
============================================================
```

---

## Step 8 — Run the Bot

```powershell
python -m app.main
```

You should see:
```
INFO: Starting bot...
INFO: Bot started successfully
```

---

## Step 9 — Test in Telegram

1. Open Telegram
2. Message your bot `/start`
3. It should reply with the main menu

---

## Running as a Windows Service (Optional)

Use **NSSM** (Non-Sucking Service Manager):

```powershell
# Download NSSM from https://nssm.cc/download
# Extract and add to PATH

# Install service
nssm install AppleIDBot
# In GUI:
#   Path: D:\appleid-bot\.venv\Scripts\python.exe
#   Startup directory: D:\appleid-bot
#   Arguments: -m app.main
#   Environment: copy all lines from .env (NSSM allows multi-line env)

# Start service
nssm start AppleIDBot

# View logs
nssm status AppleIDBot
```

---

## Backup / Restore

```powershell
# Backup
.\scripts\backup.ps1   # (create this if needed, or use pg_dump directly)

# Manual backup
pg_dump -h localhost -p 5432 -U apple_bot -d apple_store > backup_%date:~-4,4%%date:~-7,2%%date:~-10,2%.sql

# Restore
psql -h localhost -p 5432 -U apple_bot -d apple_store < backup_file.sql
```

---

## Quick Command Summary

```powershell
# Activate venv
.\.venv\Scripts\activate

# Run bot
python -m app.main

# Run migrations manually
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Run tests
pytest
```

---

## Common Issues

| Issue | Fix |
|---|---|
| `psql: not recognized` | Add PostgreSQL `bin` to PATH |
| `redis connection refused` | Start Redis: `wsl sudo service redis-server start` |
| `ENCRYPTION_KEY not set` | Generate with Python command above |
| `BOT_TOKEN invalid` | Get new token from @BotFather |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` in activated venv |