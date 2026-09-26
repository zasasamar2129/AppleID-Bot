# Apple ID Store Telegram Bot

A production-grade Telegram bot for managing Apple ID sales, built with aiogram 3, PostgreSQL, Redis, and Docker.

## Features
- Bilingual (Persian/English)
- Product management (Personal & Ready-Made)
- Inventory encryption & reservation system
- Order lifecycle with state machine
- Online payment adapter (custom API) & card-to-card
- Wallet system with ledger
- Coupons, referrals, support tickets
- Admin panel with role-based access
- Broadcast system with audience filters
- Statistics, audit logs, scheduler workers
- Fully containerized with Docker

## Requirements
- Python 3.12+
- PostgreSQL 16+
- Redis 7+

## Local Installation

1. Clone repository:
   ```bash
   git clone <repo> appleid-bot
   cd appleid-bot