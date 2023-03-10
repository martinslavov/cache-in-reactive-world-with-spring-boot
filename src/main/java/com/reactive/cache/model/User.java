package com.reactive.cache.model;

import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

import java.io.Serializable;
import java.sql.Timestamp;

@Table(name = "user_t")
public class User extends Base implements Serializable {

    private String username;
    private String password;
    private String email;
    @Column("created_on")
    private Timestamp createdOn;
    @Column("last_login")
    private Timestamp lastLogin;

    public User(Long id, String username, String password, String email, Timestamp createdOn, Timestamp lastLogin) {
        super(id);
        this.username = username;
        this.password = password;
        this.email = email;
        this.createdOn = createdOn;
        this.lastLogin = lastLogin;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public Timestamp getCreatedOn() {
        return createdOn;
    }

    public void setCreatedOn(Timestamp createdOn) {
        this.createdOn = createdOn;
    }

    public Timestamp getLastLogin() {
        return lastLogin;
    }

    public void setLastLogin(Timestamp lastLogin) {
        this.lastLogin = lastLogin;
    }

    public static class UserBuilder {
        private Long id;
        private String username;
        private String password;
        private String email;
        private Timestamp createdOn;
        private Timestamp lastLogin;

        public UserBuilder setId(Long id) {
            this.id = id;
            return this;
        }

        public UserBuilder setUsername(String username) {
            this.username = username;
            return this;
        }

        public UserBuilder setPassword(String password) {
            this.password = password;
            return this;
        }

        public UserBuilder setEmail(String email) {
            this.email = email;
            return this;
        }

        public UserBuilder setCreatedOn(Timestamp createdOn) {
            this.createdOn = createdOn;
            return this;
        }

        public UserBuilder setLastLogin(Timestamp lastLogin) {
            this.lastLogin = lastLogin;
            return this;
        }

        public User createUser() {
            return new User(id, username, password, email, createdOn, lastLogin);
        }
    }
}

