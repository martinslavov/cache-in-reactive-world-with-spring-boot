package com.reactive.cache.actuator;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.AutoConfigureWebTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.reactive.server.WebTestClient;

@SpringBootTest
@AutoConfigureWebTestClient
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
public class ActuatorIntegrationTest {

    @Autowired
    private WebTestClient webTestClient;

    @Test
    @DisplayName("Actuator - Success")
    @Order(1)
    public void givenActuatorRouterWritePath_whenGetStatus_thenGotOK() {
        webTestClient.get()
                .uri("/actuator")
                .exchange()
                .expectStatus()
                .isOk();
    }

    @Test
    @DisplayName("Actuator - Not Found")
    @Order(2)
    public void givenActuatorRouterWrongPath_whenGetStatus_thenGotNotFound() {
        webTestClient.get()
                .uri("/unknown/path")
                .exchange()
                .expectStatus()
                .isNotFound();
    }

    @Test
    @DisplayName("Actuator - Env Status")
    @Order(3)
    public void givenActuatorRouterEnvPath_whenGetEnvStatus_thenGotEnv() {
        webTestClient.get()
                .uri("/actuator/env")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.activeProfiles")
                .isNotEmpty();
    }
}