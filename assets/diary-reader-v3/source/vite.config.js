import path from 'node:path';
const deps = process.env.DIARY_READER_DEPS;
export default {
  base: './',
  build: {target: 'es2022', outDir: '../runtime', emptyOutDir: true},
  resolve: {alias: deps ? [
    {find: /^three$/, replacement: path.join(deps, 'three/build/three.module.js')},
    {find: /^three\//, replacement: path.join(deps, 'three') + '/'},
    {find: /^quick_flipbook$/, replacement: path.join(deps, 'quick_flipbook/dist/flipbook.mjs')}
  ] : []}
};
