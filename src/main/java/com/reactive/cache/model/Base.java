package com.reactive.cache.model;

import org.springframework.data.annotation.Id;

public class Base {

    @Id
    protected Long id;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

}
