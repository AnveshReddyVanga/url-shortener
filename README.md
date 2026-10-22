# url-shortener: Agentic Software Engineering System — URL Shortener

Reference prototype: Java 21/Spring Boot URL shortener + Python/FastAPI stateful orchestrator + OpenAI API integration.

## Run
Prerequisites: Java 21+, Maven 3.9+, Python 3.11+, Docker.
1. `docker compose up -d postgres`
2. `cd services/url-shortener && mvn spring-boot:run`
3. If the issue - FATAL: invalid value for parameter "TimeZone": "Asia/Calcutta" occurred in above step then execute :
   `$env:JAVA_TOOL_OPTIONS="-Duser.timezone=Asia/Kolkata"`
   `mvn spring-boot:run`
4. In another terminal, configure and start the Python orchestrator:
   ```powershell
   cd services/orchestrator
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env
   # Edit .env and replace OPENAI_API_KEY with your own newly created API key.
   uvicorn app.main:app --reload --port 8000
   ```
   The `.env` file is loaded automatically. Do not commit it or share its API key.

## URL API
- `POST http://localhost:8080/api/urls` body `{"url":"https://example.com","customCode":"demo123","expiresAt":null}`
- `GET http://localhost:8080/demo123` redirects
- `GET http://localhost:8080/api/urls/demo123/analytics`
- Swagger: `http://localhost:8080/swagger-ui.html`

## Orchestrator
Start a greenfield workflow:
```
curl -X POST http://localhost:8000/workflows -H 'Content-Type: application/json' -d '{"scenario":"greenfield","requirement":"Build a URL shortener with custom aliases, expiration, analytics, and safe redirects."}'
```
Inspect `GET /workflows/{id}` and `GET /workflows/{id}/audit`. Release approval:
```
curl -X POST http://localhost:8000/workflows/WORKFLOW_ID/approve-release -H 'Content-Type: application/json' -d '{"approved_by":"reviewer@example.com","comment":"Reviewed artifacts and test evidence"}'
```

## Three scenarios
1. Greenfield: create a new shortener and generate requirements/design/implementation proposal/test plan/validation/docs.
2. Brownfield: expired aliases cause 500; propose 410 Gone and regression tests without changing valid redirects.
3. Ambiguous: “Make links safer.” asks clarification questions and blocks execution.

## Tests
Java: `cd services/url-shortener && mvn test`
Python: `cd services/orchestrator && pip install -r requirements.txt && pytest`

## Workflow graph and safety
`requirements -> design -> implementation -> validation -> documentation -> release_readiness`
`design -> test_plan -> validation`
Bounded retries, audit events, safe-stop, re-planning invalidation and explicit human approval are deterministic. LLM output is untrusted and never executed as shell commands or deployed automatically.

## Agentic implementation pipeline (added)
The orchestrator now supports a guarded two-step code workflow:
1. `POST /workflows/{id}/implementation/propose` asks the configured LLM for a JSON proposal containing complete Java source/test file contents. It does not write files.
2. Review every proposed file in the response. Then explicitly authorize application with `POST /workflows/{id}/implementation/apply-and-test` and a body such as `{"approved_by":"local-reviewer","comment":"Reviewed proposed source changes"}`.
3. The service applies only paths under the Java source, test, or resources folders, runs `mvn -B -ntp test` without a shell, and rolls back all touched files if tests fail or execution errors. Maven test output is returned in the response.

Configure `PROJECT_ROOT` to the repository root if the default cannot locate `services/url-shortener/pom.xml`. Set `MAVEN_TEST_TIMEOUT_SECONDS` to control the test timeout. The environment must have Maven and Java 21 installed. Do not expose these endpoints publicly without authentication and authorization.

## Durable orchestrator state
When `DATABASE_URL` is set (as in `.env.example`), the orchestrator creates and uses two PostgreSQL tables: `orchestrator_workflows` stores the complete workflow state as JSONB, and `orchestrator_audit_events` stores append-only audit events. Existing workflows are loaded at startup, so IDs remain usable after restarting the Python process. These tables are prefixed and separate from the Spring Boot application's tables. If `DATABASE_URL` is omitted, the orchestrator falls back to in-memory state for lightweight tests/development.

## Limitations and safety
The code-generation pipeline only changes allowlisted source/test/resource paths, does not run arbitrary generated shell commands, and does not deploy. Human review of the exact proposal is required before the apply endpoint is called. Production still needs authentication/RBAC, signed approvals, rate limiting, abuse detection, managed schema migrations, alerting, and stronger prompt-injection/data-governance controls. Do not expose these endpoints publicly without authentication and authorization.

## Java URL Shortener reliability updates

- Configure the canonical short-link origin with `SHORTENER_BASE_URL` (default `http://localhost:8080`). The service no longer builds links from the incoming `Host` header.
- Redirect click counts are incremented using one atomic PostgreSQL `UPDATE`, avoiding lost increments under concurrent traffic.
- Generated codes are inserted against the database unique constraint and retried up to 10 times if a collision occurs. A custom alias that loses a concurrent insert race returns HTTP 409.
- Liquibase manages the initial `short_urls` schema; Hibernate uses `ddl-auto: validate` instead of silently changing production schemas. Existing databases with a `short_urls` table are baselined by the initial change set and validated by Hibernate.
- Testcontainers integration coverage verifies concurrent click counting against PostgreSQL when Docker is available.

Example PowerShell configuration:

```powershell
$env:SHORTENER_BASE_URL = "http://localhost:8080"
cd services/url-shortener
mvn test
```
