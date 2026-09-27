#!/usr/bin/env python3
"""
Database setup script for Apple ID Store Bot.
Run this script on your server to initialize the database.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)  # so .env / alembic.ini resolve from any cwd

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from alembic.config import Config
from alembic import command
from app.config import settings
from app.database.base import Base
from app.database.models import *  # noqa


async def create_database_if_not_exists():
    """Create the database if it doesn't exist."""
    # Connect to postgres database to create our database
    postgres_url = f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/postgres"

    engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT")

    async with engine.connect() as conn:
        # Check if database exists
        result = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": settings.db_name}
        )
        exists = result.scalar() is not None

        if not exists:
            print(f"Creating database '{settings.db_name}'...")
            await conn.execute(text(f'CREATE DATABASE "{settings.db_name}"'))
            print(f"Database '{settings.db_name}' created successfully!")
        else:
            print(f"Database '{settings.db_name}' already exists.")

    await engine.dispose()


async def create_user_if_not_exists():
    """Create the database user if it doesn't exist."""
    postgres_url = f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/postgres"

    engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT")

    async with engine.connect() as conn:
        # Check if user exists
        result = await conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :user_name"),
            {"user_name": settings.db_user}
        )
        exists = result.scalar() is not None

        if not exists:
            print(f"Creating user '{settings.db_user}'...")
            await conn.execute(
                text(f'CREATE USER "{settings.db_user}" WITH PASSWORD \'{settings.db_password}\'')
            )
            print(f"User '{settings.db_user}' created successfully!")
        else:
            print(f"User '{settings.db_user}' already exists.")

        # Grant privileges
        print(f"Granting privileges on database '{settings.db_name}' to user '{settings.db_user}'...")
        await conn.execute(
            text(f'GRANT ALL PRIVILEGES ON DATABASE "{settings.db_name}" TO "{settings.db_user}"')
        )
        print("Privileges granted!")

    await engine.dispose()


async def run_migrations():
    """Run Alembic migrations."""
    print("Running database migrations...")

    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url_final)

    try:
        # alembic/env.py calls asyncio.run() internally -> must not be inside a live loop
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
        print("Migrations completed successfully!")
    except Exception as e:
        print(f"Error running migrations: {e}")
        raise


async def verify_tables():
    """Verify that all tables were created."""
    engine = create_async_engine(settings.database_url_final)

    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result.fetchall()]

        print(f"\nCreated tables ({len(tables)}):")
        for table in tables:
            print(f"  - {table}")

    await engine.dispose()


async def main():
    """Main setup function."""
    print("=" * 60)
    print("Apple ID Store Bot - Database Setup")
    print("=" * 60)
    print(f"Host: {settings.db_host}")
    print(f"Port: {settings.db_port}")
    print(f"Database: {settings.db_name}")
    print(f"User: {settings.db_user}")
    print("=" * 60)

    # Validate required settings
    if not settings.db_password:
        print("ERROR: DB_PASSWORD is not set in .env file!")
        sys.exit(1)

    if not settings.encryption_key:
        print("ERROR: ENCRYPTION_KEY is not set in .env file!")
        sys.exit(1)

    if not settings.bot_token:
        print("ERROR: BOT_TOKEN is not set in .env file!")
        sys.exit(1)

    try:
        # Create database and user
        await create_database_if_not_exists()
        await create_user_if_not_exists()

        # Run migrations
        await run_migrations()

        # Verify
        await verify_tables()

        print("\n" + "=" * 60)
        print("Database setup completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: Database setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())