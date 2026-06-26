#!/usr/bin/env python3
import json, re, time, urllib.parse, urllib.request, pathlib, runpy
ROOT=pathlib.Path(__file__).resolve().parent
CACHE_PATH=ROOT/'product_i18n_cache.json'
ns=runpy.run_path(str(ROOT/'build_products.py'))
PRODUCTS=ns['PRODUCTS']
LANGS=['en','fr','ar']
cache=json.loads(CACHE_PATH.read_text(encoding='utf-8')) if CACHE_PATH.exists() else {}
mem=cache.setdefault('_memory',{})
def tr(text, dst, src='en'):
    if dst==src or not text or not re.search(r'[A-Za-zÀ-ÿ]', text): return text
    key=f'{src}>{dst}:{text}'
    if key in mem: return mem[key]
    url='https://translate.googleapis.com/translate_a/single?client=gtx&dt=t&sl='+src+'&tl='+dst+'&q='+urllib.parse.quote(text)
    for a in range(4):
        try:
            data=json.loads(urllib.request.urlopen(url,timeout=20).read().decode())
            out=''.join(part[0] for part in data[0] if part and part[0])
            mem[key]=out
            CACHE_PATH.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf-8')
            time.sleep(.08)
            return out
        except Exception:
            time.sleep(.6*(a+1))
    mem[key]=text; return text
for p in PRODUCTS:
    e=cache.setdefault(p['slug'],{})
    for lang in LANGS:
        d=e.setdefault(lang,{})
        for field in ['tag','title','short','intro_heading','intro']:
            d[field]=tr(p[field],lang)
        d['benefits']=[(tr(t,lang),tr(desc,lang)) for t,desc in p['benefits']]
        d['spec_groups']=[(tr(gt,lang),[(tr(k,lang),tr(v,lang)) for k,v in rows]) for gt,rows in p['spec_groups']]
        d['tables']=[{'title':tr(t['title'],lang),'headers':[tr(h,lang) for h in t['headers']],'rows':[[tr(c,lang) for c in row] for row in t['rows']]} for t in p['tables']]
        CACHE_PATH.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf-8')
        print(p['slug'],lang)
cache['_memory']=mem
CACHE_PATH.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf-8')
print('saved',CACHE_PATH)
