# Build stage: compile the healthcheck helper (the runtime image has no compiler)
FROM dhi.io/eclipse-temurin:25-jdk-dev AS healthcheck
COPY docker/HealthCheck.java /src/HealthCheck.java
RUN javac -d /out /src/HealthCheck.java

# Package stage
FROM dhi.io/eclipse-temurin:25

# Alpine appuser
USER nonroot

# Alpine appuser home
WORKDIR /app

# Space-separated JVM options, read natively by the java launcher (no shell needed).
# Override at runtime with -e JDK_JAVA_OPTIONS="..."
ENV JDK_JAVA_OPTIONS="-XX:MaxRAMPercentage=75"

# Copy the service dependencies to the container
COPY --chown=nonroot:nonroot build/libs/rcas-*.jar rcas.jar

# Healthcheck helper (the hardened image has no shell or curl)
COPY --from=healthcheck --chown=nonroot:nonroot /out/HealthCheck.class HealthCheck.class

## Start application
ENTRYPOINT ["java", "-jar", "rcas.jar"]