COMPOSE := ./docker/run.sh

.PHONY: build up up-dry down logs restart

build:            ## Build the Docker image
	$(COMPOSE) build

up:               ## Start the container (live, detached)
	$(COMPOSE) up -d

up-dry:           ## Start in dry-run mode (no commands sent to robot)
	DRY_RUN=true $(COMPOSE) up

down:             ## Stop and remove the container
	$(COMPOSE) down

logs:             ## Follow container logs
	docker logs -f go2w_teleop_gamepad

restart:          ## Restart the container
	$(COMPOSE) down
	$(COMPOSE) up -d

help:             ## Show this help
	@grep -E '^[a-z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'
