<div align="center">

<img src="assets/logo.jpg" alt="MetaClaw" width="600">

<br/>

# Just talk to your agent — it learns and *EVOLVES*.

<p>
  <a href="https://github.com/aiming-lab/MetaClaw"><img src="https://img.shields.io/badge/github-MetaClaw-181717?style=flat&labelColor=555&logo=github&logoColor=white" alt="GitHub"></a>
  <img src="https://img.shields.io/badge/⚡_Fully_Async-yellow?style=flat&labelColor=555" alt="Fully Async" />
  <img src="https://img.shields.io/badge/☁️_No_GPU_Cluster-blue?style=flat&labelColor=555" alt="No GPU Cluster" />
  <img src="https://img.shields.io/badge/🛠️_Skill_Evolution-orange?style=flat&labelColor=555" alt="Skill Evolution" />
</p>

<p align="center">
  <video src="assets/video.mp4" controls width="600"></video>
</p>

</div>

---

## 🔥 News

- **[03/09/2026]** We release **MetaClaw** — Just talk to your agent and let it evolve automatically. **NO** GPU deployment required; just plug into the **API**. 

---

## 🎥 Demo

https://github.com/user-attachments/assets/fce77dfc-dfaa-4765-a7de-556128254655

---

## 📖 Overview



**MetaClaw turns live conversations into continuous training data — automatically.**  
Just talk to your agent as usual, and MetaClaw handles the learning loop behind the scenes.

It wraps your model behind an OpenAI-compatible API, intercepts interactions from OpenClaw, scores each turn, and continuously improves the policy through online fine-tuning. Updated weights are hot-swapped into production with no service interruption.

There is no need to maintain a dedicated GPU cluster. MetaClaw is built around **Kimi-2.5** (~200B MoE) using [Tinker](https://www.thinkingmachines.ai/tinker/) for cloud-based LoRA training, with **Qwen3-4B** available as a lightweight alternative.

## 🤖 Key Features

### **Train from real usage**
MetaClaw learns directly from live user-agent conversations. Instead of collecting static datasets and retraining offline, it continuously improves from actual deployment.

### **Skill injection**
At every turn, MetaClaw retrieves the most relevant skill instructions and injects them into the agent’s system prompt. This enables immediate behavior improvement without waiting for retraining.

### **Skill evolution**
When the agent fails, MetaClaw analyzes the full interaction trajectory and uses an LLM to generate new skills automatically. Over time, the system becomes more capable by learning from its own mistakes.

### **No GPU cluster required**
Training is offloaded to Tinker cloud, so any machine with network access can run the full system. This makes continual learning much easier to deploy and maintain.

### **Asynchronous by design**
Serving, reward modeling, and training are fully decoupled. The agent continues responding in real time while scoring and optimization run in parallel.

### **Two learning modes**
MetaClaw supports both:
- **RL (GRPO)** for learning from implicit feedback signals
- **On-Policy Distillation (OPD)** for leveraging richer natural-language supervision

This gives you a practical path to improve agents from both lightweight signals and high-quality textual feedback.

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install fastapi uvicorn httpx openai transformers
pip install tinker tinker-cookbook   # Tinker SDK
```

### 2. Configure OpenClaw

Run the setup script once to point the OpenClaw gateway at the MetaClaw proxy:

```bash
bash openclaw_model_kimi.sh   # Kimi-2.5 (recommended)
```

### 3. Start training

```bash
export TINKER_API_KEY="..."
cd /path/to/metaclaw
python examples/run_conversation_rl.py
```

That's it. Start chatting with your agent — MetaClaw automatically collects conversation turns, scores them, and trains the model. After every `batch_size` samples, new weights are hot-swapped in with no restart.

---

## ⚙️ Configuration

All settings are in `MetaClawConfig` (`metaclaw/config.py`). The most commonly adjusted fields:

| Field | Default | Description |
|-------|---------|-------------|
| `model_name` | `"moonshotai/Kimi-2.5"` | Base model |
| `lora_rank` | `32` | LoRA rank |
| `batch_size` | `32` | Samples before each training step |
| `max_steps` | `1000` | Total training steps |
| `loss_fn` | `"importance_sampling"` | `"importance_sampling"` / `"ppo"` / `"cispo"` |
| `use_prm` | `True` | Enable PRM reward scoring |
| `prm_url` | `"https://api.openai.com/v1"` | Any OpenAI-compatible judge endpoint |
| `prm_model` | `"gpt-5.2"` | Judge model |
| `use_skills` | `False` | Enable skill injection |
| `enable_skill_evolution` | `False` | Auto-generate skills from failures |
| `proxy_port` | `30000` | Proxy listen port |
| `tinker_sampling_url` | `"http://localhost:8080"` | Tinker sampling endpoint |

For programmatic rollout (no IDE needed), set `openclaw_env_data_dir` to a directory of JSONL task files:

```json
{"task_id": "task_1", "instruction": "Register the webhook at https://example.com/hook"}
```

---

## 💪 Skills

Skills are short Markdown instructions injected into the agent's system prompt at each turn. They're organized in `memory_data/conversation/conversation_skills.json` by category (`coding`, `security`, `agentic`, etc.).

Enable with:

```python
config = MetaClawConfig(use_skills=True)
```

To automatically generate new skills when the agent struggles:

```python
config = MetaClawConfig(
    use_skills=True,
    enable_skill_evolution=True,
    azure_openai_deployment="gpt-5.2",
)
```

```bash
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"
```

---

## 📚 Citation

```bibtex
@misc{xia2026metaclaw,
  author       = {Xia, Peng and Chen, Jianwen and Yang, Xinyu and Han, Siwei and Qiu, Shi and Zheng, Zeyu and Xie, Cihang and Yao, Huaxiu},
  title        = {MetaClaw},
  year         = {2026},
  organization = {GitHub},
  url          = {https://github.com/aiming-lab/MetaClaw},
}
```

---

## 🙏 Acknowledgements

MetaClaw builds on [OpenClaw](https://openclaw.ai) and [Tinker](https://www.thinkingmachines.ai/tinker/). The RL design is inspired by [OpenClaw-RL](https://github.com/Gen-Verse/OpenClaw-RL). The skill bank draws from [awesome-openclaw-skills](https://github.com/VoltAgent/awesome-openclaw-skills).

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).
