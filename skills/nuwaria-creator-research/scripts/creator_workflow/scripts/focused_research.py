import asyncio,json,re,sys,time
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from datetime import datetime,timezone,timedelta
from bs4 import BeautifulSoup
import requests
from playwright.async_api import async_playwright
from research import extract,EMAIL
from workflow_context import research_page, screening, P, CONFIG, DATE, TARGET, CUTOFF, OUTPUT, CDP
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,d):(P/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
def prepare_queue(rows):
 def norm(h):return h.strip().lstrip('@').lower()
 excluded={norm(h) for h in load('excluded_handles.json')}
 reviews=load('production_reviews.json')
 current={norm(a) for h,v in reviews.items() if v.get('verdict')=='include' for a in [h,*v.get('aliases',[])]}
 screened=screening()
 prior_screened={}
 for folder in CONFIG.get('history_projects',[]):
  previous=Path(folder)
  if previous.resolve()==P.resolve():continue
  for handle,decision in screening(previous).items():
   if isinstance(decision,dict):
    if decision.get('verdict') in ('exclude','hold'):
     prior_screened[norm(handle)]={'project':previous.name,**decision}
    elif decision.get('verdict')=='pass':prior_screened.pop(norm(handle),None)
 historical_emails={e.strip().lower() for e in load('historical_exclusions.json').get('emails',[])} if (P/'historical_exclusions.json').exists() else set()
 current_emails={(v.get('public_email') or '').strip().lower() for v in reviews.values() if v.get('verdict')=='include'}-{''}
 seen=set();ready=[];skipped=[]
 for row in rows:
  h=norm(row['handle']);reason=None
  contact=' '.join(str(row.get(k) or '') for k in ('public_email','email','emails'))
  emails={e.lower() for e in EMAIL.findall(contact)}
  if not re.fullmatch(r'[a-z0-9_.]{1,30}',h):reason='invalid_handle'
  elif h in excluded:reason='historical_handle_or_alias'
  elif h in current:reason='already_selected_or_known_alias'
  elif h in seen:reason='duplicate_in_queue'
  elif screened.get(h,{}).get('verdict')=='exclude':reason='already_excluded_in_screening'
  elif h in prior_screened and screened.get(h,{}).get('verdict')!='pass':reason='historical_screening_'+prior_screened[h]['verdict']
  elif emails & historical_emails:reason='historical_email'
  elif emails & current_emails:reason='already_selected_email'
  elif (P/'profiles'/f'{h}.json').exists() and load('profiles/'+h+'.json').get('focused_checked'):reason='already_captured'
  seen.add(h)
  if reason:
   item={'handle':h,'reason':reason}
   if reason.startswith('historical_screening_'):item['prior_screening']=prior_screened[h]
   skipped.append(item)
  else:ready.append({**row,'handle':h,'url':row.get('url') or 'https://www.instagram.com/'+h+'/'})
 return ready,skipped
def queue_check():
 source=load(sys.argv[2]);rows,skipped=prepare_queue(source)
 save('queue_preflight.json',{'queue':sys.argv[2],'checked_at':datetime.now().isoformat(),'input_count':len(source),'ready_count':len(rows),'skipped':skipped})
 print('QUEUE PREFLIGHT',len(source),'input',len(rows),'ready',len(skipped),'skipped',flush=True)
 return rows
async def scan():
 rows=queue_check()
 if not rows:return
 dest=P/'profiles';dest.mkdir(exist_ok=True);shots=P/'screenshots';shots.mkdir(exist_ok=True)
 async with async_playwright() as p:
  b=await p.chromium.connect_over_cdp(CDP);c=b.contexts[0]
  async with research_page(c) as pg:
   await pg.set_viewport_size({'width':1440,'height':1100})
   for r in rows:
    h=r['handle'];f=dest/(h+'.json')
    if f.exists() and json.loads(f.read_text(encoding='utf8')).get('focused_checked'):continue
    capt=[];tasks=[]
    async def response(res):
     if 'instagram.com' in res.url and ('graphql' in res.url or '/api/v1/' in res.url):
      try:capt.append(await asyncio.wait_for(res.json(),timeout=15))
      except:pass
    def event(res):tasks.append(asyncio.create_task(response(res)))
    pg.on('response',event)
    try:
     await pg.goto('https://www.instagram.com/'+h+'/',wait_until='domcontentloaded',timeout=40000);await pg.wait_for_timeout(4200)
     body=await pg.locator('body').inner_text(timeout=8000)
     if any(s in body.lower() for s in ['challenge_required','confirm it’s you','try again later','稍后再试']):
      save('access_stop.json',{'handle':h,'reason':'Instagram requested verification or waiting','date':str(datetime.now())});print('ACCESS STOP',h,flush=True);break
     await asyncio.gather(*tasks,return_exceptions=True)
     user,posts=extract(capt,h)
     followers=user.get('follower_count')
     outside_range=isinstance(followers,(int,float)) and not 1000<=followers<=100000
     # Inspect the first response before scrolling: out-of-range profiles need
     # only the recorded metadata, and many eligible profiles already have 24 posts.
     for _ in range(4):
      if outside_range or len(posts)>=24:break
      await pg.evaluate('window.scrollTo(0,document.body.scrollHeight)');await pg.wait_for_timeout(2000)
      await asyncio.gather(*tasks,return_exceptions=True)
      user,posts=extract(capt,h)
      followers=user.get('follower_count')
      outside_range=isinstance(followers,(int,float)) and not 1000<=followers<=100000
     # Return to the recent grid before capture so lazy-loaded thumbnails are
     # visible in the section used by quick_screen. Do not recapture old files.
     await pg.evaluate('window.scrollTo(0,0)')
     try:
      await pg.wait_for_function("Array.from(document.querySelectorAll('main img')).filter(i => i.complete && i.naturalWidth > 100).length >= 6",timeout=6000)
     except Exception:
      pass
     await pg.screenshot(path=str(shots/(h+'.png')),full_page=True)
     await asyncio.gather(*tasks,return_exceptions=True);user,posts=extract(capt,h)
     # Retain flags used to distinguish hidden counts and old pinned content.
     nodes={}
     def walk(o):
      if isinstance(o,dict):
       code=o.get('code') or o.get('shortcode')
       if code and ('like_count' in o or 'taken_at' in o):nodes.setdefault(code,[]).append(o)
       for v in o.values():walk(v)
      elif isinstance(o,list):
       for v in o:walk(v)
     walk(capt)
     for post in posts:
      for n in nodes.get(post['code'],[]):
       if n.get('like_and_view_counts_disabled') or n.get('like_count_is_disabled'):post['likes']=None;post['likes_hidden']=True
       if n.get('is_pinned') or n.get('is_pinned_for_users') or n.get('pinned_for_users'):post['pinned']=True
       for key in ['play_count','ig_play_count','video_view_count','view_count']:
        if isinstance(n.get(key),(int,float)):post['views']=n[key];break
     emails=sorted(set(EMAIL.findall(user.get('biography','')+' '+str(user.get('public_email') or '')+' '+str(user.get('business_email') or ''))))
     links=await pg.locator('a').evaluate_all('(a)=>a.map(x=>({text:x.innerText,url:x.href})).filter(x=>x.url.startsWith("http")&&!x.url.includes("instagram.com"))')
     result={**r,'checked_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'user':user,'posts':posts,'emails':emails,'text':body[:6500],'external_links':links,'focused_checked':True,'status':'ok' if len(posts)>=12 and user else 'incomplete'}
     if f.exists():
      old=P/'initial_profiles';old.mkdir(exist_ok=True)
      if not (old/f.name).exists():(old/f.name).write_bytes(f.read_bytes())
     f.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
     # Reuse public media already returned during profile capture for later review.
     # This avoids visiting the same profile again solely to recover video URLs.
     from fast_audit import media_map
     media=media_map(capt);target={x['code'] for x in posts[:12]}
     (P/'native_media').mkdir(exist_ok=True)
     save('native_media/'+h+'.json',{'checked_at':result['checked_at'],'source':result['url'],'media':{k:v for k,v in media.items() if k in target}})
     print(h,len(posts),'posts',','.join(emails) or 'NO_EMAIL',flush=True)
    except Exception as e:print(h,'ERROR',str(e)[:180],flush=True)
    finally:pg.remove_listener('response',event)
    await pg.wait_for_timeout(1500)



if __name__=="__main__":
 if sys.argv[1]=='queue-check':queue_check()
 else:asyncio.run(scan())
