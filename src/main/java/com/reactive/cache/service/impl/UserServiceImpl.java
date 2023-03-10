package com.reactive.cache.service.impl;


import com.reactive.cache.config.KPI;
import com.reactive.cache.enums.KPITypes;
import com.reactive.cache.model.User;
import com.reactive.cache.repository.UserRepository;
import com.reactive.cache.service.UserService;

import org.springframework.data.redis.core.ReactiveHashOperations;
import org.springframework.stereotype.Service;

import reactor.core.publisher.Mono;

import static com.reactive.cache.config.Constants.CACHE_NAME_USER;

@Service(value = "userService")
public class UserServiceImpl implements UserService {

    private final UserRepository userRepository;

    private final KPI kpi;

    private final ReactiveHashOperations<String, Long, User> hashOperations;

    public UserServiceImpl(UserRepository userRepository, KPI kpi, ReactiveHashOperations<String, Long, User> hashOperations) {
        this.userRepository = userRepository;
        this.kpi = kpi;
        this.hashOperations = hashOperations;
    }

    @Override
    public Mono<User> findById(Long id) {
       return kpi.measure(KPITypes.USER, "findById",
               () -> hashOperations.get(CACHE_NAME_USER, id)
                       .switchIfEmpty(userRepository.findById(id)
                               .flatMap(user -> hashOperations.put(CACHE_NAME_USER, id, user)
                                       .thenReturn(user))));
    }

}
