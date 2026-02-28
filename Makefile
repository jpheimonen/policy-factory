.PHONY: build install clean dev run docker-build docker-run docker-stop

DOCKER_IMAGE := policy-factory
DOCKER_CONTAINER := policy-factory
DOCKER_PORT ?= 8765
DOCKER_DATA_DIR ?= $(CURDIR)/data
DOCKER_DB_DIR ?= $(CURDIR)/.docker-db

# Build frontend production assets (with version stamping)
build:
	# Generate version info from git
	@mkdir -p ui/public
	@echo '{"commit":"'$$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")'","date":"'$$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"}' > ui/public/version.json
	cd ui && bun install && bun run build

# Local editable install (for development)
install: build
	uv pip install -e .
	@echo ""
	@echo "Installed locally! Run with: policy-factory server"

# Remove build artifacts
clean:
	rm -rf ui/node_modules src/policy_factory/static/dist ui/public/version.json

# Dev mode: launch backend and frontend concurrently with auto-detected port
dev:
	@# Find an available port before starting either process so the Vite
	@# proxy and the backend always agree on the port (fixes multi-instance dev).
	@export PORT=$$(uv run python -c "from policy_factory.server.port_utils import find_available_port; p = find_available_port('127.0.0.1', 8765); print(p or 8765)"); \
	echo "Using backend port $$PORT"; \
	trap 'kill 0' EXIT; \
		uv run policy-factory server --port $$PORT & \
		(cd ui && VITE_BACKEND_PORT=$$PORT bun run dev) & \
		wait

# Production server: build frontend then start the server
run: build
	@echo "Starting Policy Factory production server..."
	uv run policy-factory server

# Build the Docker image
docker-build:
	docker build -t $(DOCKER_IMAGE) .

# Run the Docker container
docker-run:
	@mkdir -p $(DOCKER_DATA_DIR) $(DOCKER_DB_DIR)
	docker run -d \
		--name $(DOCKER_CONTAINER) \
		-p $(DOCKER_PORT):8765 \
		-v $(DOCKER_DATA_DIR):/app/data \
		-v $(DOCKER_DB_DIR):/app/.db \
		-e POLICY_FACTORY_DB_PATH=/app/.db/store.db \
		-e POLICY_FACTORY_DATA_DIR=/app/data \
		-e ANTHROPIC_API_KEY=$${ANTHROPIC_API_KEY:-} \
		$(if $(wildcard .env),--env-file .env,) \
		$(DOCKER_IMAGE)
	@echo ""
	@echo "Policy Factory is running at http://localhost:$(DOCKER_PORT)"
	@echo "  Data directory: $(DOCKER_DATA_DIR)"
	@echo "  Database directory: $(DOCKER_DB_DIR)"
	@echo ""
	@echo "View logs:  docker logs -f $(DOCKER_CONTAINER)"
	@echo "Stop:       make docker-stop"

# Stop the Docker container
docker-stop:
	docker stop $(DOCKER_CONTAINER) 2>/dev/null || true
	docker rm $(DOCKER_CONTAINER) 2>/dev/null || true
	@echo "Policy Factory container stopped."
