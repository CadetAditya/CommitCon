# CommitCon Driver AI Copilot (Inference Service)

This directory contains the standalone GPU inference service and fine-tuned Ollama model configurations for the driver copilot ("Sherpa").

## Directory Structure

```
inference/
├── __init__.py
├── main.py              # FastAPI inference service bridging Ollama and CommitCon backend
├── README.md            # This documentation
└── ollama/
    ├── Modelfile        # Ollama model definition
    ├── export_metadata.json # Unsloth fine-tuning provenance
    ├── README.md        # Model weight instructions
    ├── Qwen3.5-0.8B.Q4_K_M.gguf     (Fine-tuned weights - gitignored)
    └── Qwen3.5-0.8B.BF16-mmproj.gguf (Projector weights - gitignored)
```

## How to Set Up & Run the Model

### Step 1: Install Ollama
Download and install Ollama from [https://ollama.com](https://ollama.com).

### Step 2: Register the Model in Ollama
From the `inference/ollama` directory, run:
```bash
cd inference/ollama
ollama create project-driver:latest -f Modelfile
```

Verify the model is registered:
```bash
ollama list
```

### Step 3: Run the Inference API Service
The inference API acts as an authenticated secure proxy to Ollama:
```bash
# Set your API key (must match AI_INFERENCE_KEY on the CommitCon backend)
export API_KEY="commitcon-secret-2026"
# On Windows PowerShell:
# $env:API_KEY="commitcon-secret-2026"

python -m uvicorn inference.main:app --host 0.0.0.0 --port 8001
```

### Step 4: Connecting with CommitCon Backend
In the CommitCon backend (`src/phase5_api.py`), configure environment variables to point to this inference service:
```bash
export AI_INFERENCE_URL="http://localhost:8001/chat"
export AI_INFERENCE_KEY="commitcon-secret-2026"
```
*(By default, if left unset, CommitCon falls back to the hosted GPU endpoint or the built-in local heuristics rules engine.)*
