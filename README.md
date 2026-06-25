# Stag Hunt

<!-- COWORLD-REPO-STATUS:START -->
> [!NOTE]
> Coworld repo status: **incomplete** (`coworld-incomplete`).
> Canonical repository: `Metta-AI/coworld-staghunt`.
> Manifest path: `coworld_manifest.json`.
> Build path: `Dockerfile`, `Dockerfile.tools`, `players/big_game_hunter/Dockerfile`, `players/elephant_hunter/Dockerfile`, `players/modeler/Dockerfile`, `players/moose_hunter/Dockerfile`, `players/nearest_hunter/Dockerfile`, `players/rabbiteer/Dockerfile`, `players/sidekick/Dockerfile`, `players/stag_hunter/Dockerfile`
> Certification: blocked until `uv run coworld certify coworld_manifest.json` passes and the result is recorded.
>
> Missing pieces:
> - [ ] Validate the root concrete manifest against the current Coworld schema.
> - [ ] Run `uv run coworld certify coworld_manifest.json` with the bundled players.
> - [ ] Switch the repo topic to `coworld-complete` after certification passes.
<!-- COWORLD-REPO-STATUS:END -->




Cooperative BitWorld hunting game where players surround prey together:
rabbits go down alone, but stags, moose, and elephants require coordinated
multi-player encirclement.

## Running

First-time setup — install dependencies (including `bitworld`, which isn't on
the nimble registry) via [nimby](https://github.com/treeform/nimby):

```bash
nimby sync -g nimby.lock
nimby install -g https://github.com/Metta-AI/bitworld.git
```

`-g` installs into `~/.nimby/pkgs/` and writes a local `nim.cfg` with
absolute paths to those packages (gitignored). Then build and run:

```bash
nim c -d:release -o:out/staghunt src/staghunt.nim
./out/staghunt --address:0.0.0.0 --port:8080
```

Open `http://localhost:8080/client/global` to spectate.

Or via Docker:

```bash
docker build -t cogame-staghunt .
docker run --rm -p 8080:8080 cogame-staghunt
```

## Bots

Eight reference Nim bots ship in `players/`:

- `rabbiteer` — chases rabbits only (solo kills, guaranteed energy income)
- `nearest_hunter` — greedy A* to the closest prey
- `stag_hunter` — coordinates 2-hunter stag captures
- `moose_hunter` — coordinates 3-hunter moose encirclements
- `elephant_hunter` — coordinates 4-hunter elephant captures
- `big_game_hunter` — picks the biggest prey it can take given current coalition size
- `sidekick` — follows allies and assists multi-player kills
- `modeler` — adaptive bot that learns per-ally cooperation probabilities

Build one bot:

```bash
nim c -d:release -o:out/rabbiteer players/rabbiteer/rabbiteer.nim
./out/rabbiteer --address:localhost --port:8080
```

Run a full local eval (server + N bots):

```bash
./eval.sh rabbiteer,rabbiteer,stag_hunter,stag_hunter
```

## Grader & reporter

Two Coworld supporting runnables live in `tools/` and ship in
`ghcr.io/malcolmocean/bitworld-stag-hunt-tools:latest`:

- **grader** — scores how interesting an episode was for multi-agent
  collaboration (0–1), reward-agnostic (no hardcoded prey points).
- **reporter** — a sports-commentator / newspaper recap, narrated by Claude via
  AWS Bedrock with a deterministic fallback.

Run both against a local episode:

```bash
./eval.sh big_game_hunter,big_game_hunter,big_game_hunter,big_game_hunter \
  --no-build --ticks=1500 --rounds=2 --out=tmp/ep
python tools/run_local.py tmp/ep/scores.json tmp/ep/out
```

See `tools/README.md` for details.

## Notes

See `learnings.md` for iteration notes and `stats.md` for per-change capture-rate snapshots.
