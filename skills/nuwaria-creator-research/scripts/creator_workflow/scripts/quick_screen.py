import json,sys
from pathlib import Path
from PIL import Image,ImageDraw
from workflow_context import P, CONFIG, DATE, TARGET, CUTOFF, OUTPUT, CDP
sys.stdout.reconfigure(encoding='utf8')
hs=[h for h in sys.argv[1:] if (P/'profiles'/f'{h}.json').exists()]
if not hs: sys.exit('No captured profiles')
out=Image.new('RGB',(1800,((len(hs)+2)//3)*850),'white');draw=ImageDraw.Draw(out)
for i,h in enumerate(hs):
    r=json.loads((P/'profiles'/f'{h}.json').read_text(encoding='utf8'));u=r.get('user',{})
    print(h,u.get('follower_count'),u.get('biography'), '\nLINK',u.get('external_url'), 'LATEST',[(x['date'],x.get('media_type')) for x in r.get('posts',[])[:2]])
    print('LATEST VIDEO',next((x['date'] for x in r.get('posts',[]) if x.get('media_type')==2),'NONE'))
    f=P/'screenshots'/f'{h}.png'
    if r.get('platform')=='TikTok':f=P/'screenshots'/f'tt_{r["platform_handle"]}.png'
    x=(i%3)*600;y=(i//3)*850
    draw.text((x+10,y+5),h,fill='black')
    if f.exists():
        try:
            im=Image.open(f);w,ht=im.size
            im=im.crop((int(w*.12),min(500,ht),int(w*.9),min(2100,ht)))
            im.thumbnail((590,815));out.paste(im,(x+5,y+30))
        except Exception as e:print(h,'IMAGE ERROR',e)
out.save(P/'quick_screen.jpg')
