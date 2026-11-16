package globals

import (
	"os"
	"strings"
)

// NEX configuration for "Resident Evil: Revelations" (Wii U, Capcom, 2013).
//
// AccessKey and the NEX SDK version come from the retail executable
// (BioRevHD.rpx, EUR update v16): the UTF-16 literal "59d539a9" in .rodata
// 0x1029ebdc (no static code reference: it is loaded through a table), and
// .module_id carries "[SDK+Nintendo:NEX_3_2_1]" and "[SDK+Nintendo:NEX_MM_3_2_1]".
// Confirmed against a real console: its PRUDPv1 CONNECT signature only verifies
// with this key (the other 8-hex literal in the binary, ab8db073, does not).
// kinnay.github.io's Wii U NEX database lists it too ("BIOHAZARD REVELATIONS UE":
// id 269562112 = 10113100, key 59d539a9, build 3_4_13_3_0). See RECON.md.
//
// The game links the Authentication, SecureConnection, NAT Traversal,
// MatchMaking / MatchMakingExt / MatchmakeExtension and HostMigration
// protocols and NOT Ranking or DataStore (MtNetRanking is a stub class).
//
// Console-verified: the EUR title (1012B400) asks for game server ID 10113100,
// i.e. one ID serves every region (like DKC:TF). The per-region IDs below are
// still registered defensively. The PRUDP server is region-agnostic; the IDs
// only matter to the NASC / nex_token front-end.
const (
	AccessKey = "59d539a9"

	GameServerIDEUR = "1012b400" // title 000500001012B400 (WUP-P-ABHP) - read from the dump
	GameServerIDUSA = "1012cf00" // title 000500001012CF00 (WUP-P-ABHE) - wiiubrew title DB
	GameServerIDJPN = "10113100" // title 0005000010113100 (WUP-P-ABHJ, "BIOHAZARD REVELATIONS Unveiled Edition") - wiiubrew title DB

	// ServerBuildString is echoed back to the client in Login/LoginEx as
	// strReturnMsg. The game only logs it.
	ServerBuildString = "branch:origin/release/ngs/3.4.x.3 build:3_4_13_3_0"

	// PRUDP library version reported by both endpoints: kinnay lists this
	// title as build 3_4_13_3_0 (the NEX_3_2_1 / NEX_MM_3_2_1 strings in the
	// binary are per-library tags, not the NGS build).
	NEXMajor = 3
	NEXMinor = 4
	NEXPatch = 13

	// MatchMaking pinned below 3.4.0 (pre-3.4 MatchmakeSession layout), as on
	// every other 3.4.13 title of this family.
	MatchMakingMajor = 3
	MatchMakingMinor = 3
	MatchMakingPatch = 0
)

// GameServerIDs lists every region this server is meant to serve.
var GameServerIDs = []string{GameServerIDEUR, GameServerIDUSA, GameServerIDJPN}

// LegacyConnectionSignature selects the PRUDPv1 CONNECT signature scheme.
// Console capture: the CONNECT is signed with the server connection signature
// from the SYN-ACK, i.e. legacy = false. PN_REREV_LEGACY_SIGNATURE=0|1 overrides.
var LegacyConnectionSignature = false

func init() {
	if v := strings.TrimSpace(os.Getenv("PN_REREV_LEGACY_SIGNATURE")); v != "" {
		LegacyConnectionSignature = v == "1"
	}
}
