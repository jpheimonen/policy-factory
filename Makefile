.PHONY: build install clean dev run

# Build frontend production assets
build:
	cd ui && bun install && bun run build

# Local editable install (for development)
install: build
	uv pip install -e .
	@echo ""
	@echo "Installed locally! Run with: policy-factory server"

# Remove build artifacts
clean:
	rm -rf ui/node_modules src/policy_factory/static/dist

# Dev mode: launch backend and frontend concurrently with auto-detected port
run:
	@# Find an available port before starting either process so the Vite
	@# proxy and the backend always agree on the port (fixes multi-instance dev).
	@export PORT=$$(uv run python -c "from policy_factory.server.port_utils import find_available_port; p = find_available_port('127.0.0.1', 8765); print(p or 8765)"); \
	echo "Using backend port $$PORT"; \
	trap 'kill 0' EXIT; \
		uv run policy-factory server --port $$PORT & \
		(cd ui && VITE_BACKEND_PORT=$$PORT bun run dev) & \
		wait

dev: run
