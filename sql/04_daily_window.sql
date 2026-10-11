-- LAG读取排序后的上一条日期记录；若日期缺失，不能称为严格的前一天。
WITH daily AS (
  SELECT date, SUM(spend) AS spend
  FROM ad_daily
  WHERE dataset_id = (SELECT id FROM datasets ORDER BY imported_at DESC, id LIMIT 1)
    AND date < date('2026-10-10', '-7 days')
  GROUP BY date
)
SELECT date, ROUND(spend, 2) AS spend,
       LAG(date) OVER (ORDER BY date) AS previous_record_date,
       ROUND(LAG(spend) OVER (ORDER BY date), 2) AS previous_spend,
       ROUND(spend - LAG(spend) OVER (ORDER BY date), 2) AS absolute_change
FROM daily
ORDER BY date;
