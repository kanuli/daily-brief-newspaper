#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, sys, tempfile, urllib.request, wave
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tts_hktrad_v2 as hktrad

MANIFEST=Path('data/tts-manifest.json'); OUT=Path('artifacts/canto-nano-shards')
ENGINE='typangaa/canto-tts-nano'; VERSION='canto-tts-nano-v1'; VOICE='verified-female-reference'
POLICY='canto-nano-female-hk-news-anchor-v1'; NS='cnf1'; LANG='yue-HK'
SPEAKER='runtime-ref-audio-voice-clone-verified'; PRON='jyutping-tone-cantonese-first'
PACING='hk-tv-news-semantic-pauses-v1'; TARGET='RYTsc9N5748@04:19-05:00'; QUALITY='duration_filter'; MODE='full'
REF_URL='https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/9f24c7f95a2d040c43ce9fadfa56f6f3.wav'
REF_ASSET='9f24c7f95a2d040c43ce9fadfa56f6f3.wav'; LIMIT=int(os.getenv('CANTO_NANO_ARTICLE_MAX_TEXT_CHARS','280'))
COMMA=.16; SEMI=.27; SENT=.36; QUESTION=.40; MICRO=.12; NUMBER=.14
FIELDS=('title','dek','summary','body','context','background','why','whyImportant','watchNext','nextStep')
VERBS=('表示','指出','宣布','稱','認為','警告','強調','證實','公布','透露')
SOMBER=('逝世','悼念','葬禮','罹難','遇難','死亡','死者','喪生','哀悼')
BREAKING=('速報','突發','警報','緊急','最新','即時','地震','海嘯','爆炸','空襲','襲擊')
NUM=re.compile(r'(?:[零一二三四五六七八九十百千萬億兆點]+(?:年|月|日|時|分|秒|人|宗|間|架|艘|部|公里|米|度|級|百分比|美元|港元|英鎊|歐元|日圓)|[0-9０-９]+(?:[\.．,，][0-9０-９]+)?(?:%|％|年|月|日|時|分|秒|人|宗|間|架|艘|部|公里|米|度|級|美元|港元|英鎊|歐元|日圓))')

def clean(v): return re.sub(r'\s+',' ',str(v or '')).strip()
def sid(s):
    x=s.get('id') or s.get('articleId') or s.get('storyId')
    if x: return re.sub(r'[^a-z0-9._-]+','-',clean(x).lower()).strip('-._')[:72] or 'story'
    return 'story-'+hashlib.sha256(clean(s.get('title')).encode()).hexdigest()[:16]
def is_story(x): return isinstance(x,dict) and clean(x.get('title')) and any(clean(x.get(k)) for k in FIELDS[1:])
def walk(x):
    if isinstance(x,dict):
        if is_story(x): yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)
def readj(p):
    p=Path(p)
    if not p.exists(): return None,b''
    b=p.read_bytes(); return json.loads(b.decode()),b
def sources(date):
    a=[Path('data/latest.json'),Path('data/desk-latest.json'),Path('data/live.json'),Path('data/stocks-latest.json')]
    if date: a += [Path(f'data/topic-more/{date}.json'),Path(f'data/editorial-overrides/{date}.json')]
    return a
def src_text(s):
    seen=set(); out=[]
    for k in FIELDS:
        v=clean(s.get(k))
        if v and v not in seen: seen.add(v); out.append(v)
    return '\n'.join(out)
def digest(s): return hashlib.sha256(hktrad.localize(src_text(s)).encode()).hexdigest()
def collect():
    latest,raw=readj('data/latest.json')
    if not latest: raise RuntimeError('data/latest.json missing')
    chosen={}; order=[]; hs=hashlib.sha256(); loaded=[]
    for p in sources(latest.get('date')):
        data,b=readj(p)
        if data is None: continue
        loaded.append(p.as_posix()); hs.update(p.as_posix().encode()+b'\0'+b+b'\0')
        for s in walk(data):
            t=clean(s.get('title')); score=len(src_text(s))
            if t not in chosen: chosen[t]=(s,score); order.append(t)
            elif score>chosen[t][1]: chosen[t]=(s,score)
    stories=[chosen[t][0] for t in order]
    arts=latest.get('articles') or []; lead0=next((x for x in arts if x.get('id')==latest.get('leadId')),None) or (arts[0] if arts else None)
    if not lead0: raise RuntimeError('no lead story')
    lt=clean(lead0.get('title')); stories.sort(key=lambda s:0 if clean(s.get('title'))==lt else 1)
    return latest,raw,stories,sid(lead0),lt,hs.hexdigest(),loaded

def script(s):
    vals=[]; seen=set()
    def add(v):
        v=clean(v)
        if v and v not in seen: seen.add(v); vals.append(v)
    add(s.get('title')); add(s.get('dek')); add(s.get('summary'))
    for p in [clean(x) for x in re.split(r'\n\s*\n',str(s.get('body') or '')) if clean(x)][:2]: add(p)
    add(s.get('context') or s.get('background')); add(s.get('why') or s.get('whyImportant')); add(s.get('watchNext') or s.get('nextStep'))
    out=[]; used=0
    for raw in vals:
        if used>=LIMIT: break
        x=hktrad.localize(raw)[:LIMIT-used]; used+=len(x)
        if x and x[-1] not in '。！？!?': x+='。'
        out.append(x)
    x=''.join(out)
    rem=hktrad.residual_latin_tokens(x)
    if rem: raise RuntimeError('residual Latin gate: '+', '.join(rem))
    if len(x)<8: raise RuntimeError('story too short')
    return x

def style(x):
    if any(w in x for w in BREAKING): return 'breaking-shorter',.86
    if any(w in x for w in SOMBER): return 'somber-longer',1.18
    return 'standard',1.0
def split_core(x):
    if len(x)<=26:return [{'text':x,'pause':0.,'reason':'complete-clause'}]
    m=re.match(r'^((?:在|截至|隨著|由於|根據|按照|受)[^，。！？；：]{7,25}?(?:後|前|時|期間|之際|下|中|內|方面))(.{7,})$',x)
    if m:return [{'text':m.group(1),'pause':MICRO,'reason':'modifier-boundary'},{'text':m.group(2),'pause':0.,'reason':'continuation'}]
    for v in VERBS:
        i=x.find(v)
        if 10<=i<=28 and len(x)-i>=8:return [{'text':x[:i],'pause':MICRO,'reason':'long-subject-before-verb'},{'text':x[i:],'pause':0.,'reason':'continuation'}]
    for v in VERBS:
        i=x.find(v)
        if i>=0:
            e=i+len(v)
            if e>=8 and len(x)-e>=17:return [{'text':x[:e],'pause':MICRO,'reason':'before-long-object'},{'text':x[e:],'pause':0.,'reason':'long-object'}]
    return [{'text':x,'pause':0.,'reason':'unsplit-complete-clause'}]
def num_refine(chunks):
    out=[]
    for c in chunks:
        hit=None
        for m in NUM.finditer(c['text']):
            if len(c['text'][:m.start()])>=8 and len(c['text'][m.end():])>=7: hit=m; break
        if not hit: out.append(c); continue
        x=c['text']; out += [{'text':x[:hit.start()],'pause':NUMBER,'reason':'before-key-number'},{'text':hit.group(0),'pause':NUMBER,'reason':'key-number'},{'text':x[hit.end():],'pause':c['pause'],'reason':'after-key-number'}]
    return [x for x in out if x['text'].strip()]
def units(text):
    sty,f=style(text); pieces=[]; start=0
    for m in re.finditer(r'[。！？!?，、；：]',text): pieces.append(text[start:m.end()]); start=m.end()
    if start<len(text): pieces.append(text[start:])
    out=[]
    for p in [x.strip() for x in pieces if x.strip()]:
        mark=p[-1] if p[-1] in '。！？!?，、；：' else ''; core=p[:-1].strip() if mark else p
        cs=num_refine(split_core(core))
        if not cs: continue
        if mark: cs[-1]['text']+=mark
        q=COMMA if mark and mark in '，、' else SEMI if mark and mark in '；：' else QUESTION if mark and mark in '？?' else SENT if mark and mark in '。！!' else 0.
        if q: cs[-1]['pause']=max(cs[-1]['pause'],q); cs[-1]['reason']='punctuation'
        for c in cs: c['pause']=round(c['pause']*f,3)
        out += cs
    if not out: raise RuntimeError('zero semantic units')
    return out,sty,f

def setup():
    from canto_tts import CantoTTS
    raw=Path('/tmp/canto-female-source.wav'); ref=Path('/tmp/canto-female.wav'); urllib.request.urlretrieve(REF_URL,raw)
    a,sr=sf.read(str(raw),dtype='float32',always_2d=True); a=a[:int(sr*12)]; dur=len(a)/sr
    if dur<3: raise RuntimeError('female reference too short')
    sf.write(str(ref),a,sr,subtype='PCM_16'); refsha=hashlib.sha256(ref.read_bytes()).hexdigest()
    t=CantoTTS(backend='onnx'); b=t._backend; fc=b.encode_reference_audio(str(ref)); dc=b._default_voice_codes
    fs=hashlib.sha256(json.dumps(fc,separators=(',',':')).encode()).hexdigest(); ds=hashlib.sha256(json.dumps(dc,separators=(',',':')).encode()).hexdigest()
    if not fc or fs==ds: raise RuntimeError('female conditioning not applied')
    return t,ref,{'referenceDurationSeconds':round(dur,3),'referenceSha256':refsha,'femalePromptCodesSha256':fs,'defaultPromptCodesSha256':ds}
def wavmeta(p):
    with wave.open(str(p),'rb') as w: d=w.getnframes()/w.getframerate()
    return round(d,3),p.stat().st_size
def synth(t,ref,s,out):
    u,sty,f=units(script(s)); td=Path(tempfile.mkdtemp(prefix='canto-units-')); parts=[]; sr=ch=None
    try:
        for i,x in enumerate(u):
            p=td/f'{i:03}.wav'; print(f"unit={i} reason={x['reason']} pause={x['pause']} text={x['text']}",flush=True)
            t.synthesize(x['text'],str(p),ref_audio=str(ref),quality=QUALITY,max_attempts=3,sample_mode=MODE,text_temperature=.3)
            a,r=sf.read(str(p),dtype='float32',always_2d=True)
            if sr is None:sr,ch=r,a.shape[1]
            if r!=sr or a.shape[1]!=ch:raise RuntimeError('audio format drift')
            parts.append(a)
            if x['pause']>0:parts.append(np.zeros((int(sr*x['pause']),ch),dtype=np.float32))
        m=np.concatenate(parts); out.parent.mkdir(parents=True,exist_ok=True); sf.write(str(out),np.clip(m,-1,1),sr,subtype='PCM_16')
    finally: shutil.rmtree(td,ignore_errors=True)
    d,b=wavmeta(out); chars=sum(len(x['text']) for x in u)
    if d<=2 or b<50000 or d>max(50,chars*.95):raise RuntimeError(f'invalid duration {d}s bytes {b}')
    return {'segmentCount':len(u),'semanticUnitCount':len(u),'speechTextChars':chars,'durationSeconds':d,'bytes':b,'prosodyPolicy':POLICY,'engineVersion':VERSION,'speakerMode':SPEAKER,'referenceAsset':REF_ASSET,'quality':QUALITY,'sampleMode':MODE,'textTemperature':.3,'pronunciationPolicy':PRON,'languageGate':'residual-latin-zero-before-synthesis','segmentPolicy':'semantic-completeness-breathing-audience-processing','pacingPolicy':PACING,'pacingTarget':TARGET,'tempoPolicy':'native-model-rate-no-post-stretch','pauseMarkup':'silence-joined-semantic-units','pauseStyle':sty,'pauseFactor':f,'pauseProfile':{'comma':COMMA,'semantic':SEMI,'sentence':SENT,'micro':MICRO,'number':NUMBER},'semanticUnits':u}
def previous():
    try:
        d=json.loads(MANIFEST.read_text())
        return d if d.get('engine')==ENGINE and d.get('voice')==VOICE and d.get('prosodyPolicy')==POLICY else {}
    except:return {}
def old_entry(prev,s,dig):
    for e in (prev.get('articles') or {}).values():
        if clean(e.get('title'))==clean(s.get('title')) and e.get('contentSha256')==dig and e.get('prosodyPolicy')==POLICY and e.get('speakerMode')==SPEAKER and e.get('referenceAsset')==REF_ASSET and f'-{NS}-' in str(e.get('audio') or ''):return e
    return None
def slot(s,n):return int.from_bytes(hashlib.sha256(sid(s).encode()).digest()[:8],'big')%n
def filename(s,d):return f'{sid(s)}-{NS}-{d[:12]}.wav'

def gen(args):
    latest,raw,stories,lead,lt,ss,loaded=collect(); prev=previous(); missing=[]
    for s in stories:
        d=digest(s)
        if not old_entry(prev,s,d): missing.append((s,d))
    pick=[x for x in missing if slot(x[0],args.slots)==args.slot][:1]
    entries={}; sm={}
    if pick:
        t,ref,sm=setup(); s,dig=pick[0]; fn=filename(s,dig); art=OUT/'audio'/f'slot-{args.slot}'/fn
        entries[sid(s)]={'articleId':sid(s),'title':clean(s.get('title')),'contentSha256':dig,'audioFilename':fn,'artifactAudio':art.as_posix(),'wavEncoding':'PCM16',**sm,**synth(t,ref,s,art)}
    OUT.mkdir(parents=True,exist_ok=True); p={'version':1,'engine':ENGINE,'voice':VOICE,'language':LANG,'slot':args.slot,'slots':args.slots,'generatedAt':datetime.now(timezone.utc).isoformat(),'date':latest.get('date'),'leadId':lead,'leadTitle':lt,'sourceSha256':hashlib.sha256(raw).hexdigest(),'sourceSetSha256':ss,'sourceFiles':loaded,'collectedStoryCount':len(stories),'entries':entries}
    (OUT/f'shard-{args.slot}.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n'); print(f'CANTO_NANO_SHARD_PASS slot={args.slot} generated={len(entries)}')
def publish(args):
    sh=json.loads(Path(args.shard).read_text()); es=sh.get('entries') or {}
    if not es: print('CANTO_NANO_PUBLISH_NOOP'); return
    aid,e=next(iter(es.items())); latest,raw,stories,lead,lt,ss,loaded=collect(); cur={sid(s):(s,digest(s)) for s in stories}
    if aid not in cur or cur[aid][1]!=e.get('contentSha256'): print('CANTO_NANO_PUBLISH_STALE'); return
    prev=previous(); e=dict(e); e.pop('artifactAudio',None); e['audio']=args.public_base.rstrip('/')+'/'+e.pop('audioFilename'); now=datetime.now(timezone.utc).isoformat(); e['publishedAt']=now
    ents={}
    for s in stories:
        i=sid(s); d=digest(s)
        if i==aid:ents[i]=e
        else:
            o=old_entry(prev,s,d)
            if o:ents[i]=o
    man={'version':4,'engine':ENGINE,'engineVersion':VERSION,'voice':VOICE,'language':LANG,'speakerMode':SPEAKER,'referenceAsset':REF_ASSET,'pronunciationPolicy':PRON,'prosodyPolicy':POLICY,'quality':QUALITY,'sampleMode':MODE,'pacingPolicy':PACING,'pacingTarget':TARGET,'tempoPolicy':'native-model-rate-no-post-stretch','segmentPolicy':'semantic-completeness-breathing-audience-processing','assetNamespace':NS,'coveragePolicy':'progressive-current-news-canto-nano-female-only','generationMode':'per-article-parallel-semantic-units','storageBackend':'github-release','generatedAt':now,'lastVoicePublishedAt':now,'source':'multi-source-current-site','sourceSha256':hashlib.sha256(raw).hexdigest(),'sourceSetSha256':ss,'sourceFiles':loaded,'date':latest.get('date'),'leadId':lead,'leadTitle':lt,'articleCount':len(ents),'availableArticleCount':len(ents),'collectedStoryCount':len(stories),'pendingArticleCount':len(stories)-len(ents),'coverageComplete':len(ents)==len(stories),'lastPublishedArticleId':aid,'lastPublishedTitle':e.get('title') or '','articles':ents}
    MANIFEST.write_text(json.dumps(man,ensure_ascii=False,indent=2)+'\n'); print(f'CANTO_NANO_PUBLISH_PASS article={aid} available={len(ents)}/{len(stories)}')
def reset(args):
    latest,raw,stories,lead,lt,ss,loaded=collect(); m={'version':4,'engine':ENGINE,'engineVersion':VERSION,'voice':VOICE,'language':LANG,'speakerMode':SPEAKER,'referenceAsset':REF_ASSET,'pronunciationPolicy':PRON,'prosodyPolicy':POLICY,'quality':QUALITY,'sampleMode':MODE,'pacingPolicy':PACING,'pacingTarget':TARGET,'tempoPolicy':'native-model-rate-no-post-stretch','segmentPolicy':'semantic-completeness-breathing-audience-processing','assetNamespace':NS,'coveragePolicy':'progressive-current-news-canto-nano-female-only','generationMode':'per-article-parallel-semantic-units','storageBackend':'github-release','generatedAt':'','lastVoicePublishedAt':'','source':'multi-source-current-site','sourceSha256':hashlib.sha256(raw).hexdigest(),'sourceSetSha256':ss,'sourceFiles':loaded,'date':latest.get('date'),'leadId':lead,'leadTitle':lt,'articleCount':0,'availableArticleCount':0,'collectedStoryCount':len(stories),'pendingArticleCount':len(stories),'coverageComplete':False,'lastPublishedArticleId':'','lastPublishedTitle':'','articles':{}}; MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n'); print(f'CANTO_NANO_RESET_PASS pending={len(stories)}')

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('generate-shard');p.add_argument('--slot',type=int,required=True);p.add_argument('--slots',type=int,default=10);p.set_defaults(func=gen)
    p=sp.add_parser('publish');p.add_argument('shard');p.add_argument('--public-base',required=True);p.set_defaults(func=publish)
    p=sp.add_parser('reset-manifest');p.set_defaults(func=reset)
    a=ap.parse_args();a.func(a);return 0
if __name__=='__main__':raise SystemExit(main())
