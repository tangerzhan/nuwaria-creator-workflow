import asyncio,json,sys,subprocess,io
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image,ImageDraw
from playwright.async_api import async_playwright
from workflow_context import research_page, P, CONFIG, DATE, TARGET, CUTOFF, OUTPUT, CDP
import shutil,os
FF=Path(CONFIG['ffmpeg_bin']) if CONFIG.get('ffmpeg_bin') else None
def executable(name):
    if FF:
        path=FF/(name+'.exe' if os.name=='nt' else name)
        if path.is_file():return str(path)
        raise FileNotFoundError('Missing media executable: '+str(path))
    found=shutil.which(name)
    if not found:raise FileNotFoundError(name+' is not on PATH; configure ffmpeg_bin')
    return found
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def media_map(capt):
    out={}
    def walk(o):
        if isinstance(o,dict):
            code=o.get('code') or o.get('shortcode')
            if code:
                vv=o.get('video_versions') or []
                vu=(min(vv,key=lambda x:abs((x.get('width') or 720)-720)).get('url') if vv else o.get('video_url'))
                imgs=(o.get('image_versions2') or {}).get('candidates') or []
                carousel=o.get('carousel_media') or []
                if not imgs and carousel:imgs=(carousel[0].get('image_versions2') or {}).get('candidates') or []
                iu=(imgs[0].get('url') if imgs else o.get('display_url'))
                if vu or iu:
                    prior=out.get(code,{})
                    slides=[]
                    for slide in carousel:
                        images=(slide.get('image_versions2') or {}).get('candidates') or []
                        if images:slides.append({'image':images[0]['url'],'media_type':slide.get('media_type')})
                    # Keep public tagged identities for source-backed discovery.
                    # A tag is a lead, never proof of ownership or a paid partnership.
                    tagged=set(prior.get('tagged_users',[]))
                    for node in [o,*carousel]:
                        for tag in (node.get('usertags') or {}).get('in',[]):
                            name=(tag.get('user') or {}).get('username')
                            if name:tagged.add(name)
                        for edge in (node.get('edge_media_to_tagged_user') or {}).get('edges',[]):
                            name=((edge.get('node') or {}).get('user') or {}).get('username')
                            if name:tagged.add(name)
                        for author in node.get('coauthor_producers') or []:
                            if author.get('username'):tagged.add(author['username'])
                    out[code]={'video':vu or prior.get('video'),'image':iu or prior.get('image'),'carousel':slides or prior.get('carousel',[]),'tagged_users':sorted(tagged)}
            for x in o.values():walk(x)
        elif isinstance(o,list):
            for x in o:walk(x)
    walk(capt);return out
async def capture(handles):
    async with async_playwright() as pw:
        b=await pw.chromium.connect_over_cdp(CDP)
        async with research_page(b.contexts[0]) as pg:
            for h in handles:
                r=load('profiles/'+h+'.json');cap=[];tasks=[]
                async def response(res):
                    if 'instagram.com' in res.url and ('graphql' in res.url or '/api/v1/' in res.url):
                        try:cap.append(await asyncio.wait_for(res.json(),timeout=15))
                        except:pass
                def event(res):tasks.append(asyncio.create_task(response(res)))
                pg.on('response',event)
                try:
                    await pg.goto(r['url'],wait_until='domcontentloaded',timeout=35000);await pg.wait_for_timeout(3000)
                    body=await pg.locator('body').inner_text(timeout=8000)
                    if any(s in body.lower() for s in ['challenge_required','try again later','confirm it’s you']):
                        print('ACCESS STOP',h,flush=True);break
                    target={x['code'] for x in r['posts'][:12]}
                    for _ in range(4):
                        await asyncio.gather(*tasks,return_exceptions=True)
                        m=media_map(cap)
                        if target <= set(m) and all(m[x['code']].get('video') for x in r['posts'][:12] if x.get('media_type')==2):break
                        await pg.evaluate('window.scrollTo(0,document.body.scrollHeight)');await pg.wait_for_timeout(1800)
                    await asyncio.gather(*tasks,return_exceptions=True);m=media_map(cap)
                    dest=P/'native_media';dest.mkdir(exist_ok=True)
                    save('native_media/'+h+'.json',{'checked_at':datetime.now().isoformat(),'source':r['url'],'media':{k:v for k,v in m.items() if k in target}})
                    print(h,'media',len(target&set(m)),'videos',sum(bool(m.get(x['code'],{}).get('video')) for x in r['posts'][:12]),flush=True)
                except Exception as e:print(h,'CAPTURE ERROR',str(e)[:180],flush=True)
                finally:pg.remove_listener('response',event)


def render_carousel(items):
    """Supplement selected photo carousels without replacing the 12-post audit."""
    for item in items:
        h,indices=item.split(':',1)
        r=load('profiles/'+h+'.json');m=load('native_media/'+h+'.json')
        dest=P/'post_audits'/h;dest.mkdir(exist_ok=True,parents=True)
        for index in map(int,indices.split(',')):
            if not 1<=index<=12:raise ValueError('Carousel index must be in recent 12')
            post=r['posts'][index-1];slides=m['media'][post['code']].get('carousel',[])
            evidence={'url':post['url'],'checked_at':datetime.now().isoformat(),'method':'Selected carousel still images; video slides are thumbnails, not playback','slides':[]}
            for number,slide in enumerate(slides,1):
                path=dest/f'{index:02d}_slide_{number:02d}.jpg'
                if not path.exists():
                    response=requests.get(slide['image'],timeout=45)
                    if response.status_code==429:
                        print('HTTP 429: stopped carousel capture',flush=True);return
                    response.raise_for_status();path.write_bytes(response.content)
                evidence['slides'].append({'index':number,'file':str(path),'media_type':slide['media_type']})
            if slides:
                canvas=Image.new('RGB',(1200,440*((len(slides)+3)//4)),'white');draw=ImageDraw.Draw(canvas)
                for n,slide in enumerate(evidence['slides']):
                    im=Image.open(slide['file']).convert('RGB');im.thumbnail((294,408))
                    x=(n%4)*300;y=(n//4)*440
                    draw.text((x+3,y+3),f'{h} POST {index} SLIDE {n+1}',fill='black');canvas.paste(im,(x,y+25))
                canvas.save(dest/f'{index:02d}_carousel.jpg')
            save('post_audits/'+h+f'/{index:02d}_carousel.json',evidence)
            print(h,index,'carousel slides',len(slides),flush=True)
def render_detail(items):
    """Additional evenly spaced decoded frames; does not replace the original audit."""
    for item in items:
        h,indices=item.split(':',1)
        r=load('profiles/'+h+'.json');m=load('native_media/'+h+'.json')
        dest=P/'post_audits'/h
        for index in map(int,indices.split(',')):
            if not 1<=index<=12:raise ValueError('Detail index must be in latest 12')
            post=r['posts'][index-1]
            if post.get('media_type')!=2:raise ValueError('Use media-carousel for photos')
            result=dest/f'{index:02d}_detail.jpg'
            if result.exists():continue
            res=requests.get(m['media'][post['code']]['video'],timeout=45)
            if res.status_code in (403,429):
                print('Access restriction: stopped detail capture',flush=True);return
            res.raise_for_status()
            cache=dest/f'{index:02d}_detail.mp4';cache.write_bytes(res.content)
            try:
                probe=subprocess.run([executable('ffprobe'),'-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(cache)],capture_output=True,text=True,check=True)
                duration=float(probe.stdout.strip());frames=[]
                canvas=Image.new('RGB',(1200,1320),'white');draw=ImageDraw.Draw(canvas)
                for j in range(12):
                    t=duration*(j+.5)/12;path=dest/f'{index:02d}_detail_{j:02d}.jpg'
                    subprocess.run([executable('ffmpeg'),'-hide_banner','-loglevel','error','-threads','1','-ss',str(t),'-i',str(cache),'-frames:v','1','-vf','scale=360:-2','-y',str(path)],capture_output=True,check=True)
                    im=Image.open(path).convert('RGB');im.thumbnail((295,410));x=(j%4)*300;y=(j//4)*440
                    canvas.paste(im,(x,y+25));draw.text((x+5,y+5),f'{h} #{index} {t:.1f}s',fill='black')
                    frames.append({'file':str(path),'currentTime':t,'method':'additional decoded video frame'})
                canvas.save(result)
                save(f'post_audits/{h}/{index:02d}_detail.json',{'url':post['url'],'checked_at':datetime.now().isoformat(),'method':'12 additional sampled frames, not full playback','frames':frames})
                print(h,index,'detail decoded',flush=True)
            finally:cache.unlink(missing_ok=True)

def render(handles, stop_on_forbidden=False):
    from threading import Event
    throttled=Event()
    for h in handles:
        r=load('profiles/'+h+'.json');m=load('native_media/'+h+'.json');dest=P/'post_audits'/h;dest.mkdir(exist_ok=True,parents=True)
        prev=load('post_audits/'+h+'/audit.json') if (dest/'audit.json').exists() else []
        def one(item):
            i,post=item;old=next((x for x in prev if x['index']==i+1),{})
            if old.get('url')==post['url'] and not old.get('error') and len(old.get('frames',[])) in (1,4) and all(not f.get('error') and Path(f['file']).exists() for f in old['frames']) and (dest/f'{i+1:02d}_sheet.jpg').exists():
                return old
            a={'index':i+1,'url':post['url'],'caption':post['caption'],'checked_at':datetime.now().isoformat(),'method':'Four frames extracted from public native-profile media via FFmpeg; not full playback','media_response_source':m['source'],'public_text':old.get('public_text','')}
            frames=[]
            try:
                md=m['media'][post['code']];isvid=post.get('media_type')==2
                url=md['video'] if isvid else md['image'];a['public_media_url']=url
                if not url:raise ValueError('Public native response has no media URL')
                cache=dest/f'{i+1:02d}_media.mp4' if isvid else dest/f'{i+1:02d}_original.jpg'
                if not cache.exists():
                    if throttled.is_set():raise RuntimeError('Batch stopped after access restriction; no download attempted')
                    res=requests.get(url,timeout=45)
                    if res.status_code==429 or (stop_on_forbidden and res.status_code==403):throttled.set()
                    res.raise_for_status();cache.write_bytes(res.content)
                if isvid:
                    probe=subprocess.run([executable('ffprobe'),'-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(cache)],capture_output=True,text=True,check=True)
                    duration=float(probe.stdout.strip());a['duration']=duration
                    for j,f in enumerate([.05,.35,.65,.9]):
                        t=duration*f;path=dest/f'{i+1:02d}_{j}.png'
                        subprocess.run([executable('ffmpeg'),'-hide_banner','-loglevel','error','-threads','1','-ss',str(t),'-i',str(cache),'-frames:v','1','-vf','scale=480:-2','-y',str(path)],capture_output=True,check=True)
                        frames.append({'file':str(path),'duration':duration,'currentTime':t,'error':None,'method':'decoded video frame'})
                    cache.unlink()
                else:
                    frames=[{'file':str(cache),'method':'original first photo'}]
                a['frames']=frames
                canvas=Image.new('RGB',(1200,510),'white');draw=ImageDraw.Draw(canvas);draw.text((5,5),f'{h} POST {i+1} {post["date"]}',fill='black')
                for j,fr in enumerate(frames):
                    im=Image.open(fr['file']).convert('RGB');im.thumbnail((295,460));canvas.paste(im,(j*300,30));draw.text((j*300+3,492),str(round(fr.get('currentTime') or 0,1))+' sec',fill='black')
                canvas.save(dest/f'{i+1:02d}_sheet.jpg')
            except Exception as e:a['error']=str(e)[:300]
            return a
        with ThreadPoolExecutor(max_workers=1 if stop_on_forbidden else 3) as pool:audits=list(pool.map(one,enumerate(r['posts'][:12])))
        save('post_audits/'+h+'/audit.json',audits)
        errors = [(x['index'], x['error']) for x in audits if x.get('error')]
        print(f'{h} 处理完成：{len(audits) - len(errors)}/{len(audits)} 条；错误：{len(errors)} 条', flush=True)
        for index, error in errors:
            print(f'  第 {index} 条失败：{error}', flush=True)
        if throttled.is_set():
            print('Access restriction: stopped media batch; remaining accounts were not requested.',flush=True)
            return False
    return True
