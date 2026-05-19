# Skill Token 优化修改清单

基于实际 token 消耗统计制定。目标：单 pass 完整分析从 100k-200k 降到 35k-60k 区间。

核心原则：**看摘要字段便宜，看整份脚本输出 JSON 最贵。所有改动围绕"减少原样大 JSON 进入上下文"展开。**

---

## 一、SKILL.md 瘦身（优先级：高）

当前 ~290 行，目标 80 行以内。

### 1.1 删除内联的 Acceptance Standard 和 Minimum Evidence

**现状**：每个 task（analyze-pass、trace-resource-flow 等）都在 SKILL.md 里内联了 10-20 行的 acceptance standard 和 minimum evidence。这些内容和 `references/report-shapes.md`、`references/pass-checklists.md` 高度重叠。

**改法**：
- 从 SKILL.md 中删除所有 `Minimum evidence:` 和 `Acceptance standard:` 块
- 在每个 task 路由下只保留一行指针：`写报告前读 references/report-shapes.md`
- 如果某个 task 有特殊的 acceptance 要求（比如 analyze-pass 的 cluster 规则），把它移入对应的 reference

**预估节省**：SKILL.md 自身减少 ~120 行（约 2k-3k tokens/次加载）

### 1.2 简化 Default Call Chain 为条件分支

**现状**：analyze-pass 的 call chain 列了 10 个步骤，写成线性清单，暗示 agent 每步都要做。

**改法**：改写成决策树，明确标注哪些步骤是可选的：

```
1. get_pass_packet（必选，唯一入口）
   ├─ pass 只有 clear/copy/resolve → 直接出结论，结束
   ├─ rep_draw 里的 pipe+shader 已足够定性 → 直接出结论
   ├─ pass 是 mixed 类型 → 补 1-2 个其他 cluster 的 get_draw_packet
   ├─ 需要追踪 RT 下游 → 对最重要的 1-2 个 RT 调 inspect_texture_usage
   └─ 需要 visual validation → 导出 overlay（仅在 screen contribution 存疑时）
```

**预估节省**：对简单 pass 减少 2-4 次工具调用（省 10k-30k tokens）

### 1.3 删除 Invocation Examples 和 Minimal Prompt 段

**现状**：SKILL.md 末尾有调用示例和 minimal prompt 模板，共 ~40 行。

**改法**：移到 `references/` 或直接删除。这些是给人看的，不需要每次加载进 agent 上下文。

---

## 二、工具调用去重（优先级：高）

### 2.1 在 SKILL.md 中明确 get_pass_packet 已内含 rep_draw

**现状**：`get_pass_packet` 的返回里已经有 `rep_draw`（包含完整的 pipeline state + shader summary），但 SKILL.md 的工作流还让 agent 单独调用 `inspect_pipeline_state` 和 `inspect_shader`。

**改法**：在 SKILL.md 的决策树里加一条明确规则：

> `get_pass_packet.data.rep_draw` 已包含 pipe 和 shader。
> 仅当你需要查看 rep_draw 之外的另一个 event 时，才单独调用 inspect_pipeline_state 或 inspect_shader。

**预估节省**：大多数 pass 分析减少 2 次工具调用（省 5k-15k tokens）

### 2.2 inspect_texture_usage 默认只查 1 个 RT

**现状**：工作流说"对最重要的 outputs 调用 inspect_texture_usage"，但没有限制数量。agent 容易对 2-5 个 RT 都查一遍。

**改法**：明确规则：

> 默认只对 slot 0 的主 RT 调用 inspect_texture_usage。
> 仅当 pass 是 multi-RT（如 GBuffer）且需要区分各 RT 语义时，才查第 2 个。
> 上限 2 个。

**预估节省**：减少 1-3 次 inspect_texture_usage（每次 3k-8k tokens）

---

## 三、脚本输出摘要化（优先级：最高）

这是最大的 token 消耗源。

### 3.1 脚本输出分层：summary 文件 + full 文件

**现状**：`build_pass_evidence_bundle.py` 等脚本输出完整的 `bundle.json`（通常 10k-50k tokens），agent 整段读入。

**改法**：每个脚本输出两个文件：
- `*_summary.json`：只包含结论性字段（role、confidence、top_candidates、key_evidence_refs），控制在 1k-2k tokens
- `*_full.json`：完整数据，仅在 summary 不够定性时才读取

脚本改动清单：
- `build_pass_evidence_bundle.py` → 输出 `bundle_summary.json` + `bundle_full.json`
- `scan_pass_visuals.py` → 输出 `scan_summary.json` + `scan_full.json`
- `classify_pass_taxonomy.py` → 输出 `taxonomy_summary.json` + `taxonomy_full.json`

Summary 格式示例：

```json
{
  "pass": "Colour Pass #4 (2 Targets + Depth)",
  "top_candidates": ["translucency_composite", "ui_overlay"],
  "confidence": "medium",
  "dominant_cluster": {"type": "Draw", "count": 12, "coverage": "mixed"},
  "key_evidence": ["blend_enabled", "alpha_src_SrcAlpha", "depth_write_off"],
  "needs_detail": ["consumer_shader", "visual_validation"]
}
```

**预估节省**：从读 full JSON（10k-50k tokens）降到读 summary（1k-2k tokens），省 80-90%

### 3.2 SKILL.md 中加入"摘要优先"规则

加一条硬规则：

> 永远先读 `*_summary.json`。
> 仅当 summary 中 confidence 为 low 或 needs_detail 非空时，才选择性读取 full 文件中的对应段落。
> 禁止一次性读取整个 full 文件。如果需要 full 文件中的数据，用 offset+limit 只读相关段落。

---

## 四、Reference 文件合并（优先级：中）

### 4.1 结论相关文件合三为一

合并：
- `pass-conclusion-protocol.md`
- `decision-stop-rules.md`
- `label-gates.md`

→ `references/conclusion-rules.md`

理由：这三个文件都在回答"怎么从证据到结论"，agent 几乎每次都要同时读。合并后一次读取，减少 2 次文件 IO 和重复上下文。

### 4.2 防错相关文件合二为一

合并：
- `evidence-priority.md`
- `forbidden-inference.md`

→ `references/evidence-guardrails.md`

### 4.3 报告格式文件合二为一

合并：
- `report-shapes.md`
- `report-decision-template.md`

→ `references/report-format.md`

### 合并后的 reference 清单

| 合并前（11 个） | 合并后（6 个） |
|---|---|
| tool-map.md | tool-map.md（保留） |
| heuristics.md | heuristics.md（保留） |
| pass-taxonomy.md | pass-taxonomy.md（保留） |
| render-pass-taxonomy.md | render-pass-taxonomy.md（保留，考虑合入 pass-taxonomy.md）|
| pass-checklists.md | pass-checklists.md（保留） |
| pass-conclusion-protocol.md | conclusion-rules.md（合并） |
| decision-stop-rules.md | ↑ |
| label-gates.md | ↑ |
| evidence-priority.md | evidence-guardrails.md（合并） |
| forbidden-inference.md | ↑ |
| report-shapes.md | report-format.md（合并） |
| report-decision-template.md | ↑ |
| workflows.md | workflows.md（保留，但内容随 SKILL.md 改动同步更新） |

**预估节省**：减少 5 次文件读取，每次读取省去文件头部 / 重复上下文约 500-1k tokens，总计约 3k-5k tokens

---

## 五、workflows.md 同步更新（优先级：中）

`references/workflows.md` 里的工作流要和 SKILL.md 的决策树保持一致。改动点：

- Pass Analysis 工作流改成条件分支格式（和 SKILL.md 一致）
- 删除"Call inspect_pipeline_state for the dominant cluster representative"这类已被 get_pass_packet 覆盖的步骤
- 加入"摘要优先"规则

---

## 六、.gitignore 补漏（优先级：低）

`skills/renderdoc-analysis/scripts/__pycache__/` 出现在 git status 中。

在 `.gitignore` 中加入：
```
__pycache__/
*.pyc
```

---

## 预估总收益

| 场景 | 当前消耗 | 优化后预估 |
|---|---|---|
| 简单 pass（clear/copy/depth-only） | 30k-50k | 10k-20k |
| 标准 pass（单一类型 draw） | 50k-100k | 25k-45k |
| 复杂 pass（mixed + GBuffer + visual） | 100k-200k | 40k-70k |

主要收益来源：
- 脚本输出摘要化：省 30-80%（最大杠杆）
- 工具调用去重：省 10k-20k/次
- SKILL.md 瘦身 + reference 合并：省 5k-10k/次
- 条件分支替代线性 chain：对简单 pass 省 50%+

---

## 执行顺序建议

1. **脚本输出摘要化**（三.1 + 三.2）— 最大杠杆，独立可做
2. **SKILL.md 改写为决策树 + 去重规则**（一.2 + 二.1 + 二.2）— 第二大杠杆
3. **SKILL.md 瘦身**（一.1 + 一.3）— 配合上一步一起做
4. **Reference 合并**（四）— 中等收益，改动面较大
5. **workflows.md 同步**（五）— 跟随其他改动
6. **.gitignore**（六）— 随时可做
