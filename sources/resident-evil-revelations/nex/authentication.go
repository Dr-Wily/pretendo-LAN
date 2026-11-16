// Package nex is the Resident Evil: Revelations (Wii U, Capcom) NEX server.
//
// Two PRUDP endpoints run as separate goroutines: an authentication server
// (Ticket Granting only) and a secure server (Secure Connection, Utility,
// NAT Traversal and the three matchmaking protocols). The game links no
// Ranking or DataStore -- see RECON.md and PROTOCOL_COVERAGE.md.
package nex

import (
	"fmt"
	"os"
	"strconv"

	nex "github.com/PretendoNetwork/nex-go/v2"
	"github.com/PretendoNetwork/nex-go/v2/constants"
	"github.com/PretendoNetwork/nex-go/v2/types"
	common_ticket_granting "github.com/PretendoNetwork/nex-protocols-common-go/v2/ticket-granting"
	ticket_granting "github.com/PretendoNetwork/nex-protocols-go/v2/ticket-granting"

	"github.com/Protarium-Network/re-revelations-nex/globals"
)

func StartAuthenticationServer() {
	globals.AuthenticationServer = nex.NewPRUDPServer()

	// Wii U / NEX 3.x PRUDPv1: the console signs its CONNECT with an empty
	// connection signature and expects the CONNECT-ACK signed the same way.
	// nex-go's default (false) mixes the client's connection signature into
	// the CONNECT-ACK HMAC, which a real console rejects -- it then retransmits
	// CONNECT forever and finally reports 106-0502 (Transport::ConnectionFailure),
	// confirmed from a packet capture. SYN/SYN-ACK are unaffected (they use an
	// empty connection signature either way).
	globals.AuthenticationServer.PRUDPV1Settings.LegacyConnectionSignature = globals.LegacyConnectionSignature

	globals.AuthenticationEndpoint = nex.NewPRUDPEndPoint(1)
	globals.AuthenticationEndpoint.ServerAccount = globals.AuthenticationServerAccount
	globals.AuthenticationEndpoint.AccountDetailsByPID = globals.AccountDetailsByPID
	globals.AuthenticationEndpoint.AccountDetailsByUsername = globals.AccountDetailsByUsername
	globals.AuthenticationServer.BindPRUDPEndPoint(globals.AuthenticationEndpoint)

	globals.AuthenticationServer.LibraryVersions.SetDefault(nex.NewLibraryVersion(globals.NEXMajor, globals.NEXMinor, globals.NEXPatch))
	globals.AuthenticationServer.AccessKey = globals.AccessKey
	// Revelations ships NEX 3.4.13 like the other titles of this family, whose client
	// is assumed NOT to
	// write a structure-header version byte before AuthenticationInfo.Data --
	// just a 4-byte content length. Leave ByteStreamSettings.UseStructureHeader
	// at the library default (false); setting it true misaligns every field
	// after the token string.

	globals.AuthenticationEndpoint.OnData(func(packet nex.PacketInterface) {
		request := packet.RMCMessage()
		if request == nil {
			return
		}
		pid := uint64(packet.Sender().PID())
		fmt.Printf("[REvelations Auth] PID=%d protocol=0x%02X method=0x%02X\n", pid, request.ProtocolID, request.MethodID)
	})

	registerAuthenticationServerProtocols()

	port, _ := strconv.Atoi(os.Getenv("PN_REREV_AUTH_PORT"))
	globals.Logger.Successf("[REvelations] Authentication server listening on UDP %d", port)
	globals.AuthenticationServer.Listen(port)
}

func registerAuthenticationServerProtocols() {
	ticketGrantingProtocol := ticket_granting.NewProtocol()
	globals.AuthenticationEndpoint.RegisterServiceProtocol(ticketGrantingProtocol)
	commonTicketGrantingProtocol := common_ticket_granting.NewCommonProtocol(ticketGrantingProtocol)

	securePort, _ := strconv.Atoi(os.Getenv("PN_REREV_SECURE_PORT"))

	// Must stay short (~15 chars): the retail binary truncates this field into
	// a small fixed-size buffer, so use a bare host, not a subdomain.
	secureHost := os.Getenv("PN_REREV_SECURE_HOST")
	if secureHost == "" {
		secureHost = "localhost"
	}

	secureStationURL := types.NewStationURL("")
	secureStationURL.SetURLType(constants.StationURLPRUDPS)
	secureStationURL.SetAddress(secureHost)
	secureStationURL.SetPortNumber(uint16(securePort))
	secureStationURL.SetConnectionID(1)
	secureStationURL.SetPrincipalID(types.NewPID(2))
	secureStationURL.SetStreamID(1)
	secureStationURL.SetStreamType(constants.StreamTypeRVSecure)
	secureStationURL.SetType(uint8(constants.StationURLFlagPublic))

	commonTicketGrantingProtocol.ValidateLoginData = globals.ValidateLoginData
	commonTicketGrantingProtocol.SecureStationURL = secureStationURL
	commonTicketGrantingProtocol.BuildName = types.NewString(globals.ServerBuildString)
	commonTicketGrantingProtocol.SecureServerAccount = globals.SecureServerAccount
}
