import json,re,sys
from pathlib import Path
from urllib.parse import urlparse,urljoin,unquote
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import requests
from workflow_context import P, CONFIG, DATE, TARGET, CUTOFF, OUTPUT, CDP
EMAIL=re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

def source_links(urls):
 """Read public discovery/contact links without inventing an Instagram profile."""
 from datetime import datetime
 import hashlib
 dest=P/'discovery_links';dest.mkdir(exist_ok=True)
 for url in urls:
  if urlparse(url).scheme not in ('http','https'):raise ValueError('Public HTTP(S) URL required')
  out={'source':url,'checked_at':datetime.now().isoformat()}
  try:
   res=requests.get(url,timeout=20);res.raise_for_status()
   if not res.encoding or res.encoding.lower()=='iso-8859-1':res.encoding='utf-8'
   soup=BeautifulSoup(res.text,'html.parser')
   body=soup.get_text(' ',strip=True)
   if any(t in body.lower() for t in ('verify you are human','checking your browser','just a moment...')):
    out['access_stopped']='Public page verification; no retry or bypass'
   else:
    links=[{'text':a.get_text(' ',strip=True)[:120],'url':urljoin(res.url,a['href'])} for a in soup.select('a[href]') if a['href'].startswith(('http','/','mailto:'))]
    for tag in soup(['script','style']):tag.decompose()
    body=soup.get_text(' ',strip=True)
    out.update(resolved_url=res.url,links=links[:300],text=body[:18000],emails=sorted(set(EMAIL.findall(body+' '+' '.join(x['url'] for x in links if x['url'].startswith('mailto:'))))))
  except requests.RequestException as exc:out['error']=str(exc)[:200]
  path=dest/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.json')
  path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
  print(json.dumps({'source':url,'file':str(path),'emails':out.get('emails',[]),'links':[x for x in out.get('links',[]) if any(t in x['url'] for t in ('instagram.com','youtube.com','mailto:','contact','about'))],'error':out.get('error'),'access_stopped':out.get('access_stopped')},ensure_ascii=False),flush=True)
def enrich(handles):
 dest=P/'official_links';dest.mkdir(exist_ok=True)
 def one(h):
  if (dest/(h+'.json')).exists():
   previous=json.loads((dest/(h+'.json')).read_text(encoding='utf8'))
   if previous.get('parser_version')==2 and previous.get('pages') and all('error' not in x for x in previous['pages']):return h,'cached'
  r=json.loads((P/'profiles'/(h+'.json')).read_text(encoding='utf8'));u=r['user'];urls=[]
  for x in [u.get('external_url')]+[x.get('url') for x in u.get('bio_links',[])]:
   if x and x.startswith('http') and x not in urls:urls.append(x)
  pages=[]
  for url in urls[:3]:
   try:
    res=requests.get(url,timeout=20);res.raise_for_status();s=BeautifulSoup(res.text,'html.parser')
    embedded=[]
    def social_nodes(node):
     if isinstance(node,dict):
      for key,value in node.items():
       if key in ('socialLinks','social_links') and isinstance(value,list):embedded.extend(value)
       else:social_nodes(value)
     elif isinstance(node,list):
      for value in node:social_nodes(value)
    for tag in s.select('script[type="application/json"]'):
     try:social_nodes(json.loads(tag.string or tag.get_text()))
     except (ValueError,TypeError):pass
    for tag in s(['script','style']):tag.decompose()
    links=[{'text':a.get_text(' ',strip=True)[:120],'url':urljoin(res.url,a['href'])} for a in s.select('a[href]') if a['href'].startswith(('http','/','mailto:'))]
    for item in embedded:
     if isinstance(item,dict) and isinstance(item.get('url'),str):
      links.append({'text':str(item.get('type','embedded social link')),'url':item['url']})
    text=s.get_text(' ',strip=True)
    emails=sorted(set(EMAIL.findall(text+' '+' '.join(x['url'] for x in links if x['url'].startswith('mailto:')))))
    pages.append({'source':url,'resolved_url':res.url,'status':res.status_code,'text':text[:18000],'emails':emails,'links':links[:250]})
   except Exception as e:pages.append({'source':url,'error':str(e)[:200]})
  out={'handle':h,'bio_emails':[{'email':e,'source':r['url']} for e in r.get('emails',[])],'pages':pages,'bio':u.get('biography',''),'checked_at':r['checked_at']}
  out['parser_version']=2
  (dest/(h+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
  return h,len(pages)
 with ThreadPoolExecutor(max_workers=4) as ex:
  for result in ex.map(one,handles):print(*result,flush=True)
