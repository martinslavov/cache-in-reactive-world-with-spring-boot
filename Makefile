COMPOSE ?= docker compose
HEALTH_TIMEOUT ?= 180

.PHONY: build up down logs component-tests

## Build the executable jar used by the Docker image
build:
	./gradlew bootJar -x test

## Start (requires `make build` first): build the image and start PostgreSQL, Redis and RCAS; waits until all containers are healthy
up:
	$(COMPOSE) --profile app up -d --build --wait --wait-timeout $(HEALTH_TIMEOUT)

## Stop the stack and remove containers, network and volumes
down:
	$(COMPOSE) --profile app down -v

## Print the logs of all containers
logs:
	$(COMPOSE) --profile app logs --no-color

## Run the component tests against the running stack
component-tests:
	./gradlew componentTest
