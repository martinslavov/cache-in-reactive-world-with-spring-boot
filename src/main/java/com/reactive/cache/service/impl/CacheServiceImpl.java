package com.reactive.cache.service.impl;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cache.Cache;
import org.springframework.cache.CacheManager;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;
import java.util.function.Supplier;

import reactor.cache.CacheFlux;
import reactor.cache.CacheMono;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Signal;

import com.reactive.cache.service.CacheService;

@Service(value = "cacheService")
public class CacheServiceImpl implements CacheService {

    private static final Logger logger = LoggerFactory.getLogger(CacheServiceImpl.class);

    private final CacheManager cacheManager;

    public CacheServiceImpl(CacheManager cacheManager) {
        this.cacheManager = cacheManager;
    }

    @Override
    public <T> Mono<T> getCache(Long id, String cacheName, Supplier<Mono<T>> retriever, Class<T> cls) {

        Cache cache = cacheManager.getCache(cacheName);
        return CacheMono.lookup(key -> Mono.justOrEmpty(cache.get(id, cls))
                .map(Signal::next), id)
                .onCacheMissResume(() -> {
                    logger.info("{} was not found into cache by id: {}", cls.getName(), id);
                    return retriever.get();
                })
                .andWriteWith((key, signal) -> Mono.fromRunnable(() ->
                        Optional.ofNullable(signal.get())
                                .ifPresent(value -> cache.put(key, value))));
    }

    @Override
    public <T> Flux<T> getCache(Long id, String cacheName, Supplier<Flux<T>> retriever) {
        Cache cache = cacheManager.getCache(cacheName);
        return CacheFlux
                .lookup(k -> {
                    List<T> result = cache.get(k, List.class);
                    return Mono.justOrEmpty(result)
                            .flatMap(list -> Flux.fromIterable(list).materialize().collectList());
                }, id)
                .onCacheMissResume(() -> {
                    logger.info("{} was not found into cache by id: {}", cacheName, id);
                    return Flux.defer(retriever);
                })
                .andWriteWith((k, signalList) -> Flux.fromIterable(signalList)
                        .dematerialize()
                        .collectList()
                        .doOnNext(list -> {
                            cache.put(k, list);
                        })
                        .then());
    }






}

