# Pass 工作流

目标不是逐个事件阅读，而是按 pass 顺序建立可索引的证据链。

## 工作流

1. 获取整帧 pass 列表
2. 按时间顺序遍历每个 pass
3. 为每个 pass 生成：
   - `pass.json`
   - `analysis.json`
   - `rep_draw.json`
   - 输出资源图片
4. 为关键输出资源生成资源级索引
5. 生成整帧 `flow.md`

## 产物目录

每次运行生成一个 bundle，结构如下：

```text
pipeline_bundle/
  index.json
  flow.md
  passes/
    01_21110_compute_pass_1/
      pass.json
      analysis.json
      rep_draw.json
      outputs/
    ...
  resources/
    785830/
      usage.json
      exports/
```

## 原则

- 先完整整理证据，再写解释
- 所有 pass 按顺序排列，方便理解前后依赖
- 资源按 `rid` 建目录，方便跨 pass 追踪
