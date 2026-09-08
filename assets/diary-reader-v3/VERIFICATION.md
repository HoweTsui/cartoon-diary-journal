# Reader packaging verification

- Candidate source rebuilt successfully with Vite 6.4.3 using the existing reader's dependency directory. Original reader files were not edited.
- Source package.json and package-lock.json dependency declarations match.
- Exporter unittest: 9 passed, including the existing eight-entry demo and three-entry ImageGen book (neither skipped), path escapes, missing files, repeated outputs, local URL encoding and byte identity.
- Source drag tests: 8 passed.
- Actual CLI exports: demo 8 entries / 15 referenced images; ImageGen book 3 entries / 9 referenced images.
- Both exports served through local HTTP and opened in Chrome: correct entry counts, local font loaded, poster enlarged successfully, no page errors and all reader assets loaded. The browser's optional /favicon.ico request returned 404; it does not affect reader functions.
- Temporary exports were removed after verification. This package contains no data directory, image fixtures, node_modules, review screenshots or absolute workstation paths.
- Main Three.js chunk is about 585 KB minified; Vite's size advisory is not a build failure.

Commands from Skill root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_reader_export.py -v
node --test assets/diary-reader-v3/source/src/drag.test.mjs
python3 scripts/build_diary_reader.py assets/diary-book/demo/index.html --output-dir task-output/new-reader
```

Pure source rebuild and HTTP use are documented in references/diary-reader-v3.md.
No git operations, installation changes, source-reader edits or publishing operations were performed by this packaging task.
