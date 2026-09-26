#!/bin/bash
# Apple ID Store Bot - Server Setup Script
# Run this script on your server to set up the bot

set -e

echo "=========================================="
echo "Apple ID Store Bot - Server Setup"
echo "=========================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "WARNING: Running as root. Consider using a non-root user."
fi

# Check for required tools
command -v docker >/dev/null 2>&1 || { echo "ERROR: Docker is not installed. Please install Docker first."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "ERROR: Docker Compose is not installed. Please install Docker Compose first."; exit 1; }

# Check if .env exists
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo "IMPORTANT: Please edit .env with your actual configuration values!"
        echo "Press Enter to open .env in editor, or Ctrl+C to exit..."
        read
        ${EDITOR:-nano} .env
    else
        echo "ERROR: .env.example not found!"
        exit 1
    fi
fi

# Source .env to get values
export $(grep -v '^#' .env | xargs)

# Validate required variables
if [ -z "$BOT_TOKEN" ]; then
    echo "ERROR: BOT_TOKEN is not set in .env!"
    exit 1
fi

if [ -z "$ENCRYPTION_KEY" ]; then
    echo "ERROR: ENCRYPTION_KEY is not set in .env!"
    echo "Generate one with: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
    exit 1
fi

if [ -z "$DB_PASSWORD" ]; then
    echo "ERROR: DB_PASSWORD is not set in .env!"
    exit 1
fi

echo "Configuration validated."

# Start PostgreSQL and Redis
echo "Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
        echo "PostgreSQL is ready!"
        break
    fi
    sleep 1
done

# Run database setup
echo "Setting up database..."
docker-compose run --rm bot python scripts/setup_database.py

# Start the bot
echo "Starting the bot..."
docker-compose up -d bot

echo ""
echo "=========================================="
echo "Setup completed successfully!"
echo "=========================================="
echo ""
echo "Useful commands:"
echo "  View logs:        docker-compose logs -f bot"
echo "  Stop bot:         docker-compose stop bot"
echo "  Restart bot:      docker-compose restart bot"
echo "  View all logs:    docker-compose logs -f"
echo "  Stop everything:  docker-compose down"
echo "  Backup DB:        ./scripts/backup.sh"
echo "  Restore DB:       ./scripts/restore.sh <backup_file>"
echo ""