# Schema v2 与 CLI

Agent 负责理解事实、选景、编写短文本与表情；脚本仅验证和编排。原始用户日记逐字保存在 brief.sourceText（保留换行与空格，无长度上限），不传入生图提示词。不要修改原始日记文件；brief 是其独立工作副本。

公共必填：
- schemaVersion: 2
- kind: onboarding | expression | diary
- protagonistId: characters 中精确 ID
- identity: {status: draft | confirmed, version: 非空字符串}
- characters: [{id, name, species: human | cat | dog, anchors: 2–12个可观察身份特征}]
- references: [{path: 相对 brief 所在目录的本地图片, role}]

confirmed 还需 approvedVersion=version、approvedBy=user。仅用户明确批准该版本后记录；预览不能自动改状态。
参考 role：identity-source、identity-draft、identity-approved、style、layout、scene。onboarding 必须 identity-source 且 --preview；expression/diary 预览需要 identity-draft 或 identity-approved，正式必须 identity-approved。style/layout/scene 按任务需要选用，无四图固定门槛；声明后均须存在并作为生图输入。仅支持PNG/JPEG/GIF/WebP，禁止远程、绝对、父目录或逃逸符号链接路径。源图的旧几何不具优先权。

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
