import asyncio,json,sys
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright
from workflow_context import research_page, P, CONFIG, DATE, TARGET, CUTOFF, OUTPUT, CDP
sys.stdout.reconfigure(encoding='utf8')
async def main():
 async with async_playwright() as pw:
  b=await pw.chromium.connect_over_cdp(CDP)
  async with research_page(b.contexts[0]) as pg:
   for spec in sys.argv[1:]:
    h,ids=spec.split(':');r=json.loads((P/'profiles'/f'{h}.json').read_text(encoding='utf8'));f=P/'post_audits'/h/'audit.json';a=json.loads(f.read_text(encoding='utf8'))
    try:
     await pg.goto(r['url'],wait_until='domcontentloaded',timeout=35000);await pg.wait_for_timeout(1800)
     for idx in map(int,ids.split(',')):
      q=a[idx-1];code=r['posts'][idx-1]['code']
      try:
       link=pg.locator('a[href*="'+code+'"]').first
       for _ in range(3):
        if await link.count():break
        await pg.evaluate('window.scrollTo(0,document.body.scrollHeight)');await pg.wait_for_timeout(1200)
       await link.click(timeout=7000);await pg.wait_for_timeout(1800)
       dialogs=pg.get_by_role('dialog');text=await dialogs.last.inner_text() if await dialogs.count() else await pg.locator('body').inner_text()
       if not text.strip():
        await pg.wait_for_timeout(2500)
        text=await dialogs.last.inner_text() if await dialogs.count() else await pg.locator('body').inner_text()
       if not text.strip():raise ValueError('Visible comment modal remained empty; not recorded as checked')
       q['public_text']=text;q['comments_checked_at']=datetime.now().isoformat();q['comments_method']='Native profile thumbnail click; visible default comments; no replies expanded'
       print(h,idx,'OK',len(text),flush=True)
       await pg.keyboard.press('Escape');await pg.wait_for_timeout(500)
      except Exception as e:
       q['comments_error']=str(e)[:180];print(h,idx,'ERROR',str(e)[:100],flush=True)
       await pg.keyboard.press('Escape');await pg.wait_for_timeout(500)
      f.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf8')
    except Exception as e:print(h,'PROFILE ERROR',str(e)[:100],flush=True)

asyncio.run(main())
