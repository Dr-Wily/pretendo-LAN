# Recon — Resident Evil: Revelations (Wii U)

Source: `BioRevHD.rpx` from the EUR update v16 (title `000500001012B400`,
product code WUP-P-ABHP). Everything below was read from the executable.
Reproduce with the scripts in `recon/` (see `recon/README.md`).

## Constants

| Field | Value | Evidence |
|---|---|---|
| Access key | `59d539a9` | UTF-16BE literal at `.rodata 0x1029ebdc`. **Confirmed on a real console**: the PRUDPv1 CONNECT packet it sent verifies as `HMAC-MD5(md5(key), header[4:] + sum(key) + serverConnSig + options + payload)` with this key only. The first guess, `ab8db073` (`.rodata 0x102c3164`, referenced from the NEX init block at `0x02a902f8` next to `MtNetContext`), is a different 8-hex literal and does **not** verify. Same check shows the console signs CONNECT with the server connection signature, i.e. `LegacyConnectionSignature = false`. |
| NEX version | `3.4.13` | kinnay `nexwiiu.json` entry "BIOHAZARD REVELATIONS UE": id 269562112, key `59d539a9`, `build:3_4_13_3_0`. The `NEX_3_2_1` / `NEX_MM_3_2_1` strings in `.module_id` are per-library tags, not the NGS build. |
| Game server ID | `10113100` for every region | kinnay id 269562112; **console-verified**: the EUR title (`000500001012B400`) requests `game_server_id=10113100` from the token service. Not a code literal. |

### Regions

| Region | Product code | Title ID | Game server ID | Source |
|---|---|---|---|---|
| EUR | WUP-P-ABHP | `000500001012B400` | `1012b400` | the dump |
| USA | WUP-P-ABHE | `000500001012CF00` | `1012cf00` | wiiubrew title database (derived) |
| JPN | WUP-P-ABHJ | `0005000010113100` | `10113100` | wiiubrew title database (derived), "BIOHAZARD REVELATIONS Unveiled Edition" |

Server-ID = unique-ID half of the title ID is the rule every other title in
this family follows, but the USA/JPN IDs stay unconfirmed until a console or
dump of those regions is checked. Registering all three is the safe choice;
only the `nex_token` front-end depends on them.

## What the game links

`nn::nex` classes present (statically linked): `AuthenticationClient`,
`TicketGrantingProtocolClient`, `SecureConnectionClient`,
`AccountManagementClient`, `HealthClient`, `MonitoringProtocolClient`,
`NotificationProtocolClient`, `NintendoNotificationEvent*`,
`RemoteLogDeviceProtocolClient`, `NATTraversal*` (+Relay, ReportInternal),
`MatchMakingProtocolClient`, `MatchMakingProtocolExtClient`,
`MatchmakeExtensionProtocolClient`, `HostMigrationExtension`,
`SessionClockExtension`, `DupSpaceExtension` (duplicated objects).

**Not present:** any `Ranking` or `DataStore` client or DDL.
`MtNetRanking::Score` / `ScoreList` exist as Capcom engine classes only.

Game-side RTTI shows Raid Mode flows: `cCoopMenu::cCreateSession`,
`cSearchSession`, `cSessionList`, `cLobby`, `cLobbyBase`,
`cCoopSyncData::cLobbyInSyncData` / `cReLobbyInSyncData`,
`nNetwork::SessionDatabase`, `SessionListener`, `MtNet::Nex::P2p`,
`MtNet::Nex::Session`, and `nn::nex::host_migrationCafeDDLDeclarations`.

## Server consequences

Auth + Secure endpoints; secure registers SecureConnection, Utility, NAT
Traversal, MatchMaking, MatchMakingExt, MatchmakeExtension. The executable is
stripped, so which RMC methods each menu calls was not mapped statically;
every call is logged instead.