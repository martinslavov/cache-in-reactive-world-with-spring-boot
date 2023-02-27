package com.reactive.cache.router;

import com.reactive.cache.handler.UserHandler;

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
public class UserRouter {

    /**
     * The router configuration for the User handler.
     *
     * @param userHandler - UserHandler
     * @return {@link ServerResponse}  - The user route info as part of ServerResponse
     */
    @RouterOperations({
            @RouterOperation(path = "/user/{id}",
            beanClass = UserHandler.class, beanMethod = "findById",
            operation = @Operation(operationId = "findById",
                    method = "GET",
                    parameters = @Parameter(name = "id", in = ParameterIn.PATH, schema = @Schema(type = "Long")),
                    summary = "Find user by id",
                    responses = {
                            @ApiResponse( responseCode = "200",
                                    description = "Successful operation",
                                    content = @Content(mediaType = "application/json",
                                            schema = @Schema(type = "Response",
                                                    example = "{\"user\":\"...\"}",
                                                    description = "Found user - ..., by user id - 13811939"
                                            ))),
                            @ApiResponse( responseCode = "404", description = "User not found", content = @Content),
                            @ApiResponse( responseCode = "500", description = "Internal Server Error", content = @Content)
                    }
            )),
            @RouterOperation(path = "/user/{id}/subscription",
                    beanClass = UserHandler.class, beanMethod = "findUserAndSubscriptionsByUserId",
                    operation = @Operation(operationId = "findUserAndSubscriptionsByUserId",
                            method = "GET",
                            parameters = {
                                    @Parameter(name = "id", in = ParameterIn.PATH, schema = @Schema(type = "Long")),
                            },
                            summary = "Find user and subscriptions by user id",
                            responses = {
                                    @ApiResponse( responseCode = "200",
                                            description = "Successful operation",
                                            content = @Content(mediaType = "application/json",
                                                    schema = @Schema(implementation = com.reactive.cache.model.dto.ApiResponse.class))),
                                    @ApiResponse( responseCode = "404", description = "User not found", content = @Content),
                                    @ApiResponse( responseCode = "500", description = "Internal Server Error", content = @Content)
                            }
                    ))
    })
    @Bean
    public RouterFunction<ServerResponse> userRoute(UserHandler userHandler){

        return RouterFunctions
                .route(GET("/user/{id}").and(accept(MediaType.APPLICATION_JSON)),
                        userHandler::findById)
                .andRoute(GET("/user/{id}/subscription").and(accept(MediaType.APPLICATION_JSON)),
                        userHandler::findUserAndSubscriptionsByUserId);
    }

}
