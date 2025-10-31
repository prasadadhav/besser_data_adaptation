
-- Prevent duplicate metric rows
CREATE UNIQUE INDEX IF NOT EXISTS ux_metric_type_name ON metric(type_spec, name);
