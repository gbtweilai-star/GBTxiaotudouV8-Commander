// 把 client/ 打包成 DSH 的 lazy CommonJS 模块：react 留给宿主提供，CSS 内联成字符串。
import { build, context } from 'esbuild'
import { readFile } from 'node:fs/promises'

const pkg = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'))

const options = {
  entryPoints: ['client/index.jsx'],
  outfile: 'dist/client.js',
  bundle: true,
  format: 'cjs',
  platform: 'browser',
  target: 'chrome120',
  jsx: 'transform',
  jsxFactory: 'React.createElement',
  jsxFragment: 'React.Fragment',
  external: ['react'],
  loader: { '.css': 'text' },
  minify: !process.argv.includes('--watch'),
  legalComments: 'none',
  banner: { js: `window.__ModuleLoader__.load({id:${JSON.stringify(pkg.name)},factory:(require)=>{const module={exports:{}};const exports=module.exports;` },
  footer: { js: 'return module.exports}})' },
}

if (process.argv.includes('--watch')) {
  const ctx = await context(options)
  await ctx.watch()
  console.log('watching client/')
} else {
  const result = await build({ ...options, metafile: true })
  const size = Object.values(result.metafile.outputs)[0].bytes
  console.log(`dist/client.js ${(size / 1024).toFixed(1)} KB`)
}
