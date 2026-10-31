import sys, time
sys.path.insert(0, "/Users/fred/Documents/GitHub/EasyCam/TransCoder")
MODE = sys.argv[1]
t0 = time.time()
if MODE == "b":
    import transcoder            # heavy chain: api -> services -> torch?
    print("transcoder import", round(time.time()-t0,1), flush=True)
else:
    print("mode a: no heavy import", flush=True)
GEMMA = "/Users/fred/.cache/modelscope/models/google--gemma-3-270m-it/snapshots/master"
from transformers import AutoModelForCausalLM, AutoTokenizer
t1 = time.time()
tok = AutoTokenizer.from_pretrained(GEMMA)
print("tokenizer", round(time.time()-t1,1), flush=True)
t1 = time.time()
m = AutoModelForCausalLM.from_pretrained(GEMMA, dtype="float32", device_map="cpu")
print("model load", round(time.time()-t1,1), flush=True)
