# Protocol coverage

Nothing here has been observed on a console yet. "Stock" means the
`nex-protocols-common-go` handler, unmodified.

## Transport (PRUDPv1)

`LegacyConnectionSignature` defaults to `false` on both endpoints, verified: the console's CONNECT packet is signed with the server connection signature (`PN_REREV_LEGACY_SIGNATURE=0|1` overrides).
`ByteStreamSettings.UseStructureHeader` stays `false`.

## Authentication endpoint

| Protocol | Coverage |
|---|---|
| Ticket Granting | Login / LoginEx / RequestTicket (stock) |

## Secure endpoint

| Protocol | Coverage |
|---|---|
| Secure Connection | stock, insecure `Register` enabled |
| Utility | stock, registered defensively |
| NAT Traversal | stock |
| MatchMaking / MatchMakingExt | stock; library pinned to 3.3.0 (pre-3.4 `MatchmakeSession`, no ProgressScore byte) |
| MatchmakeExtension | stock; `Cleanup*` callbacks set to no-ops so the `*_Postpone` auto-matchmake calls don't return NotImplemented |

### Likely follow-ups once a console log exists

- `AutoMatchmakeWithSearchCriteria_Postpone` mis-decoding: port `nex/automatch_patch.go` from the Sochi 2014 / Ninja Gaiden 3 servers.
- `AutoMatchmakeWithGatheringID_Postpone` (join a friend): not in the common library; port `nex/friends_automatch.go` from the same servers.
- Invitations / presence-based join.

## Not implemented

Account Management, Health, Monitoring, Notification, RemoteLogDevice (housekeeping the game doesn't need answered); Ranking and DataStore (not linked); host migration / session clock / duplicated objects (peer to peer).