import time, json, sys
sys.path.insert(0, "/Users/fred/Documents/GitHub/EasyCam/TransCoder")
t_all = time.time()
def p(*a): print(f"[{round(time.time()-t_all,1)}s]", *a, flush=True)
p("start")
import run_experiment as re_
p("import done")
dataset = re_.load_dataset(re_.RESULTS / "corpus" / "dataset.json")
pair = [x for x in dataset["pairs"] if x["pair_id"] == "la-ch1-en"][0]
runner = re_.GroupRunner("G4", dataset, events_path=re_.RESULTS / "events_probe_dry.jsonl")
t0=time.time(); prov = runner.edge_provider(); p("edge_provider build", round(time.time()-t0,2))
t0=time.time(); ts = runner.terminology(); p("terminology()", round(time.time()-t0,2))
t0=time.time(); rprov = runner.edge_reviewer_provider(); p("edge_reviewer build", round(time.time()-t0,2))
t0=time.time(); av = rprov.is_available(); p("reviewer is_available (loads gemma3)", round(time.time()-t0,2), av)
t0=time.time(); row = runner.run_pair(pair, dry=True); p("run_pair dry", round(time.time()-t0,2))
p("total", round(time.time()-t_all,2))
p(json.dumps(row, ensure_ascii=False)[:300])
