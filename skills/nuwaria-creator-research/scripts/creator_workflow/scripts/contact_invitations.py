"""Scoped invitations to explicitly authorized recovered contacts; reuse audited sender."""
import re,html,hashlib
from datetime import datetime,timezone,timedelta
from outreach import Run,read,save,flat,EMAIL,rt,para,text,digest,now

class Invitations(Run):
    def __init__(self,project):
        super().__init__(project)
        self.base=self.p/'contact_audit'
        self.o=self.base/'invitations';self.o.mkdir(exist_ok=True)
        self.scope=read(self.o/'scope.json')
        audited={d['handle']:d for d in read(self.base/'plan.json') if d['action']=='update'}
        assert len(self.scope['handles'])==self.scope['authorized_count']==18
        assert set(self.scope['handles'])==set(audited)
        self.audited=audited
    def candidates(self):
        targets={t['handle']:t for t in read(self.base/'targets.json')}
        result=[]
        for h in self.scope['handles']:
            t=targets[h];d=self.audited[h]
            aliases=set(re.findall(r'(?:instagram\.com/|tiktok\.com/@)([\w.]+)',' '.join(t['urls'])))
            # Public bio aliases are identity evidence, not additional recipients.
            doc=read(self.base/'evidence'/(d['id']+'.json'))
            for p in doc['pages']:
                if p.get('source')=='profile':
                    aliases.update(re.findall(r'IG:\s*@([\w.]+)',p.get('text','')))
            result.append({'handle':h,'name':t['before'].get('达人姓名',h),'emails':[d['email']],'url':t['urls'][0],'aliases':sorted(aliases)})
        return result
    def validate_drafts(self,drafts,tail):
        tail=tail.strip()
        assert {d['handle'] for d in drafts}==set(self.scope['handles'])
        assert len({d['to'].lower() for d in drafts})==len(drafts)
        for d in drafts:
            assert d['to']==self.audited[d['handle']]['email'] and EMAIL.fullmatch(d['to'])
            assert d['sha256']==digest({k:d[k] for k in ('to','subject','body')})
            assert d['body'].endswith(tail) and d['intro'] in d['body']
            assert d['body'].isascii() and not re.search(r'TODO|TBD|\[Name\]|affiliate',d['body'],re.I)
            assert 'Option 1' in tail and 'Option 2' in tail and '15%' in tail
            assert 'paid collaborations' in tail and 'at least 3 seconds' in tail
    def build(self):
        dd=read(self.o/'dedup.json')
        assert all(c['eligible'] for c in dd['candidates']), 'Resolve duplicate or changed contact before building'
        personal=read(self.o/'personalization.json');tail=(self.o/'template_tail.txt').read_text(encoding='utf-8').strip()
        drafts=[]
        for h in self.scope['handles']:
            p=personal[h];intro=p['intro']
            d={'handle':h,'to':self.audited[h]['email'],'name':p['name'],'subject':'NUWARIA x '+p['name']+' Collaboration Invitation','intro':intro,'body':'Hi '+p['greeting']+',\n\n'+intro+'\n\n'+tail,'evidence':p['evidence']}
            d['sha256']=digest({k:d[k] for k in ('to','subject','body')});drafts.append(d)
        self.validate_drafts(drafts,tail);save(self.o/'drafts.json',drafts)
        (self.o/'preview.txt').write_text('\n\n=====\n\n'.join('To: '+d['to']+'\nSubject: '+d['subject']+'\n\n'+d['body'] for d in drafts),encoding='utf-8')
        print('BUILT',len(drafts),flush=True)
    def approve_review(self):
        ds=read(self.o/'drafts.json');tail=(self.o/'template_tail.txt').read_text(encoding='utf-8').strip();self.validate_drafts(ds,tail)
        save(self.o/'review.json',{'reviewed_at':now(),'checks':['public identity and biography','correct platform','Option 1 and Option 2 terms','no paid proposal invitation','optional discount code and commission','no invented post observations'],'draft_hashes':{d['handle']:d['sha256'] for d in ds}})
        print('REVIEWED',len(ds),flush=True)
    def sync(self):
        sends=read(self.o/'send_log.json');ds={d['handle']:d for d in read(self.o/'drafts.json')}
        log=read(self.o/'sync_log.json') if (self.o/'sync_log.json').exists() else {}
        for h in self.scope['handles']:
            s=sends.get(h,{})
            if s.get('status')!='sent_verified':continue
            d=ds[h];assert s['sha256']==d['sha256'] and s['content_check']['matches_reviewed_body']
            pid=self.audited[h]['id'];page=self.notion('GET','pages/'+pid);f=flat(page)
            assert not page['archived'] and d['to'].lower() in str(f['公开联系方式']).lower()
            date=datetime.fromisoformat(s['accepted_at']).astimezone(timezone(timedelta(hours=8))).date().isoformat()
            props={}
            if not f.get('发送日期'):props['发送日期']={'date':{'start':date}}
            if not f.get('邮件主题'):props['邮件主题']={'rich_text':rt(d['subject'])}
            if (f.get('联系状态') or {}).get('name')=='未联系' and not f.get('回复日期') and not f.get('是否暂停推进'):
                props.update({'联系状态':{'select':{'name':'已发信'}},'建联备注':{'rich_text':rt('合作方式未确认；未选品；佣金：已提出待回应；待对方回复合作意向、选项及收件国家。')},'下一步':{'rich_text':rt('待对方回复合作意向、选项及收件国家。')}})
            if props:self.verify_properties(self.notion('PATCH','pages/'+pid,json={'properties':props}),props)
            marker='Zoho 英文邀请已发送｜'+str(s['message_id']);blocks=self.blocks(pid)
            if not any(text(b)==marker for b in blocks):
                self.notion('PATCH','blocks/'+pid+'/children',json={'children':[para(marker),para('发送日期（北京时间）：'+date+'；收件人：'+d['to']+'；主题：'+d['subject'])]+[para(p) for p in d['body'].split('\n\n')]})
            actual=self.blocks(pid);idx=next(i for i,b in enumerate(actual) if text(b)==marker);parts=d['body'].split('\n\n')
            assert [text(b) for b in actual[idx+2:idx+2+len(parts)]]==parts
            self.verify_properties(self.notion('GET','pages/'+pid),props)
            log[h]={'page_id':pid,'message_id':s['message_id'],'verified_at':now()};save(self.o/'sync_log.json',log)
            print('SYNC_VERIFIED',h,flush=True)

def run(project,action,limit):
    r=Invitations(project)
    if action=='preflight':
        # Register existing, verified pages for the base sender's own-pending exemption.
        pages={p['id']:p for p in r.all_pages()};imports={}
        for h,d in r.audited.items():
            p=pages[d['id']];f=flat(p)
            assert d['email'].lower() in str(f['公开联系方式']).lower()
            imports[h]={'page_id':d['id'],'status':'verified'}
        save(r.o/'notion_import_log.json',imports)
        # Reuse metadata cache; preflight still refreshes the recent overlap.
        source=r.p/'outreach'/'mail_cache';dest=r.o/'mail_cache';dest.mkdir(exist_ok=True)
        for p in source.glob('*.json'):
            if not (dest/p.name).exists():(dest/p.name).write_bytes(p.read_bytes())
        r.preflight()
    elif action=='build':r.build()
    elif action=='approve-review':r.approve_review()
    elif action=='send':r.send(limit=limit)
    elif action=='reconcile':r.reconcile()
    elif action=='sync':r.sync()
