import json
from pathlib import Path
m=json.loads((Path(__file__).parent/"update-manifest.json").read_text())
assert m["briefing_item_count"]==5
assert m["authority_invariant"]=="Capability may change. Authority does not."
assert set(m["components"])=={"OmniSign","SIGNAL","PRIMER","Sentinel_v3","AuthorityBench_v3","AnnealMesh","BriefOps"}
required=[
"signed model provenance",
"component admission before runtime",
"cross-domain authority gate",
"explicit sensitive transition consent",
"scoped single-use credentials",
"simulation before live physical effect",
"accessibility modality normalization no raw sensor retention",
"annealmesh fabrication maturity and verified advantage",
"ed25519 sha3 effect receipts"
]
text=json.dumps(m).lower()
for phrase in required:
    assert phrase in text, phrase
assert "model, inspector, evaluator, and component cannot grant itself authority" in text
print("manifest_valid")
