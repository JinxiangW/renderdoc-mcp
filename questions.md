  1. 你最常见的使用场景是什么？
     是材质排错、贴图检查、mesh/顶点流检查、draw call 定位、shader 资源绑定分析，还是性能归因？

     材质debug，draw call定位，逆向分析，模型、纹理导出

  2. 你最希望 AI 直接帮你回答什么问题？
     例如：

  - “这个像素为什么错了”
  - “这个材质采样了哪些纹理”
  - “这次 draw 用的是哪个 shader permutation”
  - “这个 mesh 的 UV/normal/tangent 对不对”
  - “这个 pass 输出了什么”

    这个pass所用到的资源来自哪里数据流大概是什么样，这个pass大致用了哪些资源，shader代码大致是什么内容，某个变量的值是多少

  3. 你工作里主要看哪几类 API capture？
     D3D11、D3D12、Vulkan，还是混合？

    主要看d3d11和d3d12

  4. 你更常用“开着 qrenderdoc 看当前 capture”，还是“离线批量分析 .rdc 文件”？
    
    都需要，开着qrenderdoc分析引擎渲染状态，离线分析进行逆向

  5. 对你来说，最重要的入口对象是什么？
     是：

  - event_id
  - 资源名/纹理名
  - shader 名
  - pass / marker 名
  - draw call 名
  - 文件路径
    
    这几个都可作为对象

  1. 你是否需要“反查”能力作为一等公民？
     比如：

  - 通过纹理名找所有使用它的 draws
  - 通过 shader 找所有事件
  - 通过 resource id 找绑定位置

    需要

  7. 你需要多大程度的“图像化结果”？
     是只要结构化文本，还是需要：

  - 导出纹理缩略图
  - 像素采样结果
  - mesh CSV/FBX
  - pipeline 摘要卡片

    pipeline摘要

  8. 你希望 mesh 相关能力偏哪种？

  - 快速检查：顶点数、索引数、AABB、attribute 列表
  - 技术美术工作流：CSV 导出、FBX 导出、语义猜测、decode 辅助
  - 深度调试：VS input/output、post-VS、buffer layout 还原
    
    主要是快速检查和深度调试

  1. shader 方面你最想要哪一层？

  - 只看 shader 名、入口点、资源绑定
  - 看 disassembly
  - 看常量缓冲区当前值
  - 看纹理/采样器/UAV 绑定
  - 看编译 target / debug info

    shader侧需要完整的功能

  10. 你是否需要“按 marker / pass 过滤”的所有工具都统一支持？
     我倾向于统一支持，因为 TA 很少想看整个帧。
     
     统一支持

  11. 你能接受“两阶段交互”吗？
     比如先 find_draws_by_texture 找候选，再 get_pipeline_state(event_id) 深挖。
     如果你更希望“一步到位”，那我们要做组合工具。

     可以两段交互

  12. 你更需要“导出给 DCC/表格工具”，还是“直接给 AI 读”？
     这决定我们是偏：

  - 文件导出型
    还是
  - 摘要/结构化 JSON 型

    直接给ai读，尽量精简

  13. 对 token 最敏感的对象你觉得是哪几个？
     我判断通常是：

  - draw call 全树
  - pipeline 全量绑定
  - shader disassembly
  - mesh 顶点数据
  - texture raw bytes

    差不多

  14. 你要不要“意图化工具”而不是底层工具？
     例如直接提供：

  - analyze_material_usage
  - trace_texture_usage
  - list_passes
  - inspect_mesh_attributes
    而不是全靠 get_* 原语拼。

    需要

  15. 你希望 AI 输出偏“工程师术语”，还是“面向技术美术”的翻译层？
     我可以做双层：

  - 原始字段
  - TA 解释摘要

    原始字段就好了，但是要用业内通用的图形术语

  我先给一个建议方向
  如果目标用户主要是技术美术，我建议第一版工具优先做这 6 类：

  - open_capture
  - find_events
  - inspect_pipeline_state
  - inspect_texture_usage
  - inspect_shader
  - inspect_mesh

  都先做摘要版，不直接吐大数据。
  只有在明确需要时，再补：

  - export_texture
  - export_mesh_csv
  - export_mesh_fbx
  - get_buffer_slice
  - get_shader_disasm

  你直接按编号回复就行，越短越好。我拿到答案后会把功能树和精简 schema 一起定下来。
