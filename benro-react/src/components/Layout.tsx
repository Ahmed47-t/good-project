import { useEffect, useRef } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { CHROME_TOP, FOOTER } from '../data/chrome'
import { SITE_ROOT, fileToRoute, isSiteUrl } from '../lib/site'

const SHELL_SCRIPTS = [
  SITE_ROOT + '/assets/js/i18n-data.js',
  SITE_ROOT + '/assets/js/shared.js',
  SITE_ROOT + '/assets/js/whatsapp-widget.js',
]

/** Load a script once, in order. Resolves even on error so the chain continues. */
function loadScript(src: string): Promise<void> {
  return new Promise((resolve) => {
    if (document.querySelector('script[data-shell="' + src + '"]')) return resolve()
    const s = document.createElement('script')
    s.src = src
    s.setAttribute('data-shell', src)
    s.onload = () => resolve()
    s.onerror = () => resolve()
    document.body.appendChild(s)
  })
}

export default function Layout() {
  const navigate = useNavigate()
  const topRef = useRef<HTMLDivElement>(null)
  const footRef = useRef<HTMLDivElement>(null)

  // Load global i18n data + shared behaviors + widget once for the whole app.
  useEffect(() => {
    void SHELL_SCRIPTS.reduce(
      (chain, src) => chain.then(() => loadScript(src)),
      Promise.resolve(),
    )
  }, [])

  // Route internal chrome links through React Router instead of full reloads.
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const a = (e.target as HTMLElement)?.closest('a')
      if (!a) return
      const href = a.getAttribute('href')
      if (!href || href.startsWith('#main')) return
      if (href === '#') { e.preventDefault(); navigate('/'); return }
      let url: URL
      try { url = new URL(href, window.location.origin + SITE_ROOT + '/index.html') } catch { return }
      if (isSiteUrl(url)) {
        e.preventDefault()
        navigate(fileToRoute(url.pathname) + (url.hash || ''))
      }
    }
    const top = topRef.current
    const foot = footRef.current
    top?.addEventListener('click', handler)
    foot?.addEventListener('click', handler)
    return () => {
      top?.removeEventListener('click', handler)
      foot?.removeEventListener('click', handler)
    }
  }, [navigate])

  return (
    <>
      <div ref={topRef} dangerouslySetInnerHTML={{ __html: CHROME_TOP }} />
      <Outlet />
      <div ref={footRef} dangerouslySetInnerHTML={{ __html: FOOTER }} />
    </>
  )
}
