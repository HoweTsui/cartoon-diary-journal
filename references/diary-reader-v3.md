# 日记阅读器 v3：默认新导出，旧阅读器保留

使用 Python 3.8+，无需额外 Python 依赖。先使用既有 build_diary_book.py 生成旧日记本，再导入其 index.html 内唯一的 script#diary-book-data。不会改写旧日记本、旧 runtime 或原海报。

```bash
python3 scripts/build_diary_reader.py assets/diary-book/demo/index.html --output-dir task-output/reader-v3-demo
python3 -m http.server 8000 --bind 127.0.0.1 --directory task-output/reader-v3-demo
```

打开 http://127.0.0.1:8000/ 。必须通过 HTTP 访问，不能直接用 file:// 打开。输出目录必须是 task-output 下的新目录；已有目录直接拒绝，换一个新名字即可。

v3 使用真正 Three.js / Quick FlipBook、手写字体、可替换花瓣裁剪封面、独立书名、日期/时期/人物检索、稳定 #entry 链接、阅读进度和原图放大。手机保留完整双页 spread，阅读海报细字请点“放大原图”。旧 build_diary_book.py 和 legacy runtime 不变，可继续独立使用；这个导入命令不会替换旧命令。

## 数据与发布边界

导入保留 book / periods / entries / characterIds / characters / relationships。所有非空 *Src 媒体字段（海报、头像、封面、时期封面）必须指向输入 HTML 所在目录内已存在的图片。URL、绝对路径、..、指向目录外的符号链接、缺失图片会失败；空格和中文路径转为浏览器可用的编码路径。媒体复制到 data/，不转码，不改变字节。manifest.json 在本地生成。

graphHref 等非图片字段保留为旧数据元信息，但 v3 不提供旧图谱页面；人物链接用于检索相应日记。SVG 按原样复制，不递归打包 SVG 内部外链，输入 SVG 应自包含。PNG 内文字不会被修改或 OCR。

assets/diary-reader-v3/source 是可发布源码；runtime 是可直接导出的编译代码、字体和许可。两者均不包含 diary data、测试图片、node_modules 或审阅图。任何 task-output 导出均为本地内容，不要提交到发布仓库。

封面上传仅保存在当前浏览器 IndexedDB，与 HTTP origin/端口绑定；它不会修改导出文件或上传图片。字体为本地 ZCOOL KuaiLe WOFF，SIL OFL 1.1；Three.js、Quick FlipBook、模板许可见 runtime/THIRD_PARTY_NOTICES.md。three.modifiers 未提供独立 LICENSE 的上游声明限制也保留在该文件。

## 从纯源码重建

```bash
cd assets/diary-reader-v3/source
npm ci --cache .npm-cache
npm test
npm run build
```

构建覆盖同级 runtime（仅编译运行文件），不依赖任何日记素材。打包前排除 source/node_modules 与 source/.npm-cache。package-lock.json 锁定依赖；无绝对本机路径。仅开发构建需要 npm，使用已编译 runtime 导出无需 Node。

维护时可设置 DIARY_READER_DEPS 为现有 node_modules 的路径，并用其中的 vite/bin/vite.js 构建 source，从而复用依赖；环境变量只在构建时解析，不写入成品。

```bash
python3 -m unittest discover -s tests -p test_reader_export.py -v
```

测试覆盖旧 8 篇 demo、可选的既有 3 篇 ImageGen 测试本、原图字节一致、缺失/逃逸失败、重复导出拒绝、路径编码和发布包隔离。缺少可选原测试本的安装环境会跳过该项；不会生成或发布替代图片。
