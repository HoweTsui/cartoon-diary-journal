# 生图提示词模板

优先运行 `scripts/build_diary_prompt.py --graph <task-character-graph.html>`。脚本只接受 `status: actual` 的任务图谱，并在组词前验证全部出场角色。角色缺失时先要求用户补图、转绘并入库；不要手工绕过校验。只有输入不是结构化事件时才手工填写下面模板。

```text
Use case: illustration-story
Asset type: one original vertical Chinese diary-journal page
Required input images, in order: Image 1 is this task's actual identity atlas and is identity-only; Image 2 is `assets/style-reference/character-lineup-demo.png` and is geometry-only (head, two eyes, human/animal nose grammar, limbs, shorts, shoes/paws); Image 3 is `assets/style-reference/face-geometry-closeup.png` and is the enlarged eye/break/nose grammar gate; Image 4 is `assets/style-reference/diary-layout-only.png` and is layout-only (ruled paper, header, vertical rhythm, whitespace) and contains no people or animals. Never infer character structure from Image 4 or inherit sample identities from Images 2–3. Never redraw an input atlas as a character sheet, grid, lineup, or scene content. Optional Image 5 is a simplified pet-proportion reference and optional Image 6 is an expression reference sheet. Any later user-uploaded photos are identity-only references and must be transformed into the same atlas style before use. If Images 1–4 are not all attached, stop instead of generating.

Exact top header: "{YYYY.MM.DD 周X}"
Exact subtitle: "{标题}"

Story moments:
1. {人物锚点}；{动作与场景}；mandatory caption "{4-10 字短总结}"；optional bubble "{1-6 字语气词}"
2. ...

Per-scene character-card lock: before each story moment, list every visible character as
`[角色 ID | 姓名 | atlas cell col=?, row=?] 全部 anchors`。每张卡独立生效：主角不得成为配角、路人或宠物的默认头脸、服装、四肢或鼻型。任一可见角色无法匹配自己的图集格位和全部锚点时，整页失败并重生成。

Graph lock: before generating, verify every named character against the task graph's
ID, exact name, role, anchors, and atlas cell. List only relationships whose two endpoints
appear in this page; preserve those relationship labels in the actions. If a character is
missing or ambiguous, stop and request a reference image, then rebuild the graph and re-check.

Atlas gate: inspect this task's identity atlas before generating the diary page. If any atlas character is near-front-facing, has a generic C-shaped or closed human nose, lacks the human contour break, has thick limbs, or turns an animal into a humanoid/realistic pet, rebuild the atlas first. Never propagate a failed atlas into a diary page.

PRIMARY DRAWING GATE: neutral HUMAN faces contain ONLY two geometrically perfect, identical-diameter, solid-black CIRCULAR eye dots: unoutlined filled disks, never oval, almond-shaped, hollow, or irregular; one unfilled human nose; and one low mouth. Add NO other marks above, between, or beside the eyes. Every human is shown in a clear 25-35 degree slightly forward half-side view; animals keep a species-correct half-side view. The nose points toward the facing direction while BOTH eyes stay visible. Reject front-facing poses and one-eye full profiles. For every human, draw one short curved outer-head segment from the hairline/fringe end to just ABOVE the forward eye, then leave a completely BLANK vertical channel about 1.5 eye-dot heights down to the nose root. No line may cross or fill this channel. This contour is never a long straight line.

P0 visual gate: render only after all five conditions are simultaneously true:
(1) both complete identical-diameter geometrically circular black dot eyes and one rear ear are visible in a 25-35 degree half-side view, with the outer eye clear of the outline;
(2) the human forward outer-face contour has the visible empty break; (3) humans use exactly one unfilled upper-open half-ellipse nose while animals use one species-correct solid-black nose;
(4) torso stays narrow and every limb shaft is a two-parallel-stroke tube with a white interior, no more than 1/18 of head width; hands/paws alone may be slightly wider;
(5) every repeated character matches its atlas head, eye spacing, nose direction, hair/ears, clothing blocks, limbs and shoes/paws. If any scene fails one condition, regenerate the whole page; do not accept a close approximation.

Style lock: original black-ink diary cartoon on smooth pure-white paper with
exactly 14-18 evenly spaced very pale cyan notebook rules. Every human keeps the identity atlas's
face shape, nose shape and placement, eye and mouth treatment, body proportion,
and default expression. Each human has exactly one nose. Do not give every person a long nose;
use a prominent silhouette-breaking nose only when that person's identity anchors specify it.
Every human nose must be an unfilled black-line, non-circular, slightly flattened open half-ellipse;
the nose's own contour must be deliberately broken at the UPPER side, with the upper endpoint ending
just below the two eyes and creating only slight overlap. Never make it a perfect circle, fully closed O,
solid-black button, animal nose, long bridge, forehead line, or downward U/C shape. Never place a black nostril dot inside, above, below, or beside a human nose, and never add a third facial dot to imply a nostril.
For every human, also preserve the visible open break in
the front outer head contour beside the forward eye: it must be a short curve from hairline to just above the forward eye, then remain visibly open for about 1.5 eye-dot heights until the nose root;
do not add any extra facial mark or any line that closes this gap. The visible face outline from forehead through
nose root, cheek, and chin must remain one smooth continuous organic curve; no angular kinks, stepped
cheeks, flat jaw corners, or abrupt turns. The nose itself may connect to the face naturally.
Use two perfect-round dot eyes placed slightly high with a slightly wider eye gap; keep the outer eye clear of the outline. Use tiny ears and two to eight sparse hair strokes
or one solid-black hair shape. Keep the torso narrow (no wider than about 55% of head width). Use extremely thin
double-line upper arms, forearms, thighs and calves, each tube no more than 1/18 of head width with a visible white gap;
use slightly enlarged simple hands, short 3–4 finger arcs, and oversized flat oval shoes. Put the mouth clearly
lower beneath the nose.
Every full-body or seated human visibly wears shorts or trousers. Draw a clear waistband, crotch separation, lower hem, and two distinct trouser legs; leave visible white separation between the hem and each thin calf. Never connect a shirt directly to bare-looking legs. Thin calves begin below the trouser cuffs, and trousers must not be faked by thickening the legs.
Every human face must visibly retain two eyes, one line-drawn open nose, and one mouth. Dogs use one solid-
black animal nose at the front of the muzzle; cats retain two ears, two eyes, one smaller solid-black
cat nose centered below the eyes, and a mouth. Cats never receive a human open nose, C-shaped nose line, or extra protruding muzzle contour. Animals also keep the same 25-35 degree half-side view,
a large head, narrow torso, extremely thin limb shafts and slightly larger simple paws. Never give an animal the human open half-ellipse nose, nose
bridge, nostrils, or a second nose. Nose direction must agree with face direction. Avoid square noses
and hard right-angle heads.
Use crisp slightly wobbly black outlines at about 5–6 px on a 1024px-wide canvas (scale proportionally),
with identical line weight across people, animals, outline, face, clothes, props, furniture, architecture, and background environment; pale cyan notebook rules are the only exception. Never use thin technical, perspective, or gray background lines. Both dot eyes must have identical diameter
and visual weight. Use a few solid-black fills for mouths,
hair, shirts, or shoes. No gray modeling, no shading, and no decorative colors.
Keep faces and clothing deliberately simple: no fine wrinkles, eyelashes, skin details, or accessory clutter.

Composition: strict 9:16 tall portrait; date and weekday occupy the very top; title directly
below; 3-6 airy open scenes arranged continuously from top to bottom; one action per scene.
EVERY scene has one mandatory 4-10 Chinese-character action summary in the same rounded cute
handwritten cartoon Chinese lettering. This caption is separate from dialogue. Leave at least one
full notebook-rule height of completely empty space between the bounding boxes of neighboring scenes,
preferably 1.5 rule heights. Use wide margins and no panel borders. Optional dialogue or thought bubbles
contain only 1-6 Chinese characters such as a short interjection; use at most three bubbles on the page.
Do not reproduce a published signature font.

Identity lock: repeat every listed head shape, front-contour break, nose shape and placement, eye and
mouth treatment, default expression, hair strokes, accessory, body proportion,
solid-black fill placement, clothing structure, shoe shape, and pet marking in
every scene.

Upload conversion lock: a user photo may contribute only broad identity cues
(hair silhouette, clothing block, accessory, body impression, pet ears/tail/fur
color). It must never contribute photographic rendering. Apply the current atlas
line weight, simplified head construction, two complete eyes, one nose, lower
mouth, nose-contour break, tube-like limbs, readable hands/paws, oversized shoes,
and deliberately simplified body proportion. Human lower legs stay slender two-line tubes; the atlas
and style anchor override the photo whenever they conflict. Before delivery, compare the new character
with the atlas as a style gate; regenerate if line weight, facial grammar, limb shape, or head-to-body
ratio drifts. Pets must remain a flat simplified silhouette with two ears, two eyes, a species-correct
single solid-black nose (for cats: smaller and centered below the eyes; for dogs: a single abstract black oval at the muzzle tip),
a tiny mouth, species-appropriate torso, clear legs/paws and a simple tail. Dogs use a head visibly larger than the torso,
widely spaced equal black dot eyes, and short thick rounded paws with only one to three simple toe notches per paw; never render realistic fur strands,
whiskers, eye reflections or fur shading. Use no colored fur areas; all animals remain pure black-and-white.
Long-haired animals may use
only three to five broad rounded contour notches for coat volume, never individual spikes or dense ruffs.
Expression changes may alter only the low mouth shape and up to two small external emotion marks; both eyes always remain complete, equal-size, solid-black perfect circles. The neutral face has no brows, and anger/confusion may use only one or two temporary marks outside the head.
Do not alter the identity head, nose placement,
hair/ear shape, limb length, hands/paws, shoes or head-to-body ratio.

Originality: do not reproduce any published character, signature font, page,
gag, logo, or composition. Do not copy private details from input images.

Avoid: front-facing or near-front-facing people or animals, one-eye profiles,
missing face-contour breaks, photorealism, semi-realism, realistic anatomy, cinematic lighting, 3D,
gradients, glossy surfaces, skin shading, realistic food, painterly rendering,
watercolor, pencil grain, crosshatching, paper fibers, film grain, noise,
speckles, vintage distress, solid-black human noses, animal noses on humans, human noses on animals,
closed round noses, multiple noses, misdirected noses, square noses,
hard right-angle heads, missing facial features, human noses on animals, dog-sized cat noses, misplaced cat noses, human nose bridges on animals, thick realistic legs,
thick torsos, thick arms, thick thighs, thick calves, thick animal limbs, hair-thin broken legs,
realistic pet fur, realistic pet eyes, soft pastel storybook art, kawaii sticker art, manga, polished commercial
vector art, hairline or mixed-weight outlines, bulky soft outlines, mismatched eye sizes or eye line weights, animal eye highlights,
white eye reflections, realistic dog anatomy, detailed toes, wet triangular dog noses, individual fur spikes, dense ruffs, fur strands, mechanically perfect vector curves, dense backgrounds, panel borders,
missing per-scene captions, cramped or touching neighboring scenes,
missing date, wrong weekday, copied copyrighted characters, and mixed rendering styles.
```

## 只修日期

```text
Edit only the top header. Replace it verbatim with "{YYYY.MM.DD 周X}". Keep the
pale cyan notebook rule, every drawing, caption, spacing, identity, line, and
crop unchanged. Add nothing else.
```

## 修人物漂移

重新附人物图集并重生成受影响的整页。明确写出：只使用图集中的固定脸型、鼻型、眼嘴、头身比、发型、配饰和服装结构；不要融合两个人物的特征。
