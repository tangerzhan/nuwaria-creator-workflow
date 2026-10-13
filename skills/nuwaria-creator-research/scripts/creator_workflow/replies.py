"""Reviewed, explicitly authorized Zoho thread replies with duplicate guards."""
import html,re,hashlib,os
from pathlib import Path
from bs4 import BeautifulSoup
from outreach import Run,read,save,flat,EMAIL,now,digest
from mail_sync import MailSync,local_date

def addresses(value):return {e.lower() for e in EMAIL.findall(html.unescape(str(value)))}
def normalized(value):return ' '.join(html.unescape(value).split())
def incoming_address(d):
    source=d.get('incoming_email',d['to']).lower()
    if source!=d['to'].lower():
        aliases=read(Path(os.environ['CREATOR_PROJECT'])/'contact_email_aliases.json')
        assert any(a['current_email']==d['to'].lower() and source in a['previous_emails'] for a in aliases),'Unverified email change'
    return source

class ReplyBatch:
    def __init__(self,project,folder):self.r=Run(project);self.o=Path(folder).resolve()
    def register(self):
        """Register individually reviewed, previously invited contacts before replying."""
        from mail_sync import typed
        plan=read(self.o/'registration_plan.json');review=read(self.o/'registration_review.json')
        assert review['approved'] and review['digest']==digest(plan)
        pages=self.r.all_pages();sent=self.r.sent();messages=read(self.o/'message_contents.json')
        schema=self.r.notion('GET','data_sources/'+self.r.ds)['properties']
        logpath=self.o/'registration_log.json';log=read(logpath) if logpath.exists() else {}
        for d in plan:
            incoming=[m for m in messages if m['direction']=='inbox' and d['email'] in addresses(m['meta'].get('fromAddress',''))]
            prior=[m for m in sent if d['email'] in addresses(m.get('toAddress',''))]
            assert incoming and prior,'Registration requires a verified invitation and reply'
            matches=[p for p in pages if d['email'] in addresses(flat(p).get('公开联系方式','')) or str(flat(p).get('账号','')).lstrip('@').lower()==d['handle'].lstrip('@').lower()]
            assert len(matches)<=1
            if matches:
                assert d['email'] in addresses(flat(matches[0]).get('公开联系方式','')),'Identity conflict'
                continue
            values=dict(d['fields']);assert values['账号']==d['handle'] and values['公开联系方式']==d['email']
            values.update({'联系状态':['待跟进'],'发送日期':local_date(min(prior,key=lambda x:int(x['receivedTime']))),'回复日期':local_date(max(incoming,key=lambda x:int(x['meta']['receivedTime']))['meta'])})
            props={k:typed(schema[k],v) for k,v in values.items()}
            page=self.r.notion('POST','pages',json={'parent':{'type':'data_source_id','data_source_id':self.r.ds},'properties':props})
            self.r.verify_properties(page,props);pages.append(page)
            log[d['handle']]={'page_id':page['id'],'verified_at':now()};save(logpath,log)
            print('REGISTERED',d['handle'],flush=True)
        save(self.o/'notion_before.json',pages)
    def prepare(self):
        messages=read(self.o/'message_contents.json');pages=read(self.o/'notion_before.json');sent=read(self.o/'sent_all.json');plan=[]
        for d in read(self.o/'reply_scope.json'):
            matches=[p for p in pages if d.get('record_email',d['to']).lower() in addresses(flat(p).get('公开联系方式',''))]
            untracked=not matches and ((d.get('allow_untracked_closeout') is True and d.get('status')=='已暂停') or (d.get('allow_untracked_reply') is True and d.get('status')=='待二次回复'))
            assert len(matches)==1 or untracked,d['to']
            if untracked:
                assert any({d['to'].lower(),d.get('record_email',d['to']).lower()} & addresses(m.get('toAddress','')) for m in sent),'Untracked reply requires prior invitation'
                page={'id':None,'archived':False};f={'账号':d['source_handle']}
            else:page=matches[0];f=flat(page)
            closing=d.get('allow_paused_closeout') is True and d.get('status')=='已暂停'
            reopening=d.get('allow_paused_reopen') is True and d.get('status')=='待二次回复'
            assert (not f.get('是否暂停推进') or closing or reopening) and not page['archived']
            incoming=[m for m in messages if m['direction']=='inbox' and {incoming_address(d),d['to'].lower()} & addresses(m['meta'].get('fromAddress',''))]
            latest=max(incoming,key=lambda m:int(m['meta']['receivedTime']))
            expected=d.pop('expected_incoming_id');assert str(latest['meta']['messageId'])==expected,('New incoming requires review',d['to'])
            prior=[m for m in sent if addresses(m.get('toAddress','')) & {d['to'].lower(),d.get('record_email',d['to']).lower()}]
            cc=addresses(latest['meta'].get('ccAddress',''))|addresses(latest['meta'].get('toAddress',''))
            cc-= {self.r.c['sender_email'],d['to'].lower()}
            assert '\ufffd' not in d['body']
            if d.get('language') == 'zh-Hant':
                assert '您好' in d['body'] and 'NUWARIA' in d['body']
            else:
                assert d['body'].isascii() and 'Hi ' in d['body'] and 'Warmly,' in d['body']
            subject=latest['meta']['subject'];subject=subject if subject.lower().startswith('re:') else 'Re: '+subject
            plan.append(d|{'handle':f['账号'],'page_id':page['id'],'message_id':expected,'folder_id':latest['folder_id'],'subject':subject,'cc':sorted(cc),'incoming_time':int(latest['meta']['receivedTime']),'last_outgoing_time':max([int(m['receivedTime']) for m in prior] or [0])})
        assert len({x['to'] for x in plan})==len(plan)
        save(self.o/'reply_plan.json',plan);print([(x['handle'],x['to'],x['cc']) for x in plan],flush=True)
    def send(self):
        plan=read(self.o/'reply_plan.json');review=read(self.o/'reply_review.json');assert review['approved'] and review['digest']==digest(plan)
        logpath=self.o/'reply_log.json';log=read(logpath) if logpath.exists() else {}
        # Refresh all relevant incoming/sent metadata immediately before sending.
        MailSync(self.r.p,self.o).reply_audit()
        messages=read(self.o/'message_contents.json');sent=read(self.o/'sent_all.json')
        for d in plan:
            assert digest(read(self.o/'reply_plan.json'))==review['digest'], 'Draft changed while running; stop before sending'
            assert read(self.o/'reply_review.json')['digest']==review['digest'], 'Review changed while running; stop before sending'
            if log.get(d['to'],{}).get('accepted'):continue
            assert not log.get(d['to']), 'Uncertain attempt must be reconciled, never resent automatically'
            if d['page_id'] is None:
                assert (d.get('allow_untracked_closeout') and d['status']=='已暂停') or (d.get('allow_untracked_reply') and d['status']=='待二次回复')
                assert not any({d['to'].lower(),d.get('record_email',d['to']).lower()} & addresses(flat(p).get('公开联系方式','')) for p in read(self.o/'notion_before.json')),'New Notion record requires review'
                current={'archived':False};f={}
            else:current=self.r.notion('GET','pages/'+d['page_id']);f=flat(current)
            closing=d.get('allow_paused_closeout') is True and d.get('status')=='已暂停'
            reopening=d.get('allow_paused_reopen') is True and d.get('status')=='待二次回复'
            assert not current['archived'] and (not f.get('是否暂停推进') or closing or reopening)
            incoming=[m for m in messages if m['direction']=='inbox' and {incoming_address(d),d['to'].lower()} & addresses(m['meta'].get('fromAddress',''))]
            assert max(int(m['meta']['receivedTime']) for m in incoming)==d['incoming_time'],('New incoming',d['to'])
            outgoing=[m for m in sent if addresses(m.get('toAddress','')) & {d['to'].lower(),d.get('record_email',d['to']).lower()}]
            assert max([int(m['receivedTime']) for m in outgoing] or [0])==d['last_outgoing_time'],('New outgoing',d['to'])
            # Explicit HTML links avoid Zoho's plaintext-reply https auto-link corruption.
            content=html.escape(d['body']).replace('\n','<br>')
            content=content.replace('https://www.nuwaria.com/','<a href="https://www.nuwaria.com/">https://www.nuwaria.com/</a>')
            content=content.replace('https://www.instagram.com/nuwaria.hk/','<a href="https://www.instagram.com/nuwaria.hk/">https://www.instagram.com/nuwaria.hk/</a>')
            payload={'fromAddress':self.r.c['sender_email'],'toAddress':d['to'],'subject':d['subject'],'content':'<div>'+content+'</div>','action':'reply','mailFormat':'html','encoding':'UTF-8'}
            if d['cc']:payload['ccAddress']=','.join(d['cc'])
            if d.get('local_attachments'):
                uploaded=[]
                for attachment in d['local_attachments']:
                    path=Path(attachment['path']);data=path.read_bytes()
                    assert hashlib.sha256(data).hexdigest()==attachment['sha256'],'Attachment changed after review'
                    assert path.suffix.lower() in {'.png','.jpg','.jpeg','.pdf'} and len(data)<20000000
                    result=self.r.zoho('POST','/messages/attachments',params={'fileName':path.name,'isInline':'false'},data=data)['data']
                    uploaded.append({k:result[k] for k in ('storeName','attachmentName','attachmentPath')})
                payload['attachments']=uploaded
            log[d['to']]={'attempted_at':now(),'body_digest':digest(d['body'])};save(logpath,log)
            result=self.r.zoho('POST','/messages/'+d['message_id'],json=payload)
            log[d['to']].update(accepted=True,result=result);save(logpath,log);print('REPLIED',d['handle'],flush=True)
    def verify(self):
        plan=read(self.o/'reply_plan.json');log=read(self.o/'reply_log.json');sent=self.r.sent();save(self.o/'sent_after_replies.json',sent)
        results=[];messages=read(self.o/'message_contents.json')
        for d in plan:
            accepted_id=str(log[d['to']]['result'].get('data',{}).get('messageId',''))
            matches=[m for m in sent if d['to'].lower() in addresses(m.get('toAddress','')) and int(m['receivedTime'])>d['last_outgoing_time'] and (not accepted_id or str(m['messageId'])==accepted_id)]
            assert len(matches)==1,(d['to'],len(matches))
            meta=matches[0];mid=str(meta['messageId'])
            if d.get('local_attachments'):
                from email import policy
                from email.parser import Parser
                original=self.r.zoho('GET',f'/messages/{mid}/originalmessage')['data']['content']
                mime=Parser(policy=policy.default).parsestr(original)
                hashes={hashlib.sha256(p.get_payload(decode=True)).hexdigest() for p in mime.walk() if p.get_filename() and p.get_payload(decode=True)}
                assert {a['sha256'] for a in d['local_attachments']}<=hashes,'Sent attachment mismatch'
            raw=self.r.zoho('GET',f'/folders/{self.r.sent_folder}/messages/{mid}/content')['data']['content']
            plain=BeautifulSoup(raw,'html.parser').get_text(' ',strip=True) if '<' in raw else raw
            newbody=re.split(r'\s*---- On .*? wrote ----',plain,maxsplit=1,flags=re.S)[0]
            if normalized(newbody)!=normalized(d['body']):
                # The display API may rewrite links; inspect the actual transmitted MIME.
                from email import policy
                from email.parser import Parser
                original=self.r.zoho('GET',f'/messages/{mid}/originalmessage')['data']['content']
                save(self.o/(mid+'_original.json'),{'content':original})
                mime=Parser(policy=policy.default).parsestr(original)
                part=mime.get_body(preferencelist=('plain','html')) if mime.is_multipart() else mime
                payload=part.get_content()
                transmitted=BeautifulSoup(payload,'html.parser').get_text(' ',strip=True) if part.get_content_type()=='text/html' else payload
                newbody=re.split(r'\s*---- On .*? wrote ----',transmitted,maxsplit=1,flags=re.S)[0]
                save(self.o/(mid+'_mime_body.json'),{'body':newbody,'expected':d['body']})
            exact=normalized(newbody)==normalized(d['body'])
            known_link_artifact=False
            if not exact:
                repaired=re.sub(r'https\s*http://www\.nuwaria\.com/', 'https://www.nuwaria.com/',newbody)
                hrefs={a.get('href') for a in BeautifulSoup(raw.split('---- On ')[0],'html.parser').find_all('a')}
                known_link_artifact=normalized(repaired)==normalized(d['body']) and 'http://www.nuwaria.com/' in hrefs
            assert exact or known_link_artifact,('Transmitted reply body mismatch',d['to'])
            assert set(d['cc'])<=addresses(meta.get('ccAddress',''))
            if not any(str(m['meta']['messageId'])==mid for m in messages):messages.append({'meta':meta,'direction':'sent','folder_id':self.r.sent_folder,'raw_content':raw,'full_text':plain})
            results.append({'to':d['to'],'handle':d['handle'],'message_id':mid,'new_body':newbody,'verified':True,'exact_body_match':exact,'zoho_link_display_artifact':known_link_artifact,'link_destination_validated':known_link_artifact or exact})
        save(self.o/'message_contents.json',messages);save(self.o/'reply_verified.json',{'checked_at':now(),'results':results});print('VERIFIED',len(results),flush=True)
    def sync(self):
        from closeout import Closeout
        self.verify()
        plan=read(self.o/'reply_plan.json');verified=read(self.o/'reply_verified.json')['results']
        save(self.o/'notion_before.json',self.r.all_pages())
        Closeout(self.r.p,self.o).collect()
        rows=read(self.o/'tracking_pages.json');save(self.o/'tracking_pages.json',{'results':rows,'has_more':False})
        save(self.r.o/'schema_live.json',read(self.o/'main_schema.json'))
        decisions=[]
        for d in plan:
            if d['page_id'] is None:
                assert (d.get('allow_untracked_closeout') and d['status']=='已暂停') or (d.get('allow_untracked_reply') and d['status']=='待二次回复')
                if d.get('allow_untracked_reply'):
                    save(self.o/'pending_notion_registration.json',{'reply':d,'reason':'No matching main record; verified sent reply retained for registration.'})
                continue
            s=next(v for v in verified if v['to']==d['to'])
            decisions.append({'email':d['to'],'record_email':d.get('record_email',d['to']),'messages':[d['message_id'],s['message_id']],'status':d['status'],'paused':d['status']=='已暂停','summary':d['summary'],'next':d['next'],'cooperation':d['cooperation'],'tracking':False if d['status']=='已暂停' else 'upsert','tracking_name':d['name'],'extra':{'跟进日期':None},'tracking_extra':d.get('tracking_extra',{})})
            for key in ('tracking_note','contact_name','recipient_name','cooperation_option','selected_product','needs_our_reply','quote_received','quote_evidence'):
                if key in d:decisions[-1][key]=d[key]
            current=next(p for p in read(self.o/'notion_before.json') if p['id']==d['page_id'])
            if not flat(current).get('发送日期'):
                sent_to_creator=[m for m in read(self.o/'sent_after_replies.json') if addresses(m.get('toAddress','')) & {d['to'].lower(),d.get('record_email',d['to']).lower()}]
                first=min(sent_to_creator,key=lambda m:int(m['receivedTime']))
                decisions[-1]['extra']['发送日期']=local_date(first)
        save(self.o/'decisions.json',decisions)
        sync=MailSync(self.r.p,self.o);sync.prepare()
        update=read(self.o/'update_plan.json');save(self.o/'review.json',{'plan_sha256':digest(update),'reviewed_at':now(),'reason':'Verified replies; statuses match reviewed decisions; gifts and product choices do not imply dispatch or paid acceptance.'})
        sync.apply();sync.verify()
        closed=[]
        for d in plan:
            if d['status']!='已暂停':continue
            removed=[]
            for row in rows:
                f=flat(row)
                if d['to'].lower() in addresses(f.get('邮箱','')) or str(f.get('达人账号名','')).lstrip('@')==d['handle'].lstrip('@'):
                    live=self.r.notion('GET','pages/'+row['id'])
                    if not live['archived']:self.r.notion('PATCH','pages/'+row['id'],json={'archived':True})
                    assert self.r.notion('GET','pages/'+row['id'])['archived'];removed.append(row['id'])
            closed.append({'email':d['to'],'main_page_id':d['page_id'],'removed_tracking':removed,'reason':d['summary']})
        if closed:save(self.o/'closed_contacts.json',closed)
