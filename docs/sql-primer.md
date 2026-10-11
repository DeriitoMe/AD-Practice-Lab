# 从Excel到SQL：在这个项目里学

SQL是向数据库描述“我要哪些记录、怎样组合和汇总”的语言。SQLite是本项目保存数据并执行SQL的数据库软件；两者不是同一概念。你不必先学会架设数据库服务器。

## 先认识三张表

- datasets：每份导入文件的身份，一行一个数据集。
- ad_daily：广告日明细，一行是某数据集、日期、计划和素材。
- product_events：本地软件操作记录，一行一个事件。

Excel可以类比工作表，但数据库有字段类型、主键和关联规则。不要把SQL等同于写公式；它还控制筛选、关联、分组及结果粒度。

## 一条查询怎样读

~~~sql
SELECT campaign_id,
       SUM(clicks) AS clicks,
       SUM(impressions) AS impressions,
       100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0) AS ctr_pct
FROM ad_daily
WHERE dataset_id = (SELECT id FROM datasets ORDER BY imported_at DESC, id LIMIT 1)
  AND date < date('2026-10-10', '-7 days')
GROUP BY campaign_id
ORDER BY ctr_pct DESC;
~~~

FROM说明从哪张表取数；WHERE保留某份数据和成熟日期；GROUP BY将同计划放一组；SUM分别合计点击、曝光；SELECT列出最终结果；AS给结果列起名；ORDER BY排序。

SQL写法的顺序与理解数据处理的顺序不同。学习时按“取表→筛选→分组→计算→排序”理解即可。

100.0确保采用小数除法；CTR这里乘100，返回的是百分数数值1.2，表示1.2%。NULLIF把0分母变成NULL，表示不可计算，不代表0%。

## Excel经验如何迁移

| Excel常用操作 | SQL对应思路 |
|---|---|
| 筛选某计划 | WHERE campaign_id='B' |
| 透视表按计划求和 | GROUP BY campaign_id，SUM(spend) |
| 条件计数 | SUM(CASE WHEN 条件 THEN 1 ELSE 0 END) |
| 查找另一个表的信息 | JOIN，并核对一对一/一对多关系 |
| 临时辅助表 | WITH定义查询中的中间结果 |
| 与上一行比较 | LAG(...) OVER(ORDER BY date) |
| 排名/每组第一条 | ROW_NUMBER() OVER(PARTITION BY ... ORDER BY ...) |

JOIN不是随便拼表：datasets.id唯一，连到多条ad_daily明细是正常的一对多。如果右表也有多个同ID，可能把同一广告记录复制多次，花费会被放大。先确定两边的粒度和唯一键。

COUNT(*)计算行数；COUNT(字段)只计算非NULL；COUNT(DISTINCT 字段)去重计数。它们都不能自动理解“真实用户”或“真实客户”，口径由字段含义决定。

## 本地练习

按sql目录编号执行，也可粘贴到网页编辑器：

1. 01_campaign_metrics.sql：按计划汇总CTR、CVR、CPA、ROAS、ROI。
2. 02_dataset_join.sql：关联数据集信息，核对每份文件的实际行数。
3. 03_diagnosis_events.sql：按run_id统计诊断开始、成功、失败、未结束。
4. 04_daily_window.sql：按天合计花费并比较上一天。
5. 05_period_compare.sql：把两周CTR并排，区分百分点变化与相对变化。

相对变化=(新值−旧值)/旧值；百分点变化=(新率−旧率)×100。例如1.2%降到0.48%，下降0.72个百分点，相对下降60%，不能说下降0.72%。

先运行原查询，随后每次只改一个条件。运行完用Excel或手算核对，解释“每行结果代表什么”。

## 足以支撑初级面试的练习标准

你能从业务问题确定表、粒度、时间窗和分母，独立写出筛选、聚合、关联、条件统计，解释零值/NULL/重复记录，并查出一次结果不一致的原因。窗口函数是进阶练习；记住关键词不等于掌握。

当前岗位截图没有将SQL列为硬性要求，但这些能力能支撑报表排查和AI工作流验证。后续可再补SQL性能、索引、复杂事件序列与真实业务口径，无需在第一天全部完成。

参考：[SQLite SELECT](https://www.sqlite.org/lang_select.html)、[聚合函数](https://www.sqlite.org/lang_aggfunc.html)、[窗口函数](https://www.sqlite.org/windowfunctions.html)。

