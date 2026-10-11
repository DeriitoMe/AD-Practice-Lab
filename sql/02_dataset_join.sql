-- 每份数据集单独汇总，核对导入行数；不把文件版本混成一次投放。
SELECT d.id, d.name, d.source_kind, d.row_count AS expected_rows,
       COUNT(a.date) AS actual_rows, ROUND(SUM(a.spend), 2) AS spend
FROM datasets AS d
LEFT JOIN ad_daily AS a ON a.dataset_id = d.id
GROUP BY d.id, d.name, d.source_kind, d.row_count
ORDER BY d.imported_at DESC, d.id;
