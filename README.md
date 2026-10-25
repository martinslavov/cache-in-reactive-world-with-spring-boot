# RCAS – Reactive Cache Service

**RCAS** (Reactive Cache Service) is a reactive caching service built with Spring Boot WebFlux. It serves user and subscription data without blocking threads and puts a two-level cache in front of the database:

1. **Caffeine**: a fast in-memory (L1) cache inside the application.
2. **Redis**: a shared (L2) reactive cache, accessed through reactive Redis operations.
3. **PostgreSQL**: the source of truth, accessed through non-blocking R2DBC.

A read goes through the caches first and only falls back to the database on a miss, so repeated requests are served without hitting PostgreSQL. All layers are non-blocking, which keeps the service responsive under load with a small number of threads.

## Tech stack

- Java 25
- Spring Boot 4.1.2 (WebFlux, Data R2DBC, Data Redis Reactive, Actuator, Cache)
- PostgreSQL 15 and Redis 7
- Gradle 9.8.2 (wrapper)
- Docker / Docker Compose

## Prerequisites

- JDK 25 (`JAVA_HOME` must point to it)
- Docker with Docker Compose
- Access to the Docker Hardened Images registry (`docker login dhi.io`), needed to build the Docker image

## Build

```bash
./gradlew clean build        # compile + run all tests
./gradlew bootJar            # only build the executable jar (build/libs/rcas-0.0.1-SNAPSHOT.jar)
```

The tests use Testcontainers, so Docker must be running.

## Run

### Docker Compose profiles

`docker-compose.yml` splits the stack into infrastructure and the application, so you can choose what to start:

| Command | What starts |
|---------|-------------|
| `docker compose up -d` | Only the infrastructure: PostgreSQL and Redis |
| `docker compose --profile app up -d` | Infrastructure and the `rcas` application |

`rcas` belongs to the `app` profile, so it is **not** started by default. This lets you run the dependencies in Docker and start the service yourself from the IDE.

Stop everything (the `--profile app` flag is needed to also stop the service):

```bash
docker compose --profile app down        # stop and remove containers and network
docker compose --profile app down -v     # also remove volumes
```

### Option 1: everything in Docker

The image copies the jar from `build/libs`, so build it first:

```bash
./gradlew bootJar
docker compose --profile app up -d --build
```

### Option 2: dependencies in Docker, service from the IDE

```bash
docker compose up -d
```

Then run `com.gbp.rcas.RcasApplication` from the IDE (or `./gradlew bootRun`) with the Spring profile `dev`:

```bash
SPRING_PROFILES_ACTIVE=dev ./gradlew bootRun
```

The `dev` profile connects to PostgreSQL on `127.0.0.1:5432` (`testdb`, user and password `test`) and Redis on `localhost:6379`. Both ports are published by Compose.

## Docker services

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| `postgres` | `postgres:15.2` | 5432 | `db.migration/init.sql`, `V2__InsertUser.sql` and `V3__InsertSubscription.sql` run on first start |
| `redis` | `redis:7` | 6379 | |
| `rcas` | built from `Dockerfile` | 8080 | profile `app` |

All containers share the `rcas-docker-network` network. The Compose project name is `rcas`.

The database scripts run only when the Postgres container is created for the first time. After changing them, recreate the data with `docker compose --profile app down -v`.

## Configuring the JVM

The image is based on a hardened Temurin image that has no shell, so JVM options are passed through the `JDK_JAVA_OPTIONS` environment variable, which the `java` launcher reads itself. Separate multiple options with spaces:

```yaml
environment:
  JDK_JAVA_OPTIONS: "-XX:MaxRAMPercentage=75 -Dspring.profiles.active=prod"
```

Setting the variable replaces the default from the Dockerfile (`-XX:MaxRAMPercentage=75`), it does not append to it. Spring properties can also be set as environment variables, for example `SPRING_R2DBC_URL`.

## Health check

Because the hardened image has no shell or `curl`, the container health check runs a tiny precompiled Java class (`docker/HealthCheck.java`) against the actuator endpoint. `docker compose ps` shows `rcas` as `healthy` when it succeeds.

## Endpoints

All paths are under the `/app` base path.

| URL | Description |
|-----|-------------|
| `http://localhost:8080/app/user/{id}` | Get a user |
| `http://localhost:8080/app/user/{id}/subscription` | Get a user with the subscription |
| `http://localhost:8080/app/subscription/{id}` | Get a subscription |
| `http://localhost:8080/app/subscriptions/{ids}` | Get several subscriptions |
| `http://localhost:8080/app/actuator/health` | Health (includes PostgreSQL and Redis) |
| `http://localhost:8080/app/actuator/prometheus` | Prometheus metrics |
| `http://localhost:8080/app/swagger-ui-custom.html` | Swagger UI |
| `http://localhost:8080/app/v3/api-docs` | OpenAPI document |

The Docker database is seeded with three users (ids 1 to 3) and three subscriptions for user 1 (ids 1 to 3), so every endpoint returns data out of the box.

## Tests

```bash
./gradlew test
```

Integration tests start PostgreSQL through Testcontainers, so they need a running Docker daemon.

### Component tests

Component tests live in the separate Gradle subproject `component-tests`. They call the running service over HTTP, so they exercise the whole stack: the RCAS image, PostgreSQL and Redis. They do not depend on the application code and are not run by `./gradlew build` (it only compiles them).

```bash
make build             # build the jar used by the Docker image
make up                # build the image, start the stack and wait until it is healthy
make component-tests   # ./gradlew :component-tests:componentTest against http://localhost:8080/app
make sanity-tests      # only the fast sanity (smoke) tests (@Tag("sanity"))
make down              # stop the stack and remove containers, network and volumes
```

Set `RCAS_BASE_URL` to test a service running somewhere else. `make logs` prints the container logs.

## CI/CD (GitHub Actions)

Workflows live in `.github/workflows`:

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `ci-unit-tests.yml` (CI Unit Tests) | pull request, push to `main`, manual | `./gradlew build` on JDK 25: compiles, runs unit and integration tests, uploads the test report |
| `ci-component-tests.yml` (CI Component Tests) | pull request, push to `main`, manual | Builds the image, starts the stack with docker compose (`make up`), runs the component tests, collects the logs and tears everything down (`make down`) |
| `ci-sanity-tests.yml` (CI Sanity Tests) | pull request, push to `main`, manual | Starts the stack with docker compose and runs only the fast sanity tests (`make sanity-tests`) |
| `ci-release.yml` (CI Release) | push of a tag `v*` | Builds, runs the tests and creates a GitHub release with the executable jar and generated release notes |
| `ci-code-review.yml` (CodeQL) | pull request and push to `main`, weekly | Static security analysis, results appear in the Security tab |
| `ci-pr-issue-tracking.yml` (PR Issue Tracking) | pull request opened | Creates one tracking issue per PR (found again by a hidden marker, so it is never duplicated) and links it in a PR comment |

Create a release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Recommended repository settings:

- Settings → Actions → General → Workflow permissions: allow workflows to create issues and pull request comments (the PR Issue Tracking workflow also declares its permissions in the YAML).
- Branch protection / rulesets for `main`: require the `CI Unit Tests` and `CI Component Tests` checks before merging.
- Repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (a Docker Hub access token): the Dockerfile uses Docker Hardened Images (`dhi.io`), which need a login to pull. Used by CI Component Tests.
- Code scanning must be available for the repository to see the CodeQL results.

PRs from forks get a read-only token, so PR Issue Tracking cannot create issues for them.

## Branch workflow

Commits (and pushes) from `main`/`master` are blocked by the versioned hooks in `.githooks`. Enable them once per clone and work in a branch:

```bash
git config core.hooksPath .githooks
git checkout -b feature/my-change
```

For real enforcement on GitHub also enable branch protection for `main` (see Settings → Rules).
