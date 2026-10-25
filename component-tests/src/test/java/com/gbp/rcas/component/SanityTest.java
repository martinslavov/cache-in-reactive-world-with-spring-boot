package com.gbp.rcas.component;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Fast checks that the deployed stack is alive and its main paths work. */
@Tag("sanity")
class SanityTest extends ComponentTestSupport {

    @Test
    @DisplayName("Service is UP")
    void serviceIsUp() {
        Response response = get("/actuator/health");

        assertEquals(200, response.status());
        assertEquals("UP", response.json().path("status").asText());
    }

    @Test
    @DisplayName("PostgreSQL and Redis are connected")
    void dependenciesAreUp() {
        JsonNode components = get("/actuator/health").json().path("components");

        assertEquals("UP", components.path("r2dbc").path("status").asText());
        assertEquals("UP", components.path("redis").path("status").asText());
    }

    @Test
    @DisplayName("User is read from the database")
    void userEndpointWorks() {
        Response response = get("/user/1");

        assertEquals(200, response.status());
        assertEquals("martin", response.json().path("user").path("username").asText());
    }

    @Test
    @DisplayName("Subscription is read from the database")
    void subscriptionEndpointWorks() {
        assertEquals(200, get("/user/1/subscription").status());
    }

    @Test
    @DisplayName("Repeated read is served consistently (cache path)")
    void cachedReadIsConsistent() {
        String first = get("/user/1").body();
        String second = get("/user/1").body();

        assertEquals(first, second);
    }

    @Test
    @DisplayName("API documentation is available")
    void apiDocsAvailable() {
        Response response = get("/v3/api-docs");

        assertEquals(200, response.status());
        assertTrue(response.body().contains("openapi"));
    }
}
