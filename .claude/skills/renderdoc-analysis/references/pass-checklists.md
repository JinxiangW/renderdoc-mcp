# Pass Checklists

每个候选类别都必须看固定证据，避免 agent 东看一点西看一点后直接跳结论。

## `opaque`

重点检查：

- `blend` 是否大多关闭
- `depth write` 是否开启
- `depth func` 是否像正常主几何测试
- 输入是否以材质纹理、法线、粗糙度、颜色贴图为主
- mesh 是否是静态/骨骼几何
- 图像变化是否表现为实体表面第一次被画出来

反证：

- 如果大量 draw `blend on + depth write off`，不要判成 opaque

## `translucency`

重点检查：

- `blend enabled`
- `depth write off`
- 是否依赖 `scene color / scene depth / 前序 RT`
- 是否有噪声、遮罩、ramp、distortion、volume 等输入
- 图像变化是否是叠加、发光、透明层、折射、边缘层

反证：

- 只有骨骼 mesh 多，不足以排除 translucency

## `vfx`

重点检查：

- `blend enabled`
- 局部高亮、拖尾、能量、粒子、条带等视觉变化
- 简单 mesh / billboard / trail / beam
- 纹理是否更像噪声、遮罩、flipbook、ramp、体积贴图

反证：

- 如果图像变化主要是实体表面完整出现，而不是叠加效果，不要优先判成 vfx

## `decal_or_projection`

重点检查：

- 局部覆盖
- 不写深度
- projected UV 或基于深度/法线限制
- 输入是否像 decal atlas / sign / panel / logo

反证：

- 如果变化明显附着在角色骨骼 mesh 上，优先考虑 character translucency / vfx

## `lighting_or_composite`

重点检查：

- fullscreen 或大范围 screen-space draw
- 输入是否是 GBuffer、depth、shadow、lighting intermediate
- shader 是否在重建/合成已有结果

反证：

- 如果主体是大量 mesh draw，不要优先判成 lighting composite

## `postprocess`

重点检查：

- fullscreen draw 占主导
- 只看 screen-space 输入，不看 mesh 几何属性
- 输入是否是 HDR、bloom、history、LUT、small lookup
- 输出是否趋向 LDR / final intermediate

反证：

- 少量混入的简单几何 draw 不足以把整个 pass 改判成 UI 或场景几何

## `ui`

重点检查：

- 简单几何 + 颜色/TEXCOORD
- 屏幕空间位置固定
- 小范围叠加
- 文本、血条、图标、面板类变化

反证：

- 如果主体仍然是 fullscreen 后处理，不要因为少量 UI draw 就把整个 pass 判成 UI

## `utility`

重点检查：

- copy / bootstrap / atlas build / pack / resolve
- 输出是否主要作为后续输入而不是直接可见结果
- shader 是否非常薄，只做拷贝、pack、编码

反证：

- 如果输出图像已经包含明确可见内容，就不要再叫“纯初始化”
