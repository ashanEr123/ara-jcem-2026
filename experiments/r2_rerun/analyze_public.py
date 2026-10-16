"""Reproduce supplementary numeric analyses without private text or APIs.

Run from any directory: python path/to/analyze_public.py
Requires numpy. Results are written beside this script in results/summary.json.
"""
import json
from collections import Counter
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
SEED, DRAWS = 19357, 10000

def read(name):
    return json.loads((ROOT / 'data' / name).read_text(encoding='utf-8'))

def interval(values, sources=None):
    values = np.asarray(values, dtype=float)
    assert np.isfinite(values).all() and len(values)
    rng = np.random.default_rng(SEED)
    if sources is None:
        boot = rng.choice(values, (DRAWS, len(values)), replace=True).mean(axis=1)
    else:
        # Preserve the 8 circular / 12 defence composition. Reset for each contrast.
        sources = np.asarray(sources)
        groups = [values[sources == s] for s in sorted(set(sources))]
        boot = sum(rng.choice(v, (DRAWS, len(v)), replace=True).sum(axis=1) for v in groups) / len(values)
    return {'n_questions': len(values), 'mean_difference': float(values.mean()),
            'ci95': np.quantile(boot, [.025, .975]).tolist()}

def metric(r, name):
    if name == 'correctness': return r[name]
    a, b = ('citation_supported', 'citation_total') if name == 'citation_support' else ('unsupported_claims', 'factual_claims')
    return r[a] / r[b] if r[b] else None

def main():
    trials, ratings = read('trials.json'), read('ratings.json')
    failed, contexts, ocr = read('failed_attempts.json'), read('context_comparisons.json'), read('ocr_page_counts.json')
    systems = ['ARA', 'FLOW', 'GYM', 'GPT_GROUNDED', 'MISTRAL_GROUNDED']
    expected = {f'{q}_{s}_{rep}' for q in [f'C{i:02}' for i in range(1,9)] + [f'D{i:02}' for i in range(1,13)] for s in systems for rep in range(5)}
    expected |= {f'C{i:02}_FLOW_CORRECTED_{rep}' for i in range(1,9) for rep in range(5)}
    assert len(trials) == 540 and {r['id'] for r in trials} == expected
    assert all(r['status'] == 'ok' for r in trials)
    key = read('rating_key.json')
    assert len(key) == 108 and len({k['blind_id'] for k in key}) == 108
    index = {r['id']: r for r in trials}
    for e in [1, 2]:
        rr = [r for r in ratings if r['evaluator'] == e]
        assert len(rr) == 108 and {r['blind_id'] for r in rr} == {k['blind_id'] for k in key}
        for r in rr:
            assert index[r['run_id']]['rep'] == 0
            assert r['correctness'] in [0, 1, 2]
            assert 0 <= r['citation_supported'] <= r['citation_total']
            assert 0 <= r['unsupported_claims'] <= r['factual_claims']
    result = {'completed_trials': len(trials), 'archived_failed_attempts': len(failed),
              'recorded_formal_attempts': len(trials) + len(failed),
              'statuses': dict(Counter(r['status'] for r in trials)),
              'human_rated_answers': 108, 'human_rating_rows': len(ratings),
              'completed_by_system': dict(Counter(r['system'] for r in trials)),
              'context_pairs': len(contexts), 'context_mismatches': sum(not r['equal_messages'] for r in contexts)}
    result['ocr'] = {k: sum(r[k] for r in ocr) for k in ['char_edits', 'reference_chars', 'word_edits', 'reference_words']}
    result['ocr']['CER'] = result['ocr']['char_edits']/result['ocr']['reference_chars']
    result['ocr']['WER'] = result['ocr']['word_edits']/result['ocr']['reference_words']
    per = {(r['evaluator'], r['qid'], r['system']): r for r in ratings}
    # Frozen blind-ID order reproduces the manuscript's finite bootstrap draws.
    qs = [r['qid'] for r in sorted(ratings, key=lambda r: r['blind_id']) if r['evaluator']==1 and r['system']=='ARA']
    src = {r['qid']: r['source'] for r in trials}
    result['rater_system_summaries'] = {}
    for e in [1,2]:
        for s in systems + ['FLOW_CORRECTED']:
            rr = [r for r in ratings if r['evaluator']==e and r['system']==s]
            totals = {k: sum(r[k] for r in rr) for k in ['citation_total','citation_supported','factual_claims','unsupported_claims']}
            result['rater_system_summaries'][f'E{e} {s}'] = dict(n_answers=len(rr), correctness_mean=float(np.mean([r['correctness'] for r in rr])), **totals)
    result['quality_ARA_minus'] = {}
    for s in systems[1:]:
        diffs = [np.mean([per[e,q,'ARA']['correctness']-per[e,q,s]['correctness'] for e in [1,2]]) for q in qs]
        result['quality_ARA_minus'][s] = interval(diffs, [src[q] for q in qs])
    med = {(q,s): float(np.median([r['elapsed_s'] for r in trials if r['qid']==q and r['system']==s])) for q in qs for s in systems}
    result['mean_query_median_latency_s'] = {s: float(np.mean([med[q,s] for q in qs])) for s in systems}
    result['timing_ARA_minus'] = {}
    result['timing_by_source'] = {}
    for s in systems[1:]:
        result['timing_ARA_minus'][s] = interval([med[q,'ARA']-med[q,s] for q in qs], [src[q] for q in qs])
        for source in sorted(set(src.values())):
            qq = [q for q in qs if src[q]==source]
            result['timing_by_source'][source+' '+s] = interval([med[q,'ARA']-med[q,s] for q in qq])
    result['rater_paired_comparisons'] = {}
    for e in [1,2]:
        for source in sorted(set(src.values())):
            qq = [q for q in qs if src[q]==source]
            pairs = [('ARA',s) for s in systems[1:]] + ([('FLOW_CORRECTED','FLOW')] if source=='CIRCULARS' else [])
            for a,b in pairs:
                qq = [r['qid'] for r in sorted(ratings, key=lambda r: r['blind_id']) if r['evaluator']==e and r['system']==a and r['source']==source]
                for m in ['correctness','citation_support','unsupported_rate']:
                    vals = [(metric(per[e,q,a],m),metric(per[e,q,b],m)) for q in qq]
                    vals = [x-y for x,y in vals if x is not None and y is not None]
                    if vals: result['rater_paired_comparisons'][f'E{e} {source} {a} minus {b} {m}'] = interval(vals)
    a = {r['blind_id']:r['correctness'] for r in ratings if r['evaluator']==1}
    b = {r['blind_id']:r['correctness'] for r in ratings if r['evaluator']==2}
    matrix = np.zeros((3,3))
    for k in a: matrix[a[k],b[k]] += 1
    expected_matrix = np.outer(matrix.sum(axis=1),matrix.sum(axis=0))/matrix.sum()
    weights = (np.arange(3)[:,None]-np.arange(3)[None,:])**2
    observed = float(np.trace(matrix)/matrix.sum())
    chance = float(np.trace(expected_matrix)/matrix.sum())
    result['correctness_agreement'] = {'agreement_count':int(np.trace(matrix)), 'n':len(a),'proportion':observed,
        'unweighted_kappa':(observed-chance)/(1-chance),'quadratic_weighted_kappa':float(1-(matrix*weights).sum()/(expected_matrix*weights).sum())}
    result['routing_rep0'] = dict(Counter(r.get('route','missing') for r in trials if r['system']=='ARA' and r['rep']==0))
    result['bootstrap'] = {'seed':SEED,'draws':DRAWS,'overall':'Question resampling within source, source order CIRCULARS then DEFENCE','source_specific':'Question resampling within source','confidence':'Exploratory percentile intervals, unadjusted; conditional on selected documents'}
    (ROOT/'results').mkdir(exist_ok=True)
    (ROOT/'results/summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['completed_trials','recorded_formal_attempts','human_rated_answers','context_mismatches','quality_ARA_minus','timing_ARA_minus']},indent=2))

if __name__ == '__main__': main()
