CREATE OR REPLACE FUNCTION increment_connection(target_id bigint)
RETURNS void AS $$
BEGIN
    UPDATE profiles
    SET nb_connection = COALESCE(nb_connection, 0) + 1
    WHERE id_strava = target_id;
END;
$$ LANGUAGE plpgsql;