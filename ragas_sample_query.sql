-- SQLite
-- Measures inserted for the 3 language observations
SELECT o.name AS observation, e.name AS measurand, mt.name AS metric, m.value, m.unit
FROM measure m
JOIN observation o ON o.id = m.observation_id
JOIN element e     ON e.id = m.measurand_id
JOIN metric  mt    ON mt.id = m.metric_id
WHERE o.name IN ('Obs de','Obs en','Obs fr')
ORDER BY o.name, mt.name
LIMIT 30;
