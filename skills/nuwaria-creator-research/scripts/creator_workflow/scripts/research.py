import json,re,os
from pathlib import Path
from datetime import datetime,timezone
import requests
from workflow_context import P as OUT,CONFIG
DS=CONFIG['notion_data_source'];SOP=CONFIG['notion_sop']
EMAIL=re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
def save(n,d):(OUT/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')

def load(n):return json.loads((OUT/n).read_text(encoding='utf8'))

def env(path):
 d={}
 for l in path.read_text(encoding='utf-8-sig').splitlines():
  if '=' in l and not l.lstrip().startswith('#'):
   k,v=l.split('=',1);d[k.strip()]=v.strip().strip('\"\'')
 return d

def flat(p):return {k:''.join(t.get('plain_text',t.get('text',{}).get('content','')) for t in v[v['type']]) if v['type'] in ('rich_text','title') else v.get(v['type']) for k,v in p['properties'].items()}

def extract(captured,handle):
 users=[];posts={}
 def walk(o):
  if isinstance(o,dict):
   username=o.get('username','')
   if username.lower()==handle.lower() and ('biography' in o or 'follower_count' in o or 'edge_followed_by' in o):
    users.append({k:o[k] for k in ['username','full_name','biography','follower_count','edge_followed_by','media_count','external_url','bio_links','public_email','business_email','is_private','is_business_account','category_name'] if k in o})
   owner=o.get('user') or o.get('owner') or {}
   code=o.get('code') or o.get('shortcode');stamp=o.get('taken_at') or o.get('taken_at_timestamp')
   if code and stamp and owner.get('username','').lower()==handle.lower():
    cap=o.get('caption') or {};caption=cap.get('text','') if isinstance(cap,dict) else str(cap)
    if not caption:
     ed=(o.get('edge_media_to_caption') or {}).get('edges') or [];caption=ed[0]['node']['text'] if ed else ''
    imgs=(o.get('image_versions2') or {}).get('candidates') or [];thumb=imgs[-1].get('url') if imgs else o.get('display_url')
    posts[code]={'code':code,'url':'https://www.instagram.com/p/'+code+'/','timestamp':stamp,'date':datetime.fromtimestamp(stamp,timezone.utc).date().isoformat(),'caption':caption,'likes':o.get('like_count'),'comments':o.get('comment_count'),'views':o.get('play_count',o.get('view_count')),'paid':o.get('is_paid_partnership'),'pinned':bool(o.get('is_pinned') or o.get('is_pinned_for_users')),'thumb':thumb,'media_type':o.get('media_type')}
   for v in o.values():walk(v)
  elif isinstance(o,list):
   for v in o:walk(v)
 for r in captured:walk(r)
 user=max(users,key=lambda u:len(str(u))) if users else {}
 return user,sorted(posts.values(),key=lambda p:-p['timestamp'])[:24]

def notion(method,path,**kw):
 # This client only permits source reads, including Notion's read-only query POST.
 if not (method=='GET' or (method=='POST' and path=='data_sources/'+DS+'/query')):
  raise ValueError('Only read-only Notion operations are supported')
 token=os.environ.get('NOTION_TOKEN')
 if not token:token=env(Path(CONFIG['notion_env']))['NOTION_TOKEN']
 response=requests.request(method,'https://api.notion.com/v1/'+path,headers={'Authorization':'Bearer '+token,'Notion-Version':'2025-09-03'},timeout=40,**kw)
 response.raise_for_status();return response.json()
def prepare():
 schema=notion('GET','data_sources/'+DS);pages=[];cursor=None
 while True:
  body={'page_size':100}
  if cursor:body['start_cursor']=cursor
  result=notion('POST','data_sources/'+DS+'/query',json=body);pages.extend(result['results'])
  if not result.get('has_more'):break
  cursor=result['next_cursor']
 save('schema.json',schema);save('existing.json',pages);print('Read Notion history:',len(pages))
