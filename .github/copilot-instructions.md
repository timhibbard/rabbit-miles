# GitHub Copilot Instructions for RabbitMiles

This repository contains the RabbitMiles application, which consists of a React SPA frontend and a Python-based AWS Lambda backend. Copilot should follow the conventions and constraints below when generating or modifying code.

---

## Backend Structure

All backend code lives under the `backend/` directory.

### Layout
- Each Lambda function has its own subdirectory:
  backend/
    auth_start/
      lambda_function.py
    auth_callback/
      lambda_function.py
    auth_disconnect/
      lambda_function.py
    me/
      lambda_function.py

- Each `lambda_function.py` file must expose a `handler(event, context)` function.
- Lambda handler configuration is always `lambda_function.handler`.

- All the lambdas follow the naming convention: `rabbitmiles-` + name

- Any time a new lambda is created, the github action and action secrets must be updated

### Runtime and Platform
- Runtime: Python (AWS Lambda managed runtime)
- Invocation: API Gateway HTTP API (v2 payload format)
- Deployment: Lambdas are deployed with Github actions

---

## Backend API Endpoints

The backend exposes these endpoints via API Gateway:

- GET /auth/start  
  Initiates Strava OAuth. Generates a random state value, sets the `rm_state` cookie, and redirects to Strava.

- GET /auth/callback  
  Validates OAuth state, exchanges Strava code for tokens, upserts the user record, creates a signed `rm_session` cookie, and redirects back to the frontend.

- GET /auth/disconnect  
  Clears Strava tokens in the database, clears the session cookie, and redirects to the frontend.

- GET /me  
  Reads and verifies the session cookie and returns authenticated user info.

Expected /me response shape:
{
  "athlete_id": 123456,
  "display_name": "Jane Doe"
}

---

## Authentication Model (Critical)

- Authentication is cookie-based, not token-based.
- Cookies are httpOnly, Secure, and SameSite=Lax.
- No authentication data is ever stored in:
  - localStorage
  - sessionStorage
  - query parameters
- Frontend requests must always include credentials.

### Cookies
- rm_state: short-lived OAuth CSRF token
- rm_session: signed, stateless session cookie

### APP_SECRET
- APP_SECRET is required to sign and verify session cookies.
- It must be stored as an environment variable in AWS Lambda.
- The same value must be used by:
  - auth_callback
  - auth_disconnect
  - me
- APP_SECRET must never be committed to GitHub.

---

## Database Access

- Database: Aurora PostgreSQL
- Access method: AWS RDS Data API
- Do not use Postgres drivers (psycopg2, etc.)
- Lambdas using Data API must not be placed in a VPC.

### Tables (already created)
- users
- trails
- activities
- computed_activity_stats

### Query Guidance
- Use boto3 rds-data client.
- Always use parameterized SQL.
- Avoid returning unsupported Postgres types (cast to text if needed).

---

## Secrets and Configuration

### Secrets
- Never commit secrets.
- Secrets live in:
  - AWS Lambda environment variables
  - AWS Secrets Manager

### Common Environment Variables
Copilot should assume these exist and reference them by name only:

- API_BASE_URL (for custom domain: https://api.rabbitmiles.com; for AWS default: include stage e.g. /prod)
- FRONTEND_URL (custom domain: https://rabbitmiles.com)
- APP_SECRET
- DB_CLUSTER_ARN
- DB_SECRET_ARN
- DB_NAME
- STRAVA_CLIENT_ID
- STRAVA_CLIENT_SECRET or STRAVA_SECRET_ARN

---

## Frontend Integration Rules

- Frontend is a React SPA hosted on GitHub Pages.
- Production frontend URL: https://rabbitmiles.com
- Production API base URL: https://api.rabbitmiles.com
- Frontend must:
  - Call /me on app load
  - Use cookie-based authentication
  - Handle connected, not-connected, and loading states explicitly
- Frontend must never handle access tokens or secrets.

---

## General Guidance for Copilot

- Prefer simple, explicit code.
- Do not introduce new authentication mechanisms.
- Do not introduce server-side sessions or token storage.
- Do not refactor working auth flows without explicit instruction.
- Keep Lambdas small and single-purpose.
- Assume this is a public repository.

---

## Mental Model

- Backend: stateless, signed cookies, RDS Data API
- Frontend: no secrets, cookie auth only
- Strava auth must be correct before activity or trail logic is added

If something is unclear, Copilot should ask for clarification instead of guessing.
