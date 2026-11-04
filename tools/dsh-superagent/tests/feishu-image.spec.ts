import { mkdtempSync, rmSync } from 'node:fs'
import { writeFile, readdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { Context } from '@deepseek-ai/cordis'
import type { Agent } from '@deepseek-ai/dsh-agent'
import { afterEach, beforeEach, expect, it, vi, type MockInstance } from 'vitest'
import { Commands } from '../src/infra/commands.ts'
import { testDeployment } from './fixtures/deployment.ts'
import { admissionImageKeys, readAdmissionImage } from '../src/sources/feishu-image.ts'
import type { FeishuRef } from '../src/sources/feishu-read.ts'

let directory: string
let agent: Agent
let saveImage: ReturnType<typeof vi.fn>
let resolveModelInfo: ReturnType<typeof vi.fn>
let lark: MockInstance<Commands['lark']>
const commands = new Commands(() => testDeployment(), {}, new AbortController().signal)
const source: FeishuRef = { triggerId: 'source', chatId: 'oc_chat', messageId: 'om_source' }
const text = '![Image](img_source) Plan mode'
const ref = { attachmentId: 'image-id', mediaType: 'image/png', bytes: 4, width: 1, height: 1 }
const signal = () => new AbortController().signal
beforeEach(() => {
  directory = mkdtempSync(join(tmpdir(), 'admission-image-test-'))
  saveImage = vi.fn().mockResolvedValue(ref)
  resolveModelInfo = vi.fn().mockResolvedValue({ inputModalities: ['text', 'image'] })
  const ctx = new Context()
  ctx.reflect.provide('attachments', { saveImage, imageLimits: { maxImageBytes: 100, maxMessageImageBytes: 100 } })
  ctx.reflect.provide('llm', { resolveModelInfo })
  agent = { ctx, session: { requestHeader: () => ({ config: { provider: 'chosen-provider', model: 'chosen-model' } }) }, options: {} } as unknown as Agent
  lark = vi.spyOn(Commands.prototype, 'lark').mockImplementation(async (args: string[], cwd?: string) => {
    expect(args).toEqual(['im', '+messages-resources-download', '--message-id', 'om_source', '--file-key', 'img_source', '--type', 'image', '--output', './image'])
    expect(cwd).toContain(directory)
    const saved_path = join(cwd!, 'image.png'); await writeFile(saved_path, 'data')
    return { saved_path }
  })
})
afterEach(() => { vi.restoreAllMocks(); rmSync(directory, { recursive: true, force: true }) })
it('retains the source-message pairing, commits an image reference and removes temporary files', async () => {
  expect(admissionImageKeys('![Image](img_source) {"image_key":"img_second"} img_source')).toEqual(['img_source', 'img_second'])
  expect(await readAdmissionImage(agent, commands, source, text, 'img_source', directory, signal())).toEqual({ source_message_id: 'om_source', image_key: 'img_source', image: ref })
  expect(resolveModelInfo).toHaveBeenCalledWith('chosen-provider', 'chosen-model', expect.any(AbortSignal))
  expect(saveImage).toHaveBeenCalledWith({ data: Buffer.from('data'), mediaType: 'image/png', name: 'img_source.png' })
  expect(await readdir(directory)).toEqual([])
})
it('rejects arbitrary keys and non-visual models before downloading', async () => {
  await expect(readAdmissionImage(agent, commands, source, text, '../img_other', directory, signal())).rejects.toThrow('source message')
  resolveModelInfo.mockResolvedValue({ inputModalities: ['text'] })
  await expect(readAdmissionImage(agent, commands, source, text, 'img_source', directory, signal())).rejects.toThrow('does not support image')
  expect(lark).not.toHaveBeenCalled()
  expect(saveImage).not.toHaveBeenCalled()
})
it('cleans up refused attachments and failed downloads without returning an image', async () => {
  saveImage.mockRejectedValueOnce(new Error('Invalid image bytes'))
  await expect(readAdmissionImage(agent, commands, source, text, 'img_source', directory, signal())).rejects.toThrow('Invalid image')
  expect(await readdir(directory)).toEqual([])
  lark.mockRejectedValueOnce(new Error('Resource permission denied'))
  await expect(readAdmissionImage(agent, commands, source, text, 'img_source', directory, signal())).rejects.toThrow('permission denied')
  expect(await readdir(directory)).toEqual([])
})
it('refuses escaped output paths, oversize files and unsupported types', async () => {
  const outside = join(directory, 'outside.png'); await writeFile(outside, 'data')
  lark.mockResolvedValueOnce({ saved_path: outside })
  await expect(readAdmissionImage(agent, commands, source, text, 'img_source', directory, signal())).rejects.toThrow('outside')
  for (const [name, bytes, error] of [['image.png', 101, 'byte limit'], ['image.svg', 4, 'supported']] as const) {
    lark.mockImplementationOnce(async (_args, cwd) => {
      const saved_path = join(cwd!, name); await writeFile(saved_path, Buffer.alloc(bytes)); return { saved_path }
    })
    await expect(readAdmissionImage(agent, commands, source, text, 'img_source', directory, signal())).rejects.toThrow(error)
  }
  expect(saveImage).not.toHaveBeenCalled()
  expect(await readdir(directory)).toEqual(['outside.png'])
})
