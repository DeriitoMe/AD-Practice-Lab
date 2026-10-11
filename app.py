"""Local HTTP application. No third-party dependencies."""
import argparse, json, mimetypes, os, time, uuid, webbrowser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
import lab
from simulation import simulate
from seed import sample_csv

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def reply(self,data,status=200,ctype='application/json; charset=utf-8',filename=None):
  body=data if isinstance(data,bytes) else (json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8') if ctype.startswith('application/json') else data.encode('utf-8'))
  self.send_response(status); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
  if filename: self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
  self.end_headers(); self.wfile.write(body)
 def guard(self):
  host=self.headers.get('Host','')
  if host not in {'127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)}: raise ValueError('仅接受本地访问')
  origin=self.headers.get('Origin')
  if origin and origin not in {'http://'+host}: raise ValueError('请求来源不匹配')
 def do_GET(self):
  try:
   self.guard(); url=urlsplit(self.path); q={k:v[0] for k,v in parse_qs(url.query).items()}
   if url.path=='/api/state':
    return self.reply({'datasets':lab.datasets(self.server.db),'as_of':lab.AS_OF,'llm_configured':all(os.getenv(k) for k in ['ADLAB_LLM_BASE_URL','ADLAB_LLM_API_KEY','ADLAB_LLM_MODEL'])})
   if url.path=='/api/report': return self.reply(lab.report(q.get('dataset_id',''),q.get('as_of',lab.AS_OF),q.get('campaign_id',''),self.server.db))
   if url.path=='/api/knowledge': return self.reply(lab.knowledge(q.get('q','')))
   if url.path=='/sample.csv': return self.reply('\ufeff'+sample_csv(),ctype='text/csv; charset=utf-8',filename='synthetic_ads.csv')
   if url.path=='/api/export':
    data=lab.diagnose(q.get('dataset_id',''),q.get('as_of',lab.AS_OF),self.server.db)
    lab.record('report_exported',dataset_id=q.get('dataset_id'),properties={'meaning':'server_response_generated'},db=self.server.db)
    return self.reply(data,filename='simulation_diagnosis.json')
   if url.path.startswith('/docs/'):
    target=(lab.ROOT/url.path.lstrip('/')).resolve()
    if not target.is_relative_to((lab.ROOT/'docs').resolve()) or target.suffix!='.md': raise ValueError('无效文档路径')
    return self.reply(target.read_bytes(),ctype='text/plain; charset=utf-8')
   rel='index.html' if url.path=='/' else url.path.lstrip('/')
   target=(lab.ROOT/'static'/rel).resolve()
   if not target.is_relative_to((lab.ROOT/'static').resolve()) or not target.is_file(): return self.reply({'error':'未找到'},404)
   ctype=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
   return self.reply(target.read_bytes(),ctype=ctype+'; charset=utf-8')
  except (ValueError,FileNotFoundError) as e: self.reply({'error':str(e)},400)
  except Exception: self.reply({'error':'服务内部错误，请运行测试检查本地数据'},500)
 def do_POST(self):
  started=time.monotonic(); prefix=None; rid=str(uuid.uuid4()); payload={}
  try:
   self.guard(); size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=2_100_000: raise ValueError('请求大小无效')
   payload=json.loads(self.rfile.read(size).decode('utf-8'))
   if not isinstance(payload,dict): raise ValueError('请求应为对象')
   endpoint=urlsplit(self.path).path
   if endpoint=='/api/event':
    event=payload.get('event_name')
    if event not in {'dashboard_viewed','lesson_answered'}: raise ValueError('不支持的练习事件')
    props={}
    if event=='lesson_answered':
     props=payload.get('properties',{})
     if not isinstance(props,dict) or props.get('lesson_id') not in {'roles','funnel','setup','metrics','returns','diagnosis'} or not isinstance(props.get('correct'),bool): raise ValueError('课程事件字段无效')
     props={'lesson_id':props['lesson_id'],'correct':props['correct'],'meaning':'self_reported_practice_answer'}
    return self.reply(lab.record(event,session_id=payload.get('session_id','local'),event_id=payload.get('event_id'),properties=props,db=self.server.db))
   prefix={'/api/import':'import','/api/diagnose':'diagnosis','/api/creative':'creative','/api/sql':'sql','/api/simulate':'simulation'}.get(endpoint)
   if prefix: lab.record(prefix+'_started',payload.get('session_id','local'),rid,payload.get('dataset_id'),db=self.server.db)
   if endpoint=='/api/import': result=lab.import_csv(payload.get('csv',''),payload.get('name','模拟导入'),self.server.db)
   elif endpoint=='/api/diagnose': result=lab.diagnose(payload.get('dataset_id',''),payload.get('as_of',lab.AS_OF),self.server.db)
   elif endpoint=='/api/creative': result=lab.creative_drafts(payload.get('audience',''),payload.get('angle',''))
   elif endpoint=='/api/simulate': result=simulate(payload.get('config',{}))
   elif endpoint=='/api/sql': result=lab.run_sql(payload.get('sql',''),self.server.db)
   elif endpoint=='/api/llm': result=lab.llm_explain(lab.diagnose(payload.get('dataset_id',''),payload.get('as_of',lab.AS_OF),self.server.db))
   else: return self.reply({'error':'未找到接口'},404)
   if prefix: lab.record(prefix+'_finished',payload.get('session_id','local'),rid,payload.get('dataset_id'),outcome='success',duration_ms=int((time.monotonic()-started)*1000),properties={'operation':prefix},db=self.server.db)
   self.reply(result)
  except Exception as e:
   if prefix: lab.record(prefix+'_finished',payload.get('session_id','local'),rid,payload.get('dataset_id'),outcome='failed',duration_ms=int((time.monotonic()-started)*1000),properties={'error_type':type(e).__name__},db=self.server.db)
   message=str(e) if isinstance(e,(ValueError,TypeError)) else '操作失败；请核对服务配置或输入。模型错误不会暴露密钥。'
   self.reply({'error':message},400)

def make_server(port=0,db=lab.DEFAULT_DB):
 lab.initialize(db)
 if not lab.datasets(db): lab.import_csv(sample_csv(),'56行模拟投放：4计划×14天',db)
 server=ThreadingHTTPServer(('127.0.0.1',port),Handler); server.db=db; return server
if __name__=='__main__':
 parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=0); parser.add_argument('--open',action='store_true'); args=parser.parse_args()
 server=make_server(args.port); address='http://127.0.0.1:'+str(server.server_port)
 print('Ad Practice Lab: '+address,flush=True)
 if args.open: webbrowser.open(address)
 try: server.serve_forever()
 except KeyboardInterrupt: pass
 finally: server.server_close()
