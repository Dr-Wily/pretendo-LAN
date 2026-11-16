# The matchmaking / tracking schema

**This server does not create the matchmaking schema.**
`nex-protocols-common-go` (v2.4.x) does it itself: `CommonProtocol.SetManager`
in both the `match-making` (0x15) and `matchmake-extension` (0x6D) protocols
runs, on every start:

- `CREATE SCHEMA IF NOT EXISTS matchmaking` / `tracking`
- `CREATE TABLE IF NOT EXISTS` for `matchmaking.gatherings`,
  `matchmake_sessions`, `persistent_gatherings`, `community_participations`,
  `notifications`, and `tracking.register_gathering` /
  `unregister_gathering` / `join_gathering` / `leave_gathering` /
  `disconnect_gathering` / `change_host` / `change_owner` /
  `notification_data` / `participate_community`
- `UPDATE matchmaking.gatherings SET registered=false WHERE type='MatchmakeSession'`
  and `UPDATE matchmaking.notifications SET active=false` (clean slate on restart)

So `database/connect_postgres.go` just opens the pool and pings it;
`database/init_postgres.go` is a deliberate no-op.

## Why this isn't hand-authored

An earlier version of this repo carried a hand-written schema copied from the
Mario & Sonic Sochi 2014 server, on the assumption (from that repo's NOTICE)
that the library "expects the schema to already exist and never creates it".
That is **not true for v2.4.x** — and because `initPostgres` ran before
`SetManager`, the library's `CREATE TABLE IF NOT EXISTS` became a no-op and
the hand-written column set won. The mismatches were real and console-visible:

| Column | hand-written | library | symptom |
|---|---|---|---|
| `gatherings.owner_pid`, `.host_pid`, `.participants` | `bigint` / `bigint[]` | `numeric(10)` / `numeric(10)[]` | PID scan/compare drift |
| `matchmake_sessions.flags`, `.state` | missing | present | — |
| `matchmake_sessions.system_password` | missing | `text NOT NULL DEFAULT ''` | `GetMatchmakeSessionByID` `SELECT`s it → SQL error → `Core::Unknown` (Wii U **106-0102**), then **106-0105** — every `OpenParticipation` / join failed |
| `matchmake_sessions.progress_score` | `integer` | `smallint` | — |

## If matchmaking misbehaves

The library owns the schema now, so a fresh database is the fix for schema
drift (`docker compose down -v`). If a matchmaking call still fails with a
SQL error, the failing query is in `nex-protocols-common-go`'s
`match-making*/database/` packages — pin a matching library version rather
than editing the database.
