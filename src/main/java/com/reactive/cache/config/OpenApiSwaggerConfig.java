package com.reactive.cache.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import io.swagger.v3.oas.models.servers.Server;

@Configuration
public class OpenApiSwaggerConfig {

    @Value("${env.hostname-swagger}")
    private String hostnameSwagger;

    @Value("${spring.webflux.base-path}")
    private String basePath;

    @Bean
    public OpenAPI customOpenAPI() {
        return new OpenAPI().addServersItem(new Server().url("http://localhost:8080/api/" ))
                .info(new Info().title("Reactive REST API").version("v1")
                        .license(new License().name("Apache 2.0").url("http://springdoc.org")));
    }

}
