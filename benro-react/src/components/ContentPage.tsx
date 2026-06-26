import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

const loadedExternal = new Set<string>()

function routeToFile(pathname: string): string {
  if (!pathname || pathname === '/') return '/site/index.html'
  return '/site' + pathname.replace(/\/+$/, '') + '.html'
}
function fileToRoute(filePathname: string): string {
  let rel = filePathname.replace(/^\/site/, '').replace(/\.html$/, '').replace(/\/index$/, '')
  if (rel === '/index' || rel === '' || rel === '/') return '/'
  return rel
}
function waitForShared(timeout = 4000): Promise<any> {
  return new Promise((resolve) => {
    const start = Date.now()
    const tick = () => {
      const bs = (window as any).BenroShared
      if (bs && (window as any).I18N) return resolve(bs)
      if (Date.now() - start > timeout) return resolve((window as any).BenroShared)
      setTimeout(tick, 50)
    }
    tick()
  })
}

// Chrome elements that live in the persistent Layout — strip them from page content
const CHROME_SELECTORS = '.skip-link, .topbar, header, #siteHeader, .scrim, .mnav, footer'

export default function ContentPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const file = routeToFile(location.pathname)
    setError(null)
    document.querySelectorAll('[data-benro-page]').forEach((n) => n.remove())

    fetch(file)
      .then((res) => { if (!res.ok) throw new Error('HTTP ' + res.status); return res.text() })
      .then(async (html) => {
        if (cancelled) return
        const doc = new DOMParser().parseFromString(html, 'text/html')
        const fileBase = new URL(file, window.location.origin)

        // Resolve relative asset URLs
        doc.querySelectorAll('*').forEach((el) => {
          ;['src', 'href', 'poster'].forEach((a) => {
            const v = el.getAttribute(a)
            if (v && !/^(https?:|\/\/|#|mailto:|tel:|javascript:|data:|\/)/i.test(v)) {
              try { el.setAttribute(a, new URL(v, fileBase).pathname) } catch {}
            }
          })
          const ss = el.getAttribute('srcset')
          if (ss) {
            const fixed = ss.split(',').map((part) => {
              const seg = part.trim().split(/\s+/)
              if (seg[0] && !/^(https?:|\/\/|\/|data:)/i.test(seg[0])) {
                try { seg[0] = new URL(seg[0], fileBase).pathname } catch {}
              }
              return seg.join(' ')
            }).join(', ')
            el.setAttribute('srcset', fixed)
          }
        })

        if (doc.title) document.title = doc.title
        const lang = doc.documentElement.getAttribute('lang')
        if (lang) document.documentElement.setAttribute('lang', lang)

        // Inject page-specific <style> blocks
        doc.querySelectorAll('head style, head link[rel="stylesheet"]').forEach((node) => {
          const clone = node.cloneNode(true) as HTMLElement
          clone.setAttribute('data-benro-page', '1')
          document.head.appendChild(clone)
        })

        // Strip chrome (rendered by persistent Layout) and collect scripts
        const body = doc.body
        body.querySelectorAll(CHROME_SELECTORS).forEach((n) => n.remove())
        const scripts = Array.from(body.querySelectorAll('script'))
        scripts.forEach((s) => s.remove())

        if (containerRef.current) containerRef.current.innerHTML = body.innerHTML

        // Execute page scripts (hero slider, etc.)
        const allScripts = [...Array.from(doc.querySelectorAll('head script')), ...scripts] as HTMLScriptElement[]
        allScripts.forEach((old) => {
          const src = old.getAttribute('src')
          if (src) {
            const abs = new URL(src, fileBase).pathname
            if (loadedExternal.has(abs)) return
            loadedExternal.add(abs)
            const s = document.createElement('script')
            for (const at of Array.from(old.attributes)) {
              if (at.name === 'src') s.src = abs; else s.setAttribute(at.name, at.value)
            }
            s.setAttribute('data-benro-page', '1')
            document.body.appendChild(s)
          } else {
            const s = document.createElement('script')
            s.text = (old.textContent || '').replace(/([\s"'(`,])assets\//g, '$1/site/assets/')
            s.setAttribute('data-benro-page', '1')
            document.body.appendChild(s)
            s.remove()
          }
        })

        // Re-apply current language + re-run reveal/counter animations for new content
        const bs = await waitForShared()
        if (cancelled) return
        try {
          const savedLang = localStorage.getItem('benroLang') || 'en'
          bs?.applyLang ? bs.applyLang(savedLang) : (window as any).applyLang?.(savedLang)
          bs?.initReveal?.(); bs?.initCounters?.(); bs?.initYear?.()
        } catch {}

        // Hash scroll or top
        if (location.hash) {
          const target = document.querySelector(location.hash)
          if (target) target.scrollIntoView({ behavior: 'auto' }); else window.scrollTo(0, 0)
        } else {
          window.scrollTo(0, 0)
        }
      })
      .catch((e) => { if (!cancelled) setError(String(e)) })

    return () => { cancelled = true }
  }, [location.pathname, location.hash])

  // Intercept internal content link clicks
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onClick = (e: MouseEvent) => {
      const a = (e.target as HTMLElement)?.closest('a')
      if (!a) return
      const href = a.getAttribute('href')
      if (!href || href.startsWith('#')) return
      let url: URL
      try { url = new URL(href, window.location.origin + routeToFile(location.pathname)) } catch { return }
      if (url.origin === window.location.origin && url.pathname.startsWith('/site/')) {
        e.preventDefault()
        navigate(fileToRoute(url.pathname) + (url.hash || ''))
      }
    }
    el.addEventListener('click', onClick)
    return () => el.removeEventListener('click', onClick)
  }, [location.pathname, navigate])

  return (
    <>
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