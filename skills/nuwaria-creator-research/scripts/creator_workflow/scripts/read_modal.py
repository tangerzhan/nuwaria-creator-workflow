import json,re,sys
from pathlib import Path
from workflow_context import P, CONFIG, DATE, TARGET, CUTOFF, OUTPUT, CDP
sys.stdout.reconfigure(encoding='utf8')
for spec in sys.argv[1:]:
 h,indices=spec.split(':');a=json.loads((P/'post_audits'/h/'audit.json').read_text(encoding='utf8'))
 for i in map(int,indices.split(',')):
  q=a[i-1];ls=q.get('public_text','').splitlines();out=[]
  for j,s in enumerate(ls):
   if re.match(r'^\d+(?:天|周|小时|分钟|个月|年).*回复$',s):
    start=j-1
    while start>=0 and not re.fullmatch(r'[\w.]{2,30}',ls[start],re.ASCII):start-=1
    if start>=0:out.append(ls[start]+': '+' '.join(ls[start+1:j]))
  print(h,i,'COMMENTS',len(out));print('\n'.join(out));
