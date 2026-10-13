"""Audited, resumable conversion of the same Notion status column to multi-select."""
from pathlib import Path
from outreach import Run,read,save,flat,status_names,digest,now

class StatusMigration:
    def __init__(self,project,folder):self.r=Run(project);self.o=Path(folder)
    def prepare(self):
        schema=self.r.notion('GET','data_sources/'+self.r.ds)
        pages=self.r.all_pages();save(self.o/'migration_before.json',pages);save(self.o/'migration_schema.json',schema)
        reviewed=read(self.o/'quote_decisions.json');byhandle={flat(p)['账号']:p for p in pages}
        assert set(reviewed)<=set(byhandle)
        plan=[]
        for p in pages:
            f=flat(p);tags=status_names(f.get('联系状态'));after=set(tags);h=f['账号']
            # Legacy checkbox also marks delivery failures; never infer a closed
            # collaboration from it. Preserve only explicitly reviewed stage tags.
            if h in reviewed:
                assert reviewed[h]['evidence']
                after.add('已报价')
            plan.append({'id':p['id'],'handle':h,'before':sorted(tags),'after':sorted(after),'evidence':reviewed.get(h)})
        save(self.o/'migration_plan.json',plan)
        print({'records':len(plan),'tag_changes':sum(x['before']!=x['after'] for x in plan),'quoted':sum('已报价' in x['after'] for x in plan),'paused':sum('已暂停' in x['after'] for x in plan),'both':sum({'已报价','已暂停'}<=set(x['after']) for x in plan)},flush=True)
    def apply(self):
        plan=read(self.o/'migration_plan.json');review=read(self.o/'migration_review.json');assert review['digest']==digest(plan)
        schema=self.r.notion('GET','data_sources/'+self.r.ds);prop=schema['properties']['联系状态']
        if prop['type']=='select':
            current={p['id']:status_names(flat(p).get('联系状态')) for p in self.r.all_pages()}
            assert all(current[x['id']]==set(x['before']) for x in plan),'Concurrent status change; reprepare'
            options=[{k:o[k] for k in ('id','name','color')} for o in prop['select']['options']]
            self.r.notion('PATCH','data_sources/'+self.r.ds,json={'properties':{'联系状态':{'multi_select':{'options':options}}}})
        else:assert prop['type']=='multi_select'
        schema=self.r.notion('GET','data_sources/'+self.r.ds);assert schema['properties']['联系状态']['id']==prop['id']
        assert schema['properties']['联系状态']['type']=='multi_select'
        save(self.r.o/'schema_live.json',schema)
        pages={p['id']:p for p in self.r.all_pages()};log=read(self.o/'migration_log.json') if (self.o/'migration_log.json').exists() else {}
        for item in plan:
            live=pages[item['id']];tags=status_names(flat(live).get('联系状态'))
            if tags==set(item['after']):continue
            assert tags in (set(item['before']),set()),('Concurrent change',item['handle'],tags)
            fresh=self.r.notion('GET','pages/'+item['id']);assert status_names(flat(fresh).get('联系状态'))==tags
            result=self.r.notion('PATCH','pages/'+item['id'],json={'properties':{'联系状态':{'multi_select':[{'name':n} for n in item['after']]}}})
            assert status_names(flat(result).get('联系状态'))==set(item['after'])
            log[item['id']]={'handle':item['handle'],'tags':item['after'],'verified_at':now()};save(self.o/'migration_log.json',log)
            print('UPDATED',item['handle'],flush=True)
        self.verify()
    def verify(self):
        plan=read(self.o/'migration_plan.json');pages=self.r.all_pages();byid={p['id']:p for p in pages}
        for x in plan:assert status_names(flat(byid[x['id']]).get('联系状态'))==set(x['after']),(x['handle'],'tags changed')
        save(self.o/'migration_after.json',pages)
        save(self.o/'migration_verified.json',{'verified_at':now(),'records':len(plan),'quoted':sum('已报价' in x['after'] for x in plan),'paused':sum('已暂停' in x['after'] for x in plan),'both':sum({'已报价','已暂停'}<=set(x['after']) for x in plan)})
        print(read(self.o/'migration_verified.json'),flush=True)
