# Schema v2 与 CLI

默认入口见 `style-lock.md`：已确认母版＋当前人物卡，所有 brief 自动使用。纸张与文字由本地合成；模板草稿状态不影响母版使用，默认不附实验模板。

正文入库及文案核对见 `diary-document.md`。正文允许轻润色，但标题、备注与场景均须有 sourceText 原文依据，保留否定、因果、先后和情绪强度。不能为了四到十字备注新增事实或改写用户立场。

## 强制固定参考与照片归档

`assets/style-reference/style-lock-v1/library.json` 的 approved master 是默认固定参考，onboarding/expression/diary 均强制加入，不能仅提供图片路径文字。旧 reference-manifest.json 为历史包，新任务不再附上。使用 `--request-output` 的 referenced_image_paths 原样传给生图工具，并保留调用实参和结果路径。

用户照片先执行：
```bash
python3 scripts/archive_diary_photos.py <photo...> --date 2026-09-13 --character-id <id> --output-dir task-output/2026-09-13/photo-archive
```
脚本保留 `original/` 原件，创建 `reference/` 长边2048px、JPEG质量85压缩件和 `archive-manifest.json`。brief 中照片引用使用 `origin: "user-photo"`，`path` 只能是该清单记录的 `compressedPath`；并增加 `photoArchive: {"manifest":"photo-archive/archive-manifest.json"}`。非用户照片可省略 origin，默认 `task-asset`。

日记用 `--scene N --request-output request-N.json` 每次画一个透明背景的独立场景；同时输出的 `--output` 提示词（或标准输出）与 request 的 `prompt` 逐字一致。未导出请求的多事件提示词仅是规划概览，不可直接生图。禁止整页五条横向分镜、背景矩形和沿齐边截断。模型不画纸张、横线或文字。使用 build_diary_template.py 完整等比摆放场景并生成横线与悠哉文字，按实际墨迹中心写 sceneCenters；检查实际 PNG 的图文对应和留白。

Agent 负责理解事实、选景、编写短文本与表情；脚本仅验证和编排。原始用户日记逐字保存在 brief.sourceText（保留换行与空格，无长度上限），不传入生图提示词。不要修改原始日记文件；brief 是其独立工作副本。

公共必填：

- schemaVersion: 2
- kind: onboarding | expression | diary
- protagonistId: characters 中精确 ID
- identity: {status: draft | confirmed, version: 非空字符串}
- characters: [{id, name, species: human | cat | dog, anchors: 2–12个可观察身份特征}]
- references: [{path: 相对 brief 所在目录的本地图片, role, origin?: task-asset | user-photo, id?: 引用ID, characterIds?: 身份卡适用角色ID列表}]

confirmed 还需 approvedVersion=version、approvedBy=user；正式模式另需 identity.styleVersion=style-lock-v1。旧卡先校准再由用户确认；预览不能自动改状态。
参考 role：identity-source、identity-draft、identity-approved、style、layout、scene。onboarding 必须 identity-source 且 --preview；expression/diary 预览需要 identity-draft 或 identity-approved，正式必须 identity-approved。用户提供的 references 是身份与事实来源；内置 style/layout 由脚本强制注入，无四图字段冗余写法。所有声明图片都校验存在，实际生图只附 request 中筛选后的图片，且清单图片全部附上。仅支持PNG/JPEG/GIF/WebP，禁止远程、绝对、父目录或逃逸符号链接路径。旧身份卡保留发型、服装和配饰；鼻形、鼻根断口、眼睛结构与比例按当前母版和 canonical geometry 修正，onboarding 和 preview 也不保留错误旧几何。

### 参考图与事件映射

- `role: "scene"` 必须有唯一、非空、最多64字符且无首尾空白的 `id`。每个场景参考图必须至少被一个事件的 `referenceIds` 引用；没有映射明确报错，不默认把全部背景传给每场。
- `event.referenceIds` 是 `role: "scene"` 引用ID列表，不能重复、引用未知ID或身份卡ID。省略或 `[]` 表示本场不使用场景参考图；同一参考图可以被多个事件显式复用。没有场景参考图的旧 brief 无需新增此字段。
- 身份参考图可选 `characterIds`，值必须为非空、无重复、已注册角色ID列表，仅适用于 `identity-source`／`identity-draft`／`identity-approved`。日记单场请求保留与出镜角色相交的身份卡。省略该字段表示共享人物合照／lineup，仍附给每场，但只画本场列出的角色。每个出镜角色须有适用的身份卡；正式请求只接受适用的 `identity-approved`。
- 同一路径、同一 role 不要声明冲突的ID或角色范围；复用一个引用，在多个事件中列出同一ID，或在一张身份卡的 `characterIds` 中列出多个角色。若其他引用也提供 `id`，同样必须唯一。onboarding 无事件映射，应使用 `identity-source`，不挂载 `scene` 背景。

以下是映射字段片段；合并到完整 brief 中，保留每个事件的其他必填字段：

```json
{
  "references": [
    {"path": "shared-lineup.png", "role": "identity-draft"},
    {"path": "person.png", "role": "identity-draft", "characterIds": ["person"]},
    {"path": "cat.png", "role": "identity-draft", "characterIds": ["cat"]},
    {"id": "window", "path": "window.png", "role": "scene"},
    {"id": "garden", "path": "garden.png", "role": "scene"}
  ],
  "events": [
    {"characters": ["person"], "referenceIds": ["window"]},
    {"characters": ["cat"], "referenceIds": ["garden"]}
  ]
}
```

第1场附母版、共享卡、person卡和window图；第2场附母版、共享卡、cat卡和garden图。用户照片仍需上述归档元数据，映射不能绕过归档要求。

expression 和 diary 还必填 sourceText、title（1–12字符）、events（1–5个）。diary 另需真实 ISO date（YYYY-MM-DD）。每天只产出一张海报；5个场景也在同一张3:4画面内按时间顺序编排。
每个 event：
```json
{"scene":"明确动作与可见事实","caption":"四到十字备注","characters":["角色ID"],"referenceIds":[],"emotion":"surprise","intensity":"medium","eye_state":"wide_round","eyebrows":"none","bubble":"可选","must_keep":["关键事实"],"flexible":["可简化背景"]}
```
scene≤180字符，emotion≤40；caption为4–10，bubble≤6，顶层可选summary≤20。字符按Python len计算，含标点。intensity为mild/medium/strong；eye_state见visual-atoms.md；eyebrows为none/raised/furrowed。脚本不推断或截断。must_keep/flexible为可选短字符串列表；关键事实应由Agent明确列出，scene本身始终必须保留。
每场可选 expressions 对象：键为该场角色ID，值为完整的 emotion/intensity/eye_state/eyebrows 四字段。角色覆盖优先于场景默认表情；例如 humans 使用 closed_arc，猫使用 {"emotion":"calm","intensity":"mild","eye_state":"neutral_dot","eyebrows":"none"}，不要把人的情绪复制给猫。
geometry 可省略以采用 canonical；如提供覆盖，必须通过 geometry.json 的容差与正白缝检查。禁止反复相对缩放。

眉毛限制按逐角色有效表情检查：mild/medium 必须 eyebrows=none；raised/furrowed 仅允许 strong，并由 Agent 核对事实确需夸张表达，不可为了通过校验改写情绪强度。眼珠保持正圆，半睁仅遮挡，闭眼仍是短弧。scene/emotion 应说明嘴长、弧度或张合，低位偏耳侧的嘴不再一律使用短弧。geometry.human.noseUpperGap 是鼻上缘与前脸线端的净白断口，neckWidth 是脖子外宽，均以头宽H为单位；新数值为设计目标而非图片测量。旧 geometry.human 完整覆盖对象需要补齐新增字段，通常省略 geometry 以采用当前定义。

```bash
python3 scripts/build_diary_prompt.py task-output/brief.json --preview --scene 1 --request-output task-output/request-01.json --output task-output/prompt-01.txt
python3 scripts/preflight_check.py --brief task-output/brief.json --preview
```
日记逐场更换 `--scene N` 和输出文件名；onboarding／expression 请求省略 `--scene`。正式模式去掉 --preview。--graph 可选：复用旧图谱读取接口，字符需显式species，旧图谱status=actual不代表身份已审批。
