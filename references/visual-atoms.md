# 表情原子

以 style-system.md 为唯一视觉规范，geometry.json 为唯一数值定义。身份卡中性点眼无眉；场景由 Agent 显式指定表情，脚本没有情绪分类器。

| eye_state | 语义 |
| --- | --- |
| neutral_dot | 明确平静、普通观察 |
| closed_arc | 闭眼、困倦或轻松 |
| half_lid | 怀疑、不满或尴尬 |
| wide_round | 惊讶；成对圆眼 |
| soft_lid_dot | 两颗圆点眼上各有一小段圆弧眼睑；轻松友好，不能变成眨眼 |
| upward_round | 成对纯白圆眼内的圆瞳一起移至上缘；好奇上望，额头不增加多余标记 |
| side_round | 成对纯白圆眼内保留圆瞳并同向侧看；疑惑或观察 |
| crossed | 有事实支撑的眩晕、撞击 |

eyebrows=none/raised/furrowed。mild/medium 必须 none；仅 strong 且事实明确支持夸张表情时可临时加眉，strong 不强制有眉。眉不能穿过脸部断口，不把半睁眼睑或闭眼弧误作眉毛。

点眼为等宽等高的等径实黑正圆，远侧眼不透视压成椭圆；half_lid 遮住圆眼上缘，closed_arc 保留闭眼弧。嘴长、弧度与张合由 scene/emotion 编写，在低位偏耳侧位置变化，不把所有表情锁成短钩。鼻根上方明显断口、无独立脖子但有头身分界线、圆头等粗线遵循 style-system.md。眼形变化不改变身份轮廓、鼻型、物种与段长。语义是否合理须人工对照完整sourceText，枚举验证不能代替阅读。

已确认的 24 种语义（平静、轻松微笑、好奇上望、自信露齿笑、开怀大笑、闭眼露齿笑、眯眼微笑、调皮吐舌、嘟嘴、尴尬冒汗、鼓腮、紧张咬牙、轻微惊讶、惊吓、担忧、不耐烦、委屈、侧目疑惑、哭泣、崩溃大哭、憋闷、怒喊、困倦哈欠、得意坏笑）及眼嘴组合见 `assets/style-reference/style-lock-v1/library.json` 的 `expressionVocabulary`。`human-expression-reference-v6.png` 是每个人类生图请求实际附上的表情组件参考，不只用于 expression 任务，也不替代身份卡。事件表情始终由 Agent 对照完整 sourceText 显式编写，不依靠自动情绪分类；同一角色切换表情时发型、脸型、鼻子、耳朵和年龄比例保持不变。睁眼时瞳孔均为等径正圆，瞪眼的眼白为纯白，不因情绪拉成长椭圆或变灰；嘴始终与鼻分离并位于脸下部。`expression-draft-v2.png` 仅保留为历史草稿，不再作为任何请求的实际附图。第三方表情图只提炼表情概念，不复制其角色外形或独特表情组合。
