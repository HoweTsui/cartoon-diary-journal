# 人物图库与关系

新图brief的characters使用精确id、name、species和身份anchors，protagonistId不得靠列表首项推断。角色卡与表情按style-system.md及geometry.json构造，每个角色使用自己的物种尺寸。

新角色先以identity-source和--preview生成draft，保留发型、衣服块面、宠物耳尾等大特征，修正源图错误几何。用户明确批准当前版本后才记录confirmed、approvedVersion和approvedBy=user。图谱status=actual仅说明实际数据，不代表用户审批。

图谱兼容assets/templates/character-graph-data.example.json和原build_character_graph.py接口：atlas.src/cols/rows；nodes的id/name/role/col/row/x/y/anchors；edges的source/target/label/type/curve。图谱anchors仍至少四条；brief允许两条起步，入图库前补齐实际可见特征。全局图谱无日期，不借用模板人物。

avatarSrc相对HTML；如使用独立头像则每个节点都有唯一1:1头像。旧图谱可回退atlas裁切，新日记本仍要求独立头像。按原接口构建：
```bash
python3 scripts/build_character_graph.py character-data.json --output character-graph.html
```
图谱浏览/编辑、搜索、拖拽、关系、localStorage与?character=<ID>跳转保持原接口。日记本兼容规则见diary-book-system.md。
