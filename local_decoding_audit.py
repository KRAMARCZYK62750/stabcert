#!/usr/bin/env python3
"""Write B=4 local-resource and causal-bound tables; no decoder search is run."""
from pathlib import Path
from hayden_preskill_toy.experiment import Config, random_scrambler
from hayden_preskill_toy.channels import channel_at_time, petz_entanglement_fidelity
from hayden_preskill_toy.local import light_cone_bound, petz_stinespring_resources
import csv
import numpy as np

out = Path("results"); out.mkdir(exist_ok=True)
rng = np.random.default_rng(Config().seed)
rows=[]
for regime, layers in (("none",0),("weak",1),("deep",6)):
    circuit=random_scrambler(rng,layers)
    for t in range(1,6):
        channel=channel_at_time(circuit,t); fidelity,_=petz_entanglement_fidelity(channel)
        rows.append({"regime":regime,"t":t,"petz_abstract_fidelity":fidelity,
                     **petz_stinespring_resources(channel), **light_cone_bound(t)})
with (out/"local_decoding_resources.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(f"{len(rows)} resource rows written; no local decoder search executed")
