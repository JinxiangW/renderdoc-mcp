# Shader Patterns

Use this file to recognize common disassembly motifs during `reverse-action` work.

Goal:

- identify the few patterns that explain the action
- avoid line-by-line translation
- keep conclusions tied to bindings, outputs, and downstream usage
- split the shader into functionally coherent code ranges

## Reading Order

1. note stage, entry, target, and `line_count`
2. note binding counts from `inspect_shader` or packet shader data
3. read only enough disassembly to identify decisive motifs
4. stop once the action-level conclusion is stable

## Segmentation Rule

When reversing one action, do not write one big shader summary paragraph first.
Split the decisive shader into explicit ranges such as:

- declarations and resource setup
- coordinate or basis reconstruction
- texture sampling and decode
- lighting, BRDF, or material evaluation
- output packing and final writes

Use actual disassembly line ranges from `get_shader_disasm`.
If the shader is long, you can leave uncertain ranges coarse, but every major claim should still point at one concrete range.

If the disassembly is long:

- read the first page to identify declarations and outputs
- read later pages only where the key calculations appear
- prefer a few decisive slices over the whole shader text

## Common Motifs

### Texture sampling

Typical signals:

- `sample`, `sample_l`, `sample_b`, `sample_d`, `ld`, `gather4`
- `dcl_resource_texture2d`, `dcl_sampler`

Likely meaning:

- one or more textures are actively sampled
- resource names and formats usually decide whether this is albedo, normal, depth, scene color, mask, or LUT usage

### Lighting

Typical signals:

- `dp3`, `dot`, `mul`, `mad`, `rsq`, `sqrt`, `normalize`
- saturated dot products between normal-like and light-like vectors
- half-vector or view-vector math before `pow` or repeated multiplies

Likely meaning:

- diffuse or specular lighting terms are being computed

Do not over-claim:

- one dot product alone does not prove full PBR lighting

### Normal mapping or tangent-space shading

Typical signals:

- texture sample followed by unpack or remap from `[0, 1]` to `[-1, 1]`
- z reconstruction from sampled xy
- `dp3` against tangent, bitangent, and normal basis vectors

Likely meaning:

- tangent-space normal map is being decoded and transformed

### Depth reconstruction or depth fade

Typical signals:

- sampling a depth-like texture
- divide by `w`, inverse projection math, or clip-to-view reconstruction
- subtracting scene depth from particle or surface depth and clamping the result

Likely meaning:

- screen-space depth testing, soft particles, fog, contact fade, or reconstruction of view/world position

### Refraction or scene-color compositing

Typical signals:

- sampling a scene-color-like texture
- UV offset driven by normal or screen-space derivatives
- `lerp`-like blends between sampled scene color and shaded color

Likely meaning:

- refraction, transmission, distortion, or composite-over-background behavior

### Motion vectors or reprojection

Typical signals:

- current clip or screen position compared against previous-frame position
- subtraction between current and previous projected coordinates
- secondary output written with two channels that look like screen delta

Likely meaning:

- motion vector generation for TAA, motion blur, or reprojection

### Alpha test or masked rendering

Typical signals:

- `discard`, `clip`, or a branch that kills pixels based on texture alpha or threshold

Likely meaning:

- masked foliage, decals, cutouts, or alpha-tested materials

### Fresnel or view-dependent blend

Typical signals:

- `1 - dot(N, V)`
- repeated multiply or `pow` on that term
- result used to drive blend, rim, reflectance, or opacity

Likely meaning:

- Fresnel-like rim, reflection weighting, or view-dependent opacity

### Parallax or UV offset mapping

Typical signals:

- height-like texture sample used to offset UVs before later samples
- dependent texture reads using adjusted coordinates

Likely meaning:

- parallax mapping, distortion, or relief-style UV adjustment

### Post-process or fullscreen image operation

Typical signals:

- screen-space coordinates dominate
- little or no mesh significance
- multiple samples of scene-color, history, depth, or LUT resources

Likely meaning:

- post-process, composite, temporal resolve, or screen-space effect

### Compute image processing

Typical signals:

- `cs` stage with UAV writes
- thread-ID math, shared memory, barriers, or many neighborhood samples

Likely meaning:

- filter, reduction, tiled lighting, culling, prefix work, or other compute processing

## Reporting Rules

- tie every shader claim to one of: disassembly motif, named resource, constant-buffer role, output pattern, or downstream consumer
- keep output-channel meaning provisional unless output usage supports it
- when multiple explanations fit, give the broader family and state the uncertainty
- if bindings suggest more resources than the draw packet lists, report a partial binding map rather than inventing missing inputs
- resource reports should answer what each important `t#`, `u#`, or `cb#` is doing in code, not just that it is present
