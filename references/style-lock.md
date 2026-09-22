# 默认风格与生成入口

所有 onboarding、expression、diary 默认使用 style-lock-v1 的已确认母版，无需用户开启开关。没有 styleLock 字段的旧 brief 也采用此默认值；明确传入其他版本、缺图或哈希不符都报错，不退回旧参考包。

assets/style-reference/style-lock-v1/library.json 中 master 的用户批准独立于 templates。当前母版 approved，12 张布局试验图仍为 draft；默认不附任何草稿模板，不让模板草稿阻止已确认母版生效。只有明确指定 styleLock.templateId 才选该模板；草稿模板仅供 --preview 查看，不能晋升批准状态。日记逐场请求会剔除整页模板，避免其条带构图干扰单场景。

固定视觉段唯一来源是 style-contract.md，几何数值唯一来源是 geometry.json。母版决定画法、用户角色卡决定身份、用户照片提供事实。旧角色卡若与母版不一致，先做角色校准预览；不能仅因旧卡存在就视作符合新画风。正式 identity 除批准记录外须有 styleVersion: "style-lock-v1"；这个字段只在用户确认该版本后填写。预览可继续组合草稿角色，但交付须明确待确认。

## 实际附图

运行 `python3 scripts/build_diary_prompt.py brief.json --preview --scene 1 --request-output request-01.json --output prompt.txt`。对每个场景分别运行，scene 从 1 开始。request-01.json 包含内置生图工具的两个实参：prompt 和 referenced_image_paths。读取 JSON 后原样作为调用参数，母版必须第一张，所有列出的图片必须实际附上；保存请求文件与返回图片路径。不要将请求重新压缩成一句通用“黑白卡通”，不以路径文字代替附件。

角色卡调用不带 --scene；diary 请求必须指定一个场景。检查只证明准备了哪些图片，不能冒充外部工具已经收到附件。工具不支持这些附件时报告实际限制。

## 合成与实际预览

模型只画透明背景的单场景。使用 `python3 scripts/build_diary_template.py --scenes scene-01.png scene-02.png --config config.json --output-dir output` 等比缩放并放到同一张纸上。sceneBoxes 只是不可见放置区域，不能变成背景矩形。透明边保留、身体内部白色保留；不做去白、不裁人物、不贴白板遮挡。

配置提供真实 header、title、captions；备注按实际墨迹中心定位。纸张横线贯穿备注区，悠哉文本最后合成。输出实际 PNG 后检查每场侧向五官、鼻根、完整边缘、背景自然留白、图文对应。结构预检、颜色比例通过都不代表视觉通过。已确认组件使用规则见 component-reuse.md。
