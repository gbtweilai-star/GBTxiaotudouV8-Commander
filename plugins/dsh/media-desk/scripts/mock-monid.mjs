#!/usr/bin/env node
// 沙盒用的假 monid 命令。字段结构和真实返回一致，内容都是编的，也不会花钱。
import { existsSync } from 'node:fs'

const args = process.argv.slice(2)
const say = value => console.log(JSON.stringify(value))

if (existsSync(new URL('./nokey', import.meta.url))) {
  say({ error: { code: 'AUTH_FAILED', message: 'No active API key.' } })
  process.exit(1)
}
if (args[0] === 'balance') {
  say({ balance: { value: 12.5, currency: 'USD' }, held: {}, topup: {} })
  process.exit(0)
}
if (args[0] !== 'run') {
  say({ error: { code: 'UNKNOWN', message: 'unexpected command' } })
  process.exit(1)
}

const endpoint = args[args.indexOf('-e') + 1]
const now = Math.floor(Date.now() / 1000)
const lines = ['砍掉三个选题之后，数据反而涨了', '做内容最难的是决定不写什么', '我把日更停了一个月，发生了什么', '一条视频只讲一件事', '别再收藏了，先做一遍', '读者只记得一个数字']
const body = '说白了，这件事没那么复杂。我自己试了三个月，先把最想讲的砍掉一半，剩下的才是观众真正想听的。今天就讲一个，讲透。'
const done = output => say({ runId: 'mock', status: 'COMPLETED', cost: { value: 0.01, currency: 'USD' }, output })
const png = 'https://example.invalid/cover.png'

if (endpoint.endsWith('get_user_posted_notes')) {
  done({ code: 0, success: true, data: { has_more: false, notes: lines.map((title, i) => ({
    id: `65a${String(i).padStart(21, '0')}`, title, desc: `${title}。${body}`, create_time: now - i * 86400 * 2, type: 'normal',
    likes: 900 - i * 120, comments_count: 80 - i * 9, collected_count: 300 - i * 40, share_count: 40 - i * 5, view_count: 0, images_list: [{ url: png }],
  })) } })
} else if (endpoint.endsWith('get_user_info')) {
  done({ code: 0, success: true, data: { nickname: '示例博主', desc: '慢慢做内容', fans: 12800, interactions: [{ type: 'fans', count: 12800 }] } })
} else if (endpoint.endsWith('fetch_user_post_videos') && endpoint.includes('douyin')) {
  done({ status_code: 0, aweme_list: lines.map((title, i) => ({
    aweme_id: String(7300000000000000000n + BigInt(i)), desc: `${title} ${body}`, create_time: now - i * 86400 * 3,
    statistics: { play_count: 0, digg_count: 2000 - i * 200, comment_count: 150, collect_count: 300, share_count: 90 }, video: { cover: { url_list: [png] } },
  })) })
} else if (endpoint.endsWith('handler_user_profile')) {
  done({ status_code: 0, user: { nickname: '示例博主', signature: '慢慢做内容', follower_count: 54000 } })
} else if (endpoint.includes('bilibili') && endpoint.endsWith('fetch_user_post_videos')) {
  done({ code: 0, data: { list: { vlist: lines.map((title, i) => ({
    bvid: `BV1mock${i}xx`, title, description: body, created: now - i * 86400 * 4, play: 40000 - i * 5000, comment: 300 - i * 20, pic: `//example.invalid/${i}.png`,
  })) } } })
} else if (endpoint.endsWith('fetch_user_profile')) {
  done({ code: 0, data: { name: '示例博主', sign: '慢慢做内容' } })
} else if (endpoint.endsWith('fetch_user_relation_stat')) {
  done({ follower: 8800, following: 12 })
} else {
  say({ error: { code: 'UNKNOWN', message: `unknown endpoint ${endpoint}` } })
  process.exit(1)
}
