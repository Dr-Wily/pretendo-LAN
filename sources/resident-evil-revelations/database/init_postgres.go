package database

// The matchmaking / tracking schema is NOT created here.
//
// nex-protocols-common-go v2.4.0 self-provisions its entire matchmaking
// schema: both match-making (0x15) and matchmake-extension (0x6D)
// CommonProtocol.SetManager run `CREATE SCHEMA IF NOT EXISTS` + `CREATE TABLE
// IF NOT EXISTS` for matchmaking.gatherings / matchmake_sessions /
// persistent_gatherings / community_participations / notifications and every
// tracking.* table, with the exact column types its queries expect
// (owner_pid / participants as numeric(10), matchmake_sessions.flags /
// state / system_password, progress_score smallint, ...).
//
// An earlier version of this file hand-authored that schema (copied from the
// Mario & Sonic Sochi 2014 server, whose NOTICE claims the library "expects
// the schema to already exist and never creates it" -- true for an older
// release, not v2.4.0). Because those tables were created before SetManager
// ran, its `CREATE TABLE IF NOT EXISTS` became a no-op and the mismatched
// column set surfaced to the console as SQL errors: Core::Unknown (106-0102),
// then Core::OperationAborted (106-0105).
//
// So: create the database, connect, and let SetManager build the schema.
func initPostgres() {}
