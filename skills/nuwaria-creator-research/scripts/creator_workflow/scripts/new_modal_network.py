import json,re,sys
from pathlib import Path
from workflow_context import P, CONFIG, DATE, TARGET, CUTOFF, OUTPUT, CDP
excluded=set(json.loads((P/'excluded_handles.json').read_text(encoding='utf8')))
out={}
sources=[]
for h in sys.argv[2:]:
 if h=='history':
  for folder in CONFIG.get('history_projects',[]):
   sources.extend(Path(folder).glob('post_audits/*/audit.json'))
 else:sources.append(P/'post_audits'/h/'audit.json')
for audit_path in sources:
 h=audit_path.parent.name
 a=json.loads(audit_path.read_text(encoding='utf8'))
 for q in a:
  ls=q.get('public_text','').splitlines()
  for j,s in enumerate(ls):
   if re.match(r'^\d+\s*(?:天|周|小时|分钟|个月|年).*回复$',s):
    # A comment is username, body, timestamp. Search forward after the
    # previous timestamp, not backward into one-word comment bodies.
    start=j-1
    while start>=0 and not re.search(r'(?:回复$|查看回复|已编辑.*\d+\s*(?:天|周|小时|分钟)|^\d+\s*(?:天|周|小时|分钟|个月|年)$)',ls[start]):start-=1
    block=[s.strip() for s in ls[start+1:j] if s.strip() and s.strip() not in {'已验证','查看翻译'}]
    if len(block)<2 or not re.fullmatch(r'[\w.]{2,30}',block[0],re.ASCII):continue
    k=block[0].lower()
    if k in excluded or (P/'profiles'/f'{k}.json').exists() or k==h or not re.search('[a-zA-Z]',k):continue
    out[k]={'handle':k,'url':f'https://www.instagram.com/{k}/','source':q.get('url') or f'https://www.instagram.com/{h}/','category':h+'-public-comment-network-unverified'}
(P/sys.argv[1]).write_text(json.dumps(list(out.values()),ensure_ascii=False,indent=2),encoding='utf8')
print(len(out), ' '.join(out))
