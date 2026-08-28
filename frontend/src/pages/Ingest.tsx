import { useCallback, useEffect, useState } from 'react'
import { apiStatus, listDocuments, uploadDocument } from '../api/client.ts'
import type { DocumentSummary } from '../api/types.ts'

const ACCEPT = '.pdf,.txt,.md,.docx'

function formatDate(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('pt-BR')
}

export default function Ingest() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [offline, setOffline] = useState(apiStatus().usingMocks)

  const refresh = useCallback(async () => {
    const data = await listDocuments()
    setDocuments(data.documents)
    setOffline(apiStatus().usingMocks)
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function sendFile(file: File): Promise<void> {
    setBusy(true)
    setNotice(null)
    try {
      const result = await uploadDocument(file)
      const mocked = apiStatus().usingMocks
      setOffline(mocked)
      if (mocked) {
        setNotice(
          `API offline — o arquivo «${file.name}» não foi enviado ao backend. Um item mock (${result.status}) foi adicionado só para pré-visualizar a lista.`,
        )
      } else {
        setNotice(`Enviado: ${result.filename} (${result.status})`)
      }
      await refresh()
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }

  function takeFiles(fileList: FileList | null): void {
    if (!fileList?.length) return
    const file = fileList[0]
    void sendFile(file)
  }

  return (
    <div className="page page--ingest">
      <section
        className={`dropzone ${dragging ? 'dropzone--active' : ''}`}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          takeFiles(event.dataTransfer.files)
        }}
      >
        <p>Arraste um documento (.pdf, .txt, .md, .docx) ou selecione no computador.</p>
        <label className="file-button">
          Escolher arquivo
          <input
            type="file"
            accept={ACCEPT}
            disabled={busy}
            onChange={(event) => {
              takeFiles(event.target.files)
              event.target.value = ''
            }}
          />
        </label>
        {busy ? <p className="muted">enviando…</p> : null}
      </section>

      {offline ? (
        <p className="banner banner--warn">API offline, usando mocks na lista de documentos.</p>
      ) : null}
      {notice ? <p className="banner">{notice}</p> : null}

      <div className="table-wrap">
        <table className="doc-table">
          <thead>
            <tr>
              <th>Arquivo</th>
              <th>Status</th>
              <th>Hashtags</th>
              <th>Criado em</th>
            </tr>
          </thead>
          <tbody>
            {documents.length === 0 ? (
              <tr>
                <td colSpan={4} className="muted">
                  Nenhum documento. Faça upload para indexar.
                </td>
              </tr>
            ) : (
              documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.filename}</td>
                  <td>
                    <span className={`status status--${doc.status.includes('mock') ? 'mock' : doc.status}`}>
                      {doc.status}
                    </span>
                  </td>
                  <td>
                    {doc.hashtags.length
                      ? doc.hashtags.map((tag) => (
                          <span key={tag} className="tag">
                            {tag}
                          </span>
                        ))
                      : '—'}
                  </td>
                  <td>{formatDate(doc.created_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}