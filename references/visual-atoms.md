# 表情原子

以 style-system.md 为唯一视觉规范，geometry.json 为唯一数值定义。身份卡中性点眼无眉；场景由 Agent 显式指定表情，脚本没有情绪分类器。

| eye_state | 语义 |
| --- | --- |
| neutral_dot | 明确平静、普通观察 |
| closed_arc | 闭眼、困倦或轻松 |
| half_lid | 怀疑、不满或尴尬 |
| wide_round | 惊讶；成对圆眼 |
| crossed | 有事实支撑的眩晕、撞击 |

eyebrows=none/raised/furrowed。mild/medium 必须 none；仅 strong 且事实明确支持夸张表情时可临时加眉，strong 不强制有眉。眉不能穿过脸部断口，不把半睁眼睑或闭眼弧误作眉毛。

点眼为等宽等高的等径实黑正圆，远侧眼不透视压成椭圆；half_lid 遮住圆眼上缘，closed_arc 保留闭眼弧。嘴长、弧度与张合由 scene/emotion 编写，在低位偏耳侧位置变化，不把所有表情锁成短钩。鼻根上方明显断口、细脖子和圆头等粗线遵循 style-system.md。眼形变化不改变身份轮廓、鼻型、物种与段长。语义是否合理须人工对照完整sourceText，枚举验证不能代替阅读。
