package com.reactive.cache.handler;

import com.reactive.cache.model.User;
import com.reactive.cache.service.UserService;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.AutoConfigureWebTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.reactive.server.WebTestClient;

import java.sql.Timestamp;
import java.util.Date;

import reactor.core.publisher.Mono;

import static org.mockito.BDDMockito.given;

@SpringBootTest
@AutoConfigureWebTestClient
@ActiveProfiles("test-tc")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
public class UserHandlerTest {

    @Autowired
    private WebTestClient webTestClient;

    @MockBean
    private UserService userService;

    @Test
    @DisplayName("UserHandler.findById - Success")
    @Order(1)
    public void givenUserId_whenGetUserById_thenUserFound() {
        // Given
        Long userId = Long.valueOf(1);
        var user = new User.UserBuilder()
                .setId(userId)
                     .setUsername("mslavov")
                             .setPassword("mypassword")
                                     .setEmail("slavoff.martin@gmail.com")
                                             .setCreatedOn(new Timestamp(new Date().getTime()))
                .createUser();

        // When
        given(userService.findById(userId)).willReturn(Mono.just(user));

        // Then
        webTestClient.get()
                .uri("/user/{id}", userId)
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.user.id")
                .isEqualTo(userId);
    }

    @Test
    @DisplayName("UserHandler.findById - Not Found")
    @Order(2)
    public void givenUserId_whenGetUserById_thenUserNotFound() {
        // Given
        Long userId = Long.valueOf(9_999_999_999L);

        // When
        given(userService.findById(userId)).willReturn(Mono.empty());

        // Then
        webTestClient.get()
                .uri("/user/{id}", userId)
                .exchange()
                .expectStatus()
                .isNotFound()
                .expectBody()
                .jsonPath("$.user")
                .doesNotExist();
    }
}