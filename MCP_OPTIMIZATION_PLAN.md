# MCP 修改清单

基于代码 review 整理。按优先级排列。

---

## 一、FastMCP 工具缺少描述（优先级：高）

**现状**：`runtime.py:141-310` 里所有 `@app.tool` 注册的函数都没有 docstring。FastMCP 用 docstring 作为工具描述暴露给 LLM 客户端。当前 LLM 只能看到函数签名，看不到工具用途。

同时 `app.py` 里定义了完整的 `ToolSpec.description`，但从未接入 FastMCP 注册流程。

**改法**：给每个 `@app.tool` 函数加 docstring，直接复用 `app.py` 中已有的 description 文本。示例：

```python
@app.tool
def get_pass_packet(marker: str | None = None, eid: int | None = None, limit: int = 8) -> Any:
    """Return a compact pass-level packet for the live capture."""
    ...
```

**考虑**：也可以改用 FastMCP 的 `@app.tool(description=...)` 参数，从 `ToolSpec` 自动注入，避免手写重复字符串。

**影响范围**：`src/renderdoc_mcp/server/runtime.py` 中 14 个 `@app.tool` 函数

---

## 二、`available()` 误判（优先级：高）

**现状**：`bridge_client.py:25-26`：

```python
def available(self) -> bool:
    return self.ipc_dir.exists()
```

只检查目录是否存在。如果 qrenderdoc 崩溃或正常关闭但没清理 `%TEMP%/renderdoc_mcp_bridge/`，MCP server 会认为 bridge 在线，然后每次调用都 timeout 20 秒。

**改法**：加 heartbeat 机制。

Bridge server 端（`server.py`）：每次 `_poll` 时更新一个 heartbeat 文件的时间戳：

```python
# server.py _poll() 开头
heartbeat = os.path.join(IPC_DIR, "heartbeat")
with open(heartbeat, "w") as f:
    f.write(str(time.time()))
```

Client 端检查 heartbeat 是否在合理时间窗口内：

```python
def available(self) -> bool:
    heartbeat = self.ipc_dir / "heartbeat"
    if not heartbeat.exists():
        return False
    try:
        ts = float(heartbeat.read_text())
        return (time.time() - ts) < 2.0  # 2 秒内有心跳
    except (ValueError, OSError):
        return False
```

`BridgeServer.stop()` 中清理 heartbeat 文件。

**影响范围**：
- `bridge_extension/renderdoc_mcp_bridge/server.py`
- `src/renderdoc_mcp/integration/bridge_client.py`

---

## 三、runtime.py 样板代码（优先级：中）

**现状**：`runtime.py` 中 11 个 live 工具函数重复相同的模式：

```python
@app.tool
def some_tool(params...) -> Any:
    if not live.available():
        raise RuntimeError("Live qrenderdoc bridge is not available")
    return live.invoke("some_tool", {params...})
```

约 170 行代码在做同一件事。

**改法**：用工厂函数或装饰器统一注册。示例思路：

```python
def _register_live_tools(app, live, specs):
    for spec in specs:
        # 从 ToolSpec 构建签名、docstring，注册到 app
        ...
```

具体方案取决于 FastMCP 的 `app.tool` 是否支持动态注册（需要确认 API）。如果不支持，至少可以抽一个 `_require_live` 辅助：

```python
def _require_live(live, method, params):
    if not live.available():
        raise RuntimeError("Live qrenderdoc bridge is not available")
    return live.invoke(method, params)
```

把每个函数体从 3-10 行缩到 1 行。

**影响范围**：`src/renderdoc_mcp/server/runtime.py`

---

## 四、Envelope 类型没有统一使用（优先级：中）

**现状**：`contracts/common.py` 定义了 `Envelope`、`ErrorInfo`、`MetaInfo` 数据类，但只有 offline adapter 在用。bridge extension 全部手写 dict：

```python
# bridge extension 的写法
return {
    "ok": True,
    "mode": "summary",
    "data": {...},
    "err": None,
    "meta": {"cap": "active", "truncated": False},
}
```

两套表示方式会逐渐 drift。比如 `Envelope` 里 `err` 类型是 `ErrorInfo | None`，但 bridge 端的 `err` 是 `dict | None`，字段名也可能不同步。

**改法**：两个选择（二选一）：

- **A（推荐）**：承认 bridge extension 运行在 qrenderdoc 内部、不方便引用 src 里的类型，就把 bridge 端的 dict 结构当作事实标准。在 `contracts/` 里只维护一份 JSON schema 或 TypedDict 文档作为参考，offline adapter 也改用 dict。删掉 `Envelope` dataclass。
- **B**：把 `Envelope` 等类型复制一份到 bridge extension 中，两边都用类型化对象。

方案 A 更务实——bridge extension 受限于 qrenderdoc 的 Python 环境，强制类型化收益不大。

**影响范围**：
- `src/renderdoc_mcp/contracts/common.py`
- `src/renderdoc_mcp/offline/adapter.py`
- `src/renderdoc_mcp/server/offline_bootstrap.py`
- `src/renderdoc_mcp/server/runtime.py`（`_to_jsonable` 可能不再需要）

---

## 五、`_fixed_function_state` 仅支持 D3D11（优先级：中）

**现状**：`packets.py:356-429` 硬编码调用 `controller.GetD3D11PipelineState()`。Vulkan 或 D3D12 capture 会静默返回全 None。

**改法**：

```python
def _fixed_function_state(self, eid):
    api = str(self.ctx.APIProps().pipelineType)
    # 根据 api 选择对应的 pipeline state getter
    # 或者使用 API-agnostic 的 GetPipelineState() 路径
```

RenderDoc 的 `GetPipelineState()` 返回的是抽象接口，blend/depth/rasterizer 可以通过 `GetOutputMerger()` 等通用方法取到。但不同 API 的字段差异大，短期内如果只需要 D3D11 支持，可以先加注释 + 在返回值里标注 `"api": "D3D11"` 让下游知道这个数据有 API 限制。

**影响范围**：`bridge_extension/renderdoc_mcp_bridge/domains/packets.py`

---

## 六、静默异常吞没（优先级：中低）

**现状**：bridge extension 中大量 `except Exception: pass`，例如：

- `packets.py:258`（UAV 收集）
- `texture.py:83-88`（SRV 遍历）
- `pipeline.py:183-198`（resource 计数）
- `shader.py:83-85`（SRV binding 收集）

在 qrenderdoc 插件环境下防御性 catch 有合理性，但完全静默意味着排查问题时无从下手。

**改法**：加最低限度的 logging。bridge extension 已经在 `server.py:63` 用了 `traceback.print_exc()`，在 domain 层也可以加一个轻量的 debug log：

```python
import sys

def _swallow(fn):
    try:
        return fn()
    except Exception:
        print("[renderdoc-mcp-bridge] warn:", sys.exc_info()[1], file=sys.stderr)
        return None
```

或者更简单：只在 `except` 里加 `pass  # TODO: log`，至少标记出这些位置。

**影响范围**：`bridge_extension/renderdoc_mcp_bridge/domains/` 下所有文件

---

## 七、`_select_texture` fallback 行为不合理（优先级：低）

**现状**：`texture.py:194-210`，当 `rid` 和 `name_filter` 都是 None 时，返回 capture 中第一个非 null 纹理。这几乎不可能是调用者想要的。

**改法**：当两个参数都缺失时直接返回错误：

```python
if not rid and not name_filter:
    return None  # 或者在调用侧返回 missing_args 错误
```

**影响范围**：`bridge_extension/renderdoc_mcp_bridge/domains/texture.py`

---

## 八、IPC 文件锁不可靠（优先级：低）

**现状**：`bridge_client.py:57-69` 的锁机制是"检查 lock 文件是否存在 → 写入 lock 文件"，两步之间存在 TOCTOU 竞争。对单用户场景问题不大，但如果未来有多 agent 并发调用会出问题。

**改法**：短期不需要改。如果未来需要多客户端支持，改用：
- Windows：`msvcrt.locking` 或 named mutex
- 跨平台：`filelock` 库（pip install filelock）

**影响范围**：`src/renderdoc_mcp/integration/bridge_client.py`

---

## 九、.gitignore 补漏（优先级：低）

**现状**：根目录有大量 `.tmp_*.json` 调试文件，`skills/` 下有 `__pycache__/`。当前 `.gitignore` 没有覆盖。

**改法**：在 `.gitignore` 中加入：

```
__pycache__/
*.pyc
.tmp_*.json
```

**影响范围**：`.gitignore`

---

## 执行顺序建议

1. **FastMCP docstring**（一）— 最高 ROI，只改字符串，零风险
2. **heartbeat 机制**（二）— 解决真实痛点（20s timeout），改动小
3. **runtime.py 去重**（三）— 改善可维护性，可与 1 一起做
4. **.gitignore**（九）— 随时可做
5. **Envelope 统一**（四）— 需要决策方向，改动面较大
6. **D3D11 限制标注**（五）— 短期加注释即可
7. **异常 logging**（六）— 渐进式改，不急
8. **_select_texture**（七）— 小改
9. **IPC 锁**（八）— 暂不需要
