// 2026-11-11 一次性对账：devour_state.json 账本与 store/devoured 磁盘严重不一致
// （账本 total_devours=1 / total_caps_created=0，磁盘却有 26 个胶囊、最后写入 11-10 23:30）。
// 本脚本只按磁盘事实重建计数，保留 reflections 历史，不改动胶囊文件。
import fs from 'node:fs'
import path from 'node:path'

const repo = 'C:/Users/Lenovo E14 Gen 5/Desktop/GBT小土豆V8'
const devDir = path.join(repo, 'gbt_allinone/store/devoured')
const statePath = path.join(repo, 'gbt_allinone/store/devour_state.json')

const state = JSON.parse(fs.readFileSync(statePath, 'utf8'))
const before = {
  total_devours: state.total_devours,
  total_absorbed: state.total_absorbed,
  total_caps_created: state.total_caps_created,
  last_devour_at: state.last_devour_at,
}

const dirs = fs.readdirSync(devDir, { withFileTypes: true }).filter((d) => d.isDirectory())
const caps = []
for (const d of dirs) {
  const full = path.join(devDir, d.name)
  const hasKnowledge = fs.existsSync(path.join(full, 'knowledge.json'))
  const hasRun = fs.existsSync(path.join(full, 'run.py'))
  const hasAbsorbed = fs.existsSync(path.join(full, 'absorbed_knowledge.md'))
  const mtime = fs.statSync(full).mtime.toISOString()
  caps.push({ name: d.name, hasKnowledge, hasRun, hasAbsorbed, mtime })
}

const complete = caps.filter((c) => c.hasRun && (c.hasAbsorbed || c.hasKnowledge))
const latest = caps.map((c) => c.mtime).sort().pop()

state.total_devours = caps.length
state.total_absorbed = complete.length
state.total_caps_created = caps.filter((c) => c.hasKnowledge).length
state.last_devour_at = latest
state.reconciled_at = new Date().toISOString()
state.reconcile_note =
  '2026-11-11 对账：原账本只记 total_devours=1/total_caps_created=0，磁盘实有 26 个胶囊（22 个 GitHub 吞入 + 1 个 json_repair + 3 个判据测试）。按磁盘事实重建计数；reflections 历史保留。'

fs.writeFileSync(statePath, JSON.stringify(state, null, 2), 'utf8')

console.log('capsules on disk:', caps.length)
console.log('complete (run.py + absorbed|knowledge):', complete.length)
console.log('with knowledge.json:', caps.filter((c) => c.hasKnowledge).length)
console.log('latest mtime:', latest)
console.log('before:', JSON.stringify(before))
console.log('after :', JSON.stringify({
  total_devours: state.total_devours,
  total_absorbed: state.total_absorbed,
  total_caps_created: state.total_caps_created,
  last_devour_at: state.last_devour_at,
}))
console.log('missing pieces:', JSON.stringify(caps.filter((c) => !c.hasRun || (!c.hasAbsorbed && !c.hasKnowledge))))
