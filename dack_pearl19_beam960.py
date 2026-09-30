#!/usr/bin/env python3
import json
import dack_artifact_crn_v076 as c
c.CURRENT_TARGET="Pearl Medallion"
c.m.b.CONFIG["gameplay_beam"]=960
out={}
for name in ("baseline","Pearl Medallion -> Generic Rock"):
    c.m.d.DECK=c.m.deck_for(name)
    row=c.m.b.simulate_game(19)
    out[name]={"win_turn":row["win_turn"],"keep_n":row["keep_n"],"seat":row["seat"],"keep_utility":row["keep_utility"],"mulligan_audit":row["mulligan_audit"]}
print(json.dumps(out,indent=2))
