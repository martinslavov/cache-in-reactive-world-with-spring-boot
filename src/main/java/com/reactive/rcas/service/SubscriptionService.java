package com.reactive.rcas.service;

import com.reactive.rcas.model.Subscription;

import java.util.List;


import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface SubscriptionService {

    Mono<Subscription> findById(Long id);

    Flux<Subscription> findSubscriptionsByIds(List<Long> id);

    Flux<Subscription> findSubscriptionsByUserId(Long userId);
}
