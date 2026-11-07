import os
import sys
import subprocess
import re

# =============================================================
# 1. Bootstrap prebuilt llama-cpp-python
# =============================================================
def bootstrap_llama_cpp():
    print("Bootstrapping llama-cpp-python...")
    from huggingface_hub import HfApi, hf_hub_download

    api = HfApi()
    files = api.list_repo_files("AIencoder/llama-cpp-wheels", repo_type="dataset")
    py_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"

    candidates = []
    for p in files:
        if not p.endswith(".whl") or "linux/x86_64/cpu/" not in p or "cuda" in p.lower():
            continue
        if py_tag not in p and "py3-none" not in p:
            continue
        m = re.search(r"/0\.3\.(\d+)/", p)
        if not m or int(m.group(1)) < 20:
            continue
        candidates.append((int(m.group(1)), p))

    candidates.sort(key=lambda x: x[0], reverse=True)
    chosen = candidates[0][1]
    print(f"Selected wheel: {chosen}")
    whl_path = hf_hub_download("AIencoder/llama-cpp-wheels", chosen, repo_type="dataset")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--force-reinstall", whl_path
    ])
    print("llama-cpp-python ready!")

try:
    from llama_cpp import Llama
    print("llama-cpp-python already available.")
except (ImportError, RuntimeError, OSError):
    bootstrap_llama_cpp()
    from llama_cpp import Llama

import spaces
from typing import List
import gradio as gr

# =============================================================
# 2. Load GGUF Model
# =============================================================
MODEL_PATH = "Qwen3.5-0.8B.Q4_K_M.gguf"

print(f"Loading {MODEL_PATH} via llama-cpp-python ...")
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=4096,
    n_threads=2,
    verbose=False
)
print("Model loaded successfully!")

SYSTEM_PROMPT = (
    "You are Sherpa, an AI driving assistant for the CommitCon ride-hailing "
    "repositioning platform in Bengaluru. Provide concise, direct, helpful "
    "recommendations to drivers about where to reposition for high demand, "
    "earnings, and low traffic delays."
)

def run_inference(prompt: str, history: List[dict] = None) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": prompt})
    response = llm.create_chat_completion(
        messages=messages, temperature=0.7, max_tokens=256
    )
    return response["choices"][0]["message"]["content"]

# =============================================================
# 3. Gradio Interface (duration=15 ensures ZeroGPU quota is preserved)
# =============================================================
@spaces.GPU(duration=15)
def gradio_chat(user_message, history):
    hist_formatted = []
    if history:
        for item in history:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                u, b = item
                hist_formatted.append({"role": "user", "content": str(u)})
                if b:
                    hist_formatted.append({"role": "assistant", "content": str(b)})
            elif isinstance(item, dict):
                hist_formatted.append(item)
    return run_inference(user_message, hist_formatted)

demo = gr.ChatInterface(
    fn=gradio_chat,
    title="🧭 CommitCon Sherpa Driver Copilot",
    description="Fine-tuned Qwen 0.8B Q4_K_M — llama-cpp-python inference",
    api_name="chat"
)

# =============================================================
# 4. Native ZeroGPU Launch
# =============================================================
if __name__ == "__main__":
    demo.launch()
