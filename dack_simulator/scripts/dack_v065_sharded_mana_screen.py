#!/usr/bin/env python3
"""DACK v0.65 sharded mana-source instrumentation wrapper around validated v0.64 engine.

Does not modify solver rules.  It creates deterministic, matched target-vs-Plains
opening-seven contexts for every non-Plains land-access card and every nonland
RAMP_PROTECTED card in the current 99.

The six other cards and unknown library are identical between target and control.
Future library orders are also identical.  Outcomes are retained at future/seat-class
level, then aggregated per context.  Independent shards can be pooled exactly later.
"""
from __future__ import annotations
import argparse, csv, hashlib, importlib.util, json, math, os, random, sys, time
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOLVER_PATH=HERE.parent/'src'/'dack_t3_solver_v0_64_repaired.py'
if not SOLVER_PATH.exists():
    # Backward-compatible fallback for older flat checkpoint layouts.
    SOLVER_PATH=HERE/'dack_t3_solver_v0_64_repaired.py'

def load_solver():
    spec=importlib.util.spec_from_file_location('dack_v064_engine',SOLVER_PATH)
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
    return m

m=load_solver()

MDFCS={"Emeria's Call","Razorgrass Ambush"}
ROLE={
    'Sol Ring':'fast_mana','Mana Vault':'fast_mana','Grim Monolith':'fast_mana','Basalt Monolith':'fast_mana',
    'Lotus Petal':'fast_mana','Lion\'s Eye Diamond':'fast_mana','Mox Diamond':'fast_mana','Chrome Mox':'fast_mana',
    'Mox Opal':'fast_mana','Jeweled Amulet':'fast_mana',
    'Arcane Signet':'mana_rock','Fellwar Stone':'mana_rock','The Mind Stone':'mana_rock','Prismatic Lens':'mana_rock',
    'Pentad Prism':'mana_rock','Liquimetal Torque':'mana_rock','Coalition Relic':'mana_rock',
    'Everflowing Chalice':'mana_rock','Tooth of Ramos':'mana_rock',
    'Pearl Medallion':'cost_reducer','Candelabra of Tawnos':'mana_untap','Voltaic Key':'mana_untap','Manifold Key':'mana_untap',
    'Kozilek\'s Command':'conditional_mana','Eldrazi Confluence':'conditional_mana','Gleaming Splendor':'conditional_mana',
    'Expedition Map':'mana_tutor','Moonsilver Key':'mana_tutor','Enlightened Tutor':'mana_tutor',
    'Tezzeret, Cruel Captain':'mana_tutor','Loyal Tutor':'mana_tutor',
    'Brainstone':'repair_selection','Scroll Rack':'repair_selection','Giant\'s Boulder':'repair_selection',
}
MANA_ACCEL_ROLES={'fast_mana','mana_rock','cost_reducer','mana_untap','conditional_mana'}

TRUE_LANDS=[c for c in m.DECK if c in m.LANDS]
UNIQUE_TRUE_LANDS=sorted(set(TRUE_LANDS))
LAND_TARGETS=[c for c in UNIQUE_TRUE_LANDS if c!='Plains']+sorted(c for c in MDFCS if c in m.DECK)
INFRA_TARGETS=sorted(c for c in set(m.DECK) if c in m.RAMP_PROTECTED and c not in m.LANDS and c not in MDFCS)
TARGETS=LAND_TARGETS+INFRA_TARGETS
assert len(TRUE_LANDS)==28
assert len(UNIQUE_TRUE_LANDS)==25
assert len(LAND_TARGETS)==26
assert len(INFRA_TARGETS)==34
assert len(TARGETS)==60

WHITE_SOURCE_NAMES=set(m.WHITE_LANDS)|{'City of Brass','Mana Confluence','Gemstone Mine','Tarnished Citadel','Starting Town','Spire of Industry'}

def role(card):
    if card in MDFCS: return 'mdfc_land'
    if card in m.LANDS: return 'land'
    return ROLE.get(card,'ramp_protected_other')

def is_land_access(card): return card in m.LANDS or card in MDFCS
def card_multiplicity(card): return m.DECK.count(card)
def remove_once(seq, card):
    x=list(seq); x.remove(card); return x
def remove_multiset(seq, cards):
    x=list(seq)
    for c in cards: x.remove(c)
    return x
def stable_int(*parts):
    b='|'.join(map(str,parts)).encode()
    return int.from_bytes(hashlib.blake2b(b,digest_size=8).digest(),'big')

def hand_features(cards):
    cards=list(cards)
    return {
        'land_access_n':sum(is_land_access(c) for c in cards),
        'literal_land_n':sum(c in m.LANDS for c in cards),
        'mdfc_n':sum(c in MDFCS for c in cards),
        'ramp_protected_n':sum(c in m.RAMP_PROTECTED for c in cards),
        'mana_accel_n':sum(role(c) in MANA_ACCEL_ROLES for c in cards),
        'fast_mana_n':sum(role(c)=='fast_mana' for c in cards),
        'white_source_n':sum(c in WHITE_SOURCE_NAMES or c in MDFCS for c in cards),
        'repair_n':sum(role(c)=='repair_selection' for c in cards),
        'tutor_n':sum(role(c)=='mana_tutor' for c in cards),
    }

def evaluate_ordered(hand, ordered_lib, beam):
    hand=tuple(sorted(hand)); ordered_lib=tuple(ordered_lib)
    if 'Gemstone Caverns' in hand:
        w0=m._win_turn_from_unknown_order(hand,ordered_lib,0,beam,max_turn=3)
        w1=m._win_turn_from_unknown_order(hand,ordered_lib,1,beam,max_turn=3)
        return [('starting',1,w0),('nonstarting',3,w1)]
    w=m._win_turn_from_unknown_order(hand,ordered_lib,0,beam,max_turn=3)
    return [('all_seats',4,w)]

def metrics_from_weighted(win_rows):
    counts={1:0,2:0,3:0}; total=0
    for weight,wt in win_rows:
        total += weight
        if wt in counts: counts[wt]+=weight
    t1=counts[1]/total; t2=counts[2]/total; t3=counts[3]/total
    return {'t1':t1,'t2':t2,'t3':t3,'le2':t1+t2,'le3':t1+t2+t3,'utility':t1+t2+0.5*t3}

def build_context(target, shard_id, local_context, seed_base):
    deck_wo_target=remove_once(m.DECK,target)
    eligible=[c for c in deck_wo_target if c not in m.COMBO_CREATURES]
    rng=random.Random(stable_int(seed_base,shard_id,local_context,target,'context'))
    inds=rng.sample(range(len(eligible)),6)
    base6=[eligible[i] for i in inds]
    lib=remove_multiset(deck_wo_target,base6)
    assert len(lib)==92
    target_hand=base6+[target]
    control_hand=base6+['Plains']
    return base6,lib,target_hand,control_hand

def write_card_manifest(path):
    fields=['copy_index','card','deck_multiplicity','role','is_literal_land','is_mdfc_land','is_land_access',
            'is_ramp_protected','is_mana_acceleration','is_test_target','test_control']
    seen=Counter()
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c in m.DECK:
            seen[c]+=1
            r=role(c)
            w.writerow({'copy_index':seen[c],'card':c,'deck_multiplicity':card_multiplicity(c),'role':r,
                        'is_literal_land':int(c in m.LANDS),'is_mdfc_land':int(c in MDFCS),'is_land_access':int(is_land_access(c)),
                        'is_ramp_protected':int(c in m.RAMP_PROTECTED),'is_mana_acceleration':int(r in MANA_ACCEL_ROLES),
                        'is_test_target':int(c in TARGETS),'test_control':'Plains' if c in TARGETS else ''})

def run(args):
    out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    shard=f'{args.shard_id:04d}'
    trials_path=out/f'shard_{shard}_trials.csv'
    ctx_path=out/f'shard_{shard}_contexts.csv'
    manifest_path=out/f'shard_{shard}_manifest.json'
    card_manifest=out/'card_manifest.csv'
    if not card_manifest.exists(): write_card_manifest(card_manifest)
    if (trials_path.exists() or ctx_path.exists()) and not args.overwrite:
        raise SystemExit(f'shard {args.shard_id} outputs exist; use --overwrite')

    solver_sha=hashlib.sha256(SOLVER_PATH.read_bytes()).hexdigest()
    targets=TARGETS[args.target_start:args.target_stop]
    if args.target:
        wanted=set(args.target)
        targets=[x for x in TARGETS if x in wanted]
        missing=wanted-set(targets)
        if missing: raise SystemExit(f'unknown/non-target cards: {sorted(missing)}')

    trial_fields=['shard_id','local_context','context_id','target_card','target_role','target_group','future_index',
                  'seat_class','seat_weight','target_win_turn','control_win_turn','target_wins_by_t2','control_wins_by_t2',
                  'target_wins_by_t3','control_wins_by_t3','future_seed']
    feat_names=list(hand_features([]).keys())
    ctx_fields=['shard_id','local_context','context_id','target_card','target_role','target_group','control_card',
                'base6','target_hand','control_hand','future_samples','beam'] + \
               [f'base6_{x}' for x in feat_names]+[f'target_{x}' for x in feat_names]+[f'control_{x}' for x in feat_names]+ \
               ['target_t1','target_t2','target_t3','target_le2','target_le3','target_utility',
                'control_t1','control_t2','control_t3','control_le2','control_le3','control_utility',
                'delta_t1','delta_t2','delta_t3','delta_le2','delta_le3','delta_utility']

    started=time.time(); nctx=0
    with open(trials_path,'w',newline='',encoding='utf-8') as ft, open(ctx_path,'w',newline='',encoding='utf-8') as fc:
        tw=csv.DictWriter(ft,fieldnames=trial_fields);tw.writeheader()
        cw=csv.DictWriter(fc,fieldnames=ctx_fields);cw.writeheader()
        for target in targets:
            for local in range(args.contexts_per_target):
                context_id=f'{args.shard_id}:{local}:{target}'
                base6,lib,th,ch=build_context(target,args.shard_id,local,args.seed_base)
                target_weighted=[]; control_weighted=[]
                for j in range(args.samples):
                    fs=stable_int(args.seed_base,args.shard_id,local,target,'future',j)
                    rr=random.Random(fs); ordered=list(lib);rr.shuffle(ordered)
                    ta=evaluate_ordered(th,ordered,args.beam)
                    ca=evaluate_ordered(ch,ordered,args.beam)
                    td={s:(w,wt) for s,w,wt in ta}; cd={s:(w,wt) for s,w,wt in ca}
                    classes=['starting','nonstarting'] if ('Gemstone Caverns' in th or 'Gemstone Caverns' in ch) else ['all_seats']
                    for sc in classes:
                        if sc=='all_seats':
                            wt_t=ta[0][2]; wt_c=ca[0][2]; weight=4
                        else:
                            wt_t=td[sc][1] if 'Gemstone Caverns' in th else ta[0][2]
                            wt_c=cd[sc][1] if 'Gemstone Caverns' in ch else ca[0][2]
                            weight=1 if sc=='starting' else 3
                        target_weighted.append((weight,wt_t));control_weighted.append((weight,wt_c))
                        tw.writerow({'shard_id':args.shard_id,'local_context':local,'context_id':context_id,'target_card':target,
                                     'target_role':role(target),'target_group':'land_access' if target in LAND_TARGETS else 'infrastructure',
                                     'future_index':j,'seat_class':sc,'seat_weight':weight,'target_win_turn':wt_t,'control_win_turn':wt_c,
                                     'target_wins_by_t2':int(wt_t in (1,2)),'control_wins_by_t2':int(wt_c in (1,2)),
                                     'target_wins_by_t3':int(wt_t in (1,2,3)),'control_wins_by_t3':int(wt_c in (1,2,3)),
                                     'future_seed':fs})
                tm=metrics_from_weighted(target_weighted); cm=metrics_from_weighted(control_weighted)
                bf=hand_features(base6);tf=hand_features(th);cf=hand_features(ch)
                row={'shard_id':args.shard_id,'local_context':local,'context_id':context_id,'target_card':target,
                     'target_role':role(target),'target_group':'land_access' if target in LAND_TARGETS else 'infrastructure',
                     'control_card':'Plains','base6':' | '.join(base6),'target_hand':' | '.join(th),'control_hand':' | '.join(ch),
                     'future_samples':args.samples,'beam':args.beam}
                row.update({f'base6_{k}':v for k,v in bf.items()});row.update({f'target_{k}':v for k,v in tf.items()});row.update({f'control_{k}':v for k,v in cf.items()})
                for k,v in tm.items():row[f'target_{k}']=v
                for k,v in cm.items():row[f'control_{k}']=v
                for k in ('t1','t2','t3','le2','le3','utility'):row[f'delta_{k}']=tm[k]-cm[k]
                cw.writerow(row);nctx+=1
                if args.progress and nctx%args.progress==0:
                    print(f'contexts={nctx}/{len(targets)*args.contexts_per_target} elapsed={time.time()-started:.1f}s',flush=True)
    manifest={
        'schema_version':'DACK-mana-screen-v1','engine':'v0.64 repaired rules; v0.65 is instrumentation only',
        'solver_file':SOLVER_PATH.name,'solver_sha256':solver_sha,'deck_size':len(m.DECK),
        'literal_land_cards':len(TRUE_LANDS),'unique_literal_land_names':len(UNIQUE_TRUE_LANDS),
        'mdfc_land_access_cards':sum(c in MDFCS for c in m.DECK),'land_access_cards_total':sum(is_land_access(c) for c in m.DECK),
        'land_test_targets_vs_plains':len(LAND_TARGETS),'infrastructure_targets_vs_plains':len(INFRA_TARGETS),'total_targets':len(TARGETS),
        'shard_id':args.shard_id,'contexts_per_target':args.contexts_per_target,'samples_per_context':args.samples,
        'beam':args.beam,'seed_base':args.seed_base,'targets':targets,'elapsed_seconds':time.time()-started,
        'method':'forced target in creature-free opening seven; same six other cards, same unknown library, same future orders; target compared with Plains; weighted 1 starting + 3 nonstarting seats',
        'utility':'P(<=T2)+0.5*P(exact T3)'
    }
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'contexts':nctx,'trials_csv':str(trials_path),'contexts_csv':str(ctx_path),'manifest':str(manifest_path),'elapsed_s':round(time.time()-started,2)},indent=2))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--shard-id',type=int,required=True)
    ap.add_argument('--contexts-per-target',type=int,default=1)
    ap.add_argument('--samples',type=int,default=4)
    ap.add_argument('--beam',type=int,default=40)
    ap.add_argument('--seed-base',type=int,default=640065)
    ap.add_argument('--out-dir',default=str(HERE/'mana_screen_shards'))
    ap.add_argument('--target',action='append',help='limit to exact target card; repeatable')
    ap.add_argument('--target-start',type=int,default=0,help='slice start in canonical 60-target list')
    ap.add_argument('--target-stop',type=int,default=None,help='slice stop in canonical 60-target list')
    ap.add_argument('--overwrite',action='store_true')
    ap.add_argument('--progress',type=int,default=10)
    args=ap.parse_args();run(args)
if __name__=='__main__':main()
