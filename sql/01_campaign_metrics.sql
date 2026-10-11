-- 只分析最新导入的数据集；截至2026-10-10的完整7天归因窗。
SELECT campaign_id, campaign_name,
       SUM(impressions) AS impressions, SUM(clicks) AS clicks,
       SUM(purchases) AS purchases, ROUND(SUM(spend), 2) AS spend,
       ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 4) AS ctr_pct,
       ROUND(100.0 * SUM(purchases) / NULLIF(SUM(clicks), 0), 4) AS cvr_pct,
       ROUND(SUM(spend) / NULLIF(SUM(purchases), 0), 2) AS cpa,
       ROUND(SUM(revenue) / NULLIF(SUM(spend), 0), 4) AS roas,
       ROUND(100.0 * (SUM(revenue) - SUM(variable_cost) - SUM(spend))
             / NULLIF(SUM(variable_cost) + SUM(spend), 0), 4) AS roi_pct
FROM ad_daily
WHERE dataset_id = (SELECT id FROM datasets ORDER BY imported_at DESC, id LIMIT 1)
  AND date < date('2026-10-10', '-7 days')
GROUP BY campaign_id, campaign_name
ORDER BY cpa DESC;
