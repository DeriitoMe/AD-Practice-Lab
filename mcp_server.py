"""Minimal MCP stdio server. Protocol 2025-06-18; tool transport smoke-tested."""
import json, sys
import lab
from seed import sample_csv
SUPPORTED=['2025-06-18','2024-11-05']
SCHEMA={'type':'object','properties':{'dataset_id':{'type':'string'},'as_of':{'type':'string','default':lab.AS_OF}},'required':['dataset_id'],'additionalProperties':False}
TOOLS=[
 {'name':'list_ad_datasets','description':'列出本地模拟投放数据集及数据性质。','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
 {'name':'ad_summary','description':'计算成熟窗口内的广告指标。金额CNY，购买为转化。','inputSchema':SCHEMA},
 {'name':'diagnose_ads','description':'比较两个完整7日窗口，返回证据、假设、验证动作与官方来源。','inputSchema':SCHEMA},
 {'name':'search_ad_knowledge','description':'检索内置有来源的广告知识卡。','inputSchema':{'type':'object','properties':{'query':{'type':'string'}},'required':['query'],'additionalProperties':False}},
 {'name':'query_ads','description':'执行本地只读SQLite分析查询；最多200行、2秒。','inputSchema':{'type':'object','properties':{'sql':{'type':'string'}},'required':['sql'],'additionalProperties':False}}
]
for t in TOOLS: t['annotations']={'readOnlyHint':True,'destructiveHint':False,'idempotentHint':True,'openWorldHint':False}
def invoke(name,args,db=lab.DEFAULT_DB):
 tool=next((t for t in TOOLS if t['name']==name),None)
 if tool is None: raise ValueError('未知工具')
 schema=tool['inputSchema']
 if not isinstance(args,dict) or any(k not in schema['properties'] for k in args): raise ValueError('参数不匹配')
 if any(k not in args for k in schema.get('required',[])) or any(not isinstance(v,str) for v in args.values()): raise ValueError('参数缺失或类型不正确')
 if name=='list_ad_datasets': return lab.datasets(db)
 if name=='ad_summary': return lab.report(args['dataset_id'],args.get('as_of',lab.AS_OF),db=db)
 if name=='diagnose_ads': return lab.diagnose(args['dataset_id'],args.get('as_of',lab.AS_OF),db)
 if name=='search_ad_knowledge': return lab.knowledge(args['query'])
 if name=='query_ads': return lab.run_sql(args['sql'],db)
def main():
 sys.stdin.reconfigure(encoding='utf-8'); sys.stdout.reconfigure(encoding='utf-8')
 lab.initialize()
 if not lab.datasets(): lab.import_csv(sample_csv(),'56行模拟投放：4计划×14天')
 initialized=False; negotiated=False
 for line in sys.stdin:
  ident=None
  try:
   req=json.loads(line); ident=req.get('id'); method=req.get('method'); params=req.get('params',{})
   if not isinstance(params,dict): raise ValueError('params必须是对象')
   if method=='initialize':
    requested=params.get('protocolVersion'); negotiated=True
    result={'protocolVersion':requested if requested in SUPPORTED else SUPPORTED[0],'capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'ad-practice-lab','version':'1.0.0'},'instructions':'所有广告数据均为模拟；诊断原因是待验证假设。'}
   elif method=='notifications/initialized': initialized=negotiated; continue
   elif ident is None: continue
   elif method=='ping': result={}
   elif not initialized:
    print(json.dumps({'jsonrpc':'2.0','id':ident,'error':{'code':-32000,'message':'Initialize first'}},ensure_ascii=False),flush=True); continue
   elif method=='tools/list': result={'tools':TOOLS}
   elif method=='tools/call':
    try:
     output=invoke(params.get('name'),params.get('arguments',{}))
     result={'content':[{'type':'text','text':json.dumps(output,ensure_ascii=False)}],'isError':False}
    except (ValueError,KeyError) as e: result={'content':[{'type':'text','text':str(e)}],'isError':True}
   else:
    print(json.dumps({'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'Method not found'}}),flush=True); continue
   if ident is not None: print(json.dumps({'jsonrpc':'2.0','id':ident,'result':result},ensure_ascii=False),flush=True)
  except Exception as e:
   print(json.dumps({'jsonrpc':'2.0','id':ident,'error':{'code':-32600,'message':'Invalid request: '+type(e).__name__}},ensure_ascii=False),flush=True)
if __name__=='__main__': main()
