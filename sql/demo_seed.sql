BEGIN;

SET LOCAL app.audit_reason = 'seed demo data for portfolio review';

INSERT INTO identity.subject (external_reference)
VALUES ('demo-clinic:subject-001')
ON CONFLICT (external_reference) DO NOTHING;

INSERT INTO identity.subject_phi (subject_id, given_name, family_name, date_of_birth, contact_email)
SELECT subject_id, 'Ada', 'Lovelace', DATE '1984-12-10', 'ada@example.test'
FROM identity.subject
WHERE external_reference = 'demo-clinic:subject-001'
ON CONFLICT (subject_id) DO UPDATE SET
    given_name = EXCLUDED.given_name,
    family_name = EXCLUDED.family_name,
    date_of_birth = EXCLUDED.date_of_birth,
    contact_email = EXCLUDED.contact_email,
    updated_at = now();

INSERT INTO reasoning.variable_definition (code, display_name, value_type, unit, is_sensitive)
VALUES
    ('age_risk', 'Age risk factor', 'numeric', NULL, false),
    ('lab_signal', 'Lab-derived risk signal', 'numeric', 'score', false),
    ('history_flag', 'History flag', 'numeric', NULL, false)
ON CONFLICT (code) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    value_type = EXCLUDED.value_type,
    unit = EXCLUDED.unit,
    is_sensitive = EXCLUDED.is_sensitive;

INSERT INTO reasoning.rule_set (version, status, description, created_by, activated_at)
VALUES (
    '2026.05.0',
    'active',
    'Demo active scoring configuration with deterministic decimal weights.',
    'portfolio-demo',
    now()
)
ON CONFLICT (version) DO UPDATE SET
    status = EXCLUDED.status,
    description = EXCLUDED.description,
    activated_at = EXCLUDED.activated_at;

INSERT INTO reasoning.rule_weight (rule_set_id, variable_id, weight, lower_bound, upper_bound)
SELECT rs.rule_set_id, vd.variable_id, weights.weight, weights.lower_bound, weights.upper_bound
FROM reasoning.rule_set rs
JOIN (
    VALUES
        ('age_risk', 1.50000000::numeric, 0.00000000::numeric, 10.00000000::numeric),
        ('lab_signal', 2.25000000::numeric, 0.00000000::numeric, 10.00000000::numeric),
        ('history_flag', -0.50000000::numeric, 0.00000000::numeric, 1.00000000::numeric)
) AS weights(code, weight, lower_bound, upper_bound) ON true
JOIN reasoning.variable_definition vd ON vd.code = weights.code
WHERE rs.version = '2026.05.0'
ON CONFLICT (rule_set_id, variable_id) DO UPDATE SET
    weight = EXCLUDED.weight,
    lower_bound = EXCLUDED.lower_bound,
    upper_bound = EXCLUDED.upper_bound;

INSERT INTO reasoning.observation (subject_id, variable_id, numeric_value, observed_at, source_system)
SELECT s.subject_id, vd.variable_id, observations.numeric_value, observations.observed_at, 'demo-seed'
FROM identity.subject s
JOIN (
    VALUES
        ('age_risk', 2.00000000::numeric, TIMESTAMPTZ '2026-05-21 08:00:00+00'),
        ('lab_signal', 3.20000000::numeric, TIMESTAMPTZ '2026-05-21 08:00:00+00'),
        ('history_flag', 1.00000000::numeric, TIMESTAMPTZ '2026-05-21 08:00:00+00')
) AS observations(code, numeric_value, observed_at) ON true
JOIN reasoning.variable_definition vd ON vd.code = observations.code
WHERE s.external_reference = 'demo-clinic:subject-001'
ON CONFLICT (subject_id, variable_id, observed_at, source_system) DO UPDATE SET
    numeric_value = EXCLUDED.numeric_value;

COMMIT;
