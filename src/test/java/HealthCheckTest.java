import static org.assertj.core.api.Assertions.assertThat;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.time.Duration;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

/**
 * Unit tests for the container health check helper. HealthCheck lives in the default package
 * (it is run as {@code java -cp /app HealthCheck}), so this test is in the default package too.
 */
class HealthCheckTest {

    private HttpServer server;
    private final CountDownLatch release = new CountDownLatch(1);

    @BeforeEach
    void startServer() throws IOException {
        server = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
        server.createContext("/ok", exchange -> respond(exchange, 200));
        server.createContext("/missing", exchange -> respond(exchange, 404));
        server.createContext("/error", exchange -> respond(exchange, 500));
        server.createContext("/slow", exchange -> {
            try {
                release.await(10, TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            respond(exchange, 200);
        });
        server.setExecutor(java.util.concurrent.Executors.newCachedThreadPool());
        server.start();
    }

    @AfterEach
    void stopServer() {
        release.countDown();
        server.stop(0);
    }

    @Test
    void healthyWhenEndpointReturns200() {
        assertThat(HealthCheck.isHealthy(url("/ok"))).isTrue();
    }

    @Test
    void unhealthyWhenEndpointReturns404() {
        assertThat(HealthCheck.isHealthy(url("/missing"))).isFalse();
    }

    @Test
    void unhealthyWhenEndpointReturns500() {
        assertThat(HealthCheck.isHealthy(url("/error"))).isFalse();
    }

    @Test
    void unhealthyWhenNothingListens() throws IOException {
        int freePort;
        try (ServerSocket socket = new ServerSocket(0, 1, InetAddress.getLoopbackAddress())) {
            freePort = socket.getLocalPort();
        }
        assertThat(HealthCheck.isHealthy("http://127.0.0.1:" + freePort + "/ok")).isFalse();
    }

    @Test
    void unhealthyWhenUrlIsInvalid() {
        assertThat(HealthCheck.isHealthy("not a url")).isFalse();
        assertThat(HealthCheck.isHealthy("ftp://127.0.0.1/ok")).isFalse();
    }

    @Test
    @Timeout(10)
    void unhealthyWhenResponseIsSlowerThanReadTimeout() {
        long start = System.nanoTime();
        assertThat(HealthCheck.isHealthy(url("/slow"))).isFalse();
        // The 2 s read timeout must fire well before Docker's 5 s health check timeout.
        assertThat(Duration.ofNanos(System.nanoTime() - start)).isLessThan(Duration.ofSeconds(5));
    }

    private String url(String path) {
        return "http://127.0.0.1:" + server.getAddress().getPort() + path;
    }

    private static void respond(com.sun.net.httpserver.HttpExchange exchange, int status) throws IOException {
        exchange.sendResponseHeaders(status, -1);
        exchange.close();
    }
}
