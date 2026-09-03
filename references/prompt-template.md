# 生图提示词模板

优先运行：

```bash
python3 scripts/build_diary_prompt.py <brief.json> --graph <task-output>/character-graph.html
```

构建器支持两种输入：

```json
{"date":"2026-08-31", "text":"今天下班时突然下雨，我在门口借到一把伞。"}
```

以及需要更精确控制时的可选事件清单：

```json
{
  "date": "2026-08-31",
  "title": "门口借到伞",
  "events": [
    {
      "scene": "下班时门口突然下雨",
      "caption": "雨先到了",
      "characters": ["character-id"],
      "props": ["一把伞"],
      "must_keep": ["一个人", "下雨", "借到一把伞"],
      "flexible": ["背景建筑可简化"],
      "emotion": "surprise",
      "intensity": "medium",
      "eye_state": "wide_round"
    }
  ]
}
```

`events`、`title`、`characters`、`must_keep`、`flexible`、`emotion` 和 `eye_state` 都是可选的；缺失时根据文字/图片事实轻量补齐。显式事件覆盖自动提炼。没有日期和任何故事文本/图片时才停止并询问。

## 参考图职责

固定按以下顺序提供图像输入：Image 1 是任务实际人物图集（只锁身份）；Image 2 是 `assets/style-reference/character-lineup-demo.png`（只锁头脸、眼鼻、肢体几何）；Image 3 是 `assets/style-reference/face-geometry-closeup.png`（只锁脸部断口、人兽鼻型和有限表情眼原子）；Image 4 是 `assets/style-reference/diary-layout-only.png`（只锁横线纸、日期标题、留白和纵向节奏）。事件若有 `sourceImages`，在这四张固定参考之后逐场追加，并只把它们当作内容事实输入；这些路径必须是仓库根目录下已存在的相对本地文件，禁止绝对路径、`..` 路径和远程 URL；人物节点若有 `avatarSrc`，同时提供对应独立 1:1 上半身头像。少一张固定参考就停，不把任何示例角色当当前身份；用户照片只能临时提供身份线索。

## 公共风格块（只写一次）

```text
PRIMARY DRAWING GATE / BONE-THIN RULED-DIARY LOCK. Preserve scene facts before style. Use smooth white paper, 14-18 pale cyan notebook rules, and one 5-6px black line weight for people, animals, props, furniture, visible accessories (including eyeglass frames, bridge and temples) and background/environment strokes. Every visible subject is a clear left/right 25-35 degree slightly-forward half-side view; reject frontal faces, standard 90-degree side profiles, straight-at-camera faces, centered noses, symmetric ears/shoulders, or a frontal head on a side body.

HEAD/FACE PRIORITY: copy the approved near-round head width/height and identity silhouette before applying scene, photo or expression. Draw one short outer contour arc from the hairline/fringe end to above the forward eye, then leave a clean blank break about 1.5 eye-dot heights down to the nose root. A human must retain one short, clearly visible, horizontal, unfilled upper-open sideways half-ellipse nose under the eyes, followed by a small low mouth kept visibly separate; never omit, hide, merge or replace it with the mouth, and never use a long/downward U/C shape, black nose, nostril, bridge or closed O. Do not elongate the head, enlarge the eyes or let oversized hair cover the eye/forehead construction. An animal has one clearly visible species-correct solid-black nose only. Ear interiors stay plain white: draw the outer ear silhouette only, with no inner-ear curve, fold, hatching, shading or decoration.

Neutral eyes use the approved canonical eye-dot diameter. Expression may choose only the finite reference-derived atoms neutral_dot, closed_arc, half_lid, wide_round, or crossed; no arbitrary oval/almond/heart/highlight eyes. Eye deformation never changes head, eye placement, nose, contour break, identity silhouette or limb geometry. Use mouth, teeth, body reaction, hand gesture and at most two external marks first.

FIRST-PASS UNIFORM ULTRA-THIN LIMB LOCK: upper arms, forearms, thighs, calves and animal limb shafts excluding hands/paws share the same 1/32 head-width target, within 10%; the previous 1/28 form is compatibility-only, the same 1/24 target is only an absolute maximum ceiling, and older 1/22 is a failure ceiling. The outer shaft width no more than 1/24 of head width remains a hard upper bound. Hands/paws may be slightly larger at the terminal end; shorts/trousers step down at a clear cuff. Visible eyeglass frames, bridge and temples must use the same 5-6px black line weight as the surrounding face and clothing, with no local thickening or hairline stroke. FIRST-PASS ANTI-FRONT LOCK applies before composition.
```

## 文字、版式与场景

## 当前 0.2.4 几何覆盖

首轮提示词以 `1/32 head-width ultra-thin` 为人物和动物杆部目标；旧版 `1/28` 仅作兼容上限，头部、手部和脚部保持确认版尺寸，身体比例约为上一版的 90%（缩短约 10%）。每名角色只能是 25°–35° 偏正半侧面，禁止 frontal、true side profile、标准 90-degree 正侧面和单眼全侧面。

```text
Exact top header (verbatim, horizontal-center): "YYYY.MM.DD 周X"
Exact title (verbatim, directly below, horizontal-center): "标题"
Typography lock: one original handwritten Chinese display font description; fixed sizes across pages. Title <=12 Chinese characters, scene caption 4-10, bubble <=6. ImageGen renders all text; no extra text or gibberish; a text error is a whole-page regeneration.

One poster only. Default four open narrative zones. A single event becomes one large hero scene with 1-3 real related details and clean whitespace. Many source events stay in the internal inventory and are grouped by meaning into four zones; do not make a comic grid, a second page, tiny unreadable figures or delete must_keep facts. Each event has one main action plus at most one secondary action. Use relative left/right/front/back/near/far relations, not pixel coordinates.

Every scene has a mandatory 4-10 character caption in the fixed right-side caption lane (illustration 70-75%, caption 20-25%), with one full notebook-rule height of clean separation between neighboring zones. Dialogue bubbles are optional and cannot replace captions. By default draw one instance per character per scene; repeat only when the source explicitly requires a sequence, video/mirror or simultaneous distinct action.
```

## 角色卡与清单

Before each scene, list every visible character independently:

```text
[角色 ID | 姓名 | avatarSrc/独立 1:1 头像 | atlas col=?, row=?] 头型；发型/配饰（眼镜框、镜桥和镜腿若出现也锁定线宽）；鼻型与方向；眼基准与 eye_state；脸部断口；衣物；头身比；极细肢体；鞋/爪掌；宠物耳尾
```

Then write one inventory line per source event:

```text
Zone ? (main/grouped): source_images=[...]; subjects=...; scene=...; secondary_action=...; relation=...; must_keep=[...]; flexible=[...]; event-driven expression=...; intensity=...; eye_atom=...; caption="..."; bubble="..."
```

内容事实优先级：用户最新文字 > 当前图片可见事实 > 任务图谱身份 > 默认推断。没有事实支撑时不猜品牌、文字、精确数量或身份。`flexible` 只允许次要道具、背景和相对区域内的精确摆位变化。

## P0 验收与修正

检查主体数量、动作、道具/关系、角色卡、半侧面、断口、人兽鼻型、受控眼原子、统一线宽（含眼镜框/镜桥/镜腿）、1/32 细肢体目标与 1/24 上限、裤脚分割、右侧备注、日期标题和 exact text。非关键道具/摆位最多自动修两轮；身份、几何、关键事实、文字或画幅失败必须整页重生；仍有意义歧义时只亲切追问一个具体问题。

避免：realism、shading、texture、noise、细工程背景线、无意义背景、重复克隆人物、默认呆板表情、正面人物、单眼全侧面、下垂 U/C 人鼻、动物人鼻、任意眼睛变形、混合线宽、眼镜框/镜桥/镜腿单独变粗或变细、出版物角色/Logo/字体/构图。
