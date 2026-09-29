#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

BOOL_TAGS=(
 'land','mdfc_land','ramp','fast_mana','tutor','repair','selection','combo_piece','combo_creature',
 'aura','protection','removal','interaction','stax','utility','safe_chrome_imprint')
RELEVANCE=('direct','interaction_noncore','combo_noncore','liability','noncore')
HAND_FIELDS=('base6','target_hand','control_hand')

def sha256_file(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def parse_cards(s):
    return [x.strip() for x in (s or '').split('|') if x.strip()]

def load_annotations(p:Path):
    if p.suffix.lower()=='.json':
        rows=json.loads(p.read_text(encoding='utf-8'))
        rows=[{k:str(v) if not isinstance(v,str) else v for k,v in r.items()} for r in rows]
    else:
        rows=list(csv.DictReader(p.open(newline='',encoding='utf-8')))
    if not rows:raise SystemExit('empty annotation table')
    versions={r['annotation_version'] for r in rows}
    if len(versions)!=1:raise SystemExit(f'multiple annotation versions: {versions}')
    by={r['card_name']:r for r in rows}
    if len(by)!=len(rows):raise SystemExit('duplicate card_name in annotations')
    return versions.pop(),by

def enrich(cards,ann):
    missing=sorted(set(cards)-set(ann))
    if missing:raise SystemExit(f'unannotated cards: {missing}')
    out={}
    for tag in BOOL_TAGS:
        fld='is_'+tag
        hits=[c for c in cards if int(ann[c][fld])]
        out[f'{tag}_n']=len(hits);out[f'{tag}_cards']=' | '.join(hits)
    for rel in RELEVANCE:
        hits=[c for c in cards if ann[c]['goldfish_relevance']==rel]
        out[f'goldfish_{rel}_n']=len(hits);out[f'goldfish_{rel}_cards']=' | '.join(hits)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--annotations',required=True)
    ap.add_argument('--contexts',required=True)
    ap.add_argument('--out',required=True)
    args=ap.parse_args()
    apath=Path(args.annotations);cpath=Path(args.contexts);out=Path(args.out)
    ver,ann=load_annotations(apath)
    rows=list(csv.DictReader(cpath.open(newline='',encoding='utf-8')))
    if not rows:raise SystemExit('no context rows')
    base_fields=list(rows[0].keys())
    extra=['annotation_version','annotation_sha256','source_pooled_contexts_sha256']
    for hf in HAND_FIELDS:
        for tag in BOOL_TAGS:
            extra += [f'{hf}_{tag}_n',f'{hf}_{tag}_cards']
        for rel in RELEVANCE:
            extra += [f'{hf}_goldfish_{rel}_n',f'{hf}_goldfish_{rel}_cards']
    ann_sha=sha256_file(apath);src_sha=sha256_file(cpath)
    enriched=[]
    for row in rows:
        e=dict(row);e.update({'annotation_version':ver,'annotation_sha256':ann_sha,'source_pooled_contexts_sha256':src_sha})
        for hf in HAND_FIELDS:
            cards=parse_cards(row[hf]); vals=enrich(cards,ann)
            for k,v in vals.items(): e[f'{hf}_{k}']=v
        enriched.append(e)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=base_fields+extra);w.writeheader();w.writerows(enriched)
    print({'rows':len(enriched),'annotation_version':ver,'annotation_sha256':ann_sha,
           'source_sha256':src_sha,'output_sha256':sha256_file(out)})

if __name__=='__main__':main()