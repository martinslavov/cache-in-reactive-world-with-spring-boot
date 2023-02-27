package com.reactive.cache.model.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import com.fasterxml.jackson.databind.annotation.JsonPOJOBuilder;
import com.reactive.cache.model.Subscription;
import com.reactive.cache.model.User;

import java.util.List;

@JsonInclude(JsonInclude.Include.NON_NULL)
@JsonDeserialize(builder = ApiResponse.Builder.class)
@JsonPropertyOrder({"user", "subscriptions"})
public class ApiResponse {

    @JsonProperty("user")
    private final User user;
    @JsonProperty("subscriptions")
    private final List<Subscription> subscriptions;

    private ApiResponse(Builder builder) {
        this.user = builder.user;
        this.subscriptions = builder.subscriptions;
    }

    public static Builder builder() {
        return new Builder();
    }

    public User getUser() {
        return user;
    }

    public List<Subscription> getSubscriptions() {
        return subscriptions;
    }

    @JsonPOJOBuilder
    public static class Builder {
        private User user;
        private List<Subscription> subscriptions;

        public Builder() {}

        public Builder user(User user) {
            this.user = user;
            return this;
        }

        public Builder subscriptions(List<Subscription> subscriptions) {
            this.subscriptions = subscriptions;
            return this;
        }

        public ApiResponse build() {
            return new ApiResponse(this);
        }
    }
}