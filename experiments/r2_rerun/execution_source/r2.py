"""Supplementary evaluation harness. Run from this directory; see README.md."""
import argparse,base64,csv,hashlib,html,importlib.metadata,json,math,os,random,re,subprocess,sys,time,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
STUDY=json.loads(Path('study.json').read_text())
OUT=Path('work_rerun');OUT.mkdir(exist_ok=True)
from rerun_support import Recorder, ProviderHalt, error_details, utc

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):
 def clean(v):
  if isinstance(v,float) and not math.isfinite(v):return None
  if isinstance(v,dict):return {k:clean(z) for k,z in v.items()}
  if isinstance(v,list):return [clean(z) for z in v]
  return v
 x=clean(x)
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(p)
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def mistral():
 from dotenv import load_dotenv
 load_dotenv()
 try: from mistralai.client import Mistral
 except ImportError: from mistralai import Mistral
 return Mistral(api_key=os.environ['MISTRAL_API_KEY'])
def dump(x): return x.model_dump(mode='json')
def configure():
 # Study settings override incidental environment settings, except API keys.
 for k,v in {'ARA_API_TIMEOUT':STUDY['rerun']['request_timeout_s'],'ARA_LLM_MODEL':STUDY['models']['generator'],'ARA_EMBED_MODEL':STUDY['models']['embedding'],'ARA_AMB_MODE':'idf','ARA_USE_PARSE_DEPTH':'0','ARA_CALIB_STATS_PATH':'./calib_db/corpus_stats.json','ARA_LEARNED_WEIGHTS':'./calibration/learned_weights.json','ARA_TOP_K':STUDY['top_k'],'ARA_CHUNK_SIZE':STUDY['chunk_size'],'ARA_CHUNK_OVERLAP':STUDY['chunk_overlap'],'ARA_GYM_MAX_STEPS':6,'ARA_GYM_NUM_CANDIDATES':3}.items(): os.environ[k]=str(v)

def prepare():
 assert not (OUT/'freeze.json').exists(),'Do not modify frozen inputs'
 import fitz
 for item in read('source_manifest.json'):
  assert digest(Path('sources')/item['file'])==item['sha256'],'Source checksum differs'
 pdf=fitz.open('sources/DEFENCE.pdf')
 write(OUT/'defence_pages.json',[{'page':i+1,'text':p.get_text()} for i,p in enumerate(pdf)])
 pdf=fitz.open('sources/CIRCULARS.pdf')
 for n in STUDY['ocr_pages']:
  dest=OUT/'pages'/f'{n:02}.pdf';dest.parent.mkdir(exist_ok=True)
  if not dest.exists():
   d=fitz.open();d.insert_pdf(pdf,from_page=n-1,to_page=n-1);d.save(dest)
   pdf[n-1].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(str(dest.with_suffix('.png')))
 if not (OUT/'reference_checks.json').exists():
  write(OUT/'reference_checks.json',[{'page':n,'verified':False,'verifier':'','notes':''} for n in STUDY['ocr_pages']])
 print('Prepared source pages. Next: ocr. No API calls in prepare.')

def ocr():
 assert not (OUT/'freeze.json').exists(),'Do not modify frozen inputs'
 client=mistral()
 for n in STUDY['ocr_pages']:
  dest=OUT/'ocr'/f'{n:02}.json';md=dest.with_suffix('.md')
  if not dest.exists():
   data=base64.b64encode((OUT/'pages'/f'{n:02}.pdf').read_bytes()).decode()
   t=time.perf_counter();r=client.ocr.process(model=STUDY['models']['ocr'],document={'type':'document_url','document_url':'data:application/pdf;base64,'+data})
   write(dest,{'elapsed_s':time.perf_counter()-t,'response':dump(r)})
  obj=read(dest)
  text='\n\n'.join(p['markdown'] for p in obj['response']['pages'])
  if not text.strip(): raise ValueError(f'Blank OCR page {n}')
  if not md.exists(): md.write_text(text,encoding='utf-8')
  ref=OUT/'corrected'/f'{n:02}.md';ref.parent.mkdir(exist_ok=True)
  if not ref.exists(): ref.write_text(text,encoding='utf-8')
  print('OCR saved:',n)
 print('Correct work_rerun/corrected/*.md against images, then verify reference_checks.json and questions.json.')

def lock_inputs():
 paths=[Path('study.json'),Path('questions.json'),Path('source_manifest.json'),Path('config.py'),Path('r2.py'),Path('analyze.py'),Path('requirements.txt')]
 paths+=list(Path('.').glob('*.py'))+[Path('AMENDMENT.md'),Path('input_provenance.json')]
 paths+=list(Path('ara').glob('*.py'))+[Path('calibration/learned_weights.json'),Path('calib_db/corpus_stats.json')]
 paths+=list(Path('sources').glob('*.pdf'))+[OUT/'defence_pages.json',OUT/'reference_checks.json']
 paths+=list((OUT/'ocr').glob('*'))+list((OUT/'corrected').glob('*.md'))
 return {str(p):digest(p) for p in sorted(paths)}
def freeze():
 assert not (OUT/'freeze.json').exists(),'Already frozen; do not overwrite a registered run'
 assert (OUT/'smoke_pass.json').exists(),'Run smoke successfully before freeze'
 assert read(OUT/'smoke_pass.json')['inputs']==lock_inputs(),'Inputs changed since smoke check; rerun smoke before freezing'
 qs=read('questions.json');refs=read(OUT/'reference_checks.json')
 assert len(qs)==20 and len({q['id'] for q in qs})==20
 assert {x['page'] for x in refs}==set(STUDY['ocr_pages'])
 for x in qs+refs: assert x['verified'] is True and x['verifier'].strip(),'All references/questions need named human verification'
 for n in STUDY['ocr_pages']:
  assert (OUT/'corrected'/f'{n:02}.md').read_text(encoding='utf-8').strip()
  assert (OUT/'ocr'/f'{n:02}.json').exists()
 write(OUT/'freeze.json',{'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'sha256':lock_inputs(),'python':sys.version,'packages':subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True).splitlines()})
 print('Frozen. Do not tune on these questions or edit frozen files.')
def checked():
 f=read(OUT/'freeze.json');assert lock_inputs()==f['sha256'],'Frozen inputs changed. Preserve this experiment; investigate before continuing.'
 configure()

def pages(source):
 if source=='DEFENCE': return read(OUT/'defence_pages.json')
 folder='corrected' if source=='CORRECTED' else 'ocr'
 return [{'page':n,'text':(OUT/folder/f'{n:02}.md').read_text(encoding='utf-8')} for n in STUDY['ocr_pages']]
def index():
 checked()
 from ara.vectorstore import get_collection
 from ara import llm
 rec=Recorder()
 if (OUT/'index_calls.json').exists():rec.embeddings=read(OUT/'index_calls.json')
 def indexed_embed(texts):
  try:return rec.embed(texts)
  finally:write(OUT/'index_calls.json',rec.embeddings)
 llm.embed=indexed_embed
 for source in ['DEFENCE','CIRCULARS','CORRECTED']:
  col=get_collection(str(OUT/'indexes'/source));existing=set(col.get()['ids'])
  for page in pages(source):
   text=page['text'];step=STUDY['chunk_size']-STUDY['chunk_overlap']
   for start in range(0,len(text),step):
    chunk=text[start:start+STUDY['chunk_size']]
    if not chunk.strip():continue
    cid=f'{source}_{page["page"]:02}_{start}'
    if cid in existing:continue
    metadata={'source':f'{"CIRCULARS" if source=="CORRECTED" else source} PDF page {page["page"]}','page':page['page'],'chunk_id':cid}
    col.add(ids=[cid],documents=[chunk],embeddings=llm.embed([chunk]),metadatas=[metadata])
  print(source,col.count(),'chunks')
 write(OUT/'index_ready.json',{'freeze':digest(OUT/'freeze.json')})


def jobs():
 qs=read('questions.json');alljobs=[]
 rng=random.Random(STUDY['seed'])
 for rep in range(STUDY['repetitions']):
  batch=[]
  for q in qs:
   for system in ['ARA','FLOW','GYM','GPT_GROUNDED','MISTRAL_GROUNDED']:
    batch.append((q,system,rep))
   if q['source']=='CIRCULARS':batch.append((q,'FLOW_CORRECTED',rep))
  rng.shuffle(batch);alljobs.extend(batch)
 return alljobs

def run(limit=0,stage='primary',smoke_jobs=None):
 if smoke_jobs is None:
  checked();assert read(OUT/'index_ready.json')['freeze']==digest(OUT/'freeze.json')
 else: configure()
 import config
 from ara import llm,retriever,rag_flow,rag_gym,router,complexity
 original_retrieve=retriever.retrieve
 count=0
 for q,system,rep in (smoke_jobs if smoke_jobs is not None else jobs()):
  if smoke_jobs is None and ((stage=='primary' and rep!=0) or (stage=='timing' and rep==0)):continue
  name=f'{q["id"]}_{system}_{rep}';dest=OUT/'runs'/f'{name}.json'
  if dest.exists():continue # failures are preserved, never silently replaced
  source='CORRECTED' if system=='FLOW_CORRECTED' else q['source']
  config.DB_DIR=str(OUT/'indexes'/source)
  rec=Recorder();llm.complete=rec.completion;llm.embed=rec.embed;llm.note_fallback=rec.note_fallback
  llm.complete_json=lambda messages,temperature=.2,max_tokens=1024:rec.completion(messages,temperature,max_tokens,json_mode=True)
  def recorded_retrieve(query,top_k=None,persist_dir=None):
   t=time.perf_counter();chunks=original_retrieve(query,top_k,persist_dir)
   rec.retrievals.append({'query':query,'chunks':chunks,'elapsed_s':time.perf_counter()-t});return chunks
  retriever.retrieve=recorded_retrieve
  result={'id':name,'qid':q['id'],'source':q['source'],'system':system,'rep':rep,'question':q['question'],'freeze_sha256':digest(OUT/'freeze.json') if smoke_jobs is None else None,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
  t=time.perf_counter()
  try:
   if system=='ARA':r=router.ask(q['question'])
   elif system in ['FLOW','FLOW_CORRECTED']:r=rag_flow.answer(q['question'])
   elif system=='GYM':r=rag_gym.answer(q['question'])
   else:
    chunks=retriever.retrieve(q['question']);context=retriever.format_context(chunks)
    messages=[{'role':'system','content':rag_flow.SYSTEM},{'role':'user','content':f'Contract context:\n{context}\n\nQuestion: {q["question"]}\n\nAnswer:'}]
    provider='mistral' if system=='MISTRAL_GROUNDED' else 'openai'
    model=STUDY['models']['mistral_baseline' if provider=='mistral' else 'gpt_baseline']
    r={'answer':rec.completion(messages,temperature=.1,max_tokens=1024,provider=provider,model=model)}
   result.update(r);result['status']='ok'
   if rec.fallbacks or any('error_type' in c or any(a.get('status')=='failed' for a in c.get('attempts',[])) for c in rec.calls+rec.embeddings):result['status']='degraded' # catches swallowed original pipeline failures
  except Exception as e:result.update(status='failed',error_type=type(e).__name__,error=error_details(e),batch_halted=isinstance(e,ProviderHalt))
  finally:
   result.update(elapsed_s=time.perf_counter()-t,calls=rec.calls,retrievals=rec.retrievals,embedding_calls=rec.embeddings,fallbacks=rec.fallbacks,ended_utc=utc())
   write(dest,result)
  print(name,result['status'],round(result['elapsed_s'],1),'s',flush=True)
  count+=1
  if result['status']!='ok' and STUDY['rerun']['stop_after_non_ok']:
   print('STOPPED after a non-ok attempt. Run status and inspect the saved record before continuing.',flush=True)
   return False
  if limit and count>=limit:break
 print('Saved',count,'new attempts. Repeat the same command to resume; every existing attempt is preserved.')
 return True

def forms():
 checked()
 pending=[f'{q["id"]}_{system}_0.json' for q,system,rep in jobs() if rep==0 and not (OUT/'runs'/f'{q["id"]}_{system}_0.json').exists()]
 assert not pending,f'{len(pending)} primary jobs have not been attempted; finish primary stage before generating forms'
 assert not (OUT/'rating_key.csv').exists(),'Rating packet already exists; preserve blinding'
 qs={q['id']:q for q in read('questions.json')}
 records=[];missing=[]
 for q,system,rep in jobs():
  if rep!=0:continue
  p=OUT/'runs'/f'{q["id"]}_{system}_0.json'
  if not p.exists() or read(p)['status']!='ok':missing.append(p.name);continue
  records.append(read(p))
 assert records,'No eligible rep-0 outputs'
 rng=random.Random(STUDY['seed']+1);rng.shuffle(records)
 key=[]
 for i,r in enumerate(records):r['blind_id']=f'B{i+1:03}';key.append({'blind_id':r['blind_id'],'run_id':r['id']})
 write(OUT/'rating_missing.json',missing)
 def csvfile(p,rows,fields):
  with p.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 csvfile(OUT/'rating_key.csv',key,['blind_id','run_id'])
 for evaluator in [1,2]:
  folder=OUT/f'evaluator_{evaluator}';folder.mkdir()
  import shutil
  shutil.copytree('sources',folder/'sources')
  order=records.copy();random.Random(STUDY['seed']+evaluator+100).shuffle(order)
  rows=[];body=[]
  for r in order:
   q=qs[r['qid']];bid=r['blind_id']
   evidence='\n\n'.join('Search: '+t['query']+'\n'+'\n\n'.join(f'[{j}] '+c['metadata']['source']+'\n'+c['text'] for j,c in enumerate(t['chunks'],1)) for t in r['retrievals'])
   body.append(f'<article><h2>{bid}</h2><p><b>Question:</b> {html.escape(q["question"])}</p><h3>Answer to rate</h3><pre>{html.escape(r["answer"])}</pre><details><summary>Retrieved passages (for citation mapping)</summary><pre>{html.escape(evidence)}</pre></details><h3>Verified reference</h3><pre>{html.escape(q["reference_answer"])}</pre><p>Evidence: <a href="sources/{q["source"]}.pdf">{q["source"]}.pdf</a>, PDF pages {q["pdf_pages"]}. Check the source itself.</p></article>')
   rows.append(dict(blind_id=bid,correctness='',citation_total='',citation_supported='',factual_claims='',unsupported_claims='',notes=''))
  fields=list(rows[0]);csvfile(folder/'ratings.csv',rows,fields)
  (folder/'answers.html').write_text('<meta charset="utf-8"><style>body{font:18px sans-serif;max-width:950px;margin:40px auto}pre{white-space:pre-wrap}article{border-bottom:2px solid #bbb;padding:20px 0}</style>'+''.join(body),encoding='utf-8')
 print('Send each evaluator ONLY their evaluator_N folder plus RATING_GUIDE.md. Keep rating_key.csv private.')

def status():
 from collections import Counter
 records=[read(p) for p in (OUT/'runs').glob('*.json')]
 expected={f'{q["id"]}_{system}_{rep}' for q,system,rep in jobs()}
 present={r['id'] for r in records}
 print('Formal runs:',len(records),'of',len(expected),'planned')
 print('Statuses:',dict(Counter(r['status'] for r in records)))
 print('Unattempted:',len(expected-present))
 for stage,reps in [('Primary',{0}),('Timing',{1,2,3,4})]:
  rr=[r for r in records if r['rep'] in reps]
  print(stage,dict(Counter(r['status'] for r in rr)))
 print('Output directory:',OUT.resolve())

def preflight():
 try:
  from dotenv import load_dotenv
  load_dotenv()
 except ModuleNotFoundError:
  print('python-dotenv is not installed. Install requirements.txt before live commands; key checks below only inspect the environment.')
 configure()
 for key in ['OPENAI_API_KEY','MISTRAL_API_KEY']:
  print(key, 'present' if os.getenv(key) and os.getenv(key)!='replace_on_your_computer' else 'MISSING')
 for item in read('source_manifest.json'):
  assert digest(Path('sources')/item['file'])==item['sha256'],'Source checksum differs'
 for path,sha in read('input_provenance.json')['packaged_inputs'].items():
  assert digest(path)==sha,'Supplied input changed: '+path
 assert len(read('questions.json'))==20
 for n in STUDY['ocr_pages']:
  assert (OUT/'ocr'/f'{n:02}.md').read_text(encoding='utf-8').strip()
  assert (OUT/'corrected'/f'{n:02}.md').read_text(encoding='utf-8').strip()
 print('Input checks passed. No API calls made; this does not establish account access.')

def smoke():
 """Paid synthetic pipeline checks, segregated from formal study outputs."""
 global OUT
 assert not (OUT/'freeze.json').exists(),'Smoke is a pre-freeze technical check; do not alter an existing frozen experiment'
 configure()
 from ara import llm
 from ara.vectorstore import get_collection
 formal_out=OUT
 target=formal_out/'smoke'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
 target.mkdir(parents=True,exist_ok=False)
 print('Smoke uses synthetic questions and makes paid API calls. Output:',target)
 rec=Recorder();llm.embed=rec.embed
 try:
  for source in ['DEFENCE','CIRCULARS','CORRECTED']:
   col=get_collection(str(target/'indexes'/source))
   text='Technical test contract: the notice period is 14 days. A claim requires written notice to the engineer within 14 days and supporting records within 28 days. Late notice requires an explanation and an engineer decision.'
   col.add(ids=[source+'_TEST'],documents=[text],embeddings=llm.embed([text]),metadatas=[{'source':source+' TEST page 1','page':1,'chunk_id':source+'_TEST'}])
  q={'id':'TECH01','source':'DEFENCE','question':'If a contractor sends a late notice, explain which notice periods and supporting records apply and how the engineer should decide the claim.'}
  tests=[(q,x,0) for x in ['ARA','FLOW','GYM','GPT_GROUNDED','MISTRAL_GROUNDED']]
  tests.append((dict(q,id='TECH02',source='CIRCULARS'),'FLOW_CORRECTED',0))
  OUT=target
  ok=run(stage='primary',smoke_jobs=tests)
  rr=[read(p) for p in (OUT/'runs').glob('*.json')]
  if not ok or len(rr)!=6 or any(r['status']!='ok' for r in rr):raise RuntimeError('Smoke did not pass. Inspect logs before freezing or formal runs.')
 finally:
  write(target/'embedding_setup.json',rec.embeddings)
  OUT=formal_out
 write(OUT/'smoke_pass.json',{'utc':utc(),'path':str(target),'inputs':lock_inputs()})
 print('All six technical checks passed. You may now freeze the formal study.')

def main():
 p=argparse.ArgumentParser()
 p.add_argument('command',choices=['preflight','smoke','prepare','ocr','freeze','index','run','forms','status'])
 p.add_argument('--limit',type=int,default=0,help='Maximum NEW formal attempts this invocation; zero means all remaining in stage')
 p.add_argument('--stage',choices=['primary','timing','all'],default='primary')
 a=p.parse_args()
 if a.limit<0:p.error('--limit must be nonnegative')
 if a.command=='run':
  if not run(a.limit,a.stage):sys.exit(2)
 else:globals()[a.command]()
if __name__=='__main__':
 try:main()
 except Exception as e:
  print(type(e).__name__+': '+str(e),file=sys.stderr)
  raise
