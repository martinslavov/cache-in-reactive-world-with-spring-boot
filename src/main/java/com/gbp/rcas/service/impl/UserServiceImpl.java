package com.gbp.rcas.service.impl;


import com.gbp.rcas.config.KPI;
import com.gbp.rcas.enums.KPITypes;
import com.gbp.rcas.model.User;
import com.gbp.rcas.repository.UserRepository;
import com.gbp.rcas.service.UserService;

import org.springframework.data.redis.core.ReactiveHashOperations;
import org.springframework.stereotype.Service;

import reactor.core.publisher.Mono;

import static com.gbp.rcas.config.Constants.CACHE_NAME_USER;

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
