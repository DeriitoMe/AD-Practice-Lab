-- 全部本地诊断练习任务，包含自动化自测。成功指程序完成。
-- 先按run_id归并开始/结束，再以有开始事件的任务为分母。
WITH runs AS (
  SELECT run_id,
    MAX(CASE WHEN event_name = 'diagnosis_started' THEN 1 ELSE 0 END) AS started,
    MAX(CASE WHEN event_name = 'diagnosis_finished' AND outcome = 'success' THEN 1 ELSE 0 END) AS success,
    MAX(CASE WHEN event_name = 'diagnosis_finished' AND outcome = 'failed' THEN 1 ELSE 0 END) AS failed
  FROM product_events
  WHERE event_name IN ('diagnosis_started', 'diagnosis_finished')
    AND source_kind = 'local_practice'
  GROUP BY run_id
)
SELECT COUNT(*) AS started_runs,
       COALESCE(SUM(success), 0) AS successful_runs,
       COALESCE(SUM(failed), 0) AS failed_runs,
       COALESCE(SUM(CASE WHEN success = 0 AND failed = 0 THEN 1 ELSE 0 END), 0) AS unfinished_runs,
       ROUND(100.0 * SUM(success) / NULLIF(COUNT(*), 0), 2) AS success_pct
FROM runs
WHERE started = 1;
