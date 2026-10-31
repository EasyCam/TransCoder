"""Install P6 evaluation deps from tuna mirror (no sudo, user-writable)."""
import subprocess, sys
pkgs = ["bert-score"]
for p in pkgs:
    rc = subprocess.call([sys.executable, "-m", "pip", "install", "-q", "-i",
                          "https://pypi.tuna.tsinghua.edu.cn/simple", p])
    print(f"pip install {p} -> rc={rc}")
