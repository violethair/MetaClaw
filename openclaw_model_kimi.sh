export VLLM_API_KEY=tinker

openclaw config set models.providers.vllm --json '{
    "api": "openai-completions",
    "baseUrl": "http://127.0.0.1:30000/v1",
    "apiKey": "tinker",
    "models": [
      {
        "id": "moonshotai/Kimi-K2.5",
        "name": "Kimi-K2.5",
        "reasoning": false,
        "input": ["text"],
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        "contextWindow": 32768,
        "maxTokens": 8192
      }
    ]
  }'

openclaw config set agents.defaults.model.primary "vllm/Kimi-K2.5"

openclaw config set agents.defaults.sandbox.mode off

openclaw config get agents.defaults.model
openclaw config get models.providers.vllm

openclaw gateway restart
