-- 固定样例的两周：2026-09-19至09-25 / 09-26至10-02。
-- 这是练习查询；替换数据后需重新核对日期连续、完整与可比性。
WITH grouped AS (
  SELECT campaign_id,
    SUM(CASE WHEN date < '2026-09-26' THEN clicks ELSE 0 END) AS old_clicks,
    SUM(CASE WHEN date < '2026-09-26' THEN impressions ELSE 0 END) AS old_impressions,
    SUM(CASE WHEN date >= '2026-09-26' THEN clicks ELSE 0 END) AS new_clicks,
    SUM(CASE WHEN date >= '2026-09-26' THEN impressions ELSE 0 END) AS new_impressions
  FROM ad_daily
  WHERE dataset_id = (SELECT id FROM datasets ORDER BY imported_at DESC, id LIMIT 1)
    AND date BETWEEN '2026-09-19' AND '2026-10-02'
  GROUP BY campaign_id
), ratios AS (
  SELECT campaign_id,
    1.0 * old_clicks / NULLIF(old_impressions, 0) AS old_ctr,
    1.0 * new_clicks / NULLIF(new_impressions, 0) AS new_ctr
  FROM grouped
)
SELECT campaign_id,
       ROUND(100 * old_ctr, 4) AS old_ctr_pct,
       ROUND(100 * new_ctr, 4) AS new_ctr_pct,
       ROUND(100 * (new_ctr - old_ctr), 4) AS percentage_point_change,
       ROUND(100 * (new_ctr / NULLIF(old_ctr, 0) - 1), 2) AS relative_change_pct
FROM ratios
ORDER BY campaign_id;
