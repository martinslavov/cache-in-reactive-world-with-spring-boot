package com.reactive.rcas.service;

import com.reactive.rcas.model.User;

import reactor.core.publisher.Mono;

public interface UserService {

    Mono<User> findById(Long id);

}
