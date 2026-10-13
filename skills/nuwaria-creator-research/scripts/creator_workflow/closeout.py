"""Explicitly authorized, reviewed creator closeouts; preserves main history."""
from pathlib import Path
from outreach import Run, read, save, flat, EMAIL, now, digest, status_names
from mail_sync import typed

class Closeout:
    def __init__(self,project,folder):
        self.r=Run(project);self.o=Path(folder).resolve()

    def collect(self):
        save(self.o/'main_schema.json',self.r.notion('GET','data_sources/'+self.r.ds))
        save(self.o/'tracking_schema.json',self.r.notion('GET','data_sources/'+self.r.c['notion_tracking_data_source']))
        rows=[];cursor=None
        while True:
            body={'page_size':100}
            if cursor:body['start_cursor']=cursor
            result=self.r.notion('POST','data_sources/'+self.r.c['notion_tracking_data_source']+'/query',json=body);rows.extend(result['results'])
            if not result.get('has_more'):break
            cursor=result['next_cursor']
        save(self.o/'tracking_pages.json',rows)
        print('TRACKING',len(rows),flush=True)

    def prepare(self):
        scope=read(self.o/'closeout_scope.json');main=read(self.o/'notion_before.json');tracking=read(self.o/'tracking_pages.json')
        schema=read(self.o/'main_schema.json')['properties'];messages=read(self.o/'message_contents.json');plan=[]
        for d in scope:
            matches=[p for p in main if d['record_email'].lower() in str(flat(p).get('公开联系方式','')).lower()]
            assert len(matches)==1,(d['record_email'],len(matches))
            p=matches[0];f=flat(p)
            rows=[t for t in tracking if d['record_email'].lower() in str(flat(t).get('邮箱','')).lower() or str(flat(t).get('达人账号名','')).strip('@')==f['账号'].strip('@')]
            assert len(rows)<=1,(f['账号'],len(rows))
            assert d['evidence_ids'] and all(any(str(m['meta']['messageId'])==i for m in messages) for i in d['evidence_ids'])
            note='2026-09-17：按用户决定，本轮不推进付费合作，停止主动跟进并从建联情况表移除。对外内部评估措辞为礼貌收尾，不代表待评估任务。'+d['reason']
            values={'联系状态':'已暂停','是否暂停推进':True,'下一步':'本轮不合作，不主动跟进；保留报价与历史记录用于查重。'}
            if schema['联系状态']['type']=='multi_select':values['联系状态']={'已暂停'}|(status_names(f.get('联系状态'))&{'已报价'})
            for key in schema:
                if '跟进' in key and schema[key]['type']=='date':values[key]=None
            values['建联备注']=(f.get('建联备注') or '')+'\n'+note
            props={k:typed(schema[k],v) for k,v in values.items()}
            plan.append(d|{'handle':f['账号'],'page_id':p['id'],'before_edited':p['last_edited_time'],'properties':props,'tracking_ids':[x['id'] for x in rows],'tracking_before':rows})
        save(self.o/'closeout_plan.json',plan)
        print([(p['handle'],len(p['tracking_ids']),bool(p.get('reply'))) for p in plan],flush=True)

    def apply(self):
        plan=read(self.o/'closeout_plan.json');review=read(self.o/'closeout_review.json');assert review['digest']==digest(plan) and review['approved']
        logpath=self.o/'closeout_log.json';log=read(logpath) if logpath.exists() else {}
        sent=self.r.sent()
        for p in plan:
            if log.get(p['handle'],{}).get('done'):continue
            current=self.r.notion('GET','pages/'+p['page_id'])
            assert current['last_edited_time']==p['before_edited'],('Main record changed',p['handle'])
            entry=log.setdefault(p['handle'],{})
            if p.get('reply'):
                d=p['reply'];assert d['body'].isascii() and d['to']==p['email']
                assert not entry.get('sending') and not entry.get('sent'), 'Do not repeat uncertain send; reconcile first'
                latest=[m for m in sent if d['to'].lower() in str(m.get('toAddress','')).lower()]
                assert max(int(m['receivedTime']) for m in latest)==d['latest_sent_time'],'New outgoing mail; re-review'
                entry['sending']=now();save(logpath,log)
                result=self.r.zoho('POST','/messages/'+d['message_id'],json={'fromAddress':self.r.c['sender_email'],'toAddress':d['to'],'subject':d['subject'],'content':d['body'],'action':'reply','mailFormat':'plaintext','encoding':'UTF-8'})
                entry['sent']=result;save(logpath,log)
            result=self.r.notion('PATCH','pages/'+p['page_id'],json={'properties':p['properties']})
            assert '已暂停' in status_names(flat(result)['联系状态'])
            entry['main_updated']=now();save(logpath,log)
            for tid in p['tracking_ids']:
                result=self.r.notion('PATCH','pages/'+tid,json={'archived':True});assert result['archived']
            entry['done']=True;entry['finished_at']=now();save(logpath,log)
            print('CLOSED',p['handle'],flush=True)

    def verify(self):
        plan=read(self.o/'closeout_plan.json');sent=self.r.sent();results=[]
        for p in plan:
            live=self.r.notion('GET','pages/'+p['page_id']);f=flat(live)
            assert '已暂停' in status_names(f['联系状态']) and f['是否暂停推进'] and not live['archived']
            for tid in p['tracking_ids']:assert self.r.notion('GET','pages/'+tid)['archived']
            mid=None
            if p.get('reply'):
                d=p['reply'];matches=[m for m in sent if d['to'].lower() in str(m.get('toAddress','')).lower() and int(m['receivedTime'])>d['latest_sent_time']]
                assert len(matches)==1,(p['handle'],len(matches))
                from bs4 import BeautifulSoup
                import html,re
                mid=str(matches[0]['messageId'])
                content=self.r.zoho('GET',f'/folders/{self.r.sent_folder}/messages/{mid}/content')['data']['content']
                plain=BeautifulSoup(content,'html.parser').get_text(' ',strip=True)
                # Zoho's reply endpoint appends the original conversation automatically.
                new_body=re.split(r'\s*---- On .*? wrote ----',plain,maxsplit=1,flags=re.S)[0]
                normalize=lambda s:' '.join(html.unescape(s).split())
                assert normalize(new_body)==normalize(d['body']),('Reply body mismatch',p['handle'])
                save(self.o/(p['handle'].lstrip('@')+'_sent_verification.json'),{'message_id':mid,'new_body':new_body,'matches_reviewed_body':True,'quoted_history_appended_by_zoho':plain!=new_body})
            results.append({'handle':p['handle'],'archived_tracking':len(p['tracking_ids']),'sent_message_id':mid,'verified':True})
        save(self.o/'closeout_verified.json',{'checked_at':now(),'results':results});print(results,flush=True)
