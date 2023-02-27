package com.reactive.cache.repository;

import org.springframework.data.r2dbc.repository.Query;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;

import reactor.core.publisher.Flux;

import com.reactive.cache.model.Subscription;

public interface SubscriptionRepository extends ReactiveCrudRepository<Subscription, Long> {

    @Query(value = "SELECT * FROM subscription WHERE user_id = :id")
    Flux<Subscription> findSubscriptionsByUserId(Long id);

}
