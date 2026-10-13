"""Shared configuration; never fall back to a previous project's data."""
import json,os,re
from contextlib import asynccontextmanager
from datetime import date,timedelta
from pathlib import Path
if not os.environ.get('CREATOR_PROJECT'):
 raise RuntimeError('Use creator_workflow/workflow.py --project PATH ...')
P=Path(os.environ['CREATOR_PROJECT']).resolve()
CONFIG=json.loads((P/'project.json').read_text(encoding='utf8'))
DATE=date.fromisoformat(CONFIG['date']).isoformat();TARGET=int(CONFIG['target'])
if TARGET<1:raise ValueError('target must be positive')
CUTOFF=(date.fromisoformat(DATE)-timedelta(days=30)).isoformat()
CDP=CONFIG.get('cdp','http://127.0.0.1:9222')
OUTPUT=Path(os.environ['CREATOR_OUTPUT']).resolve() if os.environ.get('CREATOR_OUTPUT') else P/CONFIG.get('output_name',f'NUWARIA_新候选达人{TARGET}_{DATE}.xlsx')

@asynccontextmanager
async def research_page(context):
 """Always close only the tab created by this research operation."""
 page=await context.new_page()
 try:
  yield page
 finally:
  if not page.is_closed():await page.close()
def screening(project=None):
 project=Path(project) if project is not None else P
 out={}
 for f in [project/'screening_decisions.json',*sorted(project.glob('screening_extra_*.json'),key=lambda f:tuple(int(n) for n in re.findall(r'\d+',f.stem))),project/'screening.json']:
  if f.exists():out.update(json.loads(f.read_text(encoding='utf8')))
 return out
