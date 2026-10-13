"""Reusable NUWARIA research entry point; outreach requires separate user authorization."""
import argparse,asyncio,json,os,re,runpy,sys
from datetime import date
from pathlib import Path
HERE=Path(__file__).resolve().parent;SCRIPTS=HERE/'scripts';sys.path.insert(0,str(SCRIPTS))
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(p)
def history(project):
 from history_scope import external_history,scope_verified_own_records
 c=read(project/'project.json');ex=set(read(project/'excluded_handles.json'));emails=set();people=set()
 from team_history import bundled_history
 team=bundled_history()
 ex.update(team['handles']);emails.update(team['emails']);people.update(team['person_keys'])
 rx=r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
 for row in external_history(project,read(project/'existing.json')):
  props=row.get('properties',{});txt=json.dumps(props,ensure_ascii=False)
  emails.update(e.lower() for e in re.findall(rx,txt))
  ex.update(h.lower() for h in re.findall(r'(?:instagram.com/|tiktok.com/@)([\w.]+)',txt))
  for t in props.get('账号',{}).get('rich_text',[]):
   h=t.get('plain_text',t.get('text',{}).get('content','')).strip().lstrip('@')
   if re.fullmatch(r'[\w.]+',h):ex.add(h.lower())
 for folder in c.get('history_projects',[]):
  p=Path(folder).resolve()
  if p==project:continue
  if not (p/'production_reviews.json').exists():raise ValueError('历史项目不存在: '+str(p))
  ex.update(read(p/'excluded_handles.json'))
  known_aliases=read(p/'identity_aliases.json') if (p/'identity_aliases.json').exists() else {}
  prior=read(p/'historical_exclusions.json') if (p/'historical_exclusions.json').exists() else {}
  emails.update(prior.get('emails',[]));people.update(prior.get('person_keys',[]))
  for h,v in read(p/'production_reviews.json').items():
   if v.get('verdict')!='include':continue
   ex.add(h.lower());ex.add(h.removeprefix('tt__').lower());ex.update(a.lower() for a in v.get('aliases',[]));people.add(v.get('person_key',h).lower())
   ex.update(a.lower() for a in known_aliases.get(h,[]))
   r=read(p/'profiles'/f'{h}.json')
   ee=([v['public_email']] if v['public_email'] else []) if 'public_email' in v else r.get('emails',[])
   emails.update(e.lower() for e in ee)
 scope_verified_own_records(project,ex,emails,people)
 ex.update(c.get('excluded_handles',[]))
 write(project/'excluded_handles.json',sorted(ex));write(project/'historical_exclusions.json',{'handles':sorted(ex),'emails':sorted(emails),'person_keys':sorted(people)})
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--project',required=True,type=Path,help='本次项目目录（必填，防止写入旧项目）')
 sub=parser.add_subparsers(dest='command',required=True)
 init=sub.add_parser('init',help='新建独立批次，继承历史去重，不复制入选或审核结果')
 init.add_argument('--date',required=True);init.add_argument('--target',type=int,default=100);init.add_argument('--from-project',required=True,type=Path);init.add_argument('--history',action='append',default=[],type=Path)
 sub.add_parser('status');sub.add_parser('refresh-sources',help='只读刷新Notion SOP、表头、历史并更新去重')
 nr=sub.add_parser('notion-read-page',help='只读数据库记录页面正文及子块')
 nr.add_argument('page_id');nr.add_argument('--output',required=True,type=Path)
 ca=sub.add_parser('contact-audit',help='复核既有无邮箱记录的公开主页及官方联系页面')
 ca.add_argument('action',choices=['collect','crawl','supplement','report','prepare','apply','verify']);ca.add_argument('--limit',type=int,default=200)
 inv=sub.add_parser('contact-invitations',help='向邮箱复查后已获授权的既有达人发送首次邀请')
 inv.add_argument('action',choices=['preflight','build','approve-review','send','reconcile','sync']);inv.add_argument('--limit',type=int)
 sop=sub.add_parser('sync-fit-criteria',help='用户明确授权后同步项目内已审阅的产品适配标准到Notion SOP')
 ch=sub.add_parser('check');ch.add_argument('--complete',action='store_true');ch.add_argument('--workbook',type=Path)
 ex=sub.add_parser('export');ex.add_argument('--draft',action='store_true');ex.add_argument('--output',type=Path)
 merge=sub.add_parser('merge-reviews');merge.add_argument('file',type=Path);merge.add_argument('--replace',action='store_true')
 outreach=sub.add_parser('outreach',help='已获用户建联授权后使用；发送前必须查重和审阅')
 outreach.add_argument('action',choices=['preflight','build','approve-review','send','reconcile','build-import','import-notion','stats','mail-status','verify-pages','retry-bounce','sync-sent','export-progress','sync-status-rules'])
 outreach.add_argument('--limit',type=int)
 outreach.add_argument('--retry-blocked',action='store_true')
 outreach.add_argument('--handle')
 replies=sub.add_parser('replies',help='已授权的英文跟进回复：审阅、发送、回读、同步')
 replies.add_argument('--folder',required=True,type=Path);replies.add_argument('action',choices=['prepare','register','send','verify','sync'])
 close=sub.add_parser('closeout',help='明确授权后按审阅方案结束建联并归档跟进记录')
 close.add_argument('--folder',required=True,type=Path);close.add_argument('action',choices=['collect','prepare','apply','verify'])
 sync=sub.add_parser('mail-sync',help='将已审阅的来信/人工跟进同步到Notion，不发送邮件')
 sync.add_argument('--folder',required=True,type=Path);sync.add_argument('action',choices=['collect','attachments','prepare','apply','verify','export','reply_audit','reply_report','prepare_status_correction'])
 multi=sub.add_parser('status-multiselect',help='Reviewed conversion of the existing contact-status property; no mail')
 multi.add_argument('--folder',required=True,type=Path);multi.add_argument('action',choices=['prepare','apply','verify'])
 route={'scan':('focused_research.py',['scan']),'screen':('quick_screen.py',[]),'digest':('review_digest.py',[]),'board':('production_tools.py',['board']),'browse':('production_tools.py',['browse']),'comments':('modal_comments.py',[]),'read-comments':('read_modal.py',[]),'network':('new_modal_network.py',[]),'browser-links':('production_tools.py',['browser-links']),'screening-export':('export_screening.py',[])}
 route['queue-check']=('focused_research.py',['queue-check'])
 for name in list(route)+['media-capture','media-render','media-carousel','media-detail','links','source-links','tiktok','ttsearch','tiktok-render','tiktok-native','tiktok-comments','youtube-check']:
  p=sub.add_parser(name);p.add_argument('items',nargs='*')
 args=parser.parse_args();project=args.project.resolve()
 os.environ['CREATOR_PROJECT']=str(project)
 if args.command=='init':
  date.fromisoformat(args.date)
  if args.target<1:parser.error('target must be positive')
  if project.exists():parser.error('新项目目录已存在；使用 status 继续，不覆盖')
  source=args.from_project.resolve();config=read(source/'project.json')
  prior={str(source),*config.get('history_projects',[]),*(str(p.resolve()) for p in args.history)}
  # Include sibling delivered projects so the previous 100 cannot reappear in a later batch.
  prior.update(str(p.parent.resolve()) for p in source.parent.glob('candidate_research_*/production_reviews.json') if any(v.get('verdict')=='include' for v in read(p).values()))
  config.update(date=args.date,target=args.target,history_projects=sorted(prior),output_name=f'NUWARIA_新候选达人{args.target}_{args.date}.xlsx')
  project.mkdir(parents=True)
  for d in ['profiles','screenshots','post_audits','native_media','official_links']:(project/d).mkdir()
  for n in ['schema.json','existing.json','excluded_handles.json']:write(project/n,read(source/n))
  for n in ['production_reviews.json','screening.json','scores.json']:write(project/n,{})
  for n,default in [('identity_aliases.json',{}),('contact_email_aliases.json',[])]:write(project/n,read(source/n) if (source/n).exists() else default)
  write(project/'project.json',config)
  (project/'AGENTS.md').write_text('此目录使用NUWARIA固定找达人工作流。先读已安装的nuwaria-creator-research技能及references/workflow.md；通过workflow.py --project本目录运行。唯一审核主表为production_reviews.json。邮件草稿暂停，不外发、不写Notion，除非用户另行授权。',encoding='utf8')
  for p in source.glob('sop_live*'):(project/p.name).write_bytes(p.read_bytes())
  history(project);print('Created',project,'with empty review state. Refresh SOP/history before discovery.');return
 if not (project/'project.json').exists():parser.error('缺少project.json；先init或指定现有项目')
 if args.command=='contact-audit':
  from contact_audit import run
  run(project,args.action,args.limit);return
 if args.command=='contact-invitations':
  from contact_invitations import run
  run(project,args.action,args.limit);return
 if args.command=='sync-fit-criteria':
  from outreach import env,rt,text,save
  import requests
  c=read(project/'project.json');plan=read(project/'fit_criteria_update.json')
  headers={'Authorization':'Bearer '+env(c['notion_env'])['NOTION_TOKEN'],'Notion-Version':'2025-09-03'}
  def request(method,path,**kw):
   response=requests.request(method,'https://api.notion.com/v1/'+path,headers=headers,timeout=45,**kw)
   response.raise_for_status();return response.json()
  def blocks():
   out=[];cursor=None
   while True:
    result=request('GET','blocks/'+c['notion_sop']+'/children',params={'page_size':100,**({'start_cursor':cursor} if cursor else {})});out.extend(result['results'])
    if not result.get('has_more'):return out
    cursor=result['next_cursor']
  before=blocks();save(project/'sop_before_update.json',before)
  wanted=[plan['heading'],*plan['rules']]
  existing=[text(b) for b in before]
  if plan['heading'] not in existing:
   children=[{'object':'block','type':kind,kind:{'rich_text':rt(value)}} for kind,value in [('heading_3',plan['heading']),*[('bulleted_list_item',s) for s in plan['rules']]]]
   anchor=next(b['id'] for b in before if b['type']=='heading_2' and text(b).startswith('2. '))
   request('PATCH','blocks/'+c['notion_sop']+'/children',json={'children':children,'after':anchor})
  after=blocks();actual=[text(b) for b in after];assert all(v in actual for v in wanted),'SOP回读不匹配'
  save(project/'sop_update_verified.json',{'notion_sop':c['notion_sop'],'verified_text':wanted,'blocks':after});print('SOP criteria synchronized and verified');return
 if args.command=='notion-read-page':
  from outreach import Run
  run=Run(project)
  result={'page':run.notion('GET','pages/'+args.page_id),'blocks':run.blocks(args.page_id,recurse=True)}
  args.output.parent.mkdir(parents=True,exist_ok=True);write(args.output,result)
  print(json.dumps(result['blocks'],ensure_ascii=False));return
 if args.command=='replies':
  from replies import ReplyBatch
  getattr(ReplyBatch(project,args.folder),args.action)();return
 if args.command=='status-multiselect':
  from status_multiselect import StatusMigration
  getattr(StatusMigration(project,args.folder),args.action)();return
 if args.command=='closeout':
  from closeout import Closeout
  getattr(Closeout(project,args.folder),args.action)();return
 if args.command=='mail-sync':
  from mail_sync import MailSync
  getattr(MailSync(project,args.folder),args.action)();return
 if args.command=='outreach':
  from outreach import Run
  run=Run(project);method=getattr(run,args.action.replace('-','_'))
  if args.action=='send':method(args.limit,args.retry_blocked)
  elif args.action=='import-notion':method(args.limit)
  elif args.action=='retry-bounce':method(args.handle)
  else:method()
  return
 os.environ['CREATOR_PROJECT']=str(project)
 if getattr(args,'output',None):os.environ['CREATOR_OUTPUT']=str(args.output.resolve())
 from workflow_context import OUTPUT,CONFIG,screening
 if args.command=='status':
  r=read(project/'production_reviews.json');inc=sum(v.get('verdict')=='include' for v in r.values())
  print(json.dumps({'project':str(project),'date':CONFIG['date'],'target':CONFIG['target'],'included':inc,'remaining':max(0,CONFIG['target']-inc),'captured_profiles':len(list((project/'profiles').glob('*.json'))),'archived_candidates':len(read(project/'candidate_pool.json')) if (project/'candidate_pool.json').exists() else 0,'screening_decisions':len(screening()),'output':str(OUTPUT)},ensure_ascii=False));return
 if args.command=='refresh-sources':
  from research import prepare
  from sop_audit import run
  prepare();run();history(project);return
 if args.command in ('check','export','merge-reviews'):
  from validate import validate
  if args.command=='check':print(json.dumps(validate(complete=args.complete,workbook=args.workbook),ensure_ascii=False));return
  if args.command=='merge-reviews':
   current=read(project/'production_reviews.json');batch=read(args.file)
   conflicts=set(current)&set(batch)
   if conflicts and not args.replace:raise ValueError('已有审核不可意外覆盖；有意修订时使用--replace: '+','.join(conflicts))
   merged={**current,**batch};result=validate(merged)
   write(project/'production_reviews.json',merged);print(json.dumps(result,ensure_ascii=False));return
  validate(complete=not args.draft)
  if args.draft and not args.output:os.environ['CREATOR_OUTPUT']=str(project/f'NUWARIA_{CONFIG["date"]}_进度.xlsx');import workflow_context;workflow_context.OUTPUT=Path(os.environ['CREATOR_OUTPUT'])
  runpy.run_path(str(SCRIPTS/'export_production.py'),run_name='__main__')
  import workflow_context
  result=validate(complete=not args.draft,workbook=workflow_context.OUTPUT);write(project/'validation_report.json',result);return
 if args.command in route:
  if args.command in ('scan','browse','queue-check'):history(project)
  filename,prefix=route[args.command]
  if args.command!='screening-export' and not args.items:parser.error('此命令需要队列文件或账号参数')
  sys.argv=[filename,*prefix,*args.items];runpy.run_path(str(SCRIPTS/filename),run_name='__main__');return
 if not args.items:parser.error('此命令需要账号或查询参数')
 if args.command in ('media-capture','media-render'):
  if any(h.startswith('tt__') for h in args.items):raise ValueError('此媒体适配器仅支持Instagram；TikTok请通过原生页面单独核验，不能复用IG证据')
  from fast_audit import capture,render
  if args.command=='media-capture':asyncio.run(capture(args.items))
  else:render(args.items)
 elif args.command=='media-detail':
  from fast_audit import render_detail
  render_detail(args.items)
 elif args.command=='media-carousel':
  from fast_audit import render_carousel
  render_carousel(args.items)
 elif args.command=='links':
  from enrich_links import enrich
  enrich(args.items)
 elif args.command=='source-links':
  from enrich_links import source_links
  source_links(args.items)
 elif args.command in ('tiktok','ttsearch'):
  history(project)
  from tiktok_research import probe,search
  asyncio.run((probe if args.command=='tiktok' else search)(args.items))
 elif args.command=='tiktok-render':
  from tiktok_evidence import render_native
  render_native(args.items)
 elif args.command=='tiktok-native':
  history(project)
  from tiktok_evidence import capture_browser
  asyncio.run(capture_browser(args.items))
 elif args.command=='tiktok-comments':
  from tiktok_evidence import comments_native
  asyncio.run(comments_native(args.items))
 elif args.command=='youtube-check':
  from public_channel import run
  run(args.items)
if __name__=='__main__':
 try:main()
 except (ValueError,OSError) as e:print(str(e),file=sys.stderr);sys.exit(1)
