package com.reactive.cache.exceptions.database;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
public class DuplicateKeyValueViolatesUniqueConstraint extends RuntimeException {
    private final String field;

    public DuplicateKeyValueViolatesUniqueConstraint(String field) {
        super("Duplicate key value violates unique constraint:" + field);
        this.field = field;
    }


}
