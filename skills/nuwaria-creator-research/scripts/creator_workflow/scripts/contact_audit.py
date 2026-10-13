"""Evidence-first public contact recheck of existing Notion records; no outreach."""
import asyncio,json,re
from pathlib import Path
from urllib.parse import urlparse,unquote,parse_qs
from datetime import datetime,timezone
from outreach import Run,read,save,flat,EMAIL,rt,digest

def timestamp():return datetime.now(timezone.utc).isoformat()
def run(project,action,limit):
    base=project/'contact_audit';base.mkdir(exist_ok=True);r=Run(project)
    if action=='collect':
        pages=r.all_pages();save(base/'before.json',pages)
        targets=[]
        for p in pages:
            f=flat(p)
            if EMAIL.search(str(f.get('公开联系方式',''))):continue
            handle=f.get('账号','').lstrip('@')
            urls=list(dict.fromkeys(v for k in ('主页链接','Instagram主页','TikTok主页') if (v:=f.get(k)) and v.startswith('http')))
            cached=[]
            for root in project.parent.glob('candidate_research_*'):
                for h in (handle,'tt__'+handle):
                    path=root/'profiles'/(h+'.json')
                    if path.exists():cached.append(str(path))
            targets.append({'id':p['id'],'handle':handle,'urls':urls,'cached_profiles':cached,'before':f})
        save(base/'targets.json',targets);print('CONTACT_TARGETS',len(targets),flush=True)
    elif action in ('crawl','supplement'):asyncio.run(crawl(base,r,limit,action=='supplement'))
    elif action=='report':
        docs=[read(x) for x in (base/'evidence').glob('*.json')]
        print(json.dumps([{'handle':d['handle'],'emails':d['emails'],'restricted':d['restricted'],'pages':len(d['pages'])} for d in docs],ensure_ascii=False))
    elif action=='prepare':
        decisions=read(base/'decisions.json');targets=read(base/'targets.json')
        current={p['id']:p for p in r.all_pages()};save(base/'preflight.json',list(current.values()))
        sent=r.sent();recipients={e.lower() for m in sent for e in EMAIL.findall(str(m.get('toAddress','')))}
        existing={e.lower() for p in current.values() for e in EMAIL.findall(str(flat(p).get('公开联系方式','')))}
        tracking=r.notion('POST','data_sources/'+r.c['notion_tracking_data_source']+'/query',json={'page_size':100})
        assert not tracking.get('has_more');save(base/'tracking_before.json',tracking['results'])
        plan=[];retained=[]
        for t in targets:
            p=current[t['id']];f=flat(p);decision=decisions[t['handle']]
            assert not f.get('发送日期') and not f.get('回复日期') and not EMAIL.search(str(f.get('公开联系方式','')))
            assert (f.get('联系状态') or {}).get('name','未联系')=='未联系',t['handle']
            if decision['action']=='retain':retained.append({'handle':t['handle'],**decision});continue
            if decision['action']=='update':
                assert decision['email'].lower() not in existing|recipients,'Existing contact: '+t['handle']
                doc=read(base/'evidence'/(t['id']+'.json'))
                assert any(e['email'].lower()==decision['email'].lower() and e['source']==decision['source'] for e in doc['emails'])
                existing.add(decision['email'].lower())
            else:
                for row in tracking['results']:
                    vals=flat(row)
                    assert not any(str(v).strip().lower().lstrip('@')==t['handle'].lower() for v in vals.values()),'Tracking protection: '+t['handle']
            plan.append({'id':t['id'],'handle':t['handle'],**decision})
        save(base/'plan.json',plan);save(base/'review.json',{'digest':digest(plan),'at':timestamp(),'retained':retained})
        from collections import Counter
        print('PREPARED',dict(Counter(d['action'] for d in plan)),'retained',retained,flush=True)
    elif action=='verify':
        plan=read(base/'plan.json');pages=r.all_pages();byid={p['id']:p for p in pages}
        for d in plan:
            if d['action']=='archive':assert d['id'] not in byid
            else:assert flat(byid[d['id']])['公开联系方式']==d['email']
        protected=[p['id'] for p in read(base/'before.json') if flat(p).get('发送日期') or flat(p).get('回复日期')]
        assert all(pid in byid for pid in protected)
        save(base/'verified.json',{'at':timestamp(),'total':len(pages),'updated':sum(d['action']=='update' for d in plan),'removed':sum(d['action']=='archive' for d in plan),'protected_contacted':len(protected)})
        lines=['# Notion 邮箱复查与清理','', '逐条公开来源及删除原因见 decisions.json；原始 Notion 记录备份见 before.json。', '', '| 账号 | 处理 | 邮箱或原因 |', '| --- | --- | --- |']
        for d in plan:
            detail=d.get('email') or ('粉丝数不在 1,000–100,000：'+str(d['followers']) if d['reason']=='followers_out_of_range' else '未取得可用公开邮箱')
            if d.get('access_note') in ('age_restricted_profile','profile_unavailable'):detail+='（主页受限或失效）'
            lines.append('| '+d['handle']+' | '+('补邮箱' if d['action']=='update' else '从 Notion 删除')+' | '+detail+' |')
        (base/'result.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        print('VERIFIED',read(base/'verified.json'),flush=True)
    elif action=='apply':
        plan=read(base/'plan.json');review=read(base/'review.json');assert review['digest']==digest(plan)
        log=read(base/'applied.json') if (base/'applied.json').exists() else {}
        for d in plan:
            if d['id'] in log:continue
            current=r.notion('GET','pages/'+d['id']);f=flat(current)
            contact=str(f.get('公开联系方式',''))
            explicit_archive=d['action']=='archive' and d.get('explicit_user_archive') is True
            assert not current['archived'],'Changed record; review again'
            if explicit_archive:
                assert contact==d['expected_contact'] and f.get('账号','').lstrip('@')==d['handle'],'Changed identity; review again'
                recipients={e.lower() for m in r.sent() for e in EMAIL.findall(str(m.get('toAddress','')))}
                assert not recipients & {e.lower() for e in EMAIL.findall(contact)},'Preserve sent contact'
            else:assert not EMAIL.search(contact),'Changed record; review again'
            assert not f.get('发送日期') and not f.get('回复日期') and (f.get('联系状态') or {}).get('name','未联系')=='未联系','Preserve contacted history'
            if d['action']=='archive':
                assert not f.get('发送日期') and not f.get('回复日期'),'Preserve contacted history'
                result=r.notion('PATCH','pages/'+d['id'],json={'archived':True})
                assert result['archived']
            else:
                result=r.notion('PATCH','pages/'+d['id'],json={'properties':{'公开联系方式':{'rich_text':rt(d['email'])},'联系方式来源':{'rich_text':rt(d['source'])}}})
                assert flat(result)['公开联系方式']==d['email']
            log[d['id']]={'handle':d['handle'],'action':d['action'],'at':timestamp()};save(base/'applied.json',log)
            print('APPLIED',d['handle'],d['action'],flush=True)

async def crawl(base,r,limit,supplement=False):
    from playwright.async_api import async_playwright
    dest=base/'evidence';dest.mkdir(exist_ok=True)
    targets=read(base/'targets.json');stop_platform=set();sem=asyncio.Semaphore(3)
    async with async_playwright() as pw:
        browser=await pw.chromium.connect_over_cdp(read(r.p/'project.json')['cdp'])
        async def one(target):
            path=dest/(target['id']+'.json')
            if path.exists() and not supplement:return
            doc=read(path) if supplement else {'id':target['id'],'handle':target['handle'],'checked_at':timestamp(),'pages':[],'emails':[],'restricted':False}
            initial=len(doc['pages'])
            queue=[(u,0,'supplement' if supplement else 'profile') for u in target['urls']];seen=set()
            for src in ([] if supplement else target['cached_profiles']):
                old=read(src);u=old.get('user',{});urls=[u.get('external_url')]+[x.get('url') for x in u.get('bio_links',[])]
                for link in urls:
                    if link and link.startswith('http'):queue.append((link,0,'cached official profile link: '+src))
            while queue and len(doc['pages'])<initial+10:
                url,depth,source=queue.pop(0)
                url=url.split('#')[0]
                if any(s in urlparse(url).netloc.lower() for s in ('meta.ai','muse.ai','meta.com','facebook.com','buffer.com')):continue
                if url in seen:continue
                seen.add(url);host=urlparse(url).netloc.lower()
                platform='instagram' if 'instagram.com' in host else 'tiktok' if 'tiktok.com' in host else None
                if platform in stop_platform:
                    doc['restricted']=True;doc['pages'].append({'url':url,'error':'Platform access stopped after challenge'});continue
                pg=await browser.contexts[0].new_page()
                rec={'url':url,'source':source}
                try:
                    response=await pg.goto(url,wait_until='domcontentloaded',timeout=25000)
                    await pg.wait_for_timeout(1100)
                    if platform:
                        try:await pg.wait_for_function("/followers|粉丝|找不到|无法访问|受限主页/.test(document.body.innerText)",timeout=7000)
                        except Exception:pass
                        if platform=='instagram':
                            more=pg.get_by_text('更多',exact=True)
                            for index in range(await more.count()):
                                item=more.nth(index)
                                if await item.is_visible():
                                    try:await item.click(timeout=1500);await pg.wait_for_timeout(300)
                                    except Exception:pass
                                    break
                    body=await pg.locator('body').inner_text(timeout=8000)
                    links=await pg.locator('a[href]').evaluate_all('(xs)=>xs.map(x=>({text:x.innerText,url:x.href}))')
                    embedded=await pg.locator('script[type="application/json"]').all_text_contents()
                    def walk(node):
                        if isinstance(node,dict):
                            for key,value in node.items():
                                if key in ('socialLinks','social_links') and isinstance(value,list):
                                    links.extend({'text':str(x.get('type','social')),'url':x['url']} for x in value if isinstance(x,dict) and isinstance(x.get('url'),str))
                                else:walk(value)
                        elif isinstance(node,list):
                            for value in node:walk(value)
                    for raw in embedded:
                        try:walk(json.loads(raw))
                        except ValueError:pass
                    rec.update(resolved_url=pg.url,status=response.status if response else None,text=body[:24000],links=links)
                    if platform:
                        match=re.search(r'([\d,.]+)\s*([kKmM万]?)\s*(?:粉丝|followers)',body,re.I)
                        if match:
                            number=float(match[1].replace(',',''))*{'k':1000,'m':1000000,'万':10000,'':1}.get(match[2].lower(),1)
                            rec['followers']=int(number)
                            if source=='profile':doc['followers']=int(number)
                            if source=='profile' and not 1000<=number<=100000:
                                doc['out_of_range']=True;queue.clear();continue
                    blocked=any(s in body.lower() for s in ('verify you are human','just a moment...','verify to continue','access denied','captcha','验证您','安全验证')) or any(s in pg.url for s in ('/challenge/','/accounts/login/')) or (response and response.status in (403,429))
                    if blocked:
                        rec['restricted']=True;doc['restricted']=True
                        if platform:stop_platform.add(platform)
                        continue
                    if response and response.status>=400:rec['error']='HTTP '+str(response.status);doc['restricted']=True;continue
                    meta=await pg.locator('meta[name="description"],meta[property="og:description"]').evaluate_all('(xs)=>xs.map(x=>x.content)')
                    rec['meta']=meta
                    for e in sorted(set(EMAIL.findall(body+' '+' '.join(meta)+' '+' '.join(unquote(x['url']) for x in links if x['url'].startswith('mailto:'))))):
                        doc['emails'].append({'email':e,'source':pg.url})
                    for x in links:
                        link=x['url'];label=x['text'].lower()
                        if 'linktr.ee' in host and (urlparse(link).netloc==host or (label and label not in body.split('Cookie Preferences')[0].lower())):continue
                        if 'l.instagram.com/' in link:link=parse_qs(urlparse(link).query).get('u',[link])[0]
                        if not link.startswith(('https://','http://')):continue
                        lh=urlparse(link).netloc.lower()
                        lp=urlparse(link).path
                        if 'linktr.ee' in lh and lp.startswith(('/s/','/blog','/solutions','/discover','/marketplace','/features','/digital-business-cards')):continue
                        if 'beacons.ai' in lh and lp.startswith(('/i/','/signup','/login')):continue
                        social=any(s in lh for s in ('instagram.com','tiktok.com','facebook.com','pinterest.com','youtube.com','twitter.com','threads.com','threads.net'))
                        if social or any(s in lh for s in ('meta.ai','muse.ai','meta.com','buffer.com')):continue
                        contact=any(s in (label+' '+urlparse(link).path).lower() for s in ('contact','about','work with','work-with','media','portfolio','email','collab'))
                        hub=any(s in host for s in ('linktr.ee','beacons.ai','bio.site','stan.store','start.page'))
                        if depth<2 and (contact or (platform and lh not in ('help.instagram.com','about.meta.com','privacycenter.instagram.com')) or (hub and any(s in label for s in ('website','blog','official','substack')))):
                            queue.append((link,depth+1,pg.url))
                except Exception as e:rec['error']=str(e)[:250];doc['restricted']=True
                finally:
                    doc['pages'].append(rec);await pg.close()
            if queue:doc['truncated']=True
            save(path,doc)
            print('CONTACT',target['handle'],'emails',len(doc['emails']),'restricted',doc['restricted'],'pages',len(doc['pages']),flush=True)

        async def guarded(target):
            async with sem:await one(target)
        pending=read(base/'followup_queue.json')[:limit] if supplement else [t for t in targets if not (dest/(t['id']+'.json')).exists()][:limit]
        await asyncio.gather(*(guarded(t) for t in pending))
