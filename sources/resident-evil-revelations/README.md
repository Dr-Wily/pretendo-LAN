# Resident Evil: Revelations — NEX server

A preservation NEX server for the Wii U title **Resident Evil: Revelations**
(Capcom, 2013; *Biohazard Revelations Unveiled Edition* in Japan). It speaks
the game's PRUDP authentication and secure protocols so **online Raid Mode
matchmaking** (create / search / join a session, host migration) works again.

Built on the [Pretendo Network](https://github.com/PretendoNetwork) NEX
libraries (`nex-go`, `nex-protocols-go`, `nex-protocols-common-go`), unmodified.
The game links no DataStore and no Ranking, so there is no S3 and nothing to
store beyond the matchmaking tables, which `nex-protocols-common-go` creates.

> **Status:** tested on a real Wii U up to a successful connection (login,
> secure register, service token). Creating and joining Raid sessions has not
> been exercised yet. How the constants were found is in [RECON.md](RECON.md);
> per-protocol coverage is in [PROTOCOL_COVERAGE.md](PROTOCOL_COVERAGE.md).

## Recovered configuration

| Field | Value |
|---|---|
| Access key | `59d539a9` (verified against a console CONNECT packet) |
| Game server IDs | `10113100` (the one the EUR console really uses, per kinnay too); `1012b400` / `1012cf00` also registered |
| NEX version | `3.4.13` (kinnay `build:3_4_13_3_0`), MatchMaking pinned to `3.3.0` |
| PRUDPv1 legacy connection signature | off (verified from a console capture); `PN_REREV_LEGACY_SIGNATURE=1` to flip |
| Structure headers | off (library default) |

## Scope

Ticket Granting, Secure Connection, Utility, NAT Traversal, MatchMaking,
MatchMakingExt, MatchmakeExtension. Host migration, session clock and the
duplicated-object layer run peer to peer between consoles.

## Running

```bash
cp .env.example .env
cp settings.example.json settings.json   # local mode: your console's PID + NEX password
docker compose up --build                # UDP 29100 (auth) / 29101 (secure)
```

Local mode (`PN_REREV_LOCAL_MODE=1`) takes accounts from `settings.json` and
accepts any login token: isolated networks only. Shared mode
(`PN_REREV_LOCAL_MODE=0`) needs `PN_REREV_NEX_TOKEN_AES_KEY` (64 hex) and
`PN_REREV_NEX_PASSWORD_SECRET` (≥32 bytes hex) matching your account server.
`PN_REREV_SECURE_HOST` must be short (~15 chars): the retail binary truncates it.

### Pointing a console at it

The account server's `nex_token` response must map **every** game server ID
above (`1012b400`, `1012cf00`, `10113100`) to this server's host and auth port.
Do not restrict by title ID, or other regions fail (102-xxxx).

Every secure-endpoint call is logged (`[REvelations Secure] PID=… protocol=…
method=…`), which is how to see what each Raid menu action calls.

## License

AGPL-3.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE). No Capcom or Nintendo
code or assets are included.