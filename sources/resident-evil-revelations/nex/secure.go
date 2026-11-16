package nex

import (
	"fmt"
	"os"
	"strconv"

	nex "github.com/PretendoNetwork/nex-go/v2"
	"github.com/PretendoNetwork/nex-go/v2/types"
	common_globals "github.com/PretendoNetwork/nex-protocols-common-go/v2/globals"
	common_matchmaking "github.com/PretendoNetwork/nex-protocols-common-go/v2/match-making"
	common_matchmaking_ext "github.com/PretendoNetwork/nex-protocols-common-go/v2/match-making-ext"
	common_matchmake_extension "github.com/PretendoNetwork/nex-protocols-common-go/v2/matchmake-extension"
	common_nat_traversal "github.com/PretendoNetwork/nex-protocols-common-go/v2/nat-traversal"
	common_secure "github.com/PretendoNetwork/nex-protocols-common-go/v2/secure-connection"
	common_utility "github.com/PretendoNetwork/nex-protocols-common-go/v2/utility"
	matchmaking "github.com/PretendoNetwork/nex-protocols-go/v2/match-making"
	matchmaking_ext "github.com/PretendoNetwork/nex-protocols-go/v2/match-making-ext"
	matchmaking_types "github.com/PretendoNetwork/nex-protocols-go/v2/match-making/types"
	matchmake_extension "github.com/PretendoNetwork/nex-protocols-go/v2/matchmake-extension"
	nat_traversal "github.com/PretendoNetwork/nex-protocols-go/v2/nat-traversal"
	secure "github.com/PretendoNetwork/nex-protocols-go/v2/secure-connection"
	utility "github.com/PretendoNetwork/nex-protocols-go/v2/utility"

	"github.com/Protarium-Network/re-revelations-nex/database"
	"github.com/Protarium-Network/re-revelations-nex/globals"
)

func StartSecureServer() {
	globals.SecureServer = nex.NewPRUDPServer()

	// See authentication.go: Wii U / NEX 3.x needs the legacy (empty)
	// connection-signature scheme for the PRUDPv1 CONNECT handshake.
	globals.SecureServer.PRUDPV1Settings.LegacyConnectionSignature = globals.LegacyConnectionSignature

	globals.SecureEndpoint = nex.NewPRUDPEndPoint(1)
	globals.SecureEndpoint.IsSecureEndPoint = true
	globals.SecureEndpoint.ServerAccount = globals.SecureServerAccount
	globals.SecureEndpoint.AccountDetailsByPID = globals.AccountDetailsByPID
	globals.SecureEndpoint.AccountDetailsByUsername = globals.AccountDetailsByUsername
	globals.SecureServer.BindPRUDPEndPoint(globals.SecureEndpoint)

	globals.SecureServer.LibraryVersions.SetDefault(nex.NewLibraryVersion(globals.NEXMajor, globals.NEXMinor, globals.NEXPatch))
	// MatchMaking serialisation is pinned below 3.4.0 -- see globals/config.go.
	// Revelations is NEX 3.4.13 with the MatchMaking lib pinned to 3.3.0, so MatchmakeSession has no 3.4 ProgressScore
	// byte (pre-3.4 layout, as on Trine 2 / Sochi 2014) but has
	// SessionKey. UseStructureHeader stays false (see authentication.go).
	globals.SecureServer.LibraryVersions.MatchMaking = nex.NewLibraryVersion(globals.MatchMakingMajor, globals.MatchMakingMinor, globals.MatchMakingPatch)
	globals.SecureServer.AccessKey = globals.AccessKey

	globals.SecureEndpoint.OnData(func(packet nex.PacketInterface) {
		request := packet.RMCMessage()
		if request == nil {
			return
		}
		pid := uint64(packet.Sender().PID())
		fmt.Printf("[REvelations Secure] PID=%d protocol=0x%02X method=0x%02X\n", pid, request.ProtocolID, request.MethodID)
	})

	globals.SecureEndpoint.OnConnectionEnded(func(connection *nex.PRUDPConnection) {
		fmt.Printf("[REvelations Secure] PID=%d disconnected\n", uint64(connection.PID()))
	})

	// The matchmaking manager needs the secure endpoint and the database.
	globals.MatchmakingManager = common_globals.NewMatchmakingManager(globals.SecureEndpoint, database.Postgres)
	globals.MatchmakingManager.GetUserFriendPIDs = globals.GetUserFriendPIDs

	registerSecureServerProtocols()

	port, _ := strconv.Atoi(os.Getenv("PN_REREV_SECURE_PORT"))
	globals.Logger.Successf("[REvelations] Secure server listening on UDP %d", port)
	globals.SecureServer.Listen(port)
}

// registerSecureServerProtocols wires the secure-connection handshake,
// Utility, NAT Traversal and the three matchmaking protocols -- the exact
// set BioRevHD.rpx proves it links (nn::nex::SecureConnectionService /
// NATTraversal / MatchMakingService / MatchmakeExtension DDL declarations).
// No Ranking, no DataStore: the game links neither.
func registerSecureServerProtocols() {
	// Secure Connection (0x0B) -- Register / RegisterEx: the console tells us
	// the station URLs other party members should use to reach it.
	secureProtocol := secure.NewProtocol()
	globals.SecureEndpoint.RegisterServiceProtocol(secureProtocol)
	secureCommon := common_secure.NewCommonProtocol(secureProtocol)
	secureCommon.EnableInsecureRegister()
	secureCommon.CreateReportDBRecord = func(pid types.PID, reportID types.UInt32, reportData types.QBuffer) error {
		globals.Logger.Warningf("[REvelations] Player report from PID %d (report ID %d, %d bytes) discarded: this server does not store reports",
			pid, reportID, len(reportData))
		return nil
	}

	// Utility (0x6E) -- NEX unique IDs. Not proven linked (no Utility DDL in
	// the RPX), registered defensively: it costs nothing at runtime and a
	// missing handler for a call the game does make is a silent hang.
	utilityProtocol := utility.NewProtocol()
	globals.SecureEndpoint.RegisterServiceProtocol(utilityProtocol)
	common_utility.NewCommonProtocol(utilityProtocol)

	// NAT Traversal (0x03) -- hole punching between the up-to-three consoles
	// in a co-op session.
	natTraversalProtocol := nat_traversal.NewProtocol()
	globals.SecureEndpoint.RegisterServiceProtocol(natTraversalProtocol)
	common_nat_traversal.NewCommonProtocol(natTraversalProtocol)

	// MatchMaking (0x15) + MatchMakingExt (0x32) -- gathering lifecycle,
	// participation, session URLs, host migration.
	matchMakingProtocol := matchmaking.NewProtocol()
	globals.SecureEndpoint.RegisterServiceProtocol(matchMakingProtocol)
	common_matchmaking.NewCommonProtocol(matchMakingProtocol).SetManager(globals.MatchmakingManager)

	matchMakingExtProtocol := matchmaking_ext.NewProtocol()
	globals.SecureEndpoint.RegisterServiceProtocol(matchMakingExtProtocol)
	common_matchmaking_ext.NewCommonProtocol(matchMakingExtProtocol).SetManager(globals.MatchmakingManager)

	// MatchmakeExtension (0x6D) -- create / browse / join / auto-matchmake a
	// co-op session. The RPX shows the game calls AutoMatchmake,
	// AutoMatchmakeWithSearchCriteria, AutoMatchmakeWithGatheringId,
	// CreateMatchmakeSession, BrowseMatchmakeSession, JoinMatchmakeSession(Ex),
	// Open/CloseParticipation and ModifyCurrentGameAttribute.
	matchmakeExtensionProtocol := matchmake_extension.NewProtocol()
	globals.SecureEndpoint.RegisterServiceProtocol(matchmakeExtensionProtocol)
	commonMatchmakeExtensionProtocol := common_matchmake_extension.NewCommonProtocol(matchmakeExtensionProtocol)
	commonMatchmakeExtensionProtocol.SetManager(globals.MatchmakingManager)

	// AutoMatchmakePostpone / AutoMatchmakeWithSearchCriteriaPostpone
	// hard-fail with Core::NotImplemented if these two cleanup callbacks are
	// nil, even though there is nothing to clean up. Pretendo's own reference
	// server sets the same pair to no-ops.
	commonMatchmakeExtensionProtocol.CleanupMatchmakeSessionSearchCriterias = func(searchCriterias types.List[matchmaking_types.MatchmakeSessionSearchCriteria]) {}
	commonMatchmakeExtensionProtocol.CleanupSearchMatchmakeSession = func(matchmakeSession *matchmaking_types.MatchmakeSession) {}

	// No Revelations matchmaking capture exists, so log the decoded request server
	// side for the call a host makes. OnAfter* runs only after the common
	// handler succeeds -- a safe, non-intrusive hook (unlike replacing the
	// handler itself).
	commonMatchmakeExtensionProtocol.OnAfterCreateMatchmakeSession = func(packet nex.PacketInterface, anyGathering matchmaking_types.GatheringHolder, message types.String, participationCount types.UInt16) {
		if ms, ok := anyGathering.Object.(matchmaking_types.MatchmakeSession); ok {
			fmt.Printf("[MM] CreateMatchmakeSession OK: gameMode=%d attribs=%v min=%d max=%d open=%v sysType=%d appBuf=%dB msg=%q pc=%d\n",
				uint32(ms.GameMode), ms.Attributes, uint16(ms.Gathering.MinimumParticipants), uint16(ms.Gathering.MaximumParticipants),
				bool(ms.OpenParticipation), uint32(ms.MatchmakeSystemType), len(ms.ApplicationBuffer), string(message), uint16(participationCount))
		}
	}
	commonMatchmakeExtensionProtocol.OnAfterOpenParticipation = func(packet nex.PacketInterface, gid types.UInt32) {
		fmt.Printf("[MM] OpenParticipation OK: gid=%d\n", uint32(gid))
	}
}
