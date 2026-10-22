## 1. Changes Made

1. **Secure short URLs:** Use `SHORTENER_BASE_URL` to generate short links instead of trusting the incoming request hostname. This prevents Host-header attacks and incorrect URLs.

2. **Accurate click counts:** Update click counts directly in the database to avoid losing updates when multiple users access a link simultaneously.

3. **Handle code collisions:** Retry generated codes up to 10 times. Return HTTP `409 Conflict` if a custom alias already exists, including concurrent conflicts.

4. **Manage database schema:** Use Liquibase to create the `short_urls` table. Hibernate validates the schema at startup instead of modifying it automatically.

5. **Add tests:** Test canonical URL generation, click-count updates, code collisions, and concurrent click updates using PostgreSQL Testcontainers.

## 2. Run Tests

From `services/url-shortener`, run:

```powershell
mvn test
```

## 3. Deployment Configuration

Set `SHORTENER_BASE_URL` to your public URL, for example `https://sho.rt.example`.

Never derive this value from request headers. Keep database credentials out of source control in non-local environments.