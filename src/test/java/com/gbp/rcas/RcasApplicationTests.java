package com.gbp.rcas;

import com.gbp.rcas.handler.SubscriptionHandler;
import com.gbp.rcas.handler.UserHandler;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test-tc")
class RcasApplicationTests {
    @Autowired
    private UserHandler userHandler;

    @Autowired
    private SubscriptionHandler subscriptionHandler;

    @Test
    void contextLoads() {
        assertThat(userHandler).isNotNull();
        assertThat(subscriptionHandler).isNotNull();
    }
}
