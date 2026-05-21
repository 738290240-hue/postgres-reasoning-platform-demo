"""initial reasoning schema

Revision ID: 20260521_0001
Revises:
Create Date: 2026-05-21
"""

from alembic import op


revision = "20260521_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS identity")
    op.execute("CREATE SCHEMA IF NOT EXISTS reasoning")
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute(
        """
        CREATE TYPE reasoning.rule_set_status AS ENUM ('draft', 'active', 'retired');
        """
    )

    op.execute(
        """
        CREATE TABLE identity.subject (
            subject_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            external_reference text NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE identity.subject_phi (
            subject_id uuid PRIMARY KEY REFERENCES identity.subject(subject_id) ON DELETE CASCADE,
            given_name text,
            family_name text,
            date_of_birth date,
            contact_email text,
            updated_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE reasoning.variable_definition (
            variable_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            code text NOT NULL UNIQUE,
            display_name text NOT NULL,
            value_type text NOT NULL CHECK (value_type IN ('numeric', 'boolean', 'coded')),
            unit text,
            is_sensitive boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE reasoning.rule_set (
            rule_set_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            version text NOT NULL UNIQUE,
            status reasoning.rule_set_status NOT NULL DEFAULT 'draft',
            description text NOT NULL,
            created_by text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            activated_at timestamptz,
            retired_at timestamptz,
            CHECK (
                (status = 'active' AND activated_at IS NOT NULL)
                OR status IN ('draft', 'retired')
            )
        );

        CREATE UNIQUE INDEX one_active_rule_set
            ON reasoning.rule_set ((status))
            WHERE status = 'active';

        CREATE TABLE reasoning.rule_weight (
            rule_weight_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            rule_set_id uuid NOT NULL REFERENCES reasoning.rule_set(rule_set_id) ON DELETE CASCADE,
            variable_id uuid NOT NULL REFERENCES reasoning.variable_definition(variable_id),
            weight numeric(18, 8) NOT NULL,
            lower_bound numeric(18, 8),
            upper_bound numeric(18, 8),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (rule_set_id, variable_id),
            CHECK (lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound)
        );

        CREATE TABLE reasoning.observation (
            observation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            subject_id uuid NOT NULL REFERENCES identity.subject(subject_id),
            variable_id uuid NOT NULL REFERENCES reasoning.variable_definition(variable_id),
            numeric_value numeric(18, 8),
            coded_value text,
            observed_at timestamptz NOT NULL,
            source_system text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (subject_id, variable_id, observed_at, source_system),
            CHECK (numeric_value IS NOT NULL OR coded_value IS NOT NULL)
        );

        CREATE INDEX observation_subject_variable_time
            ON reasoning.observation (subject_id, variable_id, observed_at DESC);

        CREATE TABLE reasoning.score_run (
            score_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            subject_id uuid NOT NULL REFERENCES identity.subject(subject_id),
            rule_set_id uuid NOT NULL REFERENCES reasoning.rule_set(rule_set_id),
            input_fingerprint text NOT NULL,
            total_score numeric(18, 8) NOT NULL,
            run_reason text NOT NULL,
            run_by text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (subject_id, rule_set_id, input_fingerprint)
        );

        CREATE TABLE reasoning.score_contribution (
            score_run_id uuid NOT NULL REFERENCES reasoning.score_run(score_run_id) ON DELETE CASCADE,
            variable_id uuid NOT NULL REFERENCES reasoning.variable_definition(variable_id),
            observed_value numeric(18, 8) NOT NULL,
            weight numeric(18, 8) NOT NULL,
            contribution numeric(18, 8) NOT NULL,
            PRIMARY KEY (score_run_id, variable_id)
        );

        CREATE TABLE audit.change_log (
            audit_id bigserial PRIMARY KEY,
            schema_name text NOT NULL,
            table_name text NOT NULL,
            row_pk jsonb NOT NULL,
            action text NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
            actor text NOT NULL DEFAULT current_user,
            reason text NOT NULL DEFAULT COALESCE(current_setting('app.audit_reason', true), 'not provided'),
            before_row jsonb,
            after_row jsonb,
            changed_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX change_log_table_time
            ON audit.change_log (schema_name, table_name, changed_at DESC);

        CREATE INDEX change_log_row_pk
            ON audit.change_log USING gin (row_pk);
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit.capture_change() RETURNS trigger AS $$
        DECLARE
            row_data jsonb;
            pk jsonb;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                row_data = to_jsonb(OLD);
                pk = jsonb_build_object(
                    'id',
                    COALESCE(
                        row_data ->> 'rule_set_id',
                        row_data ->> 'rule_weight_id',
                        row_data ->> 'variable_id',
                        row_data ->> 'score_run_id'
                    )
                );
                INSERT INTO audit.change_log(schema_name, table_name, row_pk, action, before_row)
                VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, pk, TG_OP, row_data);
                RETURN OLD;
            END IF;

            row_data = to_jsonb(NEW);
            pk = jsonb_build_object(
                'id',
                COALESCE(
                    row_data ->> 'rule_set_id',
                    row_data ->> 'rule_weight_id',
                    row_data ->> 'variable_id',
                    row_data ->> 'score_run_id'
                )
            );
            INSERT INTO audit.change_log(schema_name, table_name, row_pk, action, before_row, after_row)
            VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, pk, TG_OP, CASE WHEN TG_OP = 'UPDATE' THEN to_jsonb(OLD) END, row_data);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER audit_rule_set
            AFTER INSERT OR UPDATE OR DELETE ON reasoning.rule_set
            FOR EACH ROW EXECUTE FUNCTION audit.capture_change();

        CREATE TRIGGER audit_rule_weight
            AFTER INSERT OR UPDATE OR DELETE ON reasoning.rule_weight
            FOR EACH ROW EXECUTE FUNCTION audit.capture_change();

        CREATE TRIGGER audit_variable_definition
            AFTER INSERT OR UPDATE OR DELETE ON reasoning.variable_definition
            FOR EACH ROW EXECUTE FUNCTION audit.capture_change();

        CREATE TRIGGER audit_score_run
            AFTER INSERT OR UPDATE OR DELETE ON reasoning.score_run
            FOR EACH ROW EXECUTE FUNCTION audit.capture_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS audit CASCADE")
    op.execute("DROP SCHEMA IF EXISTS reasoning CASCADE")
    op.execute("DROP SCHEMA IF EXISTS identity CASCADE")
