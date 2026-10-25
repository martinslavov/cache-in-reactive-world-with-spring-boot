package com.gbp.rcas.component;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ServiceComponentTest extends ComponentTestSupport {

    @Test
    @DisplayName("Health endpoint reports UP with PostgreSQL and Redis connected")
    void healthIsUp() {
        Response response = get("/actuator/health");

        assertEquals(200, response.status());
        assertEquals("UP", response.json().path("status").asText());
    }

    @Test
    @DisplayName("Get user by id returns the seeded user")
    void findUserById() {
        Response response = get("/user/1");

        assertEquals(200, response.status());
        assertEquals("martin", response.json().path("user").path("username").asText());
    }

    @Test
    @DisplayName("Get unknown user returns 404")
    void findUnknownUser() {
        assertEquals(404, get("/user/999999").status());
    }

    @Test
    @DisplayName("Get user with subscriptions returns the seeded subscriptions")
    void findUserWithSubscriptions() {
        Response response = get("/user/1/subscription");

        assertEquals(200, response.status());
        JsonNode body = response.json();
        assertEquals("martin", body.path("user").path("username").asText());
        assertTrue(body.path("subscriptions").size() >= 3, "expected at least 3 subscriptions");
    }

    @Test
    @DisplayName("Get subscription by id returns the seeded subscription")
    void findSubscriptionById() {
        Response response = get("/subscription/1");

        assertEquals(200, response.status());
        assertEquals(1, response.json().path("subscriptions").size());
    }

    @Test
    @DisplayName("Get subscriptions by ids returns every requested subscription")
    void findSubscriptionsByIds() {
        Response response = get("/subscriptions/1,2");

        assertEquals(200, response.status());
        assertEquals(2, response.json().path("subscriptions").size());
    }

    @Test
    @DisplayName("Repeated reads are served consistently through the cache layers")
    void repeatedReadsAreConsistent() {
        String first = get("/user/1").body();
        String second = get("/user/1").body();

        assertEquals(first, second);
    }

    @Test
    @DisplayName("OpenAPI documentation is exposed")
    void openApiIsExposed() {
        Response response = get("/v3/api-docs");

        assertEquals(200, response.status());
        assertTrue(response.json().has("paths"));
    }
}
