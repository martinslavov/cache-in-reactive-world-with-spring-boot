package com.reactive.cache.router;

import com.reactive.cache.handler.SubscriptionHandler;

import org.springdoc.core.annotations.RouterOperation;
import org.springdoc.core.annotations.RouterOperations;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.server.RouterFunction;
import org.springframework.web.reactive.function.server.RouterFunctions;
import org.springframework.web.reactive.function.server.ServerResponse;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.enums.ParameterIn;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;

import static org.springframework.web.reactive.function.server.RequestPredicates.GET;
import static org.springframework.web.reactive.function.server.RequestPredicates.accept;

@Configuration
public class SubscriptionRouter {

    /**
     * The router configuration for the Subscription handler.
     *
     * @param subscriptionHandler - SubscriptionHandler
     * @return {@link ServerResponse}  - The subscription route info as part of ServerResponse
     */
    @RouterOperations({
            @RouterOperation(path = "/subscription/{id}",
            beanClass = SubscriptionHandler.class, beanMethod = "findById",
            operation = @Operation(operationId = "findById",
                    method = "GET",
                    parameters = @Parameter(name = "id", in = ParameterIn.PATH, schema = @Schema(type = "Long")),
                    summary = "Find subscription by id",
                    responses = {
                            @ApiResponse(
                                    responseCode = "200",
                                    description = "Successful operation",
                                    content = @Content(mediaType = "application/json",
                                            schema = @Schema(
                                                    type = "Response",
                                                    example = "{\"subscription\":1}",
                                                    description = "Found subscription - '...,...,...', by id - 1"))),
                            @ApiResponse( responseCode = "404", description = "Subscription not found", content = @Content),
                            @ApiResponse( responseCode = "500", description = "Internal Server Error", content = @Content)
                    }
            )),
            @RouterOperation(path = "/subscriptions/{ids}",
                    beanClass = SubscriptionHandler.class, beanMethod = "findSubscriptionsByIds",
                    operation = @Operation(operationId = "findSubscriptionsByIds",
                            method = "GET",
                            parameters = @Parameter(name = "ids", in = ParameterIn.PATH, schema = @Schema(type = "String")),
                            summary = "Find subscriptions by ids",
                            responses = {
                                    @ApiResponse(
                                            responseCode = "200",
                                            description = "Successful operation",
                                            content = @Content(mediaType = "application/json",
                                                    schema = @Schema(
                                                            type = "Response",
                                                            example = "{\"subscription\":[...,...,...]}",
                                                            description = "Found subscription - '...,...,...', by id - 1,2,3"))),
                                    @ApiResponse( responseCode = "404", description = "Subscriptions not found", content = @Content),
                                    @ApiResponse( responseCode = "500", description = "Internal Server Error", content = @Content)
                            }
                    ))
    })
    @Bean
    public RouterFunction<ServerResponse> subscriptionRoute(SubscriptionHandler subscriptionHandler) {

        return RouterFunctions
                .route(GET("/subscription/{id}").and(accept(MediaType.APPLICATION_JSON))
                        , subscriptionHandler::findById)
                .andRoute(GET("/subscriptions/{ids}").and(accept(MediaType.APPLICATION_JSON))
                        , subscriptionHandler::findSubscriptionsByIds);
    }
}
