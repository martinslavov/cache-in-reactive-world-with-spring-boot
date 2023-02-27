package com.reactive.cache.handler;

import com.reactive.cache.exceptions.GlobalException;
import com.reactive.cache.model.Subscription;
import com.reactive.cache.model.dto.ApiResponse;
import com.reactive.cache.service.SubscriptionService;
import com.reactive.cache.service.UserService;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;

import java.util.ArrayList;
import java.util.List;

import reactor.core.publisher.Mono;

import static reactor.core.publisher.Mono.just;

@Component
public class UserHandler {

    private static final Logger logger = LoggerFactory.getLogger(UserHandler.class);

    private final UserService userService;

    private final SubscriptionService subscriptionService;

    public UserHandler(UserService userService, SubscriptionService subscriptionService) {
        this.userService = userService;
        this.subscriptionService = subscriptionService;
    }

    /**
     * The handler to get user by id.
     *
     * @param serverRequest - ServerRequest
     * @return {@link ServerResponse}  - The user info as part of ServerResponse
     */
    public Mono<ServerResponse> findById(ServerRequest serverRequest) {
        Long id = Long.valueOf(serverRequest.pathVariable("id"));
        logger.info("Find user by id: " + id);

        return userService.findById(id)
                .flatMap(user -> {
                    logger.debug("Found user - {}, by id - {}", user, id);
                    return ServerResponse.ok()
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(Mono.just(ApiResponse.builder().user(user).build()), ApiResponse.class);
                })
                .switchIfEmpty(Mono.defer(() -> {
                    logger.debug("User was not found by id: " + id);
                    return ServerResponse.notFound().build();
                }))
                .onErrorResume(throwable -> {
                    logger.error("Exception during searching for user by id: {}, exception: {}", id, throwable);
                    return Mono.error(new GlobalException(HttpStatus.INTERNAL_SERVER_ERROR, "Internal server error", throwable ));
                });
   }

    /**
     * The handler to get user and subscriptions by userId.
     *
     * @param serverRequest - ServerRequest
     * @return {@link ServerResponse}  - The user and subscriptions info as part of ServerResponse
     */
    public Mono<ServerResponse> findUserAndSubscriptionsByUserId(ServerRequest serverRequest){

        Long id = Long.valueOf(serverRequest.pathVariable("id"));
        logger.info("Find user and subscriptions by user id: " + id);

        return userService.findById(id)
                .flatMap(user -> {
                    logger.debug("Found user - {}, by id - {}", user.getId(), id);
                    return subscriptionService.findSubscriptionsByUserId(user.getId())
                            .collectList()
                            .flatMap(subscriptions -> {
                                ApiResponse response;
                                if (subscriptions.isEmpty()) {
                                    logger.debug("Subscriptions were not found by user id: " + user.getId().intValue());
                                    response = ApiResponse.builder().user(user).build();
                                }else {
                                    List<Subscription> subscriptionList = new ArrayList<>(subscriptions);
                                    logger.debug("Found subscriptions - {}, by user id - {}", subscriptions, user.getId().intValue());
                                    response = ApiResponse.builder().user(user).subscriptions(subscriptionList).build();
                                }
                                return ServerResponse.ok()
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .body(just(response), ApiResponse.class);
                            })
                            .onErrorResume(throwable -> {
                                logger.error("Exception during searching for subscriptions by user id: {}, exception: {}", user.getId().intValue(), throwable);
                                return Mono.error(new GlobalException(HttpStatus.INTERNAL_SERVER_ERROR, "Internal server error", throwable ));
                            });
                })
                .switchIfEmpty(Mono.defer(() -> {
                    logger.debug("User was not found by id: " + id);
                    return ServerResponse.notFound().build();
                }))
                .onErrorResume(throwable -> {
                    logger.error("Exception during searching for user by id: {}, exception: {}", id, throwable);
                    return Mono.error(new GlobalException(HttpStatus.INTERNAL_SERVER_ERROR, "Internal server error", throwable));
                });
    }
}
