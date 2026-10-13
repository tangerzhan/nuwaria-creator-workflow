"""Read-only mailbox scans with a 48-hour overlap and daily reconciliation."""
import time
from pathlib import Path
from outreach import read,save

def scan_folder(run,folder_id,force_full=False,clock=None):
    clock=time.time() if clock is None else clock
    path=run.o/'mail_cache'/('folder_'+str(folder_id)+'.json')
    state=read(path) if path.exists() else {}
    old={str(m['messageId']):m for m in state.get('messages',[])}
    full=force_full or not state or clock-state.get('full_at',0)>=86400
    # Anchor overlap to the previous successful check, including after long gaps.
    cutoff=int((state.get('checked_at',clock)-48*3600)*1000)
    found={};pages=0;descending=True;previous=None;finished=False
    for start in range(1,20001,80):
        batch=run.zoho('GET','/messages/view',params={'folderId':str(folder_id),'limit':100,'start':start})['data'];pages+=1
        times=[int(m['receivedTime']) for m in batch]
        descending=descending and times==sorted(times,reverse=True)
        if previous and batch and not (previous&{str(m['messageId']) for m in batch}):
            raise RuntimeError('Mailbox pagination shifted beyond overlap; retry without advancing cache')
        for m in batch:found[str(m['messageId'])]=m
        if len(batch)<100:finished=True;break
        if not full and descending and times[-1]<cutoff:break
        previous={str(m['messageId']) for m in batch}
    else:raise RuntimeError('Mailbox scan cap reached; cache not advanced')
    # Recent removals are reconciled now; older moves/removals at daily full scan.
    merged={} if full or finished else {k:v for k,v in old.items() if int(v['receivedTime'])<cutoff}
    merged.update(found)
    rows=sorted(merged.values(),key=lambda m:int(m['receivedTime']),reverse=True)
    report={'folder_id':str(folder_id),'mode':'full' if full or finished else 'incremental','pages_fetched':pages,'metadata_fetched':len(found),'new_message_ids':[k for k in found if k not in old]}
    save(path,{'checked_at':clock,'full_at':clock if full or finished else state['full_at'],'messages':rows})
    if not hasattr(run,'mail_scan_reports'):run.mail_scan_reports=[]
    run.mail_scan_reports.append(report)
    return rows
