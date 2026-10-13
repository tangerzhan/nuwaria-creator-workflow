import json
from datetime import datetime,timezone,timedelta
from research import notion,SOP,OUT
from workflow_context import DATE
def run():
 page=notion('GET','pages/'+SOP)
 def children(bid):
  rows=[];cursor=None
  while True:
   path='blocks/'+bid+'/children?page_size=100'
   if cursor:path+='&start_cursor='+cursor
   data=notion('GET',path);rows.extend(data['results'])
   if not data.get('has_more'):break
   cursor=data['next_cursor']
  for b in rows:
   if b.get('has_children'):b['children']=children(b['id'])
  return rows
 blocks=children(SOP)
 now=datetime.now(timezone(timedelta(hours=8))).isoformat()
 out={'checked_at':now,'page':page,'blocks':blocks}
 (OUT/f'sop_live_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 lines=['页面：'+page.get('url',''),'最新编辑：'+page.get('last_edited_time',''),'读取：'+now]
 def texts(xs):return ''.join(x.get('plain_text',x.get('text',{}).get('content','')) for x in xs)
 def flat(bs,depth=0):
  for b in bs:
   typ=b['type'];v=b.get(typ,{})
   if typ=='table_row':t=' | '.join(texts(c) for c in v['cells'])
   else:t=texts(v.get('rich_text',[])) or v.get('title','') or v.get('url','') or v.get('caption','')
   if t:lines.append('  '*depth+'['+typ+'] '+str(t)+' {block:'+b['id']+'}')
   flat(b.get('children',[]),depth+1)
 flat(blocks)
 content='\n'.join(lines);(OUT/f'sop_live_readable_{DATE}.txt').write_text(content,encoding='utf8');print(content)
