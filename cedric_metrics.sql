-- SQLite
SELECT id, name, description
FROM metric
GROUP BY 1,2
ORDER BY id