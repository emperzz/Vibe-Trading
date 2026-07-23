# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Vibe-Trading (`vibe-trading-ai` on PyPI, v0.1.12) is a natural-language finance research AI agent. The PyPI package ships three console-script entry points:

- `vibe-trading` — interactive CLI / TUI. Auto-runs the onboarding wizard if no `.env` exists. Subcommands delegate to `cli._legacy` (`serve`, `init`, `run`, `alpha …`, `connector …`, `channels …`, `provider …`, `backtest …`, `memory …`, `hypothesis …`, `swarm …`, `data …`, `resume <id>`, `setup`, `dev`). In-chat slash commands include `/halt`, `/stop`, `/resume`, `/connector`, `/data`, `/journal`, `/shadow`, `/memory`, `/goal`, `/show`, `/session`, `/help`.
- `vibe-trading serve --port 8899` — FastAPI web server for the React SPA (port 8899 in container, 8000 from CLI default).
- `vibe-trading-mcp` — MCP server (stdio by default; `--transport sse` legacy SSE; `--transport http` current Streamable HTTP at `/mcp`). Surfaces **54 read-only / research-only tools** — no order placing or cancelling ever crosses MCP.

Backend = LangChain 1.x + LangGraph ReAct agent; data layer = 23 free market-data sources with ban-risk fallback; backtest = 8 engines + composite cross-market; alpha research = 462 pre-built alphas across `qlib158` / `alpha101` / `gtja191` / `academic` / `fundamental` zoos; swarm = 30 preset multi-agent teams; live trading = 12 broker connectors behind a mandate gate.

## Install & Run

```bash
# Editable dev install (Python 3.11+)
pip install -e ".[dev]"

# Optional broker / channel / provider extras (add only what you need)
pip install -e ".[ibkr,longbridge,mt5,deepseek,anthropic,ashare,harmonic,channels]"

# First-time .env setup
vibe-trading init          # interactive wizard
cp agent/.env.example agent/.env   # or copy & edit manually

# Launch
vibe-trading               # CLI / TUI
vibe-trading serve --port 8899
vibe-trading-mcp           # stdio
vibe-trading-mcp --transport http --port 8899   # Streamable HTTP
```

Docker path: `cp agent/.env.example agent/.env && docker compose up --build` → `http://localhost:8899`. Persistent state (memory, sessions, runs, swarm history, broker config, uploads) lives in named Docker volumes and survives rebuilds. Inside the container `localhost` is the container itself — Ollama defaults to `http://host.docker.internal:11434` via `host-gateway` `extra_hosts`.

## Common commands

### Backend tests (pytest)

```bash
# Full safe suite (used by CI)
pytest --ignore=agent/tests/e2e_backtest \
       --ignore=agent/tests/test_e2e_harness_v2.py \
       --tb=short -q

# Targeted — pick the narrowest that matches your change
pytest agent/tests/test_sdk_order_gate.py \
       agent/tests/test_mandate_enforcement.py \
       agent/tests/test_killswitch_blocks_orders.py \
       agent/tests/test_readonly_default.py -q        # live / order safety

pytest agent/tests/factors/test_alpha_purity.py \
       agent/tests/factors/test_lookahead.py -q       # factor-zoo changes

pytest agent/tests/test_alpha_bench_strict_cli.py -q # alpha bench --strict CLI

# Single test
pytest agent/tests/test_alpha_compare_tool.py::test_compare_ranks_by_ir -q
```

`test_e2e_harness_v2.py` and `e2e_backtest/` are gated by `VIBE_TRADING_RUN_LIVE_E2E=1` (real LLM) and are gitignored as `agent/tests/e2e_*.py` / `agent/tests/test_e2e_*.py`. They must never silently run in CI.

### Lint / format

```bash
black --check agent/src/example.py agent/tests/test_example.py
ruff check agent/src/example.py agent/tests/test_example.py
```

Config in `pyproject.toml`: `ruff` (target py311, line-length 120, `E`/`F`/`W`, ignores `E501`); `black>=24,<27`. The repo deliberately does NOT enforce whole-tree Black/Ruff — keep formatting cleanup out of focused PRs. Per-file ignore for `agent/src/factors/zoo/**/*.py` (F401 only).

### Frontend

```bash
cd frontend && npm ci && npm run build         # CI build
cd frontend && npm run dev                     # Vite dev on :5899 (proxies /api → :8899)
cd frontend && npx vitest run --reporter=verbose   # vitest suite
```

### Repository safety gates (CI)

```bash
bash tools/ci_grep_gates.sh
pytest tools/test_ci_env_var_gate.py -q
```

These enforce the AST-based "no raw `os.getenv`" rule (every env read must go through `src.config.env_schema.EnvConfig`) and several other invariants.

### Quick syntax check

```bash
cd agent
python -m compileall -q cli
python -m py_compile api_server.py mcp_server.py src/agent/loop.py src/tools/__init__.py backtest/runner.py
```

## Codebase map

```
agent/                          ← Python package (src = package, root = entry points)
  api_server.py                 ← FastAPI app: thin assembler (~390 LoC). All routes in src/api/*_routes.py.
  mcp_server.py                 ← MCP server (FastMCP). Lazy-singleton registry; shell tools OFF by default.
  cli/                          ← Interactive front door + subcommands (split from monolithic cli.py on 2026-05-21)
    main.py           REPL entry; auto-runs onboarding wizard if no .env; intercepts /halt /resume /connector /data
    _legacy.py        Preserves every cli.cmd_* public symbol so legacy callers keep working
    _version.py       Single source of version (avoids 0.1.8 drift)
    commands/         chat, session, show, memory, goal, help, slash_router
    components/       chat_log, hint_bar, tool_event, working_indicator
    ui/               banner, rail, transcript
    utils/, input.py, completer.py, theme.py, onboard.py, intro.py, stream.py, __main__.py
  src/
    agent/        loop.py (5-layer context compaction), context.py, memory.py, tools.py, skills.py, trace.py, progress.py
    api/          runs/sessions/swarm/live/settings/auth/system/uploads/channels/alpha/qveris/scheduled_routes.py + models, security, helpers, state
    channels/     16 IM adapters (telegram, slack, discord, weixin, wecom, feishu, dingtalk, msteams, …) + bus, pairing, runtime, manager, utils (SSRF guards)
    core/         runner.py, state.py
    factors/      registry.py, base.py, bench_runner.py, bench_runner_strict.py, compare_runner.py, factor_analysis_core.py, cli_handlers.py
                  zoo/ qlib158/ alpha101/ gtja191/ academic/ fundamental/   (462 alphas)
    swarm/        runtime.py, worker.py, models.py, store.py, task_store.py, grounding.py, serialization.py
                  presets/  (YAMLs bundled inside src.swarm; user overrides at ~/.vibe-trading/swarm/presets/)
    trading/      service.py (connector-first facade), profiles.py, types.py, tap_forward.py
                  connectors/<broker>/  ibkr/, robinhood/, alpaca/, tiger/, okx/, binance/, futu/, mt5/, longbridge/, dhan/, shoonya/, trading212/
                                  each: sdk.py, classification.py (Tier-2 curated map)
    live/         registry.py (3-tier broker-tool classification), halt.py, mandate/, order_guard.py, enforcement.py, sdk_order_gate.py,
                  audit.py, classification.py, daily_count.py, paths.py, advisory/, extractors/, runtime/
    providers/    llm.py (ChatOpenAIWithReasoning), capabilities.py, content_filter.py, openai_codex.py, llm_providers.json
    skills/       88 finance skill bundles (data-routing, factor-research, options-strategy, alpha-zoo, …); each = SKILL.md + supporting .yaml/.py
    tools/        ~70 tool modules: backtest, alpha_*, shadow, swarm, ocr, trade_journal, market_data, hypothesis, goal, sd_m_*, etc.
    config/       env_schema.py (Pydantic EnvConfig sub-models), accessor.py (thread-safe singleton), schema.py, loader.py, paths.py
    security/     network.py (re-export from channels.utils), scanner.py, workspace_access.py, workspace_policy.py
    session/      store.py (JSONL), search.py (SQLite FTS5), service.py, models.py, events.py, goal_state.py, webui_turns.py
    memory/       persistent.py (long-term cross-session memory), lifecycle.py (quality-driven reinforcement, Ebbinghaus-inspired decay, capacity-based GC; single-writer file-level locking; Tier 1 = archive only — `ENABLE_DELETE = False`)
    shadow_account/, goal/, hypotheses/, strategy_store/, scheduled_research/, channelsui/, utils/
    market_data.py, preflight.py, ui_services.py
  backtest/                     ← testable, importable package
    runner.py (BacktestConfigSchema pydantic validator), models.py, metrics.py, validation.py, run_card.py,
    benchmark.py, correlation.py, regime.py, risk_xray.py,
    rebalance_notes.py (Portfolio Studio slice #795: per-rebalance turnover + weight-drift detail, computed from target position frame)
    engines/      china_a, china_futures, global_equity, global_futures, india_equity, crypto, forex, options_portfolio, composite, _market_hooks
    loaders/      registry.py (VALID_SOURCES + FALLBACK_CHAINS + @register decorator) + ~25 loader modules
                  (tushare, okx, binance, yfinance, akshare, baostock, tencent, mootdx, ccxt, futu, eastmoney, sina, stooq,
                   yahoo, finnhub, alphavantage, tiingo, fmp, qveris, india_broker, longbridge, mt5, local, fundamentals)
                  base.py (DataLoaderProtocol, validate_ohlc, retry_with_budget, opt-in loader cache)
    optimizers/   equal_volatility, risk_parity, mean_variance, max_diversification, turnover_aware
  tests/         ~330 pytest files mirroring src/ structure; memory/ subpackage added for lifecycle + dedup + GC; e2e_*.py / test_e2e_*.py are gitignored (manual only)
  scripts/       standalone scripts
  SKILL.md       Agent Skill manifest (consumed by Claude Desktop / OpenClaw / Cursor)

frontend/                       ← Vite + React 19 SPA
  src/                          TypeScript + Tailwind, lazy-loaded routes
  vite.config.ts                dev proxy `/api` → localhost:8899 (Vite on :5899)

tools/                          ← repo-level CI helpers
  ci_grep_gates.sh, ci_env_var_gate.py, test_ci_env_var_gate.py

scripts/dev                     ← cross-platform dev launcher (handles Windows TS build, Vite :5899, child-process cleanup)

wiki/                           ← public Cloudflare Pages site (docs + Alpha Library + Research Lab)
  deployed by .github/workflows/wiki-deploy.yml; wiki.yml validates PRs

docker-compose.yml              ← 127.0.0.1:8899 bind, host-gateway for Ollama, named volumes for persistence
Dockerfile                      ← multi-stage, digest-pinned, non-root user
```

### Big-picture architecture

The agent runs as a **LangGraph ReAct loop** in `src/agent/loop.py` with **five-layer context compaction**:

1. **microcompact** — prunes old tool results once under memory pressure
2. **context_collapse** — folds long text blocks without LLM call (zero cost)
3. **auto_compact** — LLM structured summary with token-budget tail protection
4. **compact tool** — model explicitly invokes to trigger L3
5. **iterative update** — Nth compression updates previous summary instead of starting fresh

Consecutive read-only tools run in parallel via threads (read/write batching). Each run emits a `HeartbeatTimer` (`src/agent/progress.py`) so long tools (`run_backtest`, `read_document`, `read_url`) don't look frozen.

Three surfaces expose the same loop:

1. **MCP** (`mcp_server.py`, `vibe-trading-mcp`) — stdio / SSE / Streamable HTTP. Tools listed dynamically from the registry; capability-driven schema. **Shell-capable tools are OFF by default** (module-level `_include_shell_tools = False`); must opt in via `VIBE_TRADING_ENABLE_SHELL_TOOLS=1` or `--enable-shell-tools`. Tools are read-only / research-only — order-placing tools are never exposed via MCP.
2. **CLI** (`cli/main.py`) — Rich + prompt_toolkit TUI. Routes everything except `chat`/`resume`/`interactive` to `cli._legacy` for back-compat. **Privileged surface actions intercepted in the REPL input path BEFORE the model sees them**: bare "停"/"stop"/"kill"/"halt" trips the kill switch; `/halt` `/stop` `/resume` `/connector` `/data` go through dedicated handlers; numeric mandate picks POST to `/mandate/commit` directly. Auto-runs onboarding if no `.env` is found.
3. **Web** — FastAPI in `api_server.py` (modularized into `src/api/*_routes.py`) + React SPA in `frontend/`. Vite dev server proxies `/api` → backend on :8899.

A request flows: **Plan → Ground → Execute → Validate → Deliver**. Planning picks skills/tools/swarm preset. Grounding fetches via the loader registry with ban-risk fallback chains. Execute runs tools or generates backtest config. Validate adds metrics + benchmark panel + Monte Carlo/Bootstrap/Walk-Forward + run cards. Deliver produces reports, artifacts, traces, and platform exports (Pine v6, TDX, MQL5, vnpy).

Sessions are dual-written: canonical `agent/sessions/<id>/messages.jsonl` (filesystem) + SQLite FTS5 at `~/.vibe-trading/sessions.db` (cross-session search via `SessionSearchTool`). Appends `flush+fsync` so an AI response survives a mid-write crash.

### Data layer

`backtest/loaders/registry.py` is the single source of truth.

- **Loaders self-register** via the `@register` class decorator; `_ensure_registered()` lazily imports every loader module so callers never see an empty registry.
- **Protocol**: `DataLoaderProtocol` (runtime_checkable) requires `name: str`, `markets: set[str]`, `requires_auth: bool`, `is_available() -> bool`, and `fetch(codes, start_date, end_date, *, interval="1D", fields=None) -> dict[str, pd.DataFrame]`. Returns `{symbol: DataFrame(trade_date, open, high, low, close, volume)}`.
- **Canonical sources**: `VALID_SOURCES` set in `registry.py` (regression test `test_valid_sources_covers_all_registered_loaders` enforces full coverage), shared with `BacktestConfigSchema`.
- **Fallback chains**: `FALLBACK_CHAINS` maps `market -> ordered list of source names`, ordered by IP-ban risk first, data quality second. e.g. `a_share → tencent → mootdx → eastmoney → baostock → akshare → tushare → local`.
- **No-network fallback** (`_NO_NETWORK_FALLBACK_SOURCES = {"local", "qveris"}`): an explicit request for these never silently degrades to a network source. `local` reads `~/.vibe-trading/data-bridge/config.yaml` (CSV/Parquet/DuckDB via `local:` prefix).
- **OHLC sanity** (`validate_ohlc()` in `base.py`): central loader-boundary check drops bars that violate `high ≥ low`, positive prices, or high/low bracketing. Strategies: `drop` / `warn` / `raise`.
- **Retry helpers**: `retry_with_budget()` + `check_budget()` for flaky external APIs; wall-clock deadline + small backoff applied only to caller-declared transient exception classes.
- **Opt-in loader cache**: `VIBE_TRADING_DATA_CACHE=1` enables per-symbol content-addressed (sha256) parquet cache at `~/.vibe-trading/cache/loaders/`. Atomic writes via `os.replace` with unique tmp. `loader_cache_range_is_final()` refuses to cache a range whose `end_date` is today or future (last bar still forming). `_LOADER_CACHE_VERSION = 3` (bumped on layout changes).

`get_market_data` (in `src.market_data`) is the single entry point used by swarm workers and the agent — walks the fallback chain when `source="auto"`. To add a loader: create `agent/backtest/loaders/<name>_loader.py`, append the module to `_loader_modules` in `registry.py`, and add the name to `VALID_SOURCES`.

### Backtest runner

`backtest/runner.py` reads `config.json`, validates with `BacktestConfigSchema` (pydantic), picks a loader, imports the signal engine, runs the engine. `_VALID_INTERVALS = {"1m","5m","15m","30m","1H","4H","1D"}`; `_VALID_ENGINES = {"daily","options"}`. `_detect_market` / `_detect_submarket` / `_is_china_futures` are imported from `backtest.engines._market_hooks` (shared with `composite.py`, audited 2026-05-18). Engine implementations live in `backtest/engines/{china_a,china_futures,global_equity,global_futures,india_equity,crypto,forex,options_portfolio,composite}.py`.

**Portfolio Studio slice #795** — `backtest/rebalance_notes.py::compute_rebalance_notes()` emits per-rebalance turnover + weight-drift detail from the target position frame (NaN → zero). A rebalance is any decision date whose target-weight vector moved past `epsilon=1e-6`. Works for every optimizer + the no-optimizer baseline; complements the trade-derived turnover in `metrics` (which measures what execution actually exchanged) with what the signal + optimizer *asked for* — that's where churn starts. Case-insensitive project-style periods (`1h`, `4h`, `1d`) are normalized at the loader boundary across MT5, longbridge, shoonya, OKX, Alpaca, Tiger; CCXT now maps `1W`/`1M`; yfinance `1M` = monthly (not minute); akshare/india_broker reject unsupported intervals instead of silent daily fallback. The core `_VALID_INTERVALS` set itself is unchanged.

### Alpha Zoo

`agent/src/factors/zoo/{qlib158,alpha101,gtja191,academic,fundamental}/` — each file exports `__alpha_meta__` (pydantic `AlphaMeta` in `src/factors/registry.py`, `extra="forbid", frozen=True`) and a pure `compute(panel) -> pd.DataFrame`. The source of truth is the `__alpha_meta__` literal in each module — `_meta.yaml` is generated by `export-manifest` for external consumers (wiki) only, never the load path. Module-path derivation: `src.factors.zoo.<zoo>.<alpha_id>`; both must match `^[a-z][a-z0-9_]{0,31}$`.

Two CI gates enforce purity and lookahead:

- `test_alpha_purity.py` — AST scan rejects non-allowlist imports (`os`, `subprocess`, `socket`, `urllib`, `requests`, `httpx`, `pathlib`, `Path`, `eval`, `exec`, `compile`, `__import__`, bare `open`, `getattr(_, "__…")`). Allowlist: `pandas`, `numpy`, `scipy.*`, `src.factors.base`, `__future__`, `typing`, `math`, `dataclasses`.
- `test_lookahead.py` — no negative shifts; `delta(df, d)` requires `d >= 1`.

CLI: `vibe-trading alpha list/show/bench/compare`. Apache-2 Qlib files must carry `# Adapted from <repo>@<sha>:<path> (Apache-2.0).` headers. Per-zoo `LICENSE.md` states formulas are mathematical content.

**`alpha bench --strict`** (#796) — exposes `run_bench_strict()` (same-universe random control + OOS split, catches factors that just track market beta). `--oos-split` / `--random-seeds` flags only take effect with `--strict`; the default bench path is unchanged.

### Skills

`agent/src/skills/<skill_name>/SKILL.md` is loaded by `src/agent/skills.py::SkillsLoader`. Default `skills_dir = Path(__file__).resolve().parents[1] / "skills"` → `agent/src/skills/` (the 88 bundled skill directories). User override at `USER_SKILLS_DIR = ~/.vibe-trading/skills/user/` — user skills are loaded first so they override bundled ones on name collision.

Progressive disclosure: only one-line summaries appear in the system prompt (`get_descriptions()`); full bodies load on demand via the `load_skill` tool (`get_content(name)`). Skill-writer tool surface (`sdm_register`, `sdm_status`, `sdm_decay_scan`) manages an active → monitoring → decayed → disabled lifecycle for the `strategy-dev-manager` skill, with `~/.vibe-trading/` artifacts.

### Swarm presets

Bundled YAMLs live in `agent/src/swarm/presets/` (inside the `src.swarm` package — package-data, survives editable installs and built wheels). User presets at `~/.vibe-trading/swarm/presets/` are searched first so a user file can both add to and override the bundled roster by name. Preset names are validated to a single path segment before any filesystem lookup. CLI: `vibe-trading --swarm-presets`, `vibe-trading swarm run --preset-name <name> ...`.

### Live trading safety (mandate gate)

`src/trading/service.py` is the connector-first facade. Every broker connection routes through:

```
service.py → profiles.py → connectors/<broker>/sdk.py
                       ↘ live/order_guard.py (LiveOrderGuardTool wraps every WRITE/UNKNOWN tool)
                       ↘ live/mandate/    (user-committed mandate: universe / order size / exposure / leverage / daily cap)
                       ↘ live/halt.py     (filesystem-level kill switch — trip with "停" / /halt / /stop)
                       ↘ live/audit.py    (audit ledger)
                       ↘ live/enforcement.py + sdk_order_gate.py (fail-closed pre-trade gate)
```

Per-broker structural paper/live guard (account-id format, host separation, demo flag, or trade environment) — **never a config flag**. Brokers without a structural discriminator (Longbridge, Dhan, Shoonya) are hard-capped to paper + read-only. Trading 212 is fully read-only.

MCP tool classification (`src/live/registry.py`) is a **3-tier ladder**: annotations → curated per-broker map → default-deny. UNKNOWN is treated as WRITE (fail-closed) — an unrecognized broker tool is never exposed ungated. WRITE tools get `LiveOrderGuardTool` wrapping; READ tools stay plain but are marked read-only.

Mandate commit (`POST /mandate/commit`) is a **SURFACE action** — intercepted in the REPL input path before the model sees it. The `proposal_id` in the rendered options binds the commit to the exact proposal; `consent_ack` is set by the user's keypress (the affirmative consent). `VIBE_TRADING_API_URL` is read once (no per-request override accepted from the proposal payload).

## Environment & config

All env vars flow through a single Pydantic `EnvConfig` schema (`src/config/env_schema.py`) with sub-models: `LLMConfig`, `DataConfig`, `APIConfig`, `SwarmConfig`, `AgentTuningConfig`, `PathConfig`, `OcrConfig`, `MemoryConfig`. Each field has an UPPER_SNAKE_CASE env alias; explicit constructor args take precedence; invalid numeric env values silently fall back to defaults.

`src/config/accessor.py` provides thread-safe access with double-checked locking (`get_env_config()`). Swarm workers and the agent loop both run in threads and call this concurrently. Call `reset_env_config()` after modifying `os.environ` at runtime (e.g. after the Settings API writes to `.env`).

Truthy string set: `{"1", "true", "yes", "on"}` (case-insensitive); falsy: `{"0", "false", "no", "off", ""}`.

Key vars (full list in `agent/.env.example`):

- `LANGCHAIN_PROVIDER`, `LANGCHAIN_MODEL_NAME`, `<PROVIDER>_API_KEY`, `<PROVIDER>_BASE_URL`
- `TUSHARE_TOKEN` (optional — mootdx/akshare/baostock/tencent are no-token fallbacks)
- `API_AUTH_KEY` — required when serving beyond loopback; clients send `Authorization: Bearer <key>`
- `VIBE_TRADING_ENABLE_SHELL_TOOLS=1` — opt-in for shell-capable tools (off by default in MCP and `vibe-trading serve`)
- `VIBE_TRADING_TRUST_DOCKER_LOOPBACK=1` — only for Docker Desktop host gateway
- `VIBE_TRADING_DATA_CACHE=1` — opt-in local cache at `~/.vibe-trading/cache/loaders/`
- `VIBE_TRADING_DATA_CACHE_ROOT` — override cache root
- `OLLAMA_BASE_URL` — `http://host.docker.internal:11434` in Docker, plain `http://localhost:11434` otherwise
- `CONTENT_FILTER_WARNING_THRESHOLD` — default 0.05
- `VIBE_TRADING_ENABLE_SCHEDULER=1` — enables the scheduled-research background executor (off by default)
- `LONGBRIDGE_APP_KEY` / `LONGBRIDGE_APP_SECRET` / `LONGBRIDGE_ACCESS_TOKEN` — optional Longbridge historical OHLCV loader
- `VIBE_RUN_LIVE_E2E=1` / `VIBE_TRADING_RUN_LIVE_E2E=1` — gates the real-LLM e2e suite
- `VIBE_TRADING_CHANNELS_AUTO_START` — auto-start IM channel runtime on server boot
- `VT_MEMORY_QUALITY=1` — enable memory quality scoring + access tracking (default off; reads from `MemoryConfig.quality_enabled`)
- `VT_MEMORY_GC=1` — enable memory garbage collection cycle (default off)
- `VT_MEMORY_DECAY=1` — enable Ebbinghaus-inspired importance decay (default off)

Memory lifecycle (#733) runs behind these three flags. Quality reinforcement uses events (`task_success` +0.1, `task_failure` −0.15, `user_confirm` +0.2, `user_reject` −0.3, `passive_decay` −0.05) with a per-memory per-session `_MAX_SESSION_DELTA = 0.5` cap. GC is **archive-only** at Tier 1 (`ENABLE_DELETE = False`); archive threshold = 0.15, delete threshold = 0.05, min age 7 days, max count 500. All writes are guarded by a single-writer file lock.

### Providers

17+ supported LLM providers: OpenRouter, Requesty, OpenAI, Anthropic (native Messages API, `[anthropic]` extra, lazy-imported), DeepSeek (native, `[deepseek]` extra), Gemini, Groq, DashScope/Qwen, Zhipu/GLM, Moonshot/Kimi, MiniMax, SiliconFlow (CN + Global), Xiaomi MIMO, iFlytek Spark, Z.ai, NVIDIA NIM, Ollama (local), OpenAI Codex (ChatGPT OAuth via `vibe-trading provider login openai-codex` — no env key).

When `<PROVIDER>_BASE_URL` is unset, the provider falls back to its canonical base URL, so just a key is enough. Provider-specific behavior (DeepSeek's DSML tool-call parsing, Kimi `temperature=1` requirement and User-Agent override, Gemini 2.5/3.x `thoughtSignature` round-trip, OpenRouter reasoning body) lives in `src/providers/capabilities.py` and `src/providers/content_filter.py` — no longer cross-contaminates via the OpenAI shim.

`ChatOpenAIWithReasoning` (`src/providers/llm.py`) preserves `reasoning_content` / `reasoning` across invoke + stream so Kimi / DeepSeek / OpenRouter thinking streams survive multi-turn continuations.

## Security boundaries (read before touching live/order code)

- All `/api/*` (non-loopback) reads, `/runs/*`, `/sessions/*`, `/swarm/runs`, `/upload`, `/channels/*`, `/correlation`, `/system/shutdown`, `/skills` require auth when `API_AUTH_KEY` is set. Local CLI / Web UI on `localhost:8899` remain low-friction.
- CORS is allowlist-driven (`VIBE_TRADING_TRUST_ORIGINS`); unsafe cross-site methods (POST/PUT/DELETE) are blocked at the loopback dev-mode boundary even if CORS would have allowed the response.
- File tools and shell tools are sandboxed to explicit roots (`VIBE_TRADING_ALLOWED_FILE_ROOTS`, `VIBE_TRADING_ALLOWED_RUN_ROOTS`); generated signal engines pass AST preflight before import. Backtest sandboxes block `os.environ` / `subprocess` / `eval` / `exec` / `open` / `socket`.
- MCP OAuth: single-use SSE auth tickets (`_mint_sse_ticket` / `_consume_sse_ticket`); tokens cached via `oauth-cli-kit`, not env vars. SSE auth required for `/correlation`.
- Docker: multi-stage with digest-pinned images, read-only rootfs, dropped capabilities, resource limits, localhost-only port bind, non-root user.
- Live order placement is structurally unreachable from research/backtest paths. Connector writes go through mandate → kill switch → audit ledger → pre-trade gate (fail-closed). Connector-side order caps are signed; daily order limits are atomic; consent is required before mandate commits.
- Dependency lock is hash-verified (`requirements-lock.txt`); Docker uses `pip install --require-hashes`.
- Channel media SSRF defense (`src/channels/utils.py`) rejects CGNAT/mesh/non-global targets; QQ media redirect-to-internal before fetching.

## Conventions

- **DCO required on every community commit:** `git commit -s -m "..."` appends `Signed-off-by:`. Maintainer-direct commits to `main` are exempt. **No `Co-Authored-By:` or AI-assistant attribution trailers** — the DCO is the only required trailer.
- Type-annotate all public function/method signatures; Google-style docstrings (`Args:` / `Returns:` / `Raises:`).
- Files under 400 lines where practical, 800 hard cap. No hardcoded paths, secrets, or URLs — config via `.env`, YAML, or module-level constants.
- Strict JSON for non-finite metrics: NaN/Inf serialize as `null`, never leak into payloads. The `[#761](https://github.com/HKUDS/Vibe-Trading/pull/761)–[#770](https://github.com/HKUDS/Vibe-Trading/pull/770)` reliability sweep normalizes nested non-finite values across metrics, factors, pattern, session, and journal.
- **Negative LoC delta ethos** — the project trends negative LoC per release (latest 0.1.12 = ~90 fixes since 0.1.11). Avoid speculative abstractions, scaffolding "for later", and unused code.
- Run paths use `~/.vibe-trading/` (`sessions.db`/FTS5, `cache/loaders/`, `swarm/presets/`, `skills/user/`, `data-bridge/config.yaml`, `.env`); legacy `agent/sessions/`, `agent/runs/`, `agent/uploads/` are still used and gitignored.
- README is multilingual: `README.md` (en), `README_zh.md`, `README_ja.md`, `README_ko.md`, `README_ar.md`. User-facing CLI/Web/MCP/connector/safety changes update all five.

## Key references

- `README.md` — full feature inventory, CLI/MCP/Web quickstart, env vars, fallback chains, broker connector matrix, swarm preset roster, alpha zoo catalog
- `CONTRIBUTING.md` — DCO, code style, alpha reviewer checklist, "adding a new alpha" quickstart
- `AGENT_CONTRIBUTOR_GUIDE.md` — safe local checks, high-risk surfaces (broker/MCP/credentials), targeted test hints, security rules, PR expectations
- `SECURITY.md` — vulnerability reporting policy; official-channel/impersonation warnings
- `agent/SKILL.md` — Agent Skill manifest (consumed by Claude Desktop / OpenClaw / Cursor)
- `agent/.env.example` — every supported env var with comments
- `tools/ci_grep_gates.sh` + `tools/ci_env_var_gate.py` — repository safety gates (env-var sprawl, secrets in tree, etc.)
- `docker-compose.yml` — bind to `127.0.0.1:8899`, `host-gateway` mapping for Ollama, named volumes for persistence
- `.github/workflows/ci.yml` — what CI actually runs (matches the commands above)