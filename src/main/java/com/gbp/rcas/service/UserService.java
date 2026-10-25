package com.gbp.rcas.service;

import com.gbp.rcas.model.User;

import reactor.core.publisher.Mono;

public interface UserService {

    Mono<User> findById(Long id);

}
