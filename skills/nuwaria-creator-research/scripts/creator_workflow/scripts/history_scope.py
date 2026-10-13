"""Keep this project's verified Notion imports out of its historical exclusions."""
import json


def scope_verified_own_records(project, handles, emails, people):
    """Undo inherited self-collisions only for explicitly evidenced own records.

    Recheck every available raw snapshot and prior accepted list before removing
    an identity from the aggregate index. This does not exempt new candidates.
    """
    path = project / 'own_history_references.json'
    if not path.exists():
        return
    refs = json.loads(path.read_text(encoding='utf-8'))
    reviews = json.loads((project / 'production_reviews.json').read_text(encoding='utf-8'))
    config = json.loads((project / 'project.json').read_text(encoding='utf-8'))
    from pathlib import Path
    import re
    for h, ref in refs.items():
        review = reviews.get(h, {})
        if review.get('verdict') != 'include':
            continue
        source = Path(ref['snapshot'])
        rows = json.loads(source.read_text(encoding='utf-8'))
        own_rows = [r for r in rows if r.get('id') == ref['page_id']]
        if len(own_rows) != 1 or h not in json.dumps(own_rows[0]):
            raise ValueError('Own-history reference no longer matches: ' + h)
        keys = {h.lower(), review.get('person_key', h).lower(),
                *(a.lower() for a in review.get('aliases', []))}
        mail = review.get('public_email', '').lower()
        if mail:
            keys.add(mail)
        external = set()
        for folder in [project, *(Path(p) for p in config.get('history_projects', []))]:
            snapshot = folder / 'existing.json'
            if snapshot.exists():
                for row in json.loads(snapshot.read_text(encoding='utf-8')):
                    if row.get('id') != ref['page_id']:
                        props = row.get('properties', {})
                        text = json.dumps({k: props.get(k) for k in
                                           ['账号', '公开联系方式', '主页链接', 'Instagram主页', 'TikTok主页']},
                                          ensure_ascii=False).lower()
                        tokens = set(re.findall(r'[\w.@+-]+', text))
                        external.update(keys & tokens)
            if folder.resolve() != project.resolve():
                prior = folder / 'production_reviews.json'
                if prior.exists():
                    for handle, item in json.loads(prior.read_text(encoding='utf-8')).items():
                        if item.get('verdict') == 'include':
                            identity = {handle.lower(), item.get('person_key', handle).lower(),
                                        item.get('public_email', '').lower(),
                                        *(a.lower() for a in item.get('aliases', []))}
                            external.update(keys & identity)
        removable = keys - external
        handles.difference_update(removable)
        emails.difference_update(removable)
        people.difference_update(removable)

def external_history(project, rows):
    path=project/'outreach'/'notion_import_log.json'
    refs_path=project/'own_history_references.json'
    if not path.exists() and not refs_path.exists():
        return rows
    log=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    reviews=json.loads((project/'production_reviews.json').read_text(encoding='utf-8-sig'))
    own={v['page_id']:h for h,v in log.items()
         if v.get('status')=='verified' and v.get('page_id')
         and reviews.get(h,{}).get('verdict')=='include'}
    if refs_path.exists():
        refs=json.loads(refs_path.read_text(encoding='utf-8'))
        own.update({v['page_id']:h for h,v in refs.items()
                    if reviews.get(h,{}).get('verdict')=='include'})
    result=[]
    for row in rows:
        prop=row.get('properties',{}).get('账号',{})
        account=''.join(t.get('plain_text',t.get('text',{}).get('content',''))
                        for t in prop.get(prop.get('type','rich_text'),[])).strip().lstrip('@').lower()
        if own.get(row.get('id'),'').lower()==account and account:
            continue
        result.append(row)
    return result
