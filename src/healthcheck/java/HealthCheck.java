import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URI;

/**
 * Container health check for the hardened runtime image, which has no shell or curl.
 * Run as {@code java -cp /app HealthCheck [url]}; exits 0 only when the endpoint returns HTTP 200.
 * The default URL targets the actuator inside the same container. The timeouts stay below the 5 s Docker timeout.
 */
public final class HealthCheck {

    private static final String DEFAULT_URL = "http://127.0.0.1:8080/app/actuator/health";
    private static final int TIMEOUT_MILLIS = 2000;

    private HealthCheck() {
    }

    public static void main(String[] args) {
        String url = args.length > 0 ? args[0] : DEFAULT_URL;
        System.exit(isHealthy(url) ? 0 : 1);
    }

    static boolean isHealthy(String url) {
        try {
            if (!(URI.create(url).toURL().openConnection() instanceof HttpURLConnection connection)) {
                return false;
            }
            connection.setConnectTimeout(TIMEOUT_MILLIS);
            connection.setReadTimeout(TIMEOUT_MILLIS);
            try {
                return connection.getResponseCode() == HttpURLConnection.HTTP_OK;
            } finally {
                connection.disconnect();
            }
        } catch (IOException | IllegalArgumentException e) {
            return false;
        }
    }
}
