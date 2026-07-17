# Discord IAM + Community Portal

A simple Discord-backed web platform with:
- User portal (Discord login)
- Admin IAM portal (user management + moderation tools)
- Bot-driven server sync layer

---

## 🧱 Architecture

Discord Server
|
| (Bot + Gateway)
v
Sync Service (Python / Bot)
|
| fetch /guilds/{guild.id}/members
v
Database (Users + Memberships)
|
v
Backend API
|
v
Frontend Web App
├── User Portal (events, content, dashboard)
└── Admin Portal (IAM + moderation)


---

## 🔐 Authentication

- Users sign in via Discord OAuth2
- Bot syncs server members via Discord API
- Admin access controlled via internal role system

---

## 📡 Discord Data Collected

From:
`GET /guilds/{guild.id}/members`

Each member contains:

- `id` → unique Discord user ID (primary key)
- `username` → Discord username
- `global_name` → display name
- `avatar` → profile image reference
- `discriminator` → legacy tag system (may be "0")
- `flags / public_flags` → account metadata
- `roles` → guild role IDs
- `nick` → server nickname (if set)

Stored minimal fields:

- `id`
- `username`
- `global_name`

---

## 🛠 Admin Portal (IAM)

The admin system allows:
- Import/sync members from Discord
- View and manage users
- Moderate users (warn / timeout / ban via bot)
- Future: AI-assisted risk scoring (flagging suspicious behaviour)

---

## ⚠️ Notes

- Discord is the source of identity, not system state
- Database is the source of truth for the application
- Member sync must be periodic (users change over time)


## RUNNING THE SERVER
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --ssl-keyfile=key.pem --ssl-certfile=cert.pem






