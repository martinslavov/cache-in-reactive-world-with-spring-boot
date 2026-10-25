package com.gbp.rcas.config;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.instrumentation.log4j.appender.v2_17.OpenTelemetryAppender;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Connects the Log4j2 OpenTelemetry appender to the OpenTelemetry SDK. It has an effect only when the appender is
 * configured, i.e. with {@code log4j2-otel.yaml} (see the docker compose {@code monitoring} profile).
 */
@Configuration
public class OpenTelemetryLogAppenderConfig {

    @Bean
    public InitializingBean openTelemetryLogAppenderInstaller(OpenTelemetry openTelemetry) {
        return () -> OpenTelemetryAppender.install(openTelemetry);
    }
}
