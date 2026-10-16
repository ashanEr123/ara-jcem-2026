"""Offline analysis; no APIs. Outputs are estimates, not manuscript conclusions."""
import csv,json,re,unicodedata
from pathlib import Path
import numpy as np
from rapidfuzz.distance import Levenshtein
from r2 import OUT,STUDY,checked,read,write,pages

def normal(text):
 # Prespecified content normalization applied identically to reference/hypothesis.
 # Remove Markdown image placeholders/formatting, retain visible cell/text order.
 text=unicodedata.normalize('NFC',text)
 text=re.sub(r'!\[[^\]]*\]\([^)]*\)',' ',text)
 text=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',text)
 text=re.sub(r'^\s*\|?\s*:?-{3,}.*$', ' ',text,flags=re.M)
 text=re.sub(r'(^|\n)\s*#{1,6}\s*',r'\1',text)
 text=text.replace('|',' ').replace('**','').replace('__','').replace('`','')
 return ' '.join(text.split())
def ci_diff(values):
 v=np.asarray(values,dtype=float);v=v[np.isfinite(v)]
 if len(v)==0:return {'n':0,'mean':None,'ci95':None}
 rng=np.random.default_rng(STUDY['seed']);b=rng.choice(v,(10000,len(v)),replace=True).mean(axis=1)
 return {'n':len(v),'mean':float(v.mean()),'ci95':np.quantile(b,[.025,.975]).tolist() if len(v)>1 else None}
def loadcsv(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 checked()
 ocr=[]
 for p in pages('CIRCULARS'):
  n=p['page'];hyp=normal(p['text']);ref=normal((OUT/'corrected'/f'{n:02}.md').read_text(encoding='utf-8'))
  assert ref
  ocr.append({'page':n,'char_edits':Levenshtein.distance(ref,hyp),'reference_chars':len(ref),'word_edits':Levenshtein.distance(ref.split(),hyp.split()),'reference_words':len(ref.split())})
 report={'ocr_pages':ocr,'ocr_pooled_CER':sum(x['char_edits'] for x in ocr)/sum(x['reference_chars'] for x in ocr),'ocr_pooled_WER':sum(x['word_edits'] for x in ocr)/sum(x['reference_words'] for x in ocr)}
 runs=[read(p) for p in (OUT/'runs').glob('*.json')];lookup={r['id']:r for r in runs}
 report['execution_settings']=STUDY.get('rerun',{})
 report['latency_definition']='End-to-end elapsed seconds including configured request pacing and transport retries; not directly pooled with original pilot timing.'
 report['planned_attempts']=540
 report['recorded_attempts']=len(runs)
 report['attempts']={s:{status:sum(r['system']==s and r['status']==status for r in runs) for status in ['ok','degraded','failed']} for s in sorted({r['system'] for r in runs})}
 # Explicit fairness audit: original FLOW and both grounded baselines must have identical messages.
 mismatches=[];fairpairs=0
 for flow in [r for r in runs if r['system']=='FLOW' and r['status']=='ok']:
  for system in ['GPT_GROUNDED','MISTRAL_GROUNDED']:
   other=lookup.get(f'{flow["qid"]}_{system}_{flow["rep"]}')
   if other and other['status']=='ok':
    fairpairs+=1
    if flow['calls'][0]['messages']!=other['calls'][0]['messages']:mismatches.append([flow['id'],other['id']])
 report['equal_context_audit']={'pairs_checked':fairpairs,'mismatches':mismatches}
 med={}
 for r in runs:
  if r['status']=='ok':med.setdefault((r['source'],r['qid'],r['system']),[]).append(r['elapsed_s'])
 # Require all five successful reps for paired timing; no treating 5 repetitions as 5 independent questions.
 med={k:float(np.median(v)) for k,v in med.items() if len(v)==STUDY['repetitions']}
 timing={}
 for source in ['DEFENCE','CIRCULARS']:
  for system in ['FLOW','GYM','GPT_GROUNDED','MISTRAL_GROUNDED']:
   diffs=[v-med[(s,q,system)] for (s,q,a),v in med.items() if s==source and a=='ARA' and (s,q,system) in med]
   timing[source+' ARA minus '+system]=ci_diff(diffs)
 report['paired_query_median_latency_s']=timing
 report['limitations']=['Purposively selected questions and pages; descriptive held-out-document pilot, not population generalization.','OCR normalization measures textual content including all transcribed languages, not layout accuracy.','Bootstrap intervals resample questions within a source, conditional on these documents; they do not capture between-document uncertainty.','Complete-case timing excludes failures; report failure counts alongside latency.','Model aliases may move; inspect actual response models and run dates.','Human-corrected OCR condition measures combined downstream extraction and chunking effects, not recognition in isolation.']
 keypath=OUT/'rating_key.csv'
 if keypath.exists():
  key={x['blind_id']:x['run_id'] for x in loadcsv(keypath)};allratings=[]
  for e in [1,2]:
   rows=loadcsv(OUT/f'evaluator_{e}'/'ratings.csv')
   assert len(rows)==len(key) and {r['blind_id'] for r in rows}==set(key),'Incomplete/duplicate rating IDs'
   parsed=[]
   for row in rows:
    if any(row[f]=='' for f in ['correctness','citation_total','citation_supported','factual_claims','unsupported_claims']):
     raise ValueError(f'Evaluator {e}: incomplete {row["blind_id"]}; zero is a number, not a blank')
    vals={f:int(row[f]) for f in ['correctness','citation_total','citation_supported','factual_claims','unsupported_claims']}
    assert vals['correctness'] in [0,1,2]
    assert 0<=vals['citation_supported']<=vals['citation_total']
    assert 0<=vals['unsupported_claims']<=vals['factual_claims']
    run=lookup[key[row['blind_id']]]
    parsed.append({**vals,'blind_id':row['blind_id'],'qid':run['qid'],'source':run['source'],'system':run['system'],'evaluator':e,'citation_support':vals['citation_supported']/vals['citation_total'] if vals['citation_total'] else float('nan'),'unsupported_rate':vals['unsupported_claims']/vals['factual_claims'] if vals['factual_claims'] else float('nan')})
   allratings+=parsed
  comparisons={}
  for e in [1,2]:
   rr={(r['source'],r['qid'],r['system']):r for r in allratings if r['evaluator']==e}
   for source in ['DEFENCE','CIRCULARS']:
    pairs=[('ARA',s) for s in ['FLOW','GYM','GPT_GROUNDED','MISTRAL_GROUNDED']]
    if source=='CIRCULARS':pairs.append(('FLOW_CORRECTED','FLOW'))
    for a,b in pairs:
     for metric in ['correctness','citation_support','unsupported_rate']:
      vals=[x[metric]-rr[(s,q,b)][metric] for (s,q,sys),x in rr.items() if s==source and sys==a and (s,q,b) in rr]
      comparisons[f'E{e} {source} {a} minus {b} {metric}']=ci_diff(vals)
  report['independent_rater_paired_differences']=comparisons
  summaries={}
  for e in [1,2]:
   for source in ['DEFENCE','CIRCULARS']:
    for system in sorted({r['system'] for r in allratings}):
     rr=[r for r in allratings if r['evaluator']==e and r['source']==source and r['system']==system]
     if not rr:continue
     citations=sum(r['citation_total'] for r in rr);claims=sum(r['factual_claims'] for r in rr)
     summaries[f'E{e} {source} {system}']={'n':len(rr),'correctness_mean':float(np.mean([r['correctness'] for r in rr])),'fully_correct':sum(r['correctness']==2 for r in rr),'citation_total':citations,'citation_supported':sum(r['citation_supported'] for r in rr),'citation_free_answers':sum(r['citation_total']==0 for r in rr),'factual_claims':claims,'unsupported_claims':sum(r['unsupported_claims'] for r in rr)}
  report['independent_rater_system_summaries']=summaries
  from sklearn.metrics import cohen_kappa_score
  a={r['blind_id']:r for r in allratings if r['evaluator']==1};b={r['blind_id']:r for r in allratings if r['evaluator']==2}
  report['correctness_agreement']={'exact':float(np.mean([a[k]['correctness']==b[k]['correctness'] for k in a])),'quadratic_weighted_kappa':float(cohen_kappa_score([a[k]['correctness'] for k in a],[b[k]['correctness'] for k in a],weights='quadratic'))}
  write(OUT/'analysis'/'ratings_numeric.json',allratings)
 write(OUT/'analysis'/'summary.json',report)
 print('Saved work_rerun/analysis/summary.json. Check missingness and equal-context audit before interpreting differences.')
if __name__=='__main__':main()
