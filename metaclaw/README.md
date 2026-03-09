# MetaClaw

对话模式在线 RL 训练框架。用 **Tinker**（云端 LoRA）替换了原 OpenClaw-RL 的 SLIME/Megatron 依赖，并集成了 **Skills 注入**与**自动 Skill 演化**。

---

## 目录

1. [整体架构](#1-整体架构)
2. [完整数据流](#2-完整数据流)
3. [训练流程：如何启动](#3-训练流程如何启动)
4. [配置说明](#4-配置说明)
5. [Skills 系统](#5-skills-系统)
6. [Skill 演化（自动更新）](#6-skill-演化自动更新)
7. [文件结构](#7-文件结构)
8. [与原 OpenClaw-RL 对比](#8-与原-openclaw-rl-对比)

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MetaClaw                               │
│                                                                     │
│  ┌──────────────┐   HTTP /v1/chat/completions   ┌────────────────┐  │
│  │  OpenClaw    │ ─────────────────────────────► │  API Server    │  │
│  │  IDE / Client│ ◄───────── response ────────── │  :30000        │  │
│  └──────────────┘                                │  (FastAPI)     │  │
│                                                  └───────┬────────┘  │
│                                                          │            │
│                              ┌───────────────────────────┤           │
│                              │        每次 main turn      │           │
│                              ▼                           ▼           │
│                    ┌─────────────────┐      ┌──────────────────────┐ │
│                    │  SkillManager   │      │   Tinker Sampling    │ │
│                    │  (检索 skills,  │      │   Client             │ │
│                    │   注入 system   │      │   (生成 response +   │ │
│                    │   prompt)       │      │    logprobs)         │ │
│                    └─────────────────┘      └──────────┬───────────┘ │
│                                                        │             │
│                                                        ▼             │
│                                             ┌──────────────────────┐ │
│                                             │  PRMScorer           │ │
│                                             │  (下一轮 user 回复   │ │
│                                             │   作为 next_state,   │ │
│                                             │   m 次投票 → reward) │ │
│                                             └──────────┬───────────┘ │
│                                                        │             │
│                                                        ▼             │
│                                             ┌──────────────────────┐ │
│                                             │  asyncio.Queue       │ │
│                                             │  ConversationSample  │ │
│                                             └──────────┬───────────┘ │
│                                                        │             │
│  ┌─────────────────────────────────────────────────────▼───────────┐ │
│  │  Trainer (凑齐 batch_size 个样本后触发)                          │ │
│  │                                                                  │ │
│  │  1. GRPO reward 归一化 → advantages                             │ │
│  │  2. ConversationSample → tinker.Datum                           │ │
│  │  3. forward_backward_async (loss_fn: IS / PPO / CISPO)          │ │
│  │  4. optim_step_async                                             │ │
│  │  5. save_weights → 更新 sampling client                         │ │
│  │  6. [可选] Skill 演化                                           │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 完整数据流

### 2.1 请求进入代理

```
Client → POST /v1/chat/completions
  Header: X-Session-Id: <id>
          X-Turn-Type: main | side
          X-Session-Done: 0 | 1
```

| `turn_type` | 含义 |
|-------------|------|
| `main`      | 主 agent 的回复，**收集训练数据** |
| `side`      | 工具调用、子 agent 等，**不收集** |

### 2.2 Skills 注入（仅 main turn）

1. 取最后一条 `user` 消息作为 task description
2. `SkillManager.retrieve(task_desc, top_k=6)` → 关键词匹配或向量检索
3. `format_for_conversation(skills)` → `## Active Skills\n### skill-name\n...`
4. 注入到 system message 末尾（若无 system message 则新建）

### 2.3 转发 Tinker + 获取 logprobs

- 请求转发给 Tinker sampling client（或直接 HTTP 到 `tinker_sampling_url`）
- 强制 `logprobs=True`，获取每个 response token 的 log probability

### 2.4 PRM 评分（异步，等下一轮）

- 当前轮 response 先缓存
- 下一轮 `main` 请求到来时，以该轮的 user 消息作为 `next_state`
- `PRMScorer` 并发调用 PRM 模型 `m` 次，解析 `\boxed{1}` / `\boxed{-1}` / `\boxed{0}`
- 多数投票 → 最终 `reward ∈ {-1.0, 0.0, 1.0}`

**At-least-one 保证**：若 session 内所有样本 reward=0，强制保留第一个进入 loss。

### 2.5 ConversationSample 入队

```python
ConversationSample(
    session_id, turn_num,
    prompt_tokens,     # tokenize(system + history + current_user)
    response_tokens,   # tokenize(assistant_reply)
    response_logprobs, # 来自 Tinker
    loss_mask,         # 全 1（有信号）或全 0（被排除）
    reward,            # PRM 结果
    prompt_text,       # 原文，供 skill 演化分析
    response_text,
)
```

### 2.6 训练步（凑齐 batch_size 后触发）

```
rewards    = [s.reward for s in batch]
advantages = [r - mean(rewards) for r in rewards]   # GRPO 归一化

对每个 (sample, advantage) → tinker.Datum:
  target_tokens = all_tokens[1:]                           # 左移一位
  logprobs      = [0]*prompt_len + response_logprobs
  advantages    = [0]*prompt_len + [adv*mask for mask in loss_mask]
  mask          = [0]*prompt_len + [float(m) for m in loss_mask]

training_client.forward_backward_async(datums, loss_fn="importance_sampling")
training_client.optim_step_async(AdamParams(lr=1e-4))
new_client = training_client.save_weights_and_get_sampling_client_async()
api_server.update_sampling_client(new_client)   # 热更新，无需重启
```

---

## 3. 训练流程：如何启动

### 前置条件

```bash
# 1. 安装依赖
pip install fastapi uvicorn httpx openai transformers

# 2. Tinker SDK（Thinking Machines Lab 内部）
pip install tinker tinker-cookbook

# 3. 启动 PRM 推理服务（OpenAI-compatible /v1/chat/completions）
#    任何支持 \boxed{} 输出的 judge 模型均可，例如：
vllm serve <prm_model_path> --port 8081

# 4. Skill 演化所需（可选）
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"
```

### 启动训练

```bash
cd /path/to/SkillRL
python examples/metaclaw/run_conversation_rl.py
```

代理启动后，在 OpenClaw IDE（或任意 OpenAI 兼容客户端）中配置：

```
Base URL: http://localhost:30000/v1
API Key:  (留空，或与 config.api_key 一致)
```

每次对话中，`main` turn 的请求会自动被收集、评分、入队。凑齐 `batch_size` 个样本后触发一次训练步，新权重立即热更新到 sampling client，下一条请求就用上新模型。

### 最小配置（无 PRM，用于本地调试）

```python
from metaclaw.config import MetaClawConfig
from metaclaw.trainer import MetaClawTrainer
import asyncio

config = MetaClawConfig(
    model_name="Qwen/Qwen3-4B",
    batch_size=8,
    max_steps=100,
    use_prm=False,           # 关闭 PRM，reward 全为 0
    use_skills=True,
    enable_skill_evolution=False,
)
asyncio.run(MetaClawTrainer(config).run())
```

---

## 4. 配置说明

`MetaClawConfig` 完整字段：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `model_name` | `"Qwen/Qwen3-4B"` | 基础模型 |
| `lora_rank` | `32` | LoRA rank |
| `renderer_name` | `"qwen3"` | Tinker chat template renderer |
| `learning_rate` | `1e-4` | Adam 学习率 |
| `batch_size` | `32` | 触发一次训练步所需样本数 |
| `max_steps` | `1000` | 最大训练步数 |
| `loss_fn` | `"importance_sampling"` | `"ppo"` / `"importance_sampling"` / `"cispo"` |
| `use_prm` | `True` | 是否启用 PRM 评分 |
| `prm_url` | `"http://localhost:8081"` | PRM 服务地址 |
| `prm_m` | `3` | PRM 并发投票次数（多数投票） |
| `use_skills` | `False` | 是否注入 skills |
| `skills_dir` | `"memory_data/skills"` | 包含各 skill `.md` 文件的目录 |
| `retrieval_mode` | `"template"` | `"template"`（关键词）/ `"embedding"`（向量） |
| `skill_top_k` | `6` | 每次注入的 general skills 上限 |
| `enable_skill_evolution` | `False` | 是否开启自动 skill 演化 |
| `skill_update_threshold` | `0.4` | success rate 低于此值时触发演化 |
| `max_new_skills` | `3` | 每次演化最多生成几条新 skill |
| `skill_evolution_history_path` | `"memory_data/conversation/evolution_history.jsonl"` | 演化历史（追加写，跨重启持久化） |
| `proxy_port` | `30000` | 代理服务器端口 |
| `azure_openai_deployment` | `"o3"` | Skill 演化所用 LLM 部署名 |

---

## 5. Skills 系统

### Skill 格式（Claude skill format）

```json
{
  "name": "debug-systematically",
  "description": "Use when diagnosing a bug, unexpected behavior, or test failure. Follow a structured debugging process instead of randomly changing code.",
  "content": "## Debug Systematically\n\n**Process:**\n1. Reproduce...\n2. Isolate...\n...\n\n**Anti-patterns:**\n- Changing multiple things at once..."
}
```

- `name`：小写连字符 slug，全局唯一，用于去重
- `description`：一句话触发条件，注入后以斜体显示，也是 embedding 检索的主要文本
- `content`：完整 Markdown 指令体（6–15 行），包含步骤、代码示例、反模式

### Skill Bank 结构

文件：`memory_data/conversation/conversation_skills.json`

```
general_skills         (5 条)  — 所有任务通用
task_specific_skills
  ├─ coding            (4 条)
  ├─ research          (3 条)
  ├─ data_analysis     (3 条)
  ├─ security          (3 条)
  ├─ communication     (3 条)
  ├─ automation        (3 条)
  └─ agentic           (3 条)
common_mistakes        (4 条)  — 常见错误模式警告
```

### 当前 Skill 列表

| 类别 | Name | 触发场景 |
|------|------|----------|
| general | `clarify-ambiguous-requests` | 需求不清晰、多义 |
| general | `structured-step-by-step-reasoning` | 多步推理、非平凡逻辑 |
| general | `verify-before-irreversible-action` | 删文件、推代码、发消息等不可逆操作 |
| general | `graceful-error-recovery` | 工具调用失败、命令报错 |
| general | `audience-aware-communication` | 写文档、回复、解释给他人看 |
| coding | `git-workflow` | commit、branch、PR、merge conflict |
| coding | `debug-systematically` | bug、test failure、unexpected behavior |
| coding | `secure-code-review` | 用户输入、auth、文件 I/O、SQL |
| coding | `test-before-ship` | 新功能或 bug fix 完成前 |
| research | `source-evaluation` | 引用资料、回答事实性问题 |
| research | `structured-research-workflow` | 文献调研、竞品分析、技术尽调 |
| research | `uncertainty-acknowledgment` | 不确定事实、知识截止日期后的事件 |
| data_analysis | `data-validation-first` | 数据分析、ETL 之前 |
| data_analysis | `sql-best-practices` | 写 SQL query |
| data_analysis | `visualization-selection` | 做图表、dashboard |
| security | `input-validation-and-sanitization` | API 端点、表单、CLI 接受外部输入 |
| security | `secrets-management` | API key、密码、token 处理 |
| security | `auth-and-authorization-patterns` | 登录、JWT、OAuth2、权限控制 |
| communication | `professional-email-drafting` | 写邮件、Slack 消息、公告 |
| communication | `technical-writing-clarity` | 写 README、文档、runbook |
| communication | `async-communication-etiquette` | 异步频道发消息（Slack/GitHub issues） |
| automation | `idempotent-script-design` | cron job、pipeline、批量脚本 |
| automation | `robust-error-handling-in-scripts` | shell 脚本、Python 批量任务 |
| automation | `structured-logging-and-observability` | 生产服务、需要监控的系统 |
| agentic | `tool-selection-strategy` | 决定调用哪个 tool |
| agentic | `plan-before-multi-step-execution` | 3 步以上的复杂任务 |
| agentic | `context-window-management` | 长对话、多轮 agentic session |
| mistake | `avoid-acting-on-assumptions` | 对歧义需求直接动手 |
| mistake | `avoid-hallucinating-specifics` | 不确定的 API/版本/路径 |
| mistake | `avoid-scope-creep` | 被要求做 A 顺手改了 B、C、D |
| mistake | `do-not-retry-without-diagnosis` | 失败后无脑重试 |

### 检索逻辑

**template 模式**（默认，零延迟）：

对 user 消息做关键词扫描，匹配对应 `task_specific_skills` 分类：

```
"python" / "debug" / "git" / "api"  → coding
"data" / "pandas" / "sql query"     → data_analysis
"security" / "auth" / "token"       → security
"agent" / "tool use" / "mcp"        → agentic
...（未匹配则取第一个可用分类）
```

每次注入 = `general_skills[:top_k]` + 匹配分类的全部 task skills + `common_mistakes[:5]`

**embedding 模式**（可选）：

```python
config = MetaClawConfig(
    retrieval_mode="embedding",
    embedding_model_path="Qwen/Qwen3-Embedding-0.6B",
)
```

对所有 skill 的 `name + description + content[:200]` 向量化并缓存，query 时按余弦相似度取 top-k，适合 skill bank 较大、任务类型多样的场景。

### 注入效果示例

system prompt 末尾追加：

```
## Active Skills

### debug-systematically
_Use when diagnosing a bug, unexpected behavior, or test failure._

## Debug Systematically

**Process:**
1. Reproduce the bug with the smallest possible input.
2. Isolate — narrow down which component/function causes it.
3. Hypothesize — form a specific, falsifiable hypothesis.
...

**Anti-patterns:**
- Changing multiple things at once and not knowing what fixed it.
```

---

## 6. Skill 演化（自动更新）

### 触发条件

每次训练步后自动检查：

```
success_rate = count(reward > 0) / batch_size
if success_rate < skill_update_threshold:   # 默认 0.4
    触发演化
```

### 演化流程

```
失败样本（reward <= 0，最多取 6 条）
    │  prompt_text（最后 600 字符）+ response_text（前 500 字符）
    ▼
Azure OpenAI o3
    │  分析失败模式
    │  生成 1–3 个新 skill（Claude skill 格式 + category 字段）
    ▼
解析 + 验证
    │  缺少 name/description/content → 跳过
    │  非法 slug → 替换为 dyn-NNN（从当前最大 dyn-NNN+1 开始）
    │  批内重名 → 替换为下一个 dyn-NNN
    ▼
按 category 写入 SkillManager
    │  category="common_mistakes" → 追加到顶层 common_mistakes 列表
    │  其他 category → task_specific_skills[category].append(skill)
    │  已存在同名 skill → 跳过（按 name 去重）
    ▼
conversation_skills.json  ← 持久化写回
evolution_history.jsonl   ← 追加一条记录（跨重启保留）
```

### 演化生成的 Skill 示例

```json
{
  "name": "handle-missing-context",
  "description": "Use when the user references a file, variable, or previous step that has not been shared. Ask for the missing context before proceeding.",
  "content": "## Handle Missing Context\n\n1. Identify what information is referenced but not provided.\n2. Ask the user to share it explicitly.\n3. Do not guess or hallucinate the missing details.\n\n**Anti-pattern:** Proceeding with made-up content when required context is absent.",
  "category": "coding"
}
```

### 开启演化

```python
config = MetaClawConfig(
    use_skills=True,
    enable_skill_evolution=True,
    skill_update_threshold=0.4,    # 低于此 success rate 触发
    max_new_skills=3,
    azure_openai_deployment="o3",
    skill_evolution_history_path="memory_data/conversation/evolution_history.jsonl",
)
```

```bash
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"
```

### 查看演化历史

```bash
cat memory_data/conversation/evolution_history.jsonl
# {"num_failures_analyzed": 24, "num_skills_generated": 2, "skill_names": ["handle-missing-context", "clarify-output-format"]}
# {"num_failures_analyzed": 18, "num_skills_generated": 1, "skill_names": ["dyn-001"]}
```

训练结束后，trainer 也会打印汇总：

```
[Trainer] skill evolution summary: {'total_updates': 5, 'total_skills_generated': 9, 'all_skill_names': [...]}
```

### 手动添加 Skill

直接编辑 `conversation_skills.json`，下次 `retrieve()` 调用时即生效（SkillManager 持有文件加载后的内存对象）。

若需在不重启的情况下重载文件：

```python
from metaclaw.skill_manager import SkillManager
trainer.skill_manager = SkillManager(config.skills_dir)
trainer.api_server.skill_manager = trainer.skill_manager
```

---

## 7. 文件结构

```
metaclaw/
├── __init__.py          # 公开接口导出
├── config.py            # MetaClawConfig
├── api_server.py        # FastAPI 代理（:30000）
│                          · Skills 注入
│                          · Tinker 转发 + logprobs
│                          · PRM 异步评分 + at-least-one 保证
│                          · ConversationSample → asyncio.Queue
├── trainer.py           # 主训练循环
├── data_formatter.py    # ConversationSample + sample_to_datum + compute_advantages
├── prm_scorer.py        # PRMScorer：并发 m 次 → 多数投票 → reward
├── skill_manager.py     # SkillManager：加载/检索/格式化/更新 skill bank
├── skill_evolver.py     # SkillEvolver：LLM 分析失败样本 → 生成新 skill
└── README.md

memory_data/conversation/
├── conversation_skills.json     # Skill bank（31 条，可被演化实时更新）
└── evolution_history.jsonl      # 演化日志（追加写）

examples/metaclaw/
├── run_conversation_rl.py       # 端到端 Binary RL 示例
└── run_conversation_opd.py      # OPD / CISPO 示例
```

---

## 8. 与原 OpenClaw-RL 对比

| 组件 | OpenClaw-RL（原） | MetaClaw |
|------|-----------------|----------------|
| 训练框架 | SLIME + Megatron | Tinker 云端 LoRA |
| 推理引擎 | SGLang（本地 2 GPU） | Tinker sampling client |
| 数据类型 | `slime.utils.types.Sample` | `ConversationSample` → `tinker.Datum` |
| 异步工具 | `slime.utils.async_utils` | 标准 `asyncio` |
| 数据缓冲 | SLIME data buffer | `asyncio.Queue` |
| Skills | 无 | SkillManager（template/embedding 检索） |
| Skill 演化 | 无 | SkillEvolver（LLM 分析失败轨迹，Claude skill format） |
| 硬件要求 | 8 × H100（固定） | 客户端 CPU + Tinker 云端（弹性） |
| RL 算法 | GRPO | IS / PPO / CISPO（Tinker 提供） |
| 最小启动 | 8 GPU cluster | 1 台有网络的机器 |
