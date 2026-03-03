# =============================================================================
# Policy Factory — Multi-stage Docker Build
# =============================================================================
# Stage 1 (builder): Installs bun, compiles frontend, builds Python wheel
# Stage 2 (runtime): Python + git + claude CLI + the built wheel
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install bun (for frontend build)
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# Install uv (for Python package management)
RUN pip install --no-cache-dir uv

WORKDIR /build

# Copy Python project files
COPY pyproject.toml ./
COPY src/ ./src/

# Copy frontend source
COPY ui/ ./ui/

# Generate version.json from git info (use build args since .git is excluded)
ARG BUILD_COMMIT=unknown
ARG BUILD_DATE=""
RUN mkdir -p ui/public && \
    echo "{\"commit\":\"${BUILD_COMMIT}\",\"date\":\"${BUILD_DATE:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}\"}" > ui/public/version.json

# Build frontend
RUN cd ui && bun install --frozen-lockfile && bun run build

# Build the Python wheel
RUN uv pip install --system build && python -m build --wheel --outdir /build/dist

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for claude CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install the claude CLI globally (required by claude-agent-sdk at runtime)
RUN npm install -g @anthropic-ai/claude-code

# Install uv for pip operations
RUN pip install --no-cache-dir uv

# Create a non-root user for running the application
RUN useradd --create-home --shell /bin/bash policyuser

WORKDIR /app

# Copy the built wheel from the builder stage
COPY --from=builder /build/dist/*.whl /tmp/

# Install the wheel (includes all Python dependencies)
RUN uv pip install --system /tmp/*.whl && rm -f /tmp/*.whl

# Copy prompt templates (these are loaded at runtime from the package)
# The prompts/ directory is inside the installed package via src/policy_factory/prompts/

# Create directories for volume mounts
RUN mkdir -p /app/data /app/.db && chown -R policyuser:policyuser /app

# ---------------------------------------------------------------------------
# Environment Variables
# ---------------------------------------------------------------------------

# AI agents use claude-agent-sdk which wraps the Claude Code CLI.
# No API key needed — the CLI uses the user's Claude subscription.
# Authenticate by running: claude auth login (before building or inside the container)

# SQLite database path (persisted via volume mount)
ENV POLICY_FACTORY_DB_PATH=/app/.db/store.db

# Data directory path (persisted via volume mount)
ENV POLICY_FACTORY_DATA_DIR=/app/data

# Server binding — 0.0.0.0 to accept connections from outside the container
ENV POLICY_FACTORY_HOST=0.0.0.0
ENV POLICY_FACTORY_PORT=8765

# Heartbeat configuration
ENV POLICY_FACTORY_HEARTBEAT_INTERVAL=14400
ENV POLICY_FACTORY_HEARTBEAT_ENABLED=true

# ---------------------------------------------------------------------------
# Volume mounts (documented)
# ---------------------------------------------------------------------------
# /app/data   — The data directory (separate git repo with layer markdown files).
#               Must persist across container restarts.
# /app/.db    — SQLite database directory (users, ideas, cascade state, etc.).
#               Must persist across container restarts.
VOLUME ["/app/data", "/app/.db"]

# Expose the application port
EXPOSE 8765

# Switch to non-root user
USER policyuser

# Configure git for the data directory auto-commits (as policyuser)
RUN git config --global user.email "policy-factory@localhost" && \
    git config --global user.name "Policy Factory" && \
    git config --global init.defaultBranch main

# Health check — verify the application is responsive
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8765/api/health/check || exit 1

# Entry point: start the Policy Factory server
ENTRYPOINT ["policy-factory", "server", "--host", "0.0.0.0", "--port", "8765"]
