-- SQLite
SELECT m.id, m.name, m.description, CAST(me.value AS REAL) AS value
FROM metric AS m
JOIN measure AS me
  ON me.metric_id = m.id
-- WHERE m.name = 'A1 Total'
WHERE me.value > 90;
