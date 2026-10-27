# Single-stage image on the hardened runtime: no shell, curl or compiler, so nothing is built here.
# Artifacts come from `make build`: the boot jar and the precompiled health check class (build/healthcheck).
FROM dhi.io/eclipse-temurin:25

ARG OCI_SOURCE=https://github.com/martinslavov/rcas
ARG OCI_VERSION=development
ARG OCI_REVISION=unknown
LABEL org.opencontainers.image.source=${OCI_SOURCE} \
      org.opencontainers.image.version=${OCI_VERSION} \
      org.opencontainers.image.revision=${OCI_REVISION}

USER nonroot
WORKDIR /app

# Read natively by the java launcher; override at runtime with -e JDK_JAVA_OPTIONS="..."
ENV JDK_JAVA_OPTIONS="-XX:MaxRAMPercentage=75"

COPY --chown=nonroot:nonroot build/libs/rcas-*.jar rcas.jar
COPY --chown=nonroot:nonroot build/healthcheck/HealthCheck.class HealthCheck.class

# Runs as nonroot inside the container and probes http://127.0.0.1:8080/app/actuator/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["java", "-cp", "/app", "HealthCheck"]

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "rcas.jar"]
