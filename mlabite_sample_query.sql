-- SQLite
SELECT e.name AS measurand, o.name AS observation, mt.name AS metric, m.value, m.unit
FROM measure m
JOIN observation o ON o.id = m.observation_id
JOIN metric mt     ON mt.id = m.metric_id
JOIN element e     ON e.id = m.measurand_id
ORDER BY observation, metric
LIMIT 50;

-- Exact CSV-like wide view
WITH base AS (
  SELECT
    REPLACE(e.name, 'global_eval__', '') AS language,
    mt.name                              AS metric_name,
    CAST(m.value AS REAL)                AS value
  FROM measure m
  JOIN metric      mt ON mt.id = m.metric_id
  JOIN observation  o ON o.id = m.observation_id
  JOIN dataset      d ON d.id = o.dataset_2_id
  JOIN element      e ON e.id = d.id
  WHERE o.name LIKE 'obs__%__20250704160636_global_evaluation%'
)
SELECT
  language,
  MAX(CASE WHEN metric_name='avg_answer_relevancy'      THEN value END) AS avg_answer_relevancy,
  MAX(CASE WHEN metric_name='avg_context_precision'     THEN value END) AS avg_context_precision,
  MAX(CASE WHEN metric_name='avg_context_recall'        THEN value END) AS avg_context_recall,
  MAX(CASE WHEN metric_name='avg_faithfulness'          THEN value END) AS avg_faithfulness,
  MAX(CASE WHEN metric_name='avg_noise_sensitivity'     THEN value END) AS avg_noise_sensitivity,
  MAX(CASE WHEN metric_name='count_answer_relevancy'    THEN value END) AS count_answer_relevancy,
  MAX(CASE WHEN metric_name='count_context_precision'   THEN value END) AS count_context_precision,
  MAX(CASE WHEN metric_name='count_context_recall'      THEN value END) AS count_context_recall,
  MAX(CASE WHEN metric_name='count_faithfulness'        THEN value END) AS count_faithfulness,
  MAX(CASE WHEN metric_name='count_noise_sensitivity'   THEN value END) AS count_noise_sensitivity,
  MAX(CASE WHEN metric_name='total_rows_lang'           THEN value END) AS total_rows_lang,
  MAX(CASE WHEN metric_name='unique_strategies_lang'    THEN value END) AS unique_strategies_lang
FROM base
GROUP BY language
ORDER BY language;

