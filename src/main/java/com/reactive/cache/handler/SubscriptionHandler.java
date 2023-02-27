package com.reactive.cache.handler;

import com.reactive.cache.exceptions.GlobalException;
import com.reactive.cache.model.Subscription;
import com.reactive.cache.model.dto.ApiResponse;
import com.reactive.cache.service.SubscriptionService;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Stream;

import reactor.core.publisher.Mono;

import static java.util.stream.Collectors.toList;
import static reactor.core.publisher.Mono.just;

@Component
public class SubscriptionHandler {

    private static final Logger logger = LoggerFactory.getLogger(SubscriptionHandler.class);

    private final SubscriptionService subscriptionService;

    public SubscriptionHandler(SubscriptionService subscriptionService) {
        this.subscriptionService = subscriptionService;
    }

    /**
     * The handler to get subscription by id.
     *
     * @param serverRequest - ServerRequest
     * @return {@link ServerResponse}  - The subscription info as part of ServerResponse
     */
    public Mono<ServerResponse> findById(ServerRequest serverRequest) {

        Long id = Long.valueOf(serverRequest.pathVariable("id"));
        logger.info("Find subscription by id: " + id);

        return subscriptionService.findById(id)
                .flatMap(subscription -> {
                    logger.debug("Found subscription- {}, by id - {}", subscription, id);
                    return ServerResponse.ok()
                            .contentType(MediaType.APPLICATION_JSON)
                            .body(just(ApiResponse.builder().subscriptions(Arrays.asList(subscription)).build()), ApiResponse.class);
                })
                .switchIfEmpty(Mono.defer(() -> {
                    logger.debug("Subscription was not found by id: " + id);
                    return ServerResponse.notFound().build();
                }))
                .onErrorResume(throwable -> {
                    logger.error("Exception during searching for subscription by id: {}, exception: {}", id, throwable);
                    return Mono.error(new GlobalException(HttpStatus.INTERNAL_SERVER_ERROR, "Internal server error", throwable ));
                });
    }

    /**
     * The handler to get subscriptions by ids.
     *
     * @param serverRequest - ServerRequest
     * @return {@link ServerResponse}  - The subscription info as part of ServerResponse
     */
    public Mono<ServerResponse> findSubscriptionsByIds(ServerRequest serverRequest) {

        List<Long> ids = Stream.of(serverRequest.pathVariable("ids").split(","))
                .map(String::trim)
                .map(id -> Long.valueOf(id))
                .collect(toList());
        logger.info("Find subscriptions by ids: " + ids);

        return subscriptionService.findSubscriptionsByIds(ids)
                .collectList()
                .flatMap(subscription -> {
                    if (subscription.isEmpty()) {
                        logger.debug("Subscriptions were not found by ids: " + ids);
                        return ServerResponse.notFound().build();
                    }else {
                        List<Subscription> subscriptions = new ArrayList<>(subscription);
                        logger.debug("Found subscriptions - {}, by ids - {}", subscriptions, ids);
                        return ServerResponse.ok()
                                .contentType(MediaType.APPLICATION_JSON)
                                .body(just(ApiResponse.builder().subscriptions(subscriptions).build()), ApiResponse.class);
                    }
                })
                .onErrorResume(throwable -> {
                    logger.error("Exception during searching for subscriptions by ids: {}, exception: {}", ids, throwable);
                    return Mono.error(new GlobalException(HttpStatus.INTERNAL_SERVER_ERROR, "Internal server error", throwable ));
                });
    }

}
