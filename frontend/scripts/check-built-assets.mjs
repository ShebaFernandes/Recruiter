/** Verify case-exact asset references in the actual compiled output, before release. */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { resolve, dirname, basename, join } from 'node:path'

const root = resolve(process.argv[2] || 'dist')
const files = directory => readdirSync(directory).flatMap(name => {
  const path = join(directory, name)
  return statSync(path).isDirectory() ? files(path) : [path]
})
const missing = []
let references = 0
for (const file of files(root).filter(file => /\.(html|css|js)$/.test(file))) {
  const text = readFileSync(file, 'utf8')
  const pattern = /["'`(]((?:\/?assets\/|\.\/)[^"'`()\s,;]+?\.(?:avif|webp|png|jpe?g|svg|woff2?|js|css))(?=["'`)\s,])/g
  for (const match of text.matchAll(pattern)) {
    const path = match[1]
    const target = path.startsWith('./') ? resolve(dirname(file), path) : resolve(root, path.replace(/^\//, ''))
    references++
    try {
      if (!readdirSync(dirname(target)).includes(basename(target))) missing.push({ file, path })
    } catch { missing.push({ file, path }) }
  }
}
const assets = readdirSync(join(root, 'assets'))
for (const name of ['founding', 'leadership', 'closing', 'sky', 'clouds_front', 'clouds_back']) {
  if (!assets.some(file => file.startsWith(name + '-') && file.endsWith('.avif'))) missing.push({ family: name })
}
console.log(JSON.stringify({ references, missing }, null, 2))
if (missing.length) process.exitCode = 1
