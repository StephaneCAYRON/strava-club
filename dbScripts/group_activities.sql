DROP VIEW group_activities cascade

CREATE OR REPLACE VIEW group_activities AS
SELECT 
    g.name AS group_name,
    g.id AS  group_id,
    a.*,
    p.firstname,
    p.lastname,
    p.avatar_url
   FROM group_members gm
     JOIN groups g ON gm.group_id = g.id
     JOIN activities a ON gm.athlete_id = a.id_strava
     JOIN profiles p ON a.id_strava = p.id_strava
  WHERE gm.status = 'approved'::text;

CREATE OR REPLACE VIEW group_years AS
SELECT DISTINCT
    group_id,
    EXTRACT(YEAR FROM start_date)::INTEGER AS year
FROM group_activities
WHERE start_date IS NOT NULL;