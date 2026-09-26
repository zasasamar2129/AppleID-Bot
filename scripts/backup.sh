#!/bin/bash
set -e

# Load environment
source ../.env

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
mkdir -p $BACKUP_DIR

if [ -n "$DATABASE_URL" ]; then
  # Extract connection details from URL (simplified)
  DB_HOST=$(echo $DATABASE_URL | sed -e 's/.*@//' -e 's/:.*//')
  DB_PORT=$(echo $DATABASE_URL | sed -e 's/.*://' -e 's/\/.*//')
  DB_NAME=$(echo $DATABASE_URL | sed -e 's/.*\///')
  DB_USER=$(echo $DATABASE_URL | sed -e 's/.*\/\/\(.*\):.*@.*/\1/')
  DB_PASSWORD=$(echo $DATABASE_URL | sed -e 's/.*:\/\/.*:\(.*\)@.*/\1/')
else
  DB_HOST=${DB_HOST:-localhost}
  DB_PORT=${DB_PORT:-5432}
  DB_NAME=${DB_NAME:-apple_store}
  DB_USER=${DB_USER:-apple_bot}
  DB_PASSWORD=${DB_PASSWORD}
fi

PGPASSWORD=$DB_PASSWORD pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME > "$BACKUP_DIR/backup_$TIMESTAMP.sql"

echo "Backup created: $BACKUP_DIR/backup_$TIMESTAMP.sql"