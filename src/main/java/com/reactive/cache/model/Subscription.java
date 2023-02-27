package com.reactive.cache.model;

import org.springframework.data.relational.core.mapping.Table;

@Table(name = "subscription")
public class Subscription extends Base{

    private String type;

    private int active;

    private int user_id;

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public int getActive() {
        return active;
    }

    public void setActive(int active) {
        this.active = active;
    }

    public int getUser_id() {
        return user_id;
    }

    public void setUser_id(int user_id) {
        this.user_id = user_id;
    }
}
