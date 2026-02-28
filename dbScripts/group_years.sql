CREATE OR REPLACE VIEW group_years AS
SELECT DISTINCT
    group_id,
    EXTRACT(YEAR FROM start_date)::INTEGER AS year
FROM group_activities
WHERE start_date IS NOT NULL;