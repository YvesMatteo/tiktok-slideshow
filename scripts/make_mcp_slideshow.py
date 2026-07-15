#!/usr/bin/env python3
"""Autonomous MCP-servers TikTok slideshow generator.

Each run: keeps CheckVibe as slide 1, randomly picks 4 more MCP servers for
slides 2-5, drops each server's pre-made "laptop on a desk" plate in with a
number pill + caption, builds a title slide, and writes a caption.txt plus a
self-contained post.html share sheet.

Usage:  python3 make_mcp_slideshow.py
Only requires Pillow. Plates + copy come from assets/.
"""
import base64
import html
import json
import os
import random
import sys
import zipfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_slideshow import render_slideshow, plate_path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ASSETS = os.path.join(SKILL_DIR, 'assets')
PLATES = os.path.join(ASSETS, 'mcp_plates')
RUNS = os.path.join(SKILL_DIR, 'runs_mcp')
N_CONTENT = 5   # CheckVibe + 4

POST_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__ — Slideshow Post</title>
<style>
  :root { --bg:#0b0b0b; --panel:#161616; --fg:#f2f2f2; --accent:#7cf05a; --muted:#888; }
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       background:var(--bg);color:var(--fg);padding:24px;
       padding-bottom:max(24px,env(safe-area-inset-bottom))}
  .wrap{max-width:880px;margin:0 auto}
  h1{margin:0 0 4px;font-size:22px;font-weight:700}
  .order{color:var(--muted);font-size:13px;margin-bottom:20px}
  .card{background:var(--panel);border-radius:14px;padding:18px;margin-bottom:14px}
  .label{font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
  textarea{width:100%;min-height:200px;background:transparent;color:var(--fg);
           border:1px solid #2a2a2a;border-radius:8px;padding:12px;font:15px/1.5 inherit;resize:vertical}
  .row{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
  button,.btn{background:var(--accent);color:#000;border:none;padding:14px 22px;font-weight:700;
              border-radius:8px;cursor:pointer;font-size:15px;text-decoration:none;
              display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:48px}
  button.ghost,.btn.ghost{background:#2a2a2a;color:var(--fg)}
  .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}
  .grid img{width:100%;aspect-ratio:3/4;object-fit:cover;border-radius:8px;display:block}
  .ok{background:#fff !important;color:#000 !important}
  @media (max-width:600px){ body{padding:16px} .grid{grid-template-columns:repeat(2,1fr)} button,.btn{width:100%} }
</style></head><body><div class="wrap">
  <h1>__TITLE__</h1>
  <div class="order">Generated __GENERATED__ &nbsp;•&nbsp; __ORDER__</div>
  <div class="card"><div class="label">Caption + hashtags</div>
    <textarea id="caption" readonly>__FULL_CAPTION__</textarea>
    <div class="row"><button onclick="copyCap(this)">Copy caption + hashtags</button></div></div>
  <div class="card"><div class="label">6 Slides</div>
    <div class="grid">__THUMBS__</div>
    <div class="row">
      <button onclick="saveAll(this)">Save all 6 to Photos</button>
      <a class="btn ghost" href="post.zip" download>Download ZIP</a></div></div>
</div><script>
function flash(b,m){const o=b.textContent;b.textContent=m;b.classList.add('ok');
  setTimeout(()=>{b.textContent=o;b.classList.remove('ok');},1600);}
function copyCap(b){const e=document.getElementById('caption');e.select();e.setSelectionRange(0,99999);
  const d=()=>flash(b,'✓ Copied');if(navigator.clipboard){navigator.clipboard.writeText(e.value).then(d,
    ()=>{try{document.execCommand('copy');d();}catch(x){}});}else{try{document.execCommand('copy');d();}catch(x){}}}
async function saveAll(b){const imgs=[...document.querySelectorAll('.slide')];b.disabled=true;const o=b.textContent;b.textContent='Preparing...';
  try{const files=[];for(const img of imgs){const bl=await(await fetch(img.src)).blob();files.push(new File([bl],img.dataset.name,{type:'image/jpeg'}));}
    b.textContent=o;b.disabled=false;if(navigator.canShare&&navigator.canShare({files})){try{await navigator.share({files});flash(b,'✓ Shared');return;}catch(e){if(e.name==='AbortError')return;}}
    for(const f of files){const a=document.createElement('a');a.href=URL.createObjectURL(f);a.download=f.name;document.body.appendChild(a);a.click();a.remove();await new Promise(r=>setTimeout(r,150));}flash(b,'✓ Downloaded');}
  catch(e){b.disabled=false;b.textContent=o;alert('Save failed: '+e.message);}}
</script></body></html>"""


def _b64(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


def write_post_page(out_dir, title, full_caption, order, slide_files):
    with zipfile.ZipFile(os.path.join(out_dir, 'post.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
        for f in slide_files:
            z.write(os.path.join(out_dir, f), f)
    thumbs = ''.join(
        f'<img class="slide" data-name="{f}" src="data:image/jpeg;base64,{_b64(os.path.join(out_dir, f))}">'
        for f in slide_files)
    page = (POST_HTML.replace('__TITLE__', html.escape(title))
            .replace('__ORDER__', html.escape(order))
            .replace('__FULL_CAPTION__', html.escape(full_caption))
            .replace('__THUMBS__', thumbs)
            .replace('__GENERATED__', datetime.now().strftime('%Y-%m-%d %H:%M')))
    with open(os.path.join(out_dir, 'post.html'), 'w') as fp:
        fp.write(page)


def main():
    bank = json.load(open(os.path.join(ASSETS, 'mcp_copy_bank.json')))
    servers = bank['servers']

    first = bank['first_slide']
    pool = [s for s in bank['rotating_pool'] if s != first]
    rest = random.sample(pool, N_CONTENT - 1)
    chosen = [first] + rest

    hook = random.choice(bank['title_hook'])
    sub = random.choice(bank['title_sub'])
    highlight = bank.get('title_highlight', '')
    plate_paths = [plate_path(PLATES, servers[k]['plate']) for k in chosen]

    config = [{'type': 'title', 'hook': hook, 'sub': sub, 'highlight': highlight,
               'bg': plate_path(PLATES, servers[first]['plate']),
               'thumbs': plate_paths}]
    for i, key in enumerate(chosen):
        s = servers[key]
        config.append({'type': 'content', 'plate': s['plate'], 'num': i + 1,
                       'name': s['name'], 'caption': random.choice(s['copy'])})

    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    out_dir = os.path.join(RUNS, stamp)
    render_slideshow(config, PLATES, out_dir)

    title = random.choice(bank['slideshow_title'])
    tags = ' '.join(random.sample(bank['hashtags'], 5))
    order = ' -> '.join(['title'] + [servers[k]['name'] for k in chosen])
    server_list = '\n'.join(f"{i+1}. {servers[k]['name']}: {servers[k]['tagline']}"
                            for i, k in enumerate(chosen))
    template = random.choice(bank['caption_templates'])
    full_caption = template.replace('{server_list}', server_list).replace('{hashtags}', tags)
    with open(os.path.join(out_dir, 'caption.txt'), 'w') as f:
        f.write(f"TITLE: {title}\n\nCAPTION:\n{full_caption}\n\n---\nSlides: {order}\n"
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    slide_files = [f"slide_{i:02d}.jpg" for i in range(len(config))]
    write_post_page(out_dir, title, full_caption, order, slide_files)

    now = datetime.now()
    print(f"GENERATED AT: {now.strftime('%H:%M  %a %b %d')}")
    print(f"FIRST SLIDE: {servers[first]['name']}")
    print(f"Slideshow ready: {out_dir}")
    print(f"  Servers: {order}")
    print(f"  Title: {title}")
    print(f"  Hook: {hook}")
    print(f"  Hashtags: {tags}")
    return out_dir


if __name__ == '__main__':
    main()
