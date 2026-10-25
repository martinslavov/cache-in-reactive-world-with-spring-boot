package com.gbp.rcas.service;

import com.gbp.rcas.model.Subscription;

import java.util.List;


import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface SubscriptionService {

    Mono<Subscription> findById(Long id);

    Flux<Subscription> findSubscriptionsByIds(List<Long> id);

    Flux<Subscription> findSubscriptionsByUserId(Long userId);
}
