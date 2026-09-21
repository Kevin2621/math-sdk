# Wild Pickins math workspace

Updated 2026-09-12. Approved 5x3 crop/Wild/scatter rules, Golden picks, sticky bonus Wilds, collision spins, scatter retriggers and Full Harvest are implemented in the game-local experimental path. There are no approved separate Wild multipliers or bonus-buy modes.

Authoritative documentation: ../../../wild-pickins/README.md and ../../../wild-pickins/docs/current-status.md (relative to this directory).

Implemented: line_model.py, round_model.py, reel_source.py, book_export.py, generate_experimental.py; equal-weight evaluation and coverage tooling. optimize_experimental.py contains an unfinished isolated SDK optimizer bridge and basic weighted evaluator. No optimized output is accepted.

IMPORTANT: copied gamestate.py/run.py/game_config.py/game_optimization.py and reel CSVs retain template behavior/settings. They are not the approved Wild Pickins production model. Use the explicit experimental JSON configs and generate_experimental.py for rule-valid sampled experiments.

From the Development workspace:
PYTHONPATH=math-sdk .venv/bin/python -m unittest discover -s math-sdk/games/wild_pickins -p 'test_*.py' -v

Latest math suite: 27 passing tests. Latest consistent pilot: 100,000 paid-round books, 49.55972% observed equal-weight return. Target is 96.7% RTP and medium volatility; production paytable, line count, strips/rates, cap and budget remain open. The 30-spin and 1,000x settings are experimental.

Coverage policy correction is documented but not yet implemented in coverage_books.py: no eligible Golden target is correctness-only, not a collection quota; ordinary non-Harvest cap termination is unreachable under the current pilot inputs. Preserve correctness tests and separate candidate/provenance evidence. Kevin will provide next implementation steps after the documentation refresh.

Latest experiment: compare_base_game.py compares original base inputs, 20% base Golden frequency and crop-focused base strips. All bonus inputs and 25-line payouts stay fixed. Reproducible candidate: experiments/wp25-base-crop-focus.json. See ../../../wild-pickins/docs/base-game-experiment.md for evidence and selection limits. Current suite: 34 math tests pass.
