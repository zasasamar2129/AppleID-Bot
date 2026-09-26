#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <backup_file.sql>"
  exit 1
fi

source ../.env

if [ -n "$DATABASE_URL" ]; then
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

PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME < "$1"

echo "Restore completed from $1"