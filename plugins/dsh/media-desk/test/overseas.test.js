// 海外平台：链接识别、接口返回整理、Instagram 先查 ID 再读帖子。返回结构取自真实接口，只留用得到的字段。
import assert from 'node:assert/strict'
import test from 'node:test'
import { fetchAccount, normalizePosts, normalizeProfile, parseAccountUrl } from '../src/monid.js'

test('海外主页链接：TikTok、Instagram、X 认得出，帖子页和功能页不当成账号', () => {
  assert.deepEqual(parseAccountUrl('https://www.tiktok.com/@tiktok?lang=en'), { platform: 'TikTok', id: 'tiktok', url: 'https://www.tiktok.com/@tiktok' })
  assert.deepEqual(parseAccountUrl('https://www.instagram.com/instagram/'), { platform: 'Instagram', id: 'instagram', url: 'https://www.instagram.com/instagram/' })
  assert.equal(parseAccountUrl('https://twitter.com/X').platform, 'X')
  assert.equal(parseAccountUrl('https://x.com/elonmusk').id, 'elonmusk')
  for (const bad of ['https://www.instagram.com/p/DfQCqMnhpsG/', 'https://www.instagram.com/explore/', 'https://x.com/home', 'https://x.com/i/status/1', 'https://www.tiktok.com/foryou', 'https://x.com/a/status/2']) {
    assert.equal(parseAccountUrl(bad), null, bad)
  }
})

test('海外平台的帖子和资料整理成统一字段', () => {
  const [tt] = normalizePosts('TikTok', { status_code: 0, aweme_list: [{ aweme_id: '7702947070604332319', desc: 'already planning next halloween? 👀\nmore', create_time: 1793482137, author: { unique_id: 'tiktok' }, statistics: { play_count: 511307, digg_count: 6671, comment_count: 2166, collect_count: 628, share_count: 600 }, video: { cover: { url_list: ['https://p16.tiktokcdn.com/c.jpg'] } } }] })
  assert.equal(tt.url, 'https://www.tiktok.com/@tiktok/video/7702947070604332319')
  assert.equal(tt.title, 'already planning next halloween? 👀')
  assert.equal(tt.views, 511307)
  assert.equal(tt.saves, 628)

  const [ig] = normalizePosts('Instagram', { items: [{ code: 'DfQCqMnhpsG', taken_at: 1793647575, like_count: 238456, comment_count: 10356, ig_play_count: 72003563, caption: { text: 'Go make music in your bedroom 🎶' }, image_versions2: { candidates: [{ url: 'https://scontent.cdninstagram.com/a.jpg' }] } }] })
  assert.equal(ig.url, 'https://www.instagram.com/p/DfQCqMnhpsG/')
  assert.equal(ig.views, 72003563)
  assert.equal(ig.cover, 'https://scontent.cdninstagram.com/a.jpg')

  const xOutput = { status: 'ok', timeline: [{ tweet_id: '2117375669432664133', created_at: 'Mon Nov 02 21:57:53 +0000 2026', text: 'ah yes welcome back irl dark mode', views: '2373286', favorites: 11880, replies: 838, retweets: 858, quotes: 172, bookmarks: 502, media: [] }], user: { profile: 'X', name: 'X', desc: "what's happening?!", sub_count: 60655339 } }
  const [x] = normalizePosts('X', xOutput)
  assert.equal(x.url, 'https://x.com/X/status/2117375669432664133')
  assert.equal(x.views, 2373286)
  assert.equal(x.shares, 1030)
  assert.equal(x.publishedAt, '2026-11-02T21:57:53.000Z')

  assert.deepEqual(normalizeProfile('TikTok', { profile: { user: { nickname: 'TikTok', signature: 'Your next discovery', follower_count: 96598422 } } }), { nickname: 'TikTok', description: 'Your next discovery', followers: 96598422 })
  assert.equal(normalizeProfile('Instagram', { profile: { data: { user: { full_name: 'Instagram', edge_followed_by: { count: 686329479 } } } } }).followers, 686329479)
  assert.equal(normalizeProfile('X', { profile: xOutput.user }).followers, 60655339)
  assert.throws(() => normalizePosts('TikTok', { status_code: 5, status_msg: 'user not found' }), /user not found/)
})

test('fetchAccount：Instagram 先查用户 ID 再读帖子；X 一次调用拿到帖子和资料', async () => {
  const calls = []
  const run = async (args) => {
    const endpoint = args[args.indexOf('-e') + 1]
    const query = JSON.parse(args[args.indexOf('--query') + 1])
    calls.push([endpoint, query])
    if (endpoint.endsWith('fetch_user_info_by_username')) return { status: 'COMPLETED', cost: { value: 0.001 }, output: { data: { user: { id: '25025320', full_name: 'Instagram', edge_followed_by: { count: 9 } } } } }
    if (endpoint.endsWith('instagram/v1/fetch_user_posts')) return { status: 'COMPLETED', cost: { value: 0.001 }, output: { items: [{ code: 'abcdef', taken_at: 1793647575, like_count: 1, caption: { text: 'hi' } }] } }
    if (endpoint.endsWith('fetch_user_post_tweet')) return { status: 'COMPLETED', cost: { value: 0.001 }, output: { status: 'ok', timeline: [{ tweet_id: '1', text: 'hello', created_at: 'Mon Nov 02 21:57:53 +0000 2026' }], user: { profile: 'X', name: 'X', sub_count: 5 } } }
    throw new Error(`unexpected ${endpoint}`)
  }
  const ig = await fetchAccount({ platform: 'Instagram', id: 'instagram' }, run)
  assert.deepEqual(calls.map(c => c[1]), [{ username: 'instagram' }, { user_id: '25025320', count: Math.min(calls[1][1].count, 50) }])
  assert.equal(ig.profile.nickname, 'Instagram')
  assert.equal(ig.posts.length, 1)
  assert.equal(ig.cost, 0.002)

  calls.length = 0
  const x = await fetchAccount({ platform: 'X', id: 'X' }, run)
  assert.equal(calls.length, 1)
  assert.equal(x.profile.followers, 5)
})
