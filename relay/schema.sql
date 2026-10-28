CREATE EXTENSION IF NOT EXISTS vector;
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='relay_app') THEN
  CREATE ROLE relay_app LOGIN PASSWORD 'relay_app' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
 END IF;
END $$;
CREATE TABLE IF NOT EXISTS runs (
 id text PRIMARY KEY, started_at timestamptz NOT NULL DEFAULT now(), tokens_reserved bigint NOT NULL DEFAULT 0,
 token_limit bigint NOT NULL
);
CREATE TABLE IF NOT EXISTS kb (
 tenant text NOT NULL, id text NOT NULL, title text NOT NULL, body text NOT NULL,
 internal boolean NOT NULL, embedding vector(768) NOT NULL, PRIMARY KEY(tenant,id)
);
CREATE TABLE IF NOT EXISTS tickets (
 tenant text NOT NULL, id text NOT NULL, payload jsonb NOT NULL,
 status text NOT NULL DEFAULT 'queued', revision int NOT NULL DEFAULT 0,
 tokens_reserved bigint NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant,id)
);
CREATE TABLE IF NOT EXISTS jobs (
 id bigserial PRIMARY KEY, tenant text NOT NULL, ticket_id text NOT NULL, run_id text NOT NULL REFERENCES runs(id),
 state text NOT NULL DEFAULT 'ready', attempts int NOT NULL DEFAULT 0, lease_token text,
 lease_until timestamptz, available_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant,ticket_id), FOREIGN KEY(tenant,ticket_id) REFERENCES tickets(tenant,id)
);
CREATE TABLE IF NOT EXISTS decisions (
 tenant text NOT NULL, ticket_id text NOT NULL, record jsonb NOT NULL, PRIMARY KEY(tenant,ticket_id)
);
CREATE TABLE IF NOT EXISTS approvals (
 tenant text NOT NULL, ticket_id text NOT NULL, revision int NOT NULL, text text NOT NULL,
 kb_refs jsonb NOT NULL, state text NOT NULL DEFAULT 'pending', feedback text,
 created_at timestamptz NOT NULL DEFAULT now(), decided_at timestamptz, decided_by text,
 PRIMARY KEY(tenant,ticket_id,revision)
);
CREATE TABLE IF NOT EXISTS outbox (
 tenant text NOT NULL, ticket_id text NOT NULL, text text NOT NULL,
 approved_by text NOT NULL, approved_at timestamptz NOT NULL DEFAULT now(), idempotency_key text NOT NULL UNIQUE,
 PRIMARY KEY(tenant,ticket_id)
);
CREATE TABLE IF NOT EXISTS cases (
 tenant text NOT NULL, ticket_id text NOT NULL, owner text NOT NULL, severity text NOT NULL,
 reason text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant,ticket_id)
);
CREATE TABLE IF NOT EXISTS audit (
 id bigserial PRIMARY KEY, tenant text NOT NULL, ticket_id text, actor text NOT NULL,
 event text NOT NULL, reason text NOT NULL, at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS model_calls (
 id bigserial PRIMARY KEY, tenant text NOT NULL, ticket_id text, run_id text NOT NULL,
 task text NOT NULL, model text NOT NULL, tokens_in int NOT NULL, tokens_out int NOT NULL,
 latency_ms int NOT NULL, error text, at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS rejected_inputs (
 id bigserial PRIMARY KEY, run_id text NOT NULL, line_number int NOT NULL,
 reason text NOT NULL, at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE ON runs TO relay_app;
GRANT SELECT, INSERT ON rejected_inputs TO relay_app;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['kb','tickets','jobs','decisions','approvals','outbox','cases','audit','model_calls'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('DROP POLICY IF EXISTS tenant_boundary ON %I',t);
  EXECUTE format('CREATE POLICY tenant_boundary ON %I USING (tenant = NULLIF(current_setting(''app.tenant_id'',true),'''')) WITH CHECK (tenant = NULLIF(current_setting(''app.tenant_id'',true),''''))',t);
  EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I TO relay_app',t);
 END LOOP;
END $$;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO relay_app;
