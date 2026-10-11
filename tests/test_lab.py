import csv, io, json, sqlite3, subprocess, sys, tempfile, threading, unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import lab, app
from seed import sample_csv

class LabTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); self.db=Path(self.temp.name)/'test.sqlite3'; lab.initialize(self.db)
  self.ident=lab.import_csv(sample_csv(),'test',self.db)['dataset_id']
 def tearDown(self): self.temp.cleanup()
 def altered(self,fn):
  rows=list(csv.DictReader(io.StringIO(sample_csv())));fn(rows);out=io.StringIO();w=csv.DictWriter(out,fieldnames=lab.FIELDS);w.writeheader();w.writerows(rows);return out.getvalue()
 def test_formula_example(self):
  m=lab.metrics({'impressions':100000,'clicks':1000,'landing_views':900,'purchases':20,'spend':1000,'revenue':4000,'variable_cost':2000})
  self.assertEqual(m['cpa'],50);self.assertEqual(m['roas'],4);self.assertAlmostEqual(m['roi'],1/3);self.assertEqual(m['cpm'],10)
 def test_zero_denominators(self):
  m=lab.metrics({});self.assertIsNone(m['cpa']);self.assertIsNone(m['roas']);self.assertIsNone(m['ctr'])
 def test_weighted_ratio(self):
  with lab.connect(self.db) as c:
   raw=c.execute('SELECT SUM(clicks)*1.0/SUM(impressions) FROM ad_daily WHERE dataset_id=?',(self.ident,)).fetchone()[0]
  self.assertAlmostEqual(lab.report(self.ident,db=self.db)['overall']['ctr'],raw)
 def test_import_idempotency(self):
  result=lab.import_csv('\ufeff'+sample_csv(),'same',self.db);self.assertTrue(result['duplicate']);self.assertEqual(len(lab.datasets(self.db)),1)
 def test_duplicate_key(self):
  with self.assertRaises(ValueError):lab.import_csv(self.altered(lambda rows:rows.append(rows[0].copy())),db=self.db)
 def test_invalid_money_atomic(self):
  for value in ['NaN','Infinity','-1','1.234','']:
   with self.subTest(value=value),self.assertRaises(ValueError):lab.import_csv(self.altered(lambda r:r[0].update(spend=value)),db=self.db)
  self.assertEqual(len(lab.datasets(self.db)),1)
 def test_mixed_attribution(self):
  with self.assertRaises(ValueError):lab.import_csv(self.altered(lambda r:r[0].update(attribution='1d_view')),db=self.db)
 def test_invalid_funnel(self):
  with self.assertRaises(ValueError):lab.import_csv(self.altered(lambda r:r[0].update(clicks='999999')),db=self.db)
 def test_maturity(self):
  r=lab.report(self.ident,'2026-09-27',db=self.db);self.assertEqual(r['mature_rows'],4);self.assertEqual(r['excluded_rows'],52)
 def test_diagnosis_signals(self):
  r=lab.diagnose(self.ident,db=self.db);signals={(f['campaign_id'],f['code']) for f in r['findings']}
  self.assertIn(('B','ctr_drop'),signals);self.assertIn(('C','arrival_drop'),signals);self.assertIn(('D','cpm_up'),signals);self.assertFalse(any(x[0]=='A' for x in signals))
  self.assertTrue(all(f['source']['url'].startswith('https://') for f in r['findings']))
 def test_zero_spend_negative_profit_diagnosis(self):
  text=self.altered(lambda rows:[r.update(spend='0',revenue='0',variable_cost='1') for r in rows if r['campaign_id']=='A'])
  ident=lab.import_csv(text,'zero spend',self.db)['dataset_id']
  result=lab.diagnose(ident,db=self.db)
  findings=[f for f in result['findings'] if f['campaign_id']=='A' and f['code']=='negative_profit']
  self.assertEqual(len(findings),1)
  self.assertIn('ROAS 不可计算',findings[0]['evidence'])
 def test_missing_days_stop_comparison(self):
  with lab.connect(self.db) as c:c.execute('DELETE FROM ad_daily WHERE date=?',('2026-09-23',))
  self.assertEqual(lab.diagnose(self.ident,db=self.db)['status'],'insufficient_data')
 def test_read_only_sql(self):
  for sql in ['DELETE FROM ad_daily',"ATTACH DATABASE ':memory:' AS another",'PRAGMA user_version=7','SELECT 1; SELECT 2;']:
   with self.subTest(sql=sql),self.assertRaises(ValueError):lab.run_sql(sql,self.db)
  self.assertEqual(lab.run_sql('WITH x AS (SELECT 42 n) SELECT n FROM x',self.db)['rows'],[(42,)])
 def test_sql_limit(self):
  r=lab.run_sql('SELECT a.date FROM ad_daily a CROSS JOIN ad_daily b',self.db);self.assertTrue(r['truncated']);self.assertEqual(len(r['rows']),200)
 def test_event_idempotency(self):
  for _ in range(2):lab.record('dashboard_viewed',event_id='same',db=self.db)
  with lab.connect(self.db) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM product_events').fetchone()[0],1)
 def test_templates(self):
  r=lab.creative_drafts('学生','通勤收纳');self.assertEqual(r['mode'],'template');self.assertEqual(len(r['drafts']),3)
  with self.assertRaises(ValueError):lab.creative_drafts('', 'x')
 def test_http_workflow(self):
  server=app.make_server(0,self.db);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
  try:
   with urlopen(base+'/') as response:self.assertEqual(response.status,200)
   def post(path,body):
    req=Request(base+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urlopen(req) as response:return json.loads(response.read())
   r=post('/api/diagnose',{'dataset_id':self.ident});self.assertEqual(r['status'],'complete')
   try:post('/api/import',{'csv':'bad'})
   except HTTPError as error:self.assertEqual(error.code,400);error.close()
   else:self.fail('invalid CSV should return HTTP 400')
   with lab.connect(self.db) as c:
    vals=c.execute("SELECT event_name,outcome FROM product_events ORDER BY received_at").fetchall()
   self.assertIn(('diagnosis_finished','success'),[tuple(v) for v in vals]);self.assertIn(('import_finished','failed'),[tuple(v) for v in vals])
  finally:server.shutdown();server.server_close();thread.join()

class MCPTests(unittest.TestCase):
 def test_stdio_handshake_and_read_tool(self):
  messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'test','version':'1'}}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/list'},{'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'query_ads','arguments':{'sql':'SELECT 42 AS answer'}}},{'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'query_ads','arguments':{'sql':'DELETE FROM ad_daily'}}}]
  result=subprocess.run([sys.executable,str(lab.ROOT/'mcp_server.py')],input='\n'.join(json.dumps(m) for m in messages)+'\n',text=True,encoding='utf-8',capture_output=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stderr);out=[json.loads(x) for x in result.stdout.splitlines()]
  self.assertEqual(out[0]['result']['protocolVersion'],'2025-06-18');self.assertEqual(len(out[1]['result']['tools']),5)
  self.assertFalse(out[2]['result']['isError']);self.assertTrue(out[3]['result']['isError'])
if __name__=='__main__':unittest.main(verbosity=2)
