# Serving Open Models Locally with vLLM

vLLM is a high-throughput inference engine exposing an OpenAI-compatible HTTP API. Because the API shape matches commercial providers, application code can switch between cloud and local models by changing only the base URL and model name.

## CPU serving

Most laptops have no discrete GPU, but small instruction-tuned models (1B-3B parameters) are practical on modern CPUs. The key settings are the KV-cache size (`VLLM_CPU_KVCACHE_SPACE`, roughly GB of cache) and a bounded context window such as `--max-model-len 4096` to control memory.

## Baking weights into the image

Downloading model weights at container startup couples cold-start latency to network speed. Production images pre-download weights during `docker build` (via `huggingface-cli download`) so the running container starts offline-ready and reproducible.

## Fallback patterns

A resilient deployment treats the local server as one provider among several. If the primary cloud API fails or rate-limits, requests fall through to the locally served model, keeping the product usable during outages. Circuit breakers stop the system from hammering a dead endpoint on every request.
