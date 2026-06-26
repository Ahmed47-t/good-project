import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  routeToFile,
  fileToRoute,
  isSiteUrl,
  resolveAssetUrls,
  fixScriptAssetPaths,
  CHROME_SELECTORS,
} from '../lib/site'
import type { BenroShared } from '../types/benro-shared'

const PAGE_MARK = 'data-benro-page'
const loadedExternalScripts = new Set<string>()

/** Resolve once the bundled shared behaviors (BenroShared + I18N) are ready. */
function waitForShared(timeout = 4000): Promise<BenroShared | undefined> {
  return new Promise((resolve) => {
    const start = Date.now()
    const tick = () => {
      if (window.BenroShared && window.I18N) return resolve(window.BenroShared)
      if (Date.now() - start > timeout) return resolve(window.BenroShared)
      setTimeout(tick, 50)
    }
    tick()
  })
}

/** Copy the page's own <style>/<link> blocks into <head>, tagged for cleanup. */
function injectPageStyles(doc: Document): void {
  doc.querySelectorAll('head style, head link[rel="stylesheet"]').forEach((node) => {
    const clone = node.cloneNode(true) as HTMLElement
    clone.setAttribute(PAGE_MARK, '1')
    document.head.appendChild(clone)
  })
}

/** Re-create and execute page scripts (innerHTML scripts don't run on their own). */
function runPageScripts(scripts: HTMLScriptElement[], fileBase: URL): void {
  scripts.forEach((old) => {
    const s = document.createElement('script')
    const src = old.getAttribute('src')
    if (src) {
      const abs = new URL(src, fileBase).pathname
      if (loadedExternalScripts.has(abs)) return
      loadedExternalScripts.add(abs)
      for (const at of Array.from(old.attributes)) {
        if (at.name === 'src') s.src = abs
        else s.setAttribute(at.name, at.value)
      }
      s.setAttribute(PAGE_MARK, '1')
      document.body.appendChild(s)
    } else {
      s.text = fixScriptAssetPaths(old.textContent || '')
      s.setAttribute(PAGE_MARK, '1')
      document.body.appendChild(s)
      s.remove()
    }
  })
}

/** Re-apply the saved language and re-run reveal/counter animations for new content. */
function reinitContent(bs: BenroShared | undefined): void {
  try {
    const savedLang = localStorage.getItem('benroLang') || 'en'
    if (bs?.applyLang) bs.applyLang(savedLang)
    else window.applyLang?.(savedLang)
    bs?.initReveal?.()
    bs?.initCounters?.()
    bs?.initYear?.()
  } catch { /* non-fatal */ }
}

/** Scroll to the hash target if present and valid, otherwise to the top. */
function scrollToHashOrTop(hash: string): void {
  if (hash) {
    try {
      const target = document.querySelector(hash)
      if (target) { target.scrollIntoView({ behavior: 'auto' }); return }
    } catch { /* invalid selector */ }
  }
  window.scrollTo(0, 0)
}

export default function ContentPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const file = routeToFile(location.pathname)
    setError(null)
    document.querySelectorAll('[' + PAGE_MARK + ']').forEach((n) => n.remove())

    fetch(file)
      .then((res) => {
        if (!res.ok) throw new Error('HTTP ' + res.status)
        return res.text()
      })
      .then(async (html) => {
        if (cancelled) return
        const doc = new DOMParser().parseFromString(html, 'text/html')
        const fileBase = new URL(file, window.location.origin)

        resolveAssetUrls(doc, fileBase)
        if (doc.title) document.title = doc.title
        const lang = doc.documentElement.getAttribute('lang')
        if (lang) document.documentElement.setAttribute('lang', lang)

        injectPageStyles(doc)

        // Strip persistent chrome and collect scripts before injecting content.
        const body = doc.body
        body.querySelectorAll(CHROME_SELECTORS).forEach((n) => n.remove())
        const bodyScripts = Array.from(body.querySelectorAll('script'))
        bodyScripts.forEach((s) => s.remove())
        if (containerRef.current) containerRef.current.innerHTML = body.innerHTML

        const headScripts = Array.from(doc.querySelectorAll('head script')) as HTMLScriptElement[]
        runPageScripts([...headScripts, ...bodyScripts], fileBase)

        const bs = await waitForShared()
        if (cancelled) return
        reinitContent(bs)
        scrollToHashOrTop(location.hash)
      })
      .catch((e) => { if (!cancelled) setError(String(e)) })

    return () => { cancelled = true }
  }, [location.pathname, location.hash])

  // Route internal content links through React Router.
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
      if (isSiteUrl(url)) {
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
