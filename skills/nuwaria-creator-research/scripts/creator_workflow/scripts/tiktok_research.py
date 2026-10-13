import asyncio,json,sys,re
from urllib.parse import quote
from pathlib import Path
from datetime import datetime,timezone,timedelta
from playwright.async_api import async_playwright
from workflow_context import P, CONFIG, DATE, TARGET, CUTOFF, OUTPUT, CDP
async def search(queries):
 dest=P/'tiktok_discovery.json';out=json.loads(dest.read_text(encoding='utf8')) if dest.exists() else {}
 async with async_playwright() as a:
  b=await a.chromium.connect_over_cdp(CDP);pg=await b.contexts[0].new_page()
  for query in queries:
   captured=[];tasks=[]
   async def response(r):
    if 'tiktok.com' in r.url and '/api/' in r.url:
     try:captured.append(await r.json())
     except:pass
   def event(r):tasks.append(asyncio.create_task(response(r)))
   pg.on('response',event)
   try:
    await pg.goto('https://www.tiktok.com/search?q='+quote(query),wait_until='domcontentloaded',timeout=40000);await pg.wait_for_timeout(4500)
    body=await pg.locator('body').inner_text(timeout=8000)
    if any(x in body.lower() for x in ['verify to continue','drag the slider','security verification','complete the puzzle']):print('VERIFICATION_REQUIRED');break
    for _ in range(2):
     await pg.evaluate('window.scrollTo(0,document.body.scrollHeight)');await pg.wait_for_timeout(1800)
    if tasks:
     done,pending=await asyncio.wait(tasks,timeout=20)
     for task in pending:task.cancel()
     await asyncio.gather(*tasks,return_exceptions=True)
    found=set()
    def walk(o):
     if isinstance(o,dict):
      au=o.get('author') or {}
      if isinstance(au,dict) and au.get('uniqueId') and o.get('createTime') and o.get('id'):
       h=au['uniqueId'].lower();found.add(h)
       row=out.setdefault(h,{'handle':h,'name':au.get('nickname',''),'bio':au.get('signature',''),'url':'https://www.tiktok.com/@'+h,'posts':[],'queries':[]})
       if query not in row['queries']:row['queries'].append(query)
       if str(o['id']) not in [x['code'] for x in row['posts']]:row['posts'].append({'code':str(o['id']),'date':datetime.fromtimestamp(int(o['createTime']),timezone.utc).date().isoformat(),'caption':o.get('desc',''),'url':'https://www.tiktok.com/@'+h+'/video/'+str(o['id'])})
      for v in o.values():walk(v)
     elif isinstance(o,list):
      for v in o:walk(v)
    walk(captured);print(query,len(found),'authors',body[:120].replace('\n',' '),flush=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
   except Exception as e:print(query,type(e).__name__,str(e)[:100],flush=True)
   finally:pg.remove_listener('response',event)
  await pg.close()
def normalize(raw):
 h=raw['handle'];posts={};user={};stats={}
 def walk(o):
  nonlocal user,stats
  if isinstance(o,dict):
   ui=o.get('userInfo')
   if isinstance(ui,dict) and (ui.get('user') or {}).get('uniqueId','').lower()==h.lower():
    user=ui['user'];stats=ui.get('stats',{})
   au=o.get('author') or {}
   if isinstance(au,dict) and au.get('uniqueId','').lower()==h.lower() and o.get('createTime') and o.get('id'):
    st=o.get('stats') or {};v=o.get('video') or {};tm=int(o['createTime']);code=str(o['id']);thumb=v.get('originCover') or v.get('cover')
    if o.get('imagePost'):
     ims=o['imagePost'].get('images') or []
     if ims:thumb=(ims[0].get('imageURL') or {}).get('urlList',[thumb])[0]
    posts[code]={'code':code,'url':'https://www.tiktok.com/@'+h+('/photo/' if o.get('imagePost') else '/video/')+code,'timestamp':tm,'date':datetime.fromtimestamp(tm,timezone.utc).date().isoformat(),'caption':o.get('desc',''),'likes':st.get('diggCount'),'comments':st.get('commentCount'),'views':st.get('playCount'),'shares':st.get('shareCount'),'saves':st.get('collectCount'),'paid':o.get('isAd',False),'pinned':o.get('isPinnedItem',False),'thumb':thumb,'media_type':8 if o.get('imagePost') else 2}
    if not user:user=au;stats=o.get('authorStats') or {}
   for v in o.values():walk(v)
  elif isinstance(o,list):
   for v in o:walk(v)
 walk(raw['captured'])
 bio=user.get('signature','');ext=(user.get('bioLink') or {}).get('link','')
 out={'handle':'tt__'+h,'platform_handle':h,'platform':'TikTok','url':'https://www.tiktok.com/@'+h,'source':'https://www.tiktok.com/@'+h,'category':'personal-lifestyle-TikTok','user':{'username':h,'full_name':user.get('nickname',''),'biography':bio,'follower_count':stats.get('followerCount'),'external_url':ext,'bio_links':[]},'posts':sorted(posts.values(),key=lambda x:-x['timestamp'])[:30],'emails':sorted(set(re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',bio))),'text':raw['body'],'focused_checked':True,'checked_at':raw['checked_at']}
 out['status']='ok' if len(out['posts'])>=12 else 'incomplete'
 (P/'profiles'/('tt__'+h+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 return out
async def probe(handles):
 excluded_path=P/'excluded_handles.json'
 excluded={str(h).lower().lstrip('@') for h in json.loads(excluded_path.read_text(encoding='utf8'))} if excluded_path.exists() else set()
 ready=[];skipped=[];seen=set()
 for raw_handle in handles:
  h=raw_handle.strip().lstrip('@').lower()
  reason=None
  if not re.fullmatch(r'[a-z0-9_.]{1,30}',h):reason='invalid_handle'
  elif h in excluded or 'tt__'+h in excluded:reason='historical_handle_or_alias'
  elif h in seen:reason='duplicate_in_queue'
  elif (P/'profiles'/('tt__'+h+'.json')).exists():reason='already_captured'
  seen.add(h)
  if reason:skipped.append({'handle':h,'reason':reason})
  else:ready.append(h)
 (P/'tiktok_queue_preflight.json').write_text(json.dumps({'checked_at':datetime.now().isoformat(),'input_count':len(handles),'ready_count':len(ready),'skipped':skipped},ensure_ascii=False,indent=2),encoding='utf8')
 print('TIKTOK PREFLIGHT',len(handles),'input',len(ready),'ready',len(skipped),'skipped',flush=True)
 if not ready:return
 async with async_playwright() as a:
  b=await a.chromium.connect_over_cdp(CDP); pg=await b.contexts[0].new_page()
  for h in ready:
   captured=[];tasks=[]
   async def response(r):
    if 'tiktok.com' in r.url and '/api/' in r.url:
     try:captured.append(await r.json())
     except:pass
   def event(r):tasks.append(asyncio.create_task(response(r)))
   pg.on('response',event)
   try:
    await pg.goto('https://www.tiktok.com/@'+h,wait_until='domcontentloaded',timeout=40000);await pg.wait_for_timeout(5000)
    body=await pg.locator('body').inner_text(timeout=8000)
    if any(x in body.lower() for x in ['verify to continue','drag the slider','security verification','complete the puzzle']):
     print('VERIFICATION_REQUIRED',flush=True);break
    scripts=await pg.locator('script#__UNIVERSAL_DATA_FOR_REHYDRATION__,script#SIGI_STATE').all_text_contents()
    for s in scripts:
     try:captured.append(json.loads(s))
     except:pass
    for _ in range(3):
     await pg.evaluate('window.scrollTo(0,document.body.scrollHeight)');await pg.wait_for_timeout(2000)
    if tasks:
     done,pending=await asyncio.wait(tasks,timeout=20)
     for task in pending:task.cancel()
     await asyncio.gather(*tasks,return_exceptions=True)
    raw={'handle':h,'body':body,'captured':captured,'checked_at':datetime.now(timezone(timedelta(hours=8))).isoformat()}
    out=P/'tiktok_raw';out.mkdir(exist_ok=True);(out/(h+'.json')).write_text(json.dumps(raw,ensure_ascii=False),encoding='utf8')
    profile=normalize(raw);print(h,len(profile['posts']),'posts',','.join(profile['emails']) or 'NO_EMAIL',flush=True)
    await pg.screenshot(path=str(P/'screenshots'/('tt_'+h+'.png')),full_page=True)
   except Exception as e:print(h,type(e).__name__,str(e)[:120],flush=True)
   finally:pg.remove_listener('response',event)
  await pg.close()
if __name__=='__main__':asyncio.run(probe(sys.argv[1:]))
