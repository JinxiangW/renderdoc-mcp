# Action 4339 逆向报告

## 概览

`Action 4339` 是 `Colour Pass #2 (5 Targets + Depth)` 里的一个多 MRT 几何 draw。
它的核心工作不是简单“画一个模型”，而是：

- 顶点阶段完成压缩属性解码、实例/权重相关的变换表读取，以及位置和 basis 变换
- 像素阶段采样多张材质纹理，重建法线与材质参数
- 将结果打包写入 5 个 MRT

这份报告重点回答 4 件事：

- 输入资源分别是什么
- shader 分成哪些功能段
- 5 个输出 RT 更像装了什么
- 哪些点已经比较稳，哪些还不能硬命名

## 结果

### 输入资源

顶点阶段：

- `VB0 / VB1 / IB` 是主几何输入
- `Buffer 117` 是 VS 的 structured buffer，用来按索引读取变换相关数据
- `cb0` 主要是视图/投影类常量
- `cb1` 是大块的对象/实例动态参数表

像素阶段：

- `t0` 更像主颜色贴图，`rgb` 进入颜色链，`a` 参与后续标量混合
- `t1` 是主法线类输入，至少提供了一组 remap 到 `[-1,1]` 的 normal 分量
- `t2` 是三路 material blend mask，控制多组材质参数的混合
- `t3 / t6` 是同一张控制纹理，被分成“循环查询”和“最终采样”两种用途
- `t4` 是 secondary/detail normal 或 control 贴图
- `t5` 是很小的辅助控制纹理，像 LUT 或 fallback 控制贴图
- `cb2` 是这段 PS 最关键的材质参数块
- `cb3` 更像少量 packed 分类位

### 输出 RT

- `RT0` 更像 HDR 主颜色项
- `RT1.xy` 很像 motion vector 编码，`z/w` 是附加标记或权重
- `RT2` 是 material scalar pack
- `RT3.xy` 是 packed normal，`z` 是附加标量，`w` 是分类位
- `RT4.xyz` 是 blended albedo / base-color-like 数据

## Shader 分段

### VS

`lines 1-52`

- 解码压缩顶点属性，重建局部向量和 basis

`lines 53-157`

- 通过 `instanceid`、权重和索引，从 structured buffer 中读取多组变换数据
- 这段明显是在做带权重的变换表读取，不是普通静态模型路径

`lines 158-178`

- 用上一步得到的矩阵/向量去变换顶点位置与局部 basis

`lines 179-206`

- 继续从 `cb1` 中读取对象级变换，把数据送到对象/世界空间

`lines 207-244`

- 执行视图投影，输出 PS 所需的 UV、basis、位置和实例相关插值

### PS

`lines 1-35`

- 声明 `cb0..cb3`、`t0..t6`、`s0..s5`，并明确写 `o0..o4`
- 这已经说明它就是一个 5 MRT 的材质求值 shader

`lines 36-65`

- 从屏幕位置与插值量重建坐标基础
- 采样 `t0 / t1 / t4`
- 开始建立主颜色、主法线和细节控制链

`lines 66-120`

- 用 `t2` 和 `cb2` 做三路材质参数混合
- 构建一组更完整的材质状态，包含颜色、法线和标量参数

`lines 121-160`

- 把采样结果与插值 basis 合成为最终表面法线
- 按 feature 开关进入分支
- 在分支内引入一次 `t5` 的控制采样

`lines 161-240`

- 这是最复杂的一段
- 结合导数、循环和 `sample_d(texture2d)` 使用 `t6`
- 循环结束后再用 `t3` 做一次采样
- 这段很像 parallax / height-guided lookup / profile-guided search 一类逻辑

`lines 241-285`

- 将上一步得到的 feature 结果变成最终颜色贡献
- 做距离和平滑衰减

`lines 286-353`

- 开始把结果打包写入 `o0..o4`
- 这是判断 MRT 语义最关键的输出段

## 输出打包说明

### RT0

- `o0.rgb` 是最终颜色项
- 格式是 `R11G11B10_FLOAT`
- 下游会被屏幕空间 pass 作为主输入读取

最稳妥的命名：

- `scene-color / HDR lighting contribution`

### RT1

- `o1.xy` 由两组投影空间量做差后编码到 `[0,1]`
- 这个模式非常像 motion vector 压缩
- `o1.z / o1.w` 不是颜色，而是附加标记或强度

最稳妥的命名：

- `motion-vector-like buffer`

### RT2

- `o2.x / y / z / w` 全部来自材质链里的标量打包
- `o2.w` 明显来自 `cb3` 的高位 packed 值

最稳妥的命名：

- `material scalar pack`

### RT3

- `o3.xy` 是典型的二维法线编码
- `o3.z` 来自材质混合链中的一个 companion scalar
- `o3.w` 是低 bit 分类值

最稳妥的命名：

- `packed normal + material/class bits`

### RT4

- `o4.xyz` 直接来自混合后的 `r7.xyz`
- RT 本身是 `R8G8B8A8_SRGB`
- `o4.w = 0`

最稳妥的命名：

- `blended albedo/base-color-like buffer`

## 资源作用表

| 资源 | 更可能的作用 |
| --- | --- |
| `t0` | 主颜色贴图 |
| `t1` | 主法线贴图 |
| `t2` | 三路材质混合 mask |
| `t3/t6` | 高度/轮廓/引导查询类控制纹理 |
| `t4` | detail normal / control |
| `t5` | 小型 LUT / fallback 控制纹理 |
| `cb0` | 视图、投影、全局尺度与距离类常量 |
| `cb1` | 对象/实例动态参数表 |
| `cb2` | 主要材质参数块 |
| `cb3` | 少量 packed 分类位 |
| `VS t0 (Buffer 117)` | 变换表或权重相关 structured data |

## 还不能写死的点

- `RT2.xyz` 还不能稳妥命名成 `roughness / metallic / ao`
- `RT1.z / RT1.w` 的精确用途还不够明确
- `t5` 只能确定是辅助控制纹理，不能再往下命名
- `t3/t6` 很像高度或 profile 控制，但还缺更直接的 consumer 证据去锁死

## 简短结论

这个 action 的本质是：

> 一个带实例/权重变换的多材质几何 draw。VS 负责解码和变换，PS 负责主颜色、法线、layer mask 与 feature 控制的求值，最后将结果写入 5 个 GBuffer-like 目标，其中包含主颜色、运动向量样数据、材质标量、法线编码和 base-color-like 缓冲。
