# TableQueue - one build entry point for the whole repository.
#
# Every documented command is a target in this file and is run from the repository
# root: `make seed`, `make dev`, `make test-backend`. There is deliberately no second
# makefile: GNU make only reads a makefile from the current directory, so a copy in
# backend/ would be a second entry point that drifts from this one (and `make --eval`
# is not an option - this build has to work with whatever make a laptop ships).
#
# What this file is responsible for, beyond listing commands:
#
#   1. Find the backend interpreter. It is resolved once, here, before any recipe runs
#      (see "Which interpreter runs the backend" below) so that a clone without a venv
#      gets either uv's own environment or an error that says what to run next - not the
#      shell's bare "no such file or directory".
#   2. Refuse to start a server without a real backend/.env (see the guard-env target),
#      because the app itself refuses to boot without JWT_SECRET and STAFF_PIN.
#   3. Keep ports configurable, so two checkouts on one machine can run at the same time.
#
# Requirements: GNU make (any version - nothing here uses make >= 3.82), sh, uv or any
# Python 3.12 for the backend, Node 20 (see .nvmrc) and npm for the frontend.

ROOT := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))

# ---------------------------------------------------------------------------
# Knobs, all overridable on the command line or in the environment
# ---------------------------------------------------------------------------
# Interpreter path, relative to backend/ - the location `make setup` creates.
BACKEND_PY    ?= .venv/bin/python
# Set UV to a full path when uv is installed but not on PATH.
UV            ?= uv
# npm | pnpm | yarn, whatever the machine has.
FRONT_PM      ?= npm
PYTEST_ARGS   ?= -q
RUFF_ARGS     ?= .
BACKEND_HOST  ?= 0.0.0.0
BACKEND_PORT  ?= 8000
FRONTEND_PORT ?= 5173

# Where a real backend/.env lives, as seen from this file's directory.
ENV_FILE := $(ROOT)backend/.env

# ---------------------------------------------------------------------------
# Which interpreter runs the backend
# ---------------------------------------------------------------------------
#
# Resolved once, in the shell that make invokes on startup, and cached in $(PYTHON) for
# the rest of the invocation. Every recipe then uses it as an ordinary word,
#
#   cd backend && exec $(PYTHON) $(PYTHON_M) app.seed --reset
#
# which is why nothing here is passed through an `sh -c` body: a "$@" inside a script that
# make itself expanded refers to make's argument vector rather than the script's, and
# silently yields nothing, so an earlier draft of this file lost the module name and ran
# `python -m --reset`. Words built by make are words; there is nothing left to smuggle.
#
# Candidates, first executable one wins. $(BACKEND_PY) is expanded by make, so the loop
# only has to deal with plain paths, and every candidate is anchored at $(ROOT) - the
# directory of this file - because the resolution runs when make starts, before any recipe
# has had a chance to change directories:
#
#   1. $(ROOT)backend/$(BACKEND_PY)   the documented location, created by `make setup`
#   2. $(ROOT)$(BACKEND_PY)           a venv at the repository root, for clones set up
#                                     that way
#   3. ./$(BACKEND_PY)                a caller's override given relative to wherever make
#                                     was invoked, e.g.
#                                     make test-backend BACKEND_PY=../../other/.venv/bin/python
#   4. uv                             a fresh clone with uv installed runs `make seed`
#                                     with no extra step: uv builds backend/.venv once and
#                                     the command then executes from that environment
#   5. an empty result, which becomes the error below - never a silent failure
#
# The loop is a `for` test rather than a chain of `if [ -e ]` blocks: it is the only form
# that is portable on dash, and it keeps the whole resolution in one shell invocation.
_RESOLVE = \
  PY=""; \
  for cand in $(ROOT)backend/$(BACKEND_PY) $(ROOT)$(BACKEND_PY) ./$(BACKEND_PY); do \
    if [ -x "$$cand" ]; then PY="$$cand"; break; fi; \
  done; \
  if [ -n "$$PY" ]; then echo "$$PY"; exit 0; fi; \
  if command -v $(UV) >/dev/null 2>&1; then echo "$(UV)"; exit 0; fi; \
  exit 127

_RESOLVED_PYTHON := $(shell $(_RESOLVE))
# Collapsed to a single space so a path can never carry make's whitespace padding into a
# recipe, where a multi-word argument would break the [ -x ] tests in the guards.
PYTHON_PATH := $(strip $(_RESOLVED_PYTHON))
BACKEND_VENV_PY := $(ROOT)backend/$(BACKEND_PY)

# An explicit `make PYTHON=/path/to/python` always wins over what was found above.
PYTHON ?= $(PYTHON_PATH)

# Nothing can run without an interpreter, so this is decided while the makefile is read: an
# empty result means no venv in any documented location and no uv on PATH, and the message
# says what to install rather than letting a recipe fail on an empty command word. The
# message is one line and free of parentheses and quotes, both of which $(error) handles
# badly inside a multi-line expansion.
ifeq ($(strip $(PYTHON)),)
$(error no backend interpreter: no venv at backend/.venv and no uv on PATH. Run make setup with uv installed, or point BACKEND_PY at an existing venv python)
endif

# A venv interpreter is invoked directly, so it needs only `-m` before the module. uv's
# `run` would resolve a fresh environment on every call and then expect to receive the
# program itself, not `python -m <module>`, so uv is reached through its sync-then-exec
# path: sync once, run everything from that environment (see $(PYTHON_EXEC)).
ifeq ($(word 1,$(PYTHON)),$(UV))
PYTHON_EXEC = $(UV) sync --project $(ROOT)backend && exec $(BACKEND_VENV_PY) -m
else
PYTHON_EXEC = $(PYTHON) -m
endif

RUN           = cd $(ROOT)backend && exec
RUN_SEED      = $(RUN) $(PYTHON_EXEC) app.seed --reset
RUN_UVICORN   = $(RUN) $(PYTHON_EXEC) uvicorn app.main:app --reload \
                --port $(BACKEND_PORT) --host $(BACKEND_HOST)
RUN_PYTEST    = $(RUN) $(PYTHON_EXEC) pytest $(PYTEST_ARGS)
RUN_RUFF_LINT = $(RUN) $(PYTHON_EXEC) ruff check $(RUFF_ARGS)
RUN_RUFF_FMT  = $(RUN) $(PYTHON_EXEC) ruff format $(RUFF_ARGS)

# vite reads its proxy target from VITE_API_TARGET (frontend/vite.config.ts), so the proxy
# follows BACKEND_PORT instead of pointing at a different checkout's server.
VITE_TARGET = http://localhost:$(BACKEND_PORT)

# The frontend port cannot be passed as `npm run dev -- --port N`: npm needs the literal
# "--" to reach it and make reserves "--" as its own end-of-options marker, so a recipe
# relying on that token is not portable between make versions. vite's own binary is run
# instead - `vite --port N` needs no separator at all.
VITE_ARGS = --port $(FRONTEND_PORT) --strictPort

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

.PHONY: setup seed dev backend frontend test test-backend test-frontend \
        lint format help guard-env check-python

# One-time setup, in the order a new machine needs it. Everything here is idempotent:
# uv reuses an up to date environment and `npm ci` replaces node_modules from the lockfile.
#
# uv builds the environment at <project>/.venv, which for this project is backend/.venv - the
# path this file resolves first and every message below assumes. uv is required rather than
# optional: it is what makes backend/.venv reproducible from pyproject.toml + uv.lock, and
# nothing promises a laptop's system python is the 3.12 the project pins, so a missing uv
# fails this target with the install URL instead of falling through to a half-made venv.
setup:
	@set +e; \
	if ! command -v $(UV) >/dev/null 2>&1; then \
	  echo "ERROR: $(UV) not found, and it is required - the backend environment is built" >&2; \
	  echo "       from backend/pyproject.toml + backend/uv.lock. Install uv:" >&2; \
	  echo "       https://docs.astral.sh/uv/get-started/installation/" >&2; \
	  echo "       then re-run: make setup" >&2; \
	  exit 1; \
	fi; \
	echo "==> backend: create/update backend/.venv from backend/uv.lock"; \
	$(UV) sync --project backend; rc=$$?; \
	if [ $$rc -ne 0 ]; then echo "ERROR: uv sync failed with rc=$$rc" >&2; exit $$rc; fi; \
	if [ ! -x "$(BACKEND_VENV_PY)" ]; then \
	  echo "ERROR: expected backend/$(BACKEND_PY) after uv sync, but it is not executable." >&2; \
	  echo "       Override the path if this environment lives elsewhere:" >&2; \
	  echo "       make setup BACKEND_PY=../../path/to/.venv/bin/python" >&2; \
	  exit 1; \
	fi; \
	echo "==> backend: assert the dev group is importable by backend/$(BACKEND_PY)"; \
	cd $(ROOT)backend && .venv/bin/python -c "import pytest, ruff"; rc=$$?; \
	if [ $$rc -ne 0 ]; then \
	  echo "ERROR: rc=$$rc - pytest/ruff are not importable by backend/$(BACKEND_PY)." >&2; \
	  echo "       uv sync installs them from pyproject.toml's dev group; check that block." >&2; \
	  exit $$rc; \
	fi
	@echo "==> frontend: install dependencies from the lockfile"
	@set +e; \
	if ! command -v $(FRONT_PM) >/dev/null 2>&1; then \
	  echo "note: $(FRONT_PM) not on PATH, so the frontend was not installed." >&2; \
	  echo "      Install Node 20 (see .nvmrc) and run: cd frontend && npm ci" >&2; \
	elif [ "$(SKIP_FRONTEND)" = "1" ]; then \
	  echo "    skipped (SKIP_FRONTEND=1) - run 'cd frontend && npm ci' yourself"; \
	else \
	  cd $(ROOT)frontend && npm ci; \
	fi
	@echo "==> done. backend = backend/$(BACKEND_PY), frontend = node (see .nvmrc, node 20)."

# ---------------------------------------------------------------------------
# Servers
# ---------------------------------------------------------------------------

# One foreground process that owns both dev servers, so Ctrl-C stops everything. uvicorn and
# vite are started as two children of this single recipe and a trap kills both on exit, so
# the target cannot background one of them away and cannot silently mean "frontend only".
# If the frontend has no node_modules yet, the backend still starts on its own with a note,
# rather than the whole target failing.
dev: guard-env
	@echo "Development servers: backend http://localhost:$(BACKEND_PORT)  frontend http://localhost:$(FRONTEND_PORT)"
	@echo "Both are children of this one process; Ctrl-C stops them."
	@set +e; \
	if [ -d "$(ROOT)frontend/node_modules" ]; then \
	  $(RUN_UVICORN) & be=$$!; \
	  cd $(ROOT)frontend && VITE_API_TARGET=$(VITE_TARGET) \
	    ./node_modules/.bin/vite $(VITE_ARGS) & fe=$$!; \
	  trap "kill $$be $$fe 2>/dev/null" INT TERM EXIT; \
	  wait $$be; rc=$$?; kill $$fe 2>/dev/null; exit $$rc; \
	fi; \
	if [ -x "$(BACKEND_VENV_PY)" ] || command -v $(UV) >/dev/null 2>&1; then \
	  echo "note: the frontend is not installed, so only the backend can be started." >&2; \
	  echo "      Run 'make setup' (or 'cd frontend && npm ci') for the frontend too." >&2; \
	  $(RUN_UVICORN); exit $$?; \
	fi; \
	echo "ERROR: nothing is installed yet - no backend interpreter and no frontend." >&2; \
	echo "       Run 'make setup' first." >&2; \
	exit 127

backend: guard-env
	@set +e; $(RUN_UVICORN)

frontend:
	@set +e; cd $(ROOT)frontend && exec ./node_modules/.bin/vite $(VITE_ARGS)

seed: guard-env
	@set +e; $(RUN_SEED)

# ---------------------------------------------------------------------------
# Tests and checks
# ---------------------------------------------------------------------------

test: test-backend test-frontend

test-backend: guard-env
	@set +e; $(RUN_PYTEST)

test-frontend:
	@set +e; cd $(ROOT)frontend && exec npm run test -- --run

# The lint/format targets check both halves of the repository: the backend has ruff (dev
# dependency group in backend/pyproject.toml), the frontend has eslint.
lint: guard-env
	@set +e; $(RUN_RUFF_LINT); rc=$$?; \
	cd $(ROOT)frontend && npm run lint; rc2=$$?; \
	if [ $$rc -ne 0 ] || [ $$rc2 -ne 0 ]; then exit 1; fi

format: guard-env
	@set +e; $(RUN_RUFF_FMT); rc=$$?; \
	cd $(ROOT)frontend && npm run format; rc2=$$?; \
	if [ $$rc -ne 0 ] || [ $$rc2 -ne 0 ]; then exit 1; fi

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

# The app refuses to boot without a real JWT_SECRET (>= 32 characters) and STAFF_PIN, and
# it refuses the values published in backend/.env.example (security audit A-1 / D-1). The
# documented commands check the same two keys first so that a missing .env is reported as a
# missing .env, before a server is half started. seed needs backend/ as the working
# directory anyway, because seed stores its database relative to it.
guard-env:
	@set +e; \
	if [ ! -f "$(ENV_FILE)" ]; then \
	  echo "ERROR: $(ENV_FILE) not found." >&2; \
	  echo "       cp backend/.env.example backend/.env, then set JWT_SECRET (>=32 chars:" >&2; \
	  echo "       python3 -c \"import secrets; print(secrets.token_urlsafe(32))\") and STAFF_PIN." >&2; \
	  exit 1; \
	fi; \
	. $(ENV_FILE) 2>/dev/null || true; \
	if [ -z "$${JWT_SECRET:-}" ] || [ "$${#JWT_SECRET}" -lt 32 ]; then \
	  echo "ERROR: JWT_SECRET missing or shorter than 32 characters in $(ENV_FILE)." >&2; \
	  echo "       It is the signing key for staff and admin sessions - there is no safe default." >&2; \
	  exit 1; \
	fi; \
	if [ -z "$${STAFF_PIN:-}" ]; then \
	  echo "ERROR: STAFF_PIN missing in $(ENV_FILE)." >&2; \
	  exit 1; \
	fi; \
	case "$${JWT_SECRET}" in change-me-please-please-change-me*) \
	  echo "ERROR: JWT_SECRET is still the example value in $(ENV_FILE)." >&2; exit 1;; esac; \
	case "$${STAFF_PIN}" in 000000|"") \
	  echo "ERROR: STAFF_PIN is still the example value in $(ENV_FILE)." >&2; exit 1;; esac

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

# The commands are typed from the repository root. `make help` is also the answer to the
# one mistake this layout invites: typing a root-level target inside backend/, where GNU
# make cannot see this file.
help:
	@echo "TableQueue targets (run from the repository root):"
	@echo "  make setup          create backend/.venv from uv.lock, install the frontend"
	@echo "  make seed           reset the development database and fill it with sample data"
	@echo "  make dev            backend :$(BACKEND_PORT) + frontend :$(FRONTEND_PORT), one process"
	@echo "  make backend        backend only (uvicorn --reload, :$(BACKEND_PORT))"
	@echo "  make frontend       frontend only (vite, :$(FRONTEND_PORT))"
	@echo "  make test           backend and frontend suites"
	@echo "  make test-backend   pytest (backend/.venv)"
	@echo "  make test-frontend  vitest run"
	@echo "  make lint           ruff check + eslint"
	@echo "  make format         ruff format + prettier"
	@echo ""
	@echo "Current backend interpreter: $(PYTHON)"
	@echo "Override it with: make <target> BACKEND_PY=../other/.venv/bin/python"
