# 预注册判定标准（JUDGE.md）

**落盘日期：2026-10-19（实验执行之前；本文件在实验后只作核对，不修改判据）**

来源：`experiments-design.md` §3「指标与判定标准（预先写死）」。三档判定针对
G5（team-hybrid：端侧小模型生成 + 在线大模型评审）作为主处理组；统计方法
bootstrap（1,000 次，配对差）。

## 判据 ①：G5 相对 G1 显著提升

- G5（edge 生成 + 在线评审多智能体）与 G1（edge 直翻基线）在**同一批带参考译文
  的评测对**上的 BLEU 与 BERTScore（F1）配对差，bootstrap 95% CI **不跨 0**
  （提升方向：G5 更高）。
- 带参考评测对的集合在实验开始前由语料构建固定（RESULTS/corpus/dataset.json 内
  `has_reference=true` 的全部对），不事后删改。
- 指标口径：sacrebleu BLEU（en/fr/de 用 13a tokenizer，ja/ko 用 char tokenizer），
  BERTScore 统一 `bert-base-multilingual-cased`（所有语对同模型，不加 rescale）。

## 判据 ②：G5 与 G0 差距 ≤ 预注册阈值

- G5 与 G0（在线大模型直翻，上界参照）的 BLEU 差 ≤ **5 分** 或 BERTScore F1 差
  ≤ **0.05**（即：小模型+在线评审 至少逼近大模型直翻）。满足其一即该语对视为
  "逼近"；组级判定按**均值差**计算并给区间，不逐对择优。

## 判据 ③：在线 token 开销 ≤ G0 的 25%

- G5 完成任务的全程**在线 token**（评审 prompt+reply，按 o200k 统一记账，含每轮
  重试）≤ G0 直翻同方向全在线 token 的 **25%**（平均逐对比较：sum(G5 online tokens)
  / sum(G0 tokens) ≤ 0.25）。

## 三条全中 ⇒ 判定「端侧敏捷实现成立」；部分命中照实写，不圆场。

## 预注册的执行细节（与判据同批锁定）

1. temperature = 0.3（全组一致，含 edge 本地采样温度与在线调用）；seed 固定
   （主矩阵 seed=42；稳定性检验 seed ∈ {7, 42, 3407} 仅对 G5 关键子集）。
2. 语料三子集：C1-la（道德經公版章 1/8/9/15，文言原文）、C1-aq（阿Q正传 序/第一章
   节选，本地公版原典）、C2（MTMinePy 多语文学语料节选，zh↔en/fr/ja/de 方向）。
   参考译文仅用**公版/权威译本**（Legge 1891 英、Stanislas Julien 1842 法、
   井上秀天 1915 書き下し 日、George Kin Leung 1926-27 阿Q英译）；其余语对如实
   标注"无参考"，只报长度比 + 评审得分（红线：不造参考译文）。
3. G3（iterative, 5 轮）因端侧 CPU 吞吐限制，只对预先指定的子集执行：
   C1-la 的 ch1 与 ch8 两章 × 5 语向（10 对）+ C1-aq 的 xu 节选 en 向（1 对）
   + C3 第 1 对 = 共 12 对；其余组跑全部评测对。样本量与本限制写入论文
   limitation。
4. G0 上界：deepseek（RESULTS/probe.json 2026-10-19 实测 chat 可达）。
   G5 评审：deepseek-chat（同上）；备用 cycleuser-halogen（chat ping ok）。
   ollama-cloud：/models 可达但 chat completion 401（不可用于生成/评审）。
5. 端侧口径（依 2026-10-19 实测环境）：本机无 ollama/llama.cpp，无独立 GPU；
   端侧 = **Apple M4 CPU 上 transformers 5.17 / torch 2.14 的本地小模型推理**
   （权重自 ModelScope 下载，≤1B）。若此路径也不可达，则 G1-G4 声明为未实测，
   按 experiments-design §6 降级并如实记录。tok/s 用各模型自带 tokenizer 计数。
6. 模型清单实测（≤1B，逐个）：qwen3:0.6b、lfm2.5-350m、granite4:350m-h、
   gemma3:270m —— 存在性以实测下载+加载成功为准；>1B 剔除。
   **执行补充（2026-10-19，模型实测后、矩阵执行前）**：spot 探测显示仅
   qwen3:0.6b（596M 参数）具备中/日翻译能力；gemma3:270m（17 tok/s）只复读
   原文，lfm2.5-350m（3.2 tok/s）与 granite4:350m-h（0.5 tok/s，mamba 回落）
   译文不成句。故：G1–G5 的 translator = qwen3:0.6b；G4 的本地评审 = gemma3:270m
   （spec 要求"换一个本地小模型当 reviewer"；其 JSON 解析失败率如实记录）。
   端侧 torch 线程 = 6（10 核 M4 CPU，记录于事件流水）。
7. prompt 模板统一性：G1 与 G4/G5 的翻译 step 用同一 TranslatorAgent 模板；
   G2/G3 是"现有机制"对照组，沿用 core.py 既有 prompt（其模板差异属于被测
   机制的一部分，如实记录）；G0 用同一 TranslatorAgent 模板（公平对照 G5）。
8. 内部质检（team 内 ReviewerAgent pass/rewrite）与论文指标（sacrebleu/bert_score
   等）分离：内部 pass 只影响 team 轮数，不计入论文质量指标。

（核对部分在实验完成后追加于本文件下方"核对"一节，判据本身不再改动。）
---

## 核对（2026-10-19，实验完成后追加；判据原文未改动）

工具：`RESULTS/tools/judge_check.py`（bootstrap 1000 次，配对差，seed=42 主矩阵；稳定性仅 G5 refs-only 14 对）。

### 三条预注册判据

| 判据 | 实测 | 结论 |
|---|---|---|
| ① G5 相对 G1 的 BLEU/BERT 提升显著（95% CI 不跨 0） | BLEU meanΔ = −0.107，95% CI [−1.041, 0.624]；BERT F1 meanΔ = +0.004，95% CI [−0.005, 0.015] | 未达 |
| ② G5 与 G0 的差距 ≤ 阈值（BLEU ≤5 或 BERT F1 ≤0.05） | BLEU 19.183 − 2.604 = 16.579；BERT F1 0.771 − 0.676 = 0.095 | 两项均未达 |
| ③ 在线 token ≤ G0 的 25% | G0 = 9,240；G5 = 41,627 + 56,002 = 97,629；比值 10.566 | 未达 |

三条均未达标。按预注册口径如实记录，不修改判据、不做“趋势性”表述。

### 稳定性（G5，refs-only，14 对）

| seed | BLEU 均值 |
|---|---|
| 42 | 2.60 |
| 7 | 3.85 |
| 3407 | 2.62 |

三种子差异本身即大于判据①的效应量（|Δ|≈0.1），14 对样本不足以支持任何“微小提升”的结论。

### 机制性发现（必须进入论文，不得美化）

1. **G4 本地评审（gemma3:270m）结构化输出失效率 94.6%**：37 次评审仅 2 次可解析为合法 JSON；旧实现将解析失败视为通过并在第 1 轮停止（35/37），导致 G4 指标与 G1 几乎相同（BLEU 2.71 vs 2.71）。修复后的实现改为“严格重试（STRICT, T=0）→ 本地兜底 → `review_failed` 显式标记”，并新增 3 个单元测试覆盖该语义。
2. **G5 在线评审 token 被全文上下文放大**：37/37 可解析，33/37 跑满 3 轮（仅 4 条首轮通过）；每轮 prompt 含源文+译文+issues，评审侧 token（97,629）远超翻译侧，直接导致判据③失败。
3. **可复现性**：197 行结果零错误；指标经 `backfill_metrics.py` 全量重算（77 条有参考行 BERT 齐全、零指标错误）；每对仅运行一次，稳定性只覆盖 14 对、3 种子。

### 偏离记录（与预注册口径）

- 端侧 torch 线程由 6 改为 1（`OMP_NUM_THREADS=1`）：libomp 多线程 worker 池在本机确定性段错误，已记录于 handoff.md；速度损失如实计入 limitation。
- G5 seed 3407 首次运行因网络挂起被外壳超时终止，重跑后完成；未改动任何结果文件。
