-- SQLite
SELECT COUNT(*) FROM observation;  -- expect 53
SELECT COUNT(*) FROM metric;       -- expect 30
SELECT COUNT(*) FROM measure;      -- expect ~1590 after load

-- spot check joins
SELECT m.name, o.name AS observation_name, me.value
FROM measure me
JOIN metric m ON m.id = me.metric_id
JOIN observation o ON o.id = me.observation_id
ORDER BY o.id, m.id
LIMIT 50;
