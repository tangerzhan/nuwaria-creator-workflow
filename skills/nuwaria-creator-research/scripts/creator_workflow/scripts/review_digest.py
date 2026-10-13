import json,re,sys
from pathlib import Path
from workflow_context import P, CONFIG, DATE, TARGET, CUTOFF, OUTPUT, CDP
sys.stdout.reconfigure(encoding='utf8')
for h in sys.argv[1:]:
 r=json.loads((P/'profiles'/f'{h}.json').read_text(encoding='utf8'))
 print('\nACCOUNT',h,'BIO',r['user'].get('biography'),'EMAIL',r.get('emails'))
 for i,x in enumerate(r['posts'][:24]):
  print(i+1,x['date'],'PAID' if x.get('paid') else '', ' '.join(x.get('caption','').split())[:210])
 f=P/'official_links'/f'{h}.json'
 if f.exists():
  for q in json.loads(f.read_text(encoding='utf8')).get('pages',[]):
   print('LINK',q.get('source'),q.get('status'),q.get('error'))
   t=q.get('text','');print(re.split('More from Linktree|Explore other Linktrees|Discover more',t)[0][:2100])
   for z in q.get('links',[]):
    if any(k in z.get('text','').lower() for k in ['my shop','my brand','portfolio','little shop','etsy','tiktok']):print('DESTINATION',z)
