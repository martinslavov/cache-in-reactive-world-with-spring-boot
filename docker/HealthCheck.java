import java.net.HttpURLConnection;
import java.net.URL;

// Run as: java HealthCheck.java <url>. Exits 0 when the endpoint returns HTTP 200.
public class HealthCheck {
    public static void main(String[] args) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(args[0]).openConnection();
        c.setConnectTimeout(2000);
        c.setReadTimeout(2000);
        System.exit(c.getResponseCode() == 200 ? 0 : 1);
    }
}
