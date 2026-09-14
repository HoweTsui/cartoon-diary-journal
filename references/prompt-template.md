# Schema v2 与 CLI

正文入库及文案核对见 `diary-document.md`。正文允许轻润色，但标题、备注与场景均须有 sourceText 原文依据，保留否定、因果、先后和情绪强度。不能为了四到十字备注新增事实或改写用户立场。

## 强制固定参考与照片归档

`assets/style-reference/reference-manifest.json` 是内置参考包，脚本会按 `kind` 自动加入：onboarding/expression/diary 均附人物几何、人类表情、动物表情；diary 额外附3:4无人物横线模板。调用生图工具时必须实际附上输出 references 中所有 `origin=bundled` 图片，不能仅在提示词里提及，不能用用户照片或旧成果替换它们。

用户照片先执行：
```bash
python3 scripts/archive_diary_photos.py <photo...> --date 2026-09-13 --character-id <id> --output-dir task-output/2026-09-13/photo-archive
```
脚本保留 `original/` 原件，创建 `reference/` 长边2048px、JPEG质量85压缩件和 `archive-manifest.json`。brief 中照片引用使用 `origin: "user-photo"`，`path` 只能是该清单记录的 `compressedPath`；并增加 `photoArchive: {"manifest":"photo-archive/archive-manifest.json"}`。非用户照片可省略 origin，默认 `task-asset`。

日记海报先按 `assets/templates/diary-poster-text-layout.json` 预留顶部与右侧，不画人物道具，但横线贯穿右侧。检查生成图后逐场记录整页归一化高度，例如 `{"sceneCenters":[0.3,0.7]}`，通过 `scripts/build_diary_text_layer.py --anchors anchors.json` 生成悠哉透明文字层。锚点数量与场景数一致、逐图检查，不从小栏坐标或固定等距位置推断。导出PNG前检查图文对应与留白；不要让图像模型画汉字、日期、标题或备注。

Agent 负责理解事实、选景、编写短文本与表情；脚本仅验证和编排。原始用户日记逐字保存在 brief.sourceText（保留换行与空格，无长度上限），不传入生图提示词。不要修改原始日记文件；brief 是其独立工作副本。

公共必填：
- schemaVersion: 2
- kind: onboarding | expression | diary
- protagonistId: characters 中精确 ID
- identity: {status: draft | confirmed, version: 非空字符串}
- characters: [{id, name, species: human | cat | dog, anchors: 2–12个可观察身份特征}]
- references: [{path: 相对 brief 所在目录的本地图片, role, origin?: task-asset | user-photo}]

confirmed 还需 approvedVersion=version、approvedBy=user。仅用户明确批准该版本后记录；预览不能自动改状态。
参考 role：identity-source、identity-draft、identity-approved、style、layout、scene。onboarding 必须 identity-source 且 --preview；expression/diary 预览需要 identity-draft 或 identity-approved，正式必须 identity-approved。用户提供的 references 是身份与事实来源；内置 style/layout 由脚本强制注入，无四图字段冗余写法。所有声明和注入图片都须实际作为生图输入。仅支持PNG/JPEG/GIF/WebP，禁止远程、绝对、父目录或逃逸符号链接路径。源图的旧几何不具优先权。

expression 和 diary 还必填 sourceText、title（1–12字符）、events（1–5个）。diary 另需真实 ISO date（YYYY-MM-DD）。每天只产出一张海报；5个场景也在同一张3:4画面内按时间顺序编排。
每个 event：
```json
{"scene":"明确动作与可见事实","caption":"四到十字备注","characters":["角色ID"],"emotion":"surprise","intensity":"medium","eye_state":"wide_round","eyebrows":"none","bubble":"可选","must_keep":["关键事实"],"flexible":["可简化背景"]}
```
scene≤180字符，emotion≤40；caption为4–10，bubble≤6，顶层可选summary≤20。字符按Python len计算，含标点。intensity为mild/medium/strong；eye_state见visual-atoms.md；eyebrows为none/raised/furrowed。脚本不推断或截断。must_keep/flexible为可选短字符串列表；关键事实应由Agent明确列出，scene本身始终必须保留。
每场可选 expressions 对象：键为该场角色ID，值为完整的 emotion/intensity/eye_state/eyebrows 四字段。角色覆盖优先于场景默认表情；例如 humans 使用 closed_arc，猫使用 {"emotion":"calm","intensity":"mild","eye_state":"neutral_dot","eyebrows":"none"}，不要把人的情绪复制给猫。
geometry 可省略以采用 canonical；如提供覆盖，必须通过 geometry.json 的容差与正白缝检查。禁止反复相对缩放。

眉毛限制按逐角色有效表情检查：mild/medium 必须 eyebrows=none；raised/furrowed 仅允许 strong，并由 Agent 核对事实确需夸张表达，不可为了通过校验改写情绪强度。眼珠保持正圆，半睁仅遮挡，闭眼仍是短弧。scene/emotion 应说明嘴长、弧度或张合，低位偏耳侧的嘴不再一律使用短弧。geometry.human.noseUpperGap 是鼻上缘与前脸线端的净白断口，neckWidth 是脖子外宽，均以头宽H为单位；新数值为设计目标而非图片测量。旧 geometry.human 完整覆盖对象需要补齐新增字段，通常省略 geometry 以采用当前定义。

```bash
python3 scripts/build_diary_prompt.py task-output/brief.json --preview --output task-output/prompt.txt
python3 scripts/preflight_check.py --brief task-output/brief.json --preview
```
正式模式去掉 --preview。--graph 可选：复用旧图谱读取接口，字符需显式species，旧图谱status=actual不代表身份已审批。
