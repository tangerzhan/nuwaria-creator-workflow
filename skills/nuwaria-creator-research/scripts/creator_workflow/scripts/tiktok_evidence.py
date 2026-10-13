"""Evidence from captured public TikTok responses and native post pages."""
import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright
from workflow_context import P, CDP, CONFIG, DATE, CUTOFF

def read(path):
    return json.loads(path.read_text(encoding='utf8'))

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')

def key(handle):
    return 'tt__' + handle.removeprefix('tt__').lstrip('@').lower()

def media_url(value):
    if isinstance(value, str):
        return value if value.startswith('https://') else None
    if isinstance(value, dict):
        return next((u for u in value.get('urlList', []) if isinstance(u, str) and u.startswith('https://')), None)
    return None

def render_native(handles):
    from fast_audit import render
    for handle in handles:
        h = key(handle)
        profile = read(P/'profiles'/f'{h}.json')
        if profile.get('platform') != 'TikTok':
            raise ValueError('Native TikTok profile required')
        count = profile.get('user', {}).get('follower_count')
        if not isinstance(count, (int, float)) or not CONFIG.get('min_followers', 1) <= count <= CONFIG.get('max_followers', float('inf')):
            raise ValueError(f'{h}: main platform follower gate not passed')
        latest = next((p['date'] for p in profile.get('posts', []) if p.get('media_type') == 2 and p['date'] <= DATE), '')
        if len(profile.get('posts', [])) < 12 or not CUTOFF <= latest <= DATE:
            raise ValueError(f'{h}: 12-post or recent-video gate not passed')
        raw = read(P/'tiktok_raw'/f'{h.removeprefix("tt__")}.json')
        wanted = {p['code'] for p in profile['posts'][:12]}
        media = {}
        def walk(node):
            if isinstance(node, dict):
                code = str(node.get('id', ''))
                author = node.get('author') or {}
                if code in wanted and isinstance(author, dict) and author.get('uniqueId', '').lower() == profile['platform_handle'].lower():
                    video = node.get('video') or {}
                    photos = (node.get('imagePost') or {}).get('images') or []
                    image = media_url(photos[0].get('imageURL')) if photos else None
                    play = media_url(video.get('playAddr')) or media_url(video.get('downloadAddr'))
                    candidate = {'video': play, 'image': image, 'carousel': [{'image': media_url(p.get('imageURL')), 'media_type': 1} for p in photos]}
                    if image or play:
                        media[code] = candidate
                for child in node.values():
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)
        walk(raw['captured'])
        if wanted - media.keys():
            raise ValueError(f'{h}: native playable media missing for {sorted(wanted-media.keys())}; no thumbnail substitution')
        write(P/'native_media'/f'{h}.json', {'source': profile['url'], 'platform': 'TikTok', 'checked_at': raw['checked_at'], 'media': media})
        if render([h], stop_on_forbidden=True) is False:
            return

async def comments_native(items):
    async with async_playwright() as a:
        browser = await a.chromium.connect_over_cdp(CDP)
        page = await browser.contexts[0].new_page()
        try:
            for item in items:
                handle, indices = item.split(':', 1)
                h = key(handle)
                profile = read(P/'profiles'/f'{h}.json')
                audit_path = P/'post_audits'/h/'audit.json'
                audit = read(audit_path)
                for index in map(int, indices.split(',')):
                    if not 1 <= index <= 12:
                        raise ValueError('Comment index must be in latest 12')
                    entry = audit[index-1]
                    if entry['url'] != profile['posts'][index-1]['url']:
                        raise ValueError('Post/audit URL mismatch')
                    try:
                        await page.goto(entry['url'], wait_until='domcontentloaded', timeout=40000)
                        await page.wait_for_timeout(4500)
                        body = await page.locator('body').inner_text(timeout=10000)
                        if any(s in body.lower() for s in ['verify to continue', 'drag the slider', 'security verification', 'complete the puzzle', 'too many requests']):
                            entry['comments_error'] = 'Native TikTok access verification or rate limit; stopped'
                            write(audit_path, audit)
                            print(h, index, 'RESTRICTION', flush=True)
                            return
                        entry['public_text'] = body
                        entry['comments_method'] = 'Native TikTok post page visible text; review required, may include login prompt or no loaded comments'
                        entry['comments_checked_at'] = datetime.now().isoformat()
                        entry.pop('comments_error', None)
                        await page.screenshot(path=str(audit_path.parent/f'{index:02d}_comments.png'))
                        print(h, index, 'native text', len(body), flush=True)
                    except Exception as exc:
                        entry['comments_error'] = str(exc)[:250]
                        print(h, index, 'ERROR', str(exc)[:120], flush=True)
                    write(audit_path, audit)
        finally:
            await page.close()

async def capture_browser(handles):
    """Observe public TikTok videos in the user's native browser, without downloads.

    No alternate media URLs, request-header changes, or verification bypasses.
    Photos capture only the largest visible photo on the native post page;
    review must confirm it is the actual post, never a recommendation thumbnail.
    """
    from PIL import Image, ImageDraw
    from pathlib import Path
    stop_file = P/'tiktok_native_access_stop.json'
    if stop_file.exists():
        raise ValueError('Native TikTok access is stopped; preserve this record until verification is resolved by the user.')
    history = read(P/'historical_exclusions.json')
    prior = read(P/'production_reviews.json')
    excluded = set(history.get('handles', []))
    known_emails = set(history.get('emails', []))
    for review_handle, review in prior.items():
        if review.get('verdict') == 'include':
            excluded.update([review_handle, *review.get('aliases', [])])
            if review.get('public_email'):
                known_emails.add(review['public_email'].lower())
    async with async_playwright() as a:
        browser = await a.chromium.connect_over_cdp(CDP)
        page = await browser.contexts[0].new_page()
        try:
            for handle in handles:
                h = key(handle)
                profile = read(P/'profiles'/f'{h}.json')
                count = profile.get('user', {}).get('follower_count')
                if h in excluded or profile['platform_handle'].lower() in excluded:
                    print(h, 'historical identity: skipped', flush=True)
                    continue
                if any(e.lower() in known_emails for e in profile.get('emails', [])):
                    print(h, 'historical email: skipped', flush=True)
                    continue
                if not isinstance(count, (int, float)) or not CONFIG.get('min_followers', 1) <= count <= CONFIG.get('max_followers', float('inf')):
                    print(h, 'follower gate: skipped', flush=True)
                    continue
                posts = profile.get('posts', [])[:12]
                latest = next((p['date'] for p in profile.get('posts', []) if p.get('media_type') == 2 and p['date'] <= DATE), '')
                if len(posts) != 12 or not CUTOFF <= latest <= DATE or not profile.get('emails'):
                    print(h, 'profile gate: skipped', flush=True)
                    continue
                dest = P/'post_audits'/h
                dest.mkdir(parents=True, exist_ok=True)
                audit_path = dest/'audit.json'
                old = read(audit_path) if audit_path.exists() else []
                audit = []
                for number, post in enumerate(posts, 1):
                    entry = next((e for e in old if e.get('url') == post['url'] and e.get('method', '').startswith('Native browser video') and not e.get('error') and len(e.get('frames', [])) == 4 and all(Path(f['file']).exists() for f in e['frames'])), None)
                    if entry:
                        entry['index'] = number
                        audit.append(entry)
                        continue
                    entry = {'index': number, 'url': post['url'], 'caption': post['caption'], 'checked_at': datetime.now().isoformat(), 'method': 'Native browser video at four seek positions; not full playback', 'frames': []}
                    audit.append(entry)
                    try:
                        response = await page.goto(post['url'], wait_until='domcontentloaded', timeout=40000)
                        await page.wait_for_timeout(2500)
                        body = await page.locator('body').inner_text(timeout=10000)
                        if (response and response.status in (403, 429)) or any(s in body.lower() for s in ['verify to continue', 'drag the slider', 'drag the puzzle', 'security verification', 'complete the puzzle', 'too many requests', 'verify you are human']):
                            entry['error'] = 'Native page verification or access restriction; stopped without retry'
                            write(stop_file, {'url':post['url'],'detected_at':datetime.now().isoformat(),'reason':entry['error']})
                            write(audit_path, audit)
                            print(h, number, 'ACCESS STOP', flush=True)
                            return
                        entry['public_text'] = body
                        entry['comments_method'] = 'Visible native post page text, requires actual review; not inferred from counts'
                        if post.get('media_type') != 2:
                            await page.wait_for_timeout(1000)
                            candidates = await page.locator('img').evaluate_all('(imgs) => imgs.map((im,i)=>{const r=im.getBoundingClientRect();return {i,w:r.width,h:r.height,nw:im.naturalWidth,top:r.top,left:r.left};}).filter(x=>x.w>=250&&x.h>=250&&x.nw>=300&&x.top>=0&&x.top<innerHeight&&x.left>=0&&x.left<innerWidth).sort((a,b)=>b.w*b.h-a.w*a.h)')
                            if not candidates:
                                raise ValueError('No large visible native post photo; thumbnail not substituted')
                            frame = dest/f'{number:02d}_browser_photo.png'
                            await page.locator('img').nth(candidates[0]['i']).screenshot(path=str(frame))
                            await page.screenshot(path=str(dest/f'{number:02d}_browser_page.png'))
                            entry['method'] = 'Native browser first visible photo only; carousel not traversed; actual post identity requires image review'
                            entry['frames'] = [{'file':str(frame),'method':'Native visible photo screenshot; first photo only'}]
                            canvas=Image.new('RGB',(1200,510),'white')
                            draw=ImageDraw.Draw(canvas)
                            draw.text((5,5),f'{h} POST {number} {post["date"]} FIRST PHOTO ONLY',fill='black')
                            im=Image.open(frame).convert('RGB');im.thumbnail((295,460));canvas.paste(im,(0,30))
                            canvas.save(dest/f'{number:02d}_sheet.jpg')
                            write(audit_path,audit)
                            print(h,number,'native first photo; visual confirmation required',flush=True)
                            continue
                        video = page.locator('video:visible').first
                        await video.wait_for(state='visible', timeout=10000)
                        await video.evaluate('(v) => { v.muted=true; v.play().catch(()=>{}); }')
                        await page.wait_for_function('() => Array.from(document.querySelectorAll("video")).some(v => v.getBoundingClientRect().width > 0 && v.readyState >= 2 && Number.isFinite(v.duration) && v.duration > 0 && v.videoWidth > 0)', timeout=12000)
                        duration = await video.evaluate('(v) => v.duration')
                        entry['duration'] = duration
                        for frame_index, fraction in enumerate([.05, .35, .65, .9]):
                            target = duration * fraction
                            await video.evaluate('(v,t) => new Promise((resolve,reject) => { v.pause(); const timer=setTimeout(()=>{v.removeEventListener("seeked",done);reject(new Error("seek timeout"));},8000); const done=()=>{clearTimeout(timer);resolve();}; v.addEventListener("seeked",done,{once:true}); v.currentTime=t; })', target)
                            await page.wait_for_timeout(180)
                            state = await video.evaluate('(v) => ({currentTime:v.currentTime,readyState:v.readyState,width:v.videoWidth,error:v.error&&v.error.code})')
                            if state['error'] or state['readyState'] < 2 or abs(state['currentTime']-target) > 1:
                                raise ValueError('Native frame seek not confirmed')
                            frame = dest/f'{number:02d}_browser_{frame_index}.png'
                            body_now = await page.locator('body').inner_text(timeout=10000)
                            if any(s in body_now.lower() for s in ['verify to continue','drag the slider','drag the puzzle','security verification','complete the puzzle','too many requests','verify you are human']):
                                entry['error']='Verification appeared during native playback; stopped'
                                write(stop_file,{'url':post['url'],'detected_at':datetime.now().isoformat(),'reason':entry['error']})
                                write(audit_path,audit)
                                return
                            await video.screenshot(path=str(frame))
                            entry['frames'].append({'file': str(frame), 'duration': duration, 'currentTime': state['currentTime'], 'method': 'Visible native HTML5 video screenshot after confirmed seek'})
                        canvas = Image.new('RGB', (1200, 510), 'white')
                        draw = ImageDraw.Draw(canvas)
                        draw.text((5,5), f'{h} POST {number} {post["date"]}', fill='black')
                        for index, frame in enumerate(entry['frames']):
                            im = Image.open(frame['file']).convert('RGB')
                            im.thumbnail((295,460))
                            canvas.paste(im,(index*300,30))
                            draw.text((index*300+3,492),f'{frame["currentTime"]:.1f} sec',fill='black')
                        canvas.save(dest/f'{number:02d}_sheet.jpg')
                        print(h, number, 'native frames 4', flush=True)
                    except Exception as exc:
                        entry['error'] = str(exc)[:250]
                        print(h, number, 'INCOMPLETE', str(exc).splitlines()[0][:140], flush=True)
                    write(audit_path, audit)
                    if entry.get('error'):
                        # Avoid an expensive repeated failure on another post.
                        break
                write(audit_path, audit)
        finally:
            await page.close()
