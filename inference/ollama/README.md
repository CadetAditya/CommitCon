# Ollama Model Weights

This directory houses the GGUF model files and configuration for `project-driver:latest`.

## Model Information
- **Base Model**: `unsloth/Qwen3.5-0.8B`
- **Format**: GGUF (4-bit quantization: `Q4_K_M`)
- **Weights**:
  - `Qwen3.5-0.8B.Q4_K_M.gguf` (~542 MB)
  - `Qwen3.5-0.8B.BF16-mmproj.gguf` (~207 MB)

## Building the Ollama Model
```bash
ollama create project-driver:latest -f Modelfile
```
