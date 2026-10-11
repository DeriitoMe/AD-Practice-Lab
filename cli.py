import argparse,json
from pathlib import Path
import lab
from seed import sample_csv
p=argparse.ArgumentParser();p.add_argument('action',choices=['datasets','diagnose','query']);p.add_argument('--dataset');p.add_argument('--as-of',default=lab.AS_OF);p.add_argument('--file');a=p.parse_args()
lab.initialize()
if not lab.datasets():lab.import_csv(sample_csv(),'56行模拟投放：4计划×14天')
if a.action=='datasets':result=lab.datasets()
elif a.action=='diagnose':result=lab.diagnose(a.dataset or lab.datasets()[0]['id'],a.as_of)
else:
 if not a.file:p.error('query需要--file指向SQL文件')
 result=lab.run_sql(Path(a.file).read_text(encoding='utf-8-sig'))
print(json.dumps(result,ensure_ascii=False,indent=2))
