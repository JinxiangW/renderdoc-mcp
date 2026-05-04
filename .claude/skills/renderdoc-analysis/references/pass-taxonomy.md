# Pass Taxonomy

这个 taxonomy 不是给 pass 起随意名字，而是约束“最终允许输出的语义类别”。

原则：

- 先给出 `family`，再给出更具体的 `semantic label`
- 只有几何形态、覆盖范围、全屏/局部信息时，不允许直接作为最终 taxonomy
- 如果证据不足以落到 taxonomy，就必须下钻到 action / action cluster
- taxonomy 是脚本可生成的候选层，不是最终裁决层
- 最终 semantic label 需要由 agent 审核所有关键证据后确认

## 顶层 Family

### `scene_geometry`

用于场景主几何、角色主几何、地形、建筑、静态网格等。

常见子类：

- `basepass_opaque_environment`
- `basepass_opaque_character`
- `foreground_character_pass`

### `overlay_projection`

用于 decal、投影贴花、局部覆盖、logo、箭头、屏幕/面板标识等。

常见子类：

- `translucent_signage`
- `projected_sign_or_panel`
- `decal_pass`

### `lighting_composite`

用于延迟光照、全屏合成、局部 lighting volume 合成。

常见子类：

- `deferred_lighting`
- `lighting_composite`
- `light_function_or_local_lighting`

### `gbuffer_export`

用于多 RT 材质导出、延迟材质参数写出。

常见子类：

- `gbuffer_pass`
- `velocity_pass`

### `postprocess`

用于 tone map、TAA、bloom、fog composite、screen-space resolve 等。

常见子类：

- `postprocess_pass`
- `taa_or_history_pass`

### `shadow_or_mask`

用于 shadow map、shadow mask、light cookie、visibility mask。

常见子类：

- `shadow_depth_pass`
- `shadow_mask_or_light_function`

## 允许的最终输出

最终报告至少要能落到下面两层之一：

1. `family`
2. `semantic label`

例如：

- `scene_geometry / basepass_opaque_character`
- `overlay_projection / translucent_signage`
- `lighting_composite / deferred_lighting`

如果只能说：

- `fullscreen`
- `local`
- `mixed`
- `bootstrap`

这些都不算 taxonomy 结论，只能算路由信息。

## 证据升级规则

### 从 `overlay_projection` 升级到 `translucent_signage`

需要尽量满足：

- 局部小范围覆盖
- 多张 2D 纹理输入
- 不写深度
- 与已有 scene color 合成
- shader 里有 UV 旋转/缩放/居中采样特征
- 最终图像中能看到 logo、箭头、屏幕/面板标识一类视觉结果

### 从 `scene_geometry` 升级到 `basepass_opaque_character`

需要尽量满足：

- overlay 覆盖人体或角色主体轮廓
- mesh 有 `BLENDWEIGHTS / BLENDINDICES` 或明显角色骨骼特征
- 图像序列显示角色从 silhouette 被逐步补成可见实体
- draw 不是纯屏幕空间 quad

### 从 `lighting_composite` 升级到 `deferred_lighting`

需要尽量满足：

- 全屏三角形或全屏 quad
- 读多张前序 RT / depth
- 不写深度
- 输出 scene color
- 图像对比显示整屏明暗关系被重建或明显改变

## 使用规则

- taxonomy 是约束层，不是替代分析层
- 如果扫描结果只能落到 broad family，就必须在报告里写明需要继续下钻
- 如果下钻后的 action cluster 证据明确，就应该直接覆盖掉 broad family，输出更具体的 `semantic label`
- taxonomy candidate 可以直接进入最终报告，但前提是 agent 审核通过
- 当 taxonomy candidate 与 mesh、shader、视觉变化或资源链冲突时，优先由 agent 复核而不是盲信脚本结果
