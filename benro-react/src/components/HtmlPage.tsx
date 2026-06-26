import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
// Track external scripts already loaded so we don't re-add them on every navigation
const loadedExternal = new Set<string>()

function routeToFile(pathname: string): string {
  if (!pathname || pathname === '/') return '/site/index.html'
  const clean = pathname.replace(/\/+$/, '')
  return '/site' + clean + '.html'
}

function fileToRoute(filePathname: string): string {
  let rel = filePathname.replace(/^\/site/, '')
  rel = rel.replace(/\.html$/, '')
  rel = rel.replace(/\/index$/, '')
  if (rel === '/index' || rel === '' || rel === '/') return '/'
  return rel
}

function isInternalNav(url: URL): boolean {
  return url.origin === window.location.origin && url.pathname.startsWith('/site/')
}

export default function HtmlPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const file = routeToFile(location.pathname)
    setLoading(true)
    setError(null)

    // Remove styles/scripts injected by a previous page
    document.querySelectorAll('[data-benro-injected]').forEach((n) => n.remove())

    fetch(file)
      .then((res) => {
        if (!res.ok) throw new Error('HTTP ' + res.status)
        return res.text()
      })
      .then((html) => {
        if (cancelled) return
        const doc = new DOMParser().parseFromString(html, 'text/html')
        const fileBase = new URL(file, window.location.origin)

        // Resolve relative asset URLs against the source file's location
        const attrs = ['src', 'href', 'poster']
        doc.querySelectorAll('*').forEach((el) => {
          attrs.forEach((a) => {
            const v = el.getAttribute(a)
            if (
              v &&
              !/^(https?:|\/\/|#|mailto:|tel:|javascript:|data:)/i.test(v) &&
              !v.startsWith('/')
            ) {
              try {
                el.setAttribute(a, new URL(v, fileBase).pathname)
              } catch {}
            }
          })
          const ss = el.getAttribute('srcset')
          if (ss) {
            const fixed = ss
              .split(',')
              .map((part) => {
                const seg = part.trim().split(/\s+/)
                if (seg[0] && !/^(https?:|\/\/|\/|data:)/i.test(seg[0])) {
                  try { seg[0] = new URL(seg[0], fileBase).pathname } catch {}
                }
                return seg.join(' ')
              })
              .join(', ')
            el.setAttribute('srcset', fixed)
          }
        })

        // Title
        if (doc.title) document.title = doc.title

        // Inject the page's own <style> blocks and stylesheet links into <head>
        doc.querySelectorAll('head style, head link[rel="stylesheet"]').forEach((node) => {
          const clone = node.cloneNode(true) as HTMLElement
          clone.setAttribute('data-benro-injected', '1')
          document.head.appendChild(clone)
        })

        // Inject the body markup (without scripts) into our container
        const body = doc.body
        const scripts = Array.from(body.querySelectorAll('script'))
        scripts.forEach((s) => s.remove())
        if (containerRef.current) {
          containerRef.current.innerHTML = body.innerHTML
        }

        // html lang/dir from the source doc
        const lang = doc.documentElement.getAttribute('lang')
        if (lang) document.documentElement.setAttribute('lang', lang)

        // Execute scripts in order (external once, inline every time)
        const allScripts = [
          ...Array.from(doc.querySelectorAll('head script')),
          ...scripts,
        ] as HTMLScriptElement[]
        allScripts.forEach((old) => {
          const src = old.getAttribute('src')
          if (src) {
            const abs = new URL(src, fileBase).pathname
            if (loadedExternal.has(abs)) return
            loadedExternal.add(abs)
            const s = document.createElement('script')
            for (const at of Array.from(old.attributes)) {
              if (at.name === 'src') s.src = abs
              else s.setAttribute(at.name, at.value)
            }
            s.setAttribute('data-benro-injected', '1')
            document.body.appendChild(s)
          } else {
            const s = document.createElement('script')
            s.text = old.textContent || ''
            s.setAttribute('data-benro-injected', '1')
            document.body.appendChild(s)
            s.remove()
          }
        })

        window.scrollTo(0, 0)
        setLoading(false)
      })
      .catch((e) => {
        if (cancelled) return
        setError(String(e))
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [location.pathname])

  // Intercept internal link clicks for smooth client-side navigation
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onClick = (e: MouseEvent) => {
      const a = (e.target as HTMLElement)?.closest('a')
      if (!a) return
      const href = a.getAttribute('href')
      if (!href) return
      let url: URL
      try { url = new URL(href, window.location.origin + routeToFile(location.pathname)) } catch { return }
      if (isInternalNav(url)) {
        e.preventDefault()
        navigate(fileToRoute(url.pathname))
      }
    }
    el.addEventListener('click', onClick)
    return () => el.removeEventListener('click', onClick)
  }, [location.pathname, navigate])

  return (
    <>
      {loading && <div className="benro-loading">Loading…</div>}
      {error && (
        <div className="benro-error">
          <h2>Page not found</h2>
          <p>{error}</p>
          <a href="/" onClick={(e) => { e.preventDefault(); navigate('/') }}>Go home</a>
        </div>
      )}
      <div ref={containerRef} className="benro-page" />
    </>
  )
}