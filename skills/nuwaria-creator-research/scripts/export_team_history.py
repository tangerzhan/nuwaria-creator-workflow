"""Export only dedup identifiers and screening verdicts from an authorized workspace."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def export(project, output):
    project = Path(project).resolve()
    config = read(project / 'project.json')
    handles, emails, people, screening = set(), set(), set(), {}
    folders = [Path(p) for p in config.get('history_projects', [])] + [project]
    for folder in folders:
        if not (folder / 'production_reviews.json').exists():
            raise ValueError('Missing history project: ' + str(folder))
        prior = read(folder / 'historical_exclusions.json', {})
        handles.update(read(folder / 'excluded_handles.json', []))
        handles.update(prior.get('handles', []))
        emails.update(prior.get('emails', []))
        people.update(prior.get('person_keys', []))
        aliases = read(folder / 'identity_aliases.json', {})
        for h, review in read(folder / 'production_reviews.json', {}).items():
            if review.get('verdict') != 'include':
                continue
            handles.update([h, h.removeprefix('tt__'), *review.get('aliases', []), *aliases.get(h, [])])
            people.add(review.get('person_key', h))
            profile = read(folder / 'profiles' / (h + '.json'), {})
            emails.update([review['public_email']] if review.get('public_email') else profile.get('emails', []))
        for file in [folder / 'screening_decisions.json', *sorted(folder.glob('screening_extra_*.json'), key=lambda p: tuple(int(n) for n in re.findall(r'\d+', p.stem))), folder / 'screening.json']:
            for h, decision in read(file, {}).items():
                if not isinstance(decision, dict):
                    continue
                verdict = decision.get('verdict')
                if verdict in ('hold', 'exclude'):
                    screening[h.lower()] = {'verdict': verdict, 'project': folder.name,
                                           'reason': '团队历史初筛记录；有新证据可在本批明确标记pass后复查。'}
                elif verdict == 'pass':
                    screening.pop(h.lower(), None)
    normalize = lambda values: sorted({str(v).strip().lower() for v in values if v})
    result = {'version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
              'source_batches': [f.name for f in folders],
              'scope': 'Local historical exclusion indexes and selected reviews, including current unfinished batch; not live contact status.',
              'handles': normalize(handles), 'emails': normalize(emails),
              'person_keys': normalize(people), 'screening': dict(sorted(screening.items()))}
    Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return {k: len(result[k]) for k in ['handles', 'emails', 'person_keys', 'screening']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.project, args.output)))
