## ADDED Requirements

### Requirement: Main-site registration entry

The system SHALL expose registration only on the main site host `lxzxai.com` (not on tenant subdomains).

#### Scenario: Registration on main site

- **WHEN** a user opens `https://lxzxai.com/register` and submits valid registration data
- **THEN** the system accepts the registration request

#### Scenario: Registration rejected on tenant host

- **WHEN** a user submits a registration request to `{subdomain}.lxzxai.com`
- **THEN** the system rejects the request and does not create a tenant

### Requirement: Subdomain validation

The system SHALL validate `subdomain` before creating any tenant record. Validation MUST enforce: lowercase letters, digits, and hyphens only; length 3–32; MUST NOT start or end with `-`; MUST NOT be a reserved word (`www`, `admin`, `api`, `app`, `mail`, `static`, `cdn`, `lxzxai`); MUST be globally unique.

#### Scenario: Subdomain normalized to lowercase (F01-T02)

- **WHEN** a user registers with subdomain `Acme-Co` and all other fields are valid
- **THEN** the stored `tenants.subdomain` is `acme-co`

#### Scenario: Subdomain too short (F01-T03)

- **WHEN** a user registers with subdomain `ab`
- **THEN** the system returns a 4xx error and no `tenants` row is created

#### Scenario: Reserved subdomain rejected (F01-T04)

- **WHEN** a user registers with subdomain `admin`
- **THEN** the system returns a 4xx error and no `tenants` row is created

#### Scenario: Subdomain already taken (F01-T05)

- **WHEN** subdomain `acme` is already registered and another user registers with the same subdomain
- **THEN** the system returns a 4xx error indicating the subdomain is taken and no new `tenants` row is created

#### Scenario: Concurrent subdomain registration (F01-T08)

- **WHEN** two registration requests for the same unused subdomain arrive concurrently
- **THEN** exactly one succeeds and one fails; the database contains exactly one `tenants` row for that subdomain

### Requirement: Email uniqueness

The system SHALL treat email as globally unique (case-insensitive). Email MUST be stored in lowercase.

#### Scenario: Duplicate email rejected (F01-T06)

- **WHEN** an email is already registered and a new registration uses the same email (any casing)
- **THEN** the system returns a 4xx error and no new `tenants` row is created even if the requested subdomain is available

### Requirement: Password handling

The system SHALL require passwords of at least 8 characters. Passwords MUST be stored as irreversible hashes (argon2 or bcrypt). Plaintext passwords MUST NOT be persisted.

#### Scenario: Password hashed on registration

- **WHEN** a user registers with a valid password
- **THEN** only `password_hash` is stored in `users.password_hash`

### Requirement: Atomic tenant creation

The system SHALL create `users`, `tenants`, and `tenant_members` in a single database transaction on successful registration. On any failure, no partial records MUST remain.

#### Scenario: Successful registration creates all entities (F01-T01)

- **WHEN** a user registers with unused email and subdomain
- **THEN** the system returns 201; one `users` row, one `tenants` row, and one `tenant_members` row with `role=owner` exist; the response or follow-up flow exposes the registered subdomain

### Requirement: Post-registration redirect and session

The system SHALL issue a session cookie with `Domain=.lxzxai.com` on successful registration and redirect the browser to `https://{subdomain}.lxzxai.com/admin`. Cookie attributes MUST align with F02 (`Secure`, `HttpOnly`, `SameSite=Lax` or equivalent testable configuration).

#### Scenario: Redirect and cookie on success (F01-T07)

- **WHEN** a user completes a valid registration and follows the redirect
- **THEN** the `Location` header points to `https://{subdomain}.lxzxai.com/admin` and `Set-Cookie` includes `Domain=.lxzxai.com`

### Requirement: Database schema for registration

The system SHALL persist registration data in PostgreSQL schema `rag_service` using tables `users`, `tenants`, and `tenant_members` as defined in F01 data model. All tables MUST include `create_at` and `update_at` (`timestamp`, `DEFAULT now()`). `update_at` MUST be maintained by trigger `tr_{table}_lmt` calling `f_common_update_at()`.

#### Scenario: Schema constraints enforce data integrity

- **WHEN** migration is applied from F01 DDL
- **THEN** `users.email` is UNIQUE; `tenants.subdomain` is UNIQUE with format CHECK; `tenant_members` has UNIQUE (`tenant_id`, `user_id`) and `role` CHECK for `owner`
