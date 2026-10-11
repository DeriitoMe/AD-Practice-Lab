import csv, io
from datetime import date,timedelta
from lab import FIELDS

def sample_csv():
 out=io.StringIO(); writer=csv.DictWriter(out,fieldnames=FIELDS); writer.writeheader()
 names={'A':'通勤场景·对照组','B':'收纳场景·计划B','C':'电脑隔层·计划C','D':'日常出行·计划D'}
 for day in range(14):
  for cid,name in names.items():
   impressions=20000+((day*13+ord(cid))%7)*200
   ctr=.012; arrival=.9; purchase_rate=.045; cpm=20
   if day>=7:
    if cid=='B': ctr=.0048
    if cid=='C': arrival=.4
    if cid=='D': cpm=38
   clicks=round(impressions*ctr); land=round(clicks*arrival); buys=round(land*purchase_rate)
   writer.writerow(dict(date=(date(2026,9,19)+timedelta(days=day)).isoformat(),campaign_id=cid,campaign_name=name,creative_id='creative_'+cid,impressions=impressions,clicks=clicks,landing_views=land,purchases=buys,spend=round(impressions*cpm/1000,2),revenue=buys*199,variable_cost=buys*99,currency='CNY',attribution='7d_click',source_kind='simulation'))
 return out.getvalue()
