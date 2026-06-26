import { useEffect, useRef } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { CHROME_TOP, FOOTER } from '../data/chrome'

function loadScript(src: string): Promise<void> {
  return new Promise((resolve) => {
    if (document.querySelector('script[data-shell="' + src + '"]')) { resolve(); return }
    const s = document.createElement('script')
    s.src = src
    s.setAttribute('data-shell', src)
    s.onload = () => resolve()
    s.onerror = () => resolve()
    document.body.appendChild(s)
  })
}

function fileToRoute(filePathname: string): string {
  let rel = filePathname.replace(/^\/site/, '').replace(/\.html$/, '').replace(/\/index$/, '')
  if (rel === '/index' || rel === '' || rel === '/') return '/'
  return rel
}

export default function Layout() {
  const navigate = useNavigate()
  const topRef = useRef<HTMLDivElement>(null)
  const footRef = useRef<HTMLDivElement>(null)

  // Load global i18n data + shared behaviors + whatsapp widget once
  useEffect(() => {
    (async () => {
      await loadScript('/site/assets/js/i18n-data.js')
      await loadScript('/site/assets/js/shared.js')
      await loadScript('/site/assets/js/whatsapp-widget.js')
    })()
  }, [])

  // Intercept internal link clicks inside the persistent chrome -> client-side routing
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const a = (e.target as HTMLElement)?.closest('a')
      if (!a) return
      const href = a.getAttribute('href')
      if (!href || href.startsWith('#main') || href === '#') {
        if (href === '#') { e.preventDefault(); navigate('/') }
        return
      }
      let url: URL
      try { url = new URL(href, window.location.origin + '/site/index.html') } catch { return }
      if (url.origin === window.location.origin && url.pathname.startsWith('/site/')) {
        e.preventDefault()
        navigate(fileToRoute(url.pathname) + (url.hash || ''))
      }
    }
    const t = topRef.current, f = footRef.current
    t?.addEventListener('click', handler)
    f?.addEventListener('click', handler)
    return () => { t?.removeEventListener('click', handler); f?.removeEventListener('click', handler) }
  }, [navigate])

  return (
    <>
      <div ref={topRef} dangerouslySetInnerHTML={{ __html: CHROME_TOP }} />
      <Outlet />
      <div ref={footRef} dangerouslySetInnerHTML={{ __html: FOOTER }} />
    </>
  )
}
