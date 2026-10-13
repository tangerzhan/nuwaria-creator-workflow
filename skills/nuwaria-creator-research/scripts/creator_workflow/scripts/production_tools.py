import json,re,sys,asyncio
from pathlib import Path
from PIL import Image,ImageDraw
from workflow_context import P, CONFIG, DATE, TARGET, CUTOFF, OUTPUT, CDP
sys.stdout.reconfigure(encoding='utf8')

RESTRICTION_MARKERS = ('verify you are human', 'access denied', 'just a moment...',
    '正在进行安全验证', '验证您不是自动程序', 'not allowed to proceed',
    'security policy configured', 'suspiciously similar to automated requests',
    'checking if the connection is secure', 'reviewing the security of your connection')

def restricted_page(record):
    return bool(record.get('restricted')) or any(
        marker in str(record.get('text', '')).lower() for marker in RESTRICTION_MARKERS)
def load(p):return json.loads((P/p).read_text(encoding='utf8'))
def save(p,v):(P/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def board(h):
    d=P/'post_audits'/h
    canvas=Image.new('RGB',(1800,1050),'white');draw=ImageDraw.Draw(canvas)
    for i in range(12):
        f=d/f'{i+1:02d}_sheet.jpg'
        x=(i%3)*600;y=(i//3)*262
        if f.exists():
            im=Image.open(f);im.thumbnail((600,255));canvas.paste(im,(x,y))
        else:draw.text((x+5,y+20),f'{h} {i+1} MISSING',fill='red')
    canvas.save(d/'overview.jpg')
async def browser_links(hs):
    from playwright.async_api import async_playwright
    from datetime import datetime
    async with async_playwright() as pw:
        browser=await pw.chromium.connect_over_cdp(CDP)
        for h in hs:
            if h.startswith('https://'):
                import hashlib
                source_url=h
                h='discovery_'+hashlib.sha256(h.encode()).hexdigest()[:16]
                target='discovery_links/'+h+'.json'
                (P/'discovery_links').mkdir(exist_ok=True)
                doc=load(target) if (P/target).exists() else {'pages':[{'source':source_url,'error':'browser discovery requested'}]}
            else:
                target='official_links/'+h+'.json'
                doc=load(target)
            urls=[]
            for q in doc.get('pages',[]):
                  if restricted_page(q):continue
                  if q.get('error') or len(q.get('text',''))<100 or 'unsupported client' in q.get('text','').lower() or ('linktr.ee' in q.get('source','') and (not q.get('embedded_social_checked') or q.get('contact_controls_checked')!=3)):urls.append(q.get('source') or q.get('url'))
            if not urls:continue
            for url in urls:
                if not url:continue
                pg=await browser.contexts[0].new_page()
                try:
                    resp=await pg.goto(url,wait_until='domcontentloaded',timeout=35000)
                    await pg.wait_for_timeout(1800)
                    body=await pg.locator('body').inner_text(timeout=15000)
                    if restricted_page({'text':body}):
                        rec={'source':url,'resolved_url':pg.url,'status':resp.status if resp else None,
                             'text':body[:18000],'restricted':True,'checked_at':datetime.now().isoformat(),
                             'method':'native browser restriction; do not retry'}
                        doc['pages']=[q for q in doc.get('pages',[]) if (q.get('source') or q.get('url'))!=url]+[rec]
                        save(target,doc)
                        print(h,'RESTRICTION',flush=True);continue
                    # Read the public video description before collecting contacts.
                    # This expands visible content only; it never opens a gated email flow.
                    if 'youtube.com/watch' in pg.url:
                        expand=pg.locator('ytd-watch-metadata #description-inline-expander #expand')
                        if await expand.count() and await expand.first.is_visible():
                            await expand.first.click(timeout=3000)
                            body=await pg.locator('body').inner_text(timeout=15000)
                    # Linktree may reveal its public contact card through a button,
                    # rather than exposing a mailto anchor in the initial page.
                    if 'linktr.ee' in pg.url:
                        contact=pg.get_by_role('button',name=re.compile(r'^Email Contact(?:\s.*)?$',re.I))
                        if not await contact.count():
                            contact=pg.get_by_text('Email Contact',exact=True)
                        if await contact.count() and await contact.first.is_visible():
                            await contact.first.click(timeout=3000)
                            await pg.wait_for_timeout(500)
                            body=await pg.locator('body').inner_text(timeout=8000)
                    # Expand the visible public legal notice, never a submission form.
                    if 'linktr.ee' in pg.url:
                        legal=pg.get_by_role('button',name=re.compile(r'^(Impressum|Imprint)$',re.I))
                        if not await legal.count():
                            legal=pg.get_by_text('Impressum',exact=True)
                        if await legal.count() and await legal.first.is_visible():
                            await legal.first.click(timeout=3000)
                            await pg.wait_for_timeout(500)
                            body += '\nPUBLIC LEGAL NOTICE\n' + await pg.locator('body').inner_text(timeout=8000)
                    links=await pg.locator('a').evaluate_all('(xs)=>xs.map(x=>({text:x.innerText,url:x.href}))')
                    raw=await pg.locator('script[type="application/json"]').all_text_contents()
                    social=[]
                    def walk(node):
                        if isinstance(node,dict):
                            for key,value in node.items():
                                if key in ('socialLinks','social_links') and isinstance(value,list):
                                    social.extend({'text':str(x.get('type','social')),'url':x['url']} for x in value if isinstance(x,dict) and isinstance(x.get('url'),str))
                                else:walk(value)
                        elif isinstance(node,list):
                            for value in node:walk(value)
                    for item in raw:
                        try:walk(json.loads(item))
                        except (ValueError,TypeError):pass
                    links=social+links
                    rec={'source':url,'resolved_url':pg.url,'status':resp.status if resp else None,'text':body[:18000],'links':links[:250],'checked_at':datetime.now().isoformat(),'method':'native browser public linked page'}
                    rec['embedded_social_checked']=True
                    rec['contact_controls_checked']=3
                    doc['pages']=[q for q in doc.get('pages',[]) if (q.get('source') or q.get('url'))!=url]+[rec]
                    save(target,doc)
                    print(h,rec['status'],body[:500].replace('\n',' '),flush=True)
                    if h.startswith('discovery_'):
                        print(json.dumps([q for q in links if any(s in q.get('url','') for s in ('instagram.com','youtube.com','mailto:'))],ensure_ascii=False),flush=True)
                except Exception as e:print(h,str(e)[:150],flush=True)
                finally:
                    await pg.close()

async def browse(urls):
    """Read-only native Instagram discovery. Saved links are unreviewed leads."""
    from playwright.async_api import async_playwright
    from datetime import datetime
    from urllib.parse import urlparse
    for url in urls:
        u=urlparse(url)
        if u.scheme!='https' or u.netloc not in ('www.instagram.com','instagram.com'):
            raise ValueError('browse currently supports public Instagram pages only')
        if u.path.startswith(('/direct','/accounts','/settings')):
            raise ValueError('Only public discovery/content pages are allowed')
    folder=P/'native_discovery'/datetime.now().strftime('%Y%m%d_%H%M%S')
    folder.mkdir(parents=True)
    excluded=set(load('excluded_handles.json'))
    current=load('production_reviews.json')
    excluded.update(current)
    for record in current.values():excluded.update(record.get('aliases',[]))
    reserved={'explore','reels','reel','p','direct','accounts','stories','about','legal','privacy'}
    records=[];leads={}
    async with async_playwright() as pw:
        browser=await pw.chromium.connect_over_cdp(CDP)
        for page_no,url in enumerate(urls,1):
            pg=await browser.contexts[0].new_page()
            captured={};response_tasks=[]
            def collect_media(node):
                if isinstance(node,dict):
                    code=node.get('code') or node.get('shortcode')
                    owner=node.get('user') or node.get('owner') or {}
                    if code and isinstance(owner,dict) and owner.get('username'):
                        caption=node.get('caption') or {}
                        text=caption.get('text','') if isinstance(caption,dict) else str(caption)
                        if not text:
                            edges=node.get('edge_media_to_caption',{}).get('edges',[])
                            text=' '.join(x.get('node',{}).get('text','') for x in edges)
                        captured[code]={'handle':owner['username'].lower(),'caption':text,'source_post':'https://www.instagram.com/p/'+code+'/'}
                    for value in node.values():collect_media(value)
                elif isinstance(node,list):
                    for value in node:collect_media(value)
            async def receive(res):
                if 'instagram.com' in res.url and ('graphql' in res.url or '/api/v1/' in res.url):
                    try:collect_media(await asyncio.wait_for(res.json(),timeout=12))
                    except Exception:pass
            def on_response(res):response_tasks.append(asyncio.create_task(receive(res)))
            pg.on('response',on_response)
            try:
                await pg.goto(url,wait_until='domcontentloaded',timeout=35000)
                await pg.wait_for_timeout(2200)
                # Dismiss only the optional notification invitation; never a verification.
                dismiss=pg.get_by_role('button',name=re.compile(r'^(以后再说|Not Now)$',re.I))
                if await dismiss.count()==1:
                    await dismiss.click(timeout=2000)
                for step in range(4):
                    body=await pg.locator('body').inner_text(timeout=15000)
                    shot=folder/f'{page_no}_{step+1}.jpg'
                    await pg.screenshot(path=str(shot),type='jpeg',quality=80)
                    blocked=restricted_page({'text':body}) or any(x in pg.url for x in ('/challenge/','/accounts/login/'))
                    if blocked:
                        records.append({'source':url,'url':pg.url,'restricted':True,'screenshot':str(shot)})
                        print('BROWSE restriction; stop this page',flush=True);break
                    links=await pg.locator('main a[href]').evaluate_all('(xs)=>xs.map(x=>{const r=x.getBoundingClientRect();return {text:x.innerText,url:x.href,alt:x.querySelector("img")?.alt||"",x:r.x,y:r.y,width:r.width,height:r.height,visible:r.bottom>0&&r.top<innerHeight}})')
                    await asyncio.gather(*response_tasks,return_exceptions=True)
                    for link in links:
                        parts=urlparse(link['url']).path.strip('/').split('/')
                        if link.get('visible') and len(parts)==2 and parts[0] in ('p','reel') and parts[1] in captured:
                            media=captured[parts[1]];h=media['handle']
                            if h not in excluded and h not in leads and not (P/'profiles'/f'{h}.json').exists():
                                leads[h]={**media,'url':'https://www.instagram.com/'+h+'/','source':url,'screenshot':str(shot),'status':'unreviewed_native_discovery'}
                    records.append({'source':url,'url':pg.url,'screenshot':str(shot),'text':body[:22000],'links':links})
                    fresh=[]
                    for link in links:
                        parsed=urlparse(link['url']);parts=parsed.path.strip('/').split('/')
                        if parsed.netloc not in ('www.instagram.com','instagram.com') or len(parts)!=1:continue
                        h=parts[0].lower()
                        if h in reserved or not re.fullmatch(r'[a-z0-9._]{2,30}',h):continue
                        if h in excluded or (P/'profiles'/f'{h}.json').exists() or h in leads:continue
                        leads[h]={'handle':h,'url':link['url'],'source':url,'screenshot':str(shot),'status':'unreviewed_native_discovery'}
                        fresh.append(h)
                    print('BROWSE',shot,'NEW',','.join(fresh),flush=True)
                    if step<3:
                        await pg.mouse.wheel(0,850)
                        await pg.wait_for_timeout(1200)
            finally:
                pg.remove_listener('response',on_response)
                await asyncio.gather(*response_tasks,return_exceptions=True)
                await pg.close()
    (folder/'evidence.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
    (folder/'leads.json').write_text(json.dumps(list(leads.values()),ensure_ascii=False,indent=2),encoding='utf8')
    print('Saved native discovery',folder,'leads',len(leads),flush=True)

if __name__=='__main__':
 if sys.argv[1]=='board':
  for h in sys.argv[2:]:board(h)
 elif sys.argv[1]=='browser-links':asyncio.run(browser_links(sys.argv[2:]))
 elif sys.argv[1]=='browse':asyncio.run(browse(sys.argv[2:]))
