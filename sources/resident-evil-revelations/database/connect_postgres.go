package database

import (
	"database/sql"
	"os"

	_ "github.com/lib/pq"

	"github.com/Protarium-Network/re-revelations-nex/globals"
)

// Postgres backs the matchmaking manager (gatherings, matchmake sessions,
// participants, tracking logs). It is the only stateful store this server
// needs -- Revelations links no Ranking or DataStore.
var Postgres *sql.DB

func ConnectPostgres() {
	var err error

	Postgres, err = sql.Open("postgres", os.Getenv("PN_REREV_POSTGRES_URI"))
	if err != nil {
		globals.Logger.Critical(err.Error())
		os.Exit(1)
	}

	if err = Postgres.Ping(); err != nil {
		globals.Logger.Critical(err.Error())
		os.Exit(1)
	}

	globals.Logger.Success("Connected to Postgres!")

	// No schema work here: nex-protocols-common-go's SetManager provisions the
	// whole matchmaking / tracking schema itself -- see init_postgres.go.
	initPostgres()
}
