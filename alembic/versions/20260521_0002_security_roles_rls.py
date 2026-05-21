"""security roles and row-level policies

Revision ID: 20260521_0002
Revises: 20260521_0001
Create Date: 2026-05-21
"""

from alembic import op


revision = "20260521_0002"
down_revision = "20260521_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'reasoning_app') THEN
                CREATE ROLE reasoning_app NOLOGIN;
            END IF;

            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'reasoning_admin') THEN
                CREATE ROLE reasoning_admin NOLOGIN;
            END IF;

            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'phi_reader') THEN
                CREATE ROLE phi_reader NOLOGIN;
            END IF;

            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'audit_reader') THEN
                CREATE ROLE audit_reader NOLOGIN;
            END IF;
        END
        $$;

        REVOKE ALL ON SCHEMA identity, reasoning, audit FROM PUBLIC;
        GRANT USAGE ON SCHEMA reasoning TO reasoning_app, reasoning_admin;
        GRANT USAGE ON SCHEMA identity TO reasoning_app, reasoning_admin, phi_reader;
        GRANT USAGE ON SCHEMA audit TO audit_reader, reasoning_admin;

        GRANT SELECT ON identity.subject TO reasoning_app, reasoning_admin, phi_reader;
        GRANT SELECT ON identity.subject_phi TO phi_reader;
        GRANT SELECT, INSERT, UPDATE ON identity.subject TO reasoning_admin;
        GRANT SELECT, INSERT, UPDATE ON identity.subject_phi TO reasoning_admin;

        GRANT SELECT ON reasoning.variable_definition TO reasoning_app;
        GRANT SELECT ON reasoning.rule_set TO reasoning_app;
        GRANT SELECT ON reasoning.rule_weight TO reasoning_app;
        GRANT SELECT ON reasoning.observation TO reasoning_app;
        GRANT SELECT, INSERT, UPDATE ON reasoning.score_run TO reasoning_app;
        GRANT SELECT, INSERT, UPDATE ON reasoning.score_contribution TO reasoning_app;

        GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA reasoning TO reasoning_admin;
        GRANT SELECT ON audit.change_log TO audit_reader, reasoning_admin;
        GRANT USAGE, SELECT ON SEQUENCE audit.change_log_audit_id_seq TO reasoning_admin;
        GRANT phi_reader TO reasoning_admin;

        ALTER TABLE identity.subject ENABLE ROW LEVEL SECURITY;
        ALTER TABLE identity.subject_phi ENABLE ROW LEVEL SECURITY;
        ALTER TABLE reasoning.observation ENABLE ROW LEVEL SECURITY;
        ALTER TABLE reasoning.score_run ENABLE ROW LEVEL SECURITY;
        ALTER TABLE reasoning.score_contribution ENABLE ROW LEVEL SECURITY;

        CREATE POLICY subject_tenant_scope ON identity.subject
            USING (
                current_setting('app.tenant_id', true) IS NULL
                OR external_reference LIKE current_setting('app.tenant_id', true) || ':%'
            );

        CREATE POLICY subject_phi_privileged_read ON identity.subject_phi
            FOR SELECT
            USING (pg_has_role(current_user, 'phi_reader', 'member'));

        CREATE POLICY observation_subject_scope ON reasoning.observation
            USING (
                EXISTS (
                    SELECT 1
                    FROM identity.subject s
                    WHERE
                        s.subject_id = observation.subject_id
                        AND (
                            current_setting('app.tenant_id', true) IS NULL
                            OR s.external_reference LIKE current_setting('app.tenant_id', true) || ':%'
                        )
                )
            );

        CREATE POLICY score_run_subject_scope ON reasoning.score_run
            USING (
                EXISTS (
                    SELECT 1
                    FROM identity.subject s
                    WHERE
                        s.subject_id = score_run.subject_id
                        AND (
                            current_setting('app.tenant_id', true) IS NULL
                            OR s.external_reference LIKE current_setting('app.tenant_id', true) || ':%'
                        )
                )
            );

        CREATE POLICY score_run_insert_subject_scope ON reasoning.score_run
            FOR INSERT
            WITH CHECK (
                EXISTS (
                    SELECT 1
                    FROM identity.subject s
                    WHERE
                        s.subject_id = score_run.subject_id
                        AND (
                            current_setting('app.tenant_id', true) IS NULL
                            OR s.external_reference LIKE current_setting('app.tenant_id', true) || ':%'
                        )
                )
            );

        CREATE POLICY score_contribution_read_via_score_run ON reasoning.score_contribution
            USING (
                EXISTS (
                    SELECT 1
                    FROM reasoning.score_run sr
                    JOIN identity.subject s ON s.subject_id = sr.subject_id
                    WHERE
                        sr.score_run_id = score_contribution.score_run_id
                        AND (
                            current_setting('app.tenant_id', true) IS NULL
                            OR s.external_reference LIKE current_setting('app.tenant_id', true) || ':%'
                        )
                )
            );

        CREATE POLICY score_contribution_insert_via_score_run ON reasoning.score_contribution
            FOR INSERT
            WITH CHECK (
                EXISTS (
                    SELECT 1
                    FROM reasoning.score_run sr
                    JOIN identity.subject s ON s.subject_id = sr.subject_id
                    WHERE
                        sr.score_run_id = score_contribution.score_run_id
                        AND (
                            current_setting('app.tenant_id', true) IS NULL
                            OR s.external_reference LIKE current_setting('app.tenant_id', true) || ':%'
                        )
                )
            );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS score_contribution_read_via_score_run ON reasoning.score_contribution;
        DROP POLICY IF EXISTS score_contribution_insert_via_score_run ON reasoning.score_contribution;
        DROP POLICY IF EXISTS score_run_subject_scope ON reasoning.score_run;
        DROP POLICY IF EXISTS score_run_insert_subject_scope ON reasoning.score_run;
        DROP POLICY IF EXISTS observation_subject_scope ON reasoning.observation;
        DROP POLICY IF EXISTS subject_phi_privileged_read ON identity.subject_phi;
        DROP POLICY IF EXISTS subject_tenant_scope ON identity.subject;

        ALTER TABLE reasoning.score_contribution DISABLE ROW LEVEL SECURITY;
        ALTER TABLE reasoning.score_run DISABLE ROW LEVEL SECURITY;
        ALTER TABLE reasoning.observation DISABLE ROW LEVEL SECURITY;
        ALTER TABLE identity.subject_phi DISABLE ROW LEVEL SECURITY;
        ALTER TABLE identity.subject DISABLE ROW LEVEL SECURITY;

        REVOKE ALL ON SCHEMA identity, reasoning, audit FROM reasoning_app, reasoning_admin, phi_reader, audit_reader;
        """
    )
