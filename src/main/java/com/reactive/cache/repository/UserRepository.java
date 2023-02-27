package com.reactive.cache.repository;

import org.springframework.data.r2dbc.repository.Query;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;

import reactor.core.publisher.Mono;

import com.reactive.cache.model.User;

public interface UserRepository extends ReactiveCrudRepository<User, Long> {

    @Query(value = "SELECT * FROM user_t WHERE id = :id ")
    Mono<User> findUserById(Long id);

}
