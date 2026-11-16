// Command re-revelations-nex is a preservation NEX server for the Wii U title
// Trine 2: Director's Cut (Frozenbyte, 2012).
//
// It runs the two PRUDP servers the game expects: an authentication server
// that hands out Kerberos tickets, and a secure server that does the
// online co-op matchmaking (NAT Traversal + MatchMaking + MatchMakingExt +
// MatchmakeExtension). The game links no Ranking or DataStore protocols, so
// this server implements none.
package main

import (
	"sync"

	"github.com/Protarium-Network/re-revelations-nex/nex"
)

func main() {
	var wg sync.WaitGroup
	wg.Add(2)

	go func() {
		defer wg.Done()
		nex.StartAuthenticationServer()
	}()
	go func() {
		defer wg.Done()
		nex.StartSecureServer()
	}()

	wg.Wait()
}
