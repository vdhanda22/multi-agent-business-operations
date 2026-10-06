import { marked } from 'marked'

const escapeHtml = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

// Model output is untrusted: render Markdown, but show any raw HTML as plain text.
marked.use({ renderer: { html: ({ text }) => escapeHtml(text) } })

export default function Markdown({ text }) {
  return <div className="md" dangerouslySetInnerHTML={{ __html: marked.parse(text || '') }} />
}
