-- SQLite
WITH lang_measures AS (
  SELECT
    REPLACE(e.name, 'Lang=', '')            AS language,
    mt.name                                  AS metric_name,
    m.unit                                   AS unit,
    CAST(m.value AS REAL)                    AS value
  FROM measure m
  JOIN metric      mt ON mt.id = m.metric_id
  JOIN observation  o ON o.id = m.observation_id
  JOIN element      e ON e.id = m.measurand_id
  -- Optional: uncomment to only include the imported obs
  -- WHERE o.name IN ('Obs de','Obs en','Obs fr')
)
SELECT
  language,
  MAX(CASE WHEN metric_name='total_rows'              AND unit='count' THEN value END) AS total_rows_lang,
  MAX(CASE WHEN metric_name='unique_strategies'       AND unit='count' THEN value END) AS unique_strategies_lang,

  AVG(CASE WHEN metric_name='answer_relevancy'        AND unit='ratio' THEN value END) AS avg_answer_relevancy,
  AVG(CASE WHEN metric_name='context_precision'       AND unit='ratio' THEN value END) AS avg_context_precision,
  AVG(CASE WHEN metric_name='context_recall'          AND unit='ratio' THEN value END) AS avg_context_recall,
  AVG(CASE WHEN metric_name='faithfulness'            AND unit='ratio' THEN value END) AS avg_faithfulness,
  AVG(CASE WHEN metric_name='noise_sensitivity'       AND unit='ratio' THEN value END) AS avg_noise_sensitivity,

  SUM(CASE WHEN metric_name='answer_relevancy_count'  AND unit='count' THEN value END) AS count_answer_relevancy,
  SUM(CASE WHEN metric_name='context_precision_count' AND unit='count' THEN value END) AS count_context_precision,
  SUM(CASE WHEN metric_name='context_recall_count'    AND unit='count' THEN value END) AS count_context_recall,
  SUM(CASE WHEN metric_name='faithfulness_count'      AND unit='count' THEN value END) AS count_faithfulness,
  SUM(CASE WHEN metric_name='noise_sensitivity_count' AND unit='count' THEN value END) AS count_noise_sensitivity
FROM lang_measures
GROUP BY language
ORDER BY language;
