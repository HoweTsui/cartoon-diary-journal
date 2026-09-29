# 默认风格与生成入口

旧海报修改、补充元素和局部替换也必须经过相同入口，详见 `poster-revision.md`；旧图不是画风参考。猫狗附件与人物组件一样在生成前强制校验，缺少或错配直接阻止请求。

所有 onboarding、expression、diary 默认使用 style-lock-v2 的已确认母版，无需用户开启开关。没有 styleLock 字段的旧 brief 也采用此默认值；明确传入其他版本、缺图或哈希不符都报错，不退回旧参考包。

assets/style-reference/style-lock-v1/library.json 中 master 的用户批准独立于 templates。当前人物母版为 approved-v2，风格版本 style-lock-v2；目录名沿用历史路径。12张旧布局试验图保留归档，版本不同，即使 --preview 也不能作为新版生图附件。布局继续使用本地 sceneBoxes。猫狗角色出现时只附对应物种图，不附含旧人物的整张母版；逐场请求会按出镜角色筛选。

固定视觉段唯一来源是 style-contract.md，几何数值唯一来源是 geometry.json。母版决定画法、用户角色卡决定身份、用户照片提供事实。旧角色卡若与母版不一致，先做角色校准预览；不能仅因旧卡存在就视作符合新画风。正式 identity 除批准记录外须有 styleVersion: "style-lock-v2"；这个字段只在用户确认该版本后填写。预览可继续组合草稿角色，但交付须明确待确认。

## 实际附图

运行 `python3 scripts/build_diary_prompt.py brief.json --preview --scene 1 --request-output request-01.json --output prompt.txt`。对每个场景分别运行，scene 从 1 开始。request-01.json 包含内置生图工具的两个实参：prompt 和 referenced_image_paths。读取 JSON 后原样作为调用参数，母版必须第一张，所有列出的图片必须实际附上；保存请求文件与返回图片路径。不要将请求重新压缩成一句通用“黑白卡通”，不以路径文字代替附件。

角色卡调用不带 --scene；diary 请求必须指定一个场景。检查只证明准备了哪些图片，不能冒充外部工具已经收到附件。工具不支持这些附件时报告实际限制。

每个含 human 的请求还会强制实际附上发型/外观、年龄/体型、开放式人物组件、正式24种表情四类参考，并按角色 ID 与可见角色过滤；用户身份来源仍逐角色附上。只按组件借鉴参考，不临摹整个人物；参考的具体职责、年龄和体型约束、零容差视觉验收见 `identity-fidelity.md`。缺少任一图或身份映射时，构建请求失败，不允许只靠提示词补救。

## 合成与实际预览

模型只画透明背景的单场景。使用 `python3 scripts/build_diary_template.py --scenes scene-01.png scene-02.png --config config.json --output-dir output` 等比缩放并放到同一张纸上。sceneBoxes 只是不可见放置区域，不能变成背景矩形。透明边保留、身体内部白色保留；不做去白、不裁人物、不贴白板遮挡。

配置提供真实 header、title、captions；备注按实际墨迹中心定位。纸张横线贯穿备注区，悠哉文本最后合成。输出实际 PNG 后检查每场侧向五官、鼻根、完整边缘、背景自然留白、图文对应。结构预检、颜色比例通过都不代表视觉通过。已确认组件使用规则见 component-reuse.md。

场景适配只略去 alpha=0 的外围空白，保留至少3像素透明边，再按完整主体等比放大到放置区域；保留所有非零alpha像素和内部白色，原文件不改。禁止按固定原始像素高度限制主体尺寸。主体受行高限制时不拉宽或裁切；备注字号44px，空间不足换行，不缩字。
