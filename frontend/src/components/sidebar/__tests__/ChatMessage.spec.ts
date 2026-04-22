import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatMessage from '../ChatMessage.vue'

describe('ChatMessage', () => {
  it('renders assistant messages through MarkdownRenderer (bold + lists)', () => {
    const message = {
      id: 1,
      role: 'assistant',
      content: '**bold** answer\n\n- one\n- two',
      created_at: '2026-04-22T10:00:00Z',
    }
    const w = mount(ChatMessage, { props: { message: message as never } })
    expect(w.html()).toContain('<strong>bold</strong>')
    expect(w.findAll('li')).toHaveLength(2)
  })

  it('renders user messages as plain text (no markdown parse)', () => {
    const message = {
      id: 2,
      role: 'user',
      content: '**not bold** really',
      created_at: '2026-04-22T10:00:00Z',
    }
    const w = mount(ChatMessage, { props: { message: message as never } })
    expect(w.html()).not.toContain('<strong>not bold</strong>')
    expect(w.text()).toContain('**not bold** really')
  })
})
