# Render Pass Taxonomy

这个 taxonomy 不是给 pass 随便起名字，而是限制最终结论只能落到一组常见游戏渲染类别里。

规则：

- 先选 `family`，再选 `label`
- 不能把 `fullscreen`、`local`、`mixed` 这类几何描述当最终结论
- 不能从单一弱信号直接跳到具体语义
- 如果证据不够，只允许停在更宽的类别，或者继续下钻

## 顶层 Family

### `depth`

常见 label：

- `depth_prepass`
- `shadow_depth`
- `depth_copy_or_resolve`
- `depth_mask_or_utility`

### `gbuffer`

常见 label：

- `gbuffer_export`
- `velocity_export`
- `material_property_export`

### `opaque`

常见 label：

- `opaque_environment`
- `opaque_terrain`
- `opaque_foliage`
- `opaque_character`
- `opaque_mixed_scene`

### `translucency`

常见 label：

- `character_translucency`
- `scene_translucency`
- `water_or_refraction`
- `glass_or_distortion`
- `mixed_translucency`

### `vfx`

常见 label：

- `particle_vfx`
- `mesh_vfx`
- `beam_or_trail_vfx`
- `energy_overlay`
- `outline_or_highlight`

### `decal_or_projection`

常见 label：

- `decal`
- `projected_overlay`
- `signage_or_logo_overlay`
- `panel_or_screen_overlay`

### `lighting_or_composite`

常见 label：

- `deferred_lighting`
- `opaque_composite`
- `translucency_composite`
- `light_function`
- `fog_or_volumetric_composite`

### `postprocess`

常见 label：

- `tonemap`
- `bloom_or_glare`
- `taa_or_history`
- `color_grading`
- `final_post_chain`

### `ui`

常见 label：

- `hud`
- `screen_space_ui`
- `world_space_ui`
- `debug_overlay`

### `utility`

常见 label：

- `copy_or_bootstrap`
- `mask_or_id`
- `atlas_or_lookup_build`
- `resolve_or_pack`

## 使用规则

- `mesh 类型` 只用于判断“作用对象”，不能单独决定 pass 语义
- `blend/depth/输入依赖/图像贡献` 共同决定最终类别
- `角色骨骼 mesh + blend on + depth write off` 优先考虑 `translucency` 或 `vfx`
- `fullscreen + 只读前序 RT + 只写一个 RT` 优先考虑 `copy_or_bootstrap` 或 `postprocess`
- `fullscreen + 多张中间 RT + 色调/模糊/阈值采样` 优先考虑 `postprocess`

## 不允许的输出

这些不能作为最终 pass 结论：

- `fullscreen pass`
- `local overlay`
- `mixed pass`
- `bootstrap`
- `collect`
- `finalize`

它们只能作为中间路由信息。
