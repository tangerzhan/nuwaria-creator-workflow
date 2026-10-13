"""Read public channel metadata for cross-platform identity and follower checks."""
import json,re,sys,requests
from datetime import datetime,timezone
from workflow_context import P

def youtube(url):
    res=requests.get(url,params={'hl':'en'},headers={'Accept-Language':'en-US,en;q=0.9'},timeout=40);res.raise_for_status()
    if 'youtu.be/' in url or '/watch' in url:
        player=re.search(r'var ytInitialPlayerResponse = (.*?);</script>',res.text)
        if not player:raise ValueError('Public video channel identity unavailable')
        details=json.loads(player.group(1)).get('videoDetails',{})
        channel_id=details.get('channelId','')
        if not re.fullmatch(r'UC[A-Za-z0-9_-]+',channel_id):raise ValueError('Public video channel ID unavailable')
        result=youtube('https://www.youtube.com/channel/'+channel_id)
        result['identity_source']=url
        result['video_author']=details.get('author')
        return result
    match=re.search(r'var ytInitialData = (.*?);</script>',res.text)
    if not match:raise ValueError('Public YouTube channel data unavailable')
    data=json.loads(match.group(1));texts=[];videos=[]
    def walk(obj):
        if isinstance(obj,dict):
            if isinstance(obj.get('content'),str):texts.append(obj['content'])
            if isinstance(obj.get('simpleText'),str):texts.append(obj['simpleText'])
            if obj.get('videoRenderer'):videos.append(obj['videoRenderer'])
            for v in obj.values():walk(v)
        elif isinstance(obj,list):
            for v in obj:walk(v)
    walk(data)
    counts=[t for t in texts if re.fullmatch(r'[\d.,]+\s*[kKmMbB]?\s+subscribers?',t)]
    if not counts:raise ValueError('Public subscriber count unavailable')
    raw=counts[0];m=re.match(r'([\d.,]+)\s*([kKmMbB]?)',raw)
    count=round(float(m[1].replace(',',''))*{'':1,'k':1000,'m':1000000,'b':1000000000}[m[2].lower()])
    return {'platform':'YouTube','url':url,'resolved_url':res.url,'followers':count,'count_display':raw,'rounded':bool(m[2]),'checked_at':datetime.now(timezone.utc).isoformat(),'metadata':data.get('metadata'), 'header':data.get('header'),'videos':videos,'method':'Public native channel HTML ytInitialData; subscriber count may be rounded'}

def run(items):
    dest=P/'channel_checks';dest.mkdir(exist_ok=True)
    for item in items:
        key,url=item.split('=',1)
        try:
            d=youtube(url);(dest/(key+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
            print(key,d['followers'],d['count_display'],len(d['videos']),'videos',flush=True)
        except Exception as e:
            (dest/(key+'.json')).write_text(json.dumps({'url':url,'error':str(e),'checked_at':datetime.now(timezone.utc).isoformat()},ensure_ascii=False),encoding='utf8')
            print(key,'UNVERIFIED',str(e)[:180],flush=True)

if __name__=='__main__':run(sys.argv[1:])
