package com.reactive.cache.service;

import com.reactive.cache.model.User;

import reactor.core.publisher.Mono;

public interface UserService {

    Mono<User> findById(Long id);

}
