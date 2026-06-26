// Single source of truth for site routing + content-loading helpers.
export const SITE_ROOT = '/site'

// Chrome elements rendered by the persistent <Layout>; stripped from page content.
export const CHROME_SELECTORS = '.skip-link, .topbar, header, #siteHeader, .scrim, .mnav, footer'

/** Map a clean route path to its source HTML file under /site. */
export function routeToFile(pathname: string): string {
  if (!pathname || pathname === '/') return SITE_ROOT + '/index.html'
  return SITE_ROOT + pathname.replace(/\/+$/, '') + '.html'
}

/** Map a /site/*.html file path back to its clean route. */
export function fileToRoute(filePathname: string): string {
  const rel = filePathname
    .replace(new RegExp('^' + SITE_ROOT), '')
    .replace(/\.html$/, '')
    .replace(/\/index$/, '')
  if (rel === '/index' || rel === '' || rel === '/') return '/'
  return rel
}

/** True when a URL points at our bundled static site content. */
export function isSiteUrl(url: URL): boolean {
  return url.origin === window.location.origin && url.pathname.startsWith(SITE_ROOT + '/')
}

/** Rewrite relative asset URLs (src/href/poster/srcset) to absolute /site paths. */
export function resolveAssetUrls(doc: Document, fileBase: URL): void {
  const skip = /^(https?:|\/\/|#|mailto:|tel:|javascript:|data:|\/)/i
  doc.querySelectorAll('*').forEach((el) => {
    ;['src', 'href', 'poster'].forEach((attr) => {
      const v = el.getAttribute(attr)
      if (v && !skip.test(v)) {
        try { el.setAttribute(attr, new URL(v, fileBase).pathname) } catch { /* ignore malformed url */ }
      }
    })
    const ss = el.getAttribute('srcset')
    if (ss) {
      const fixed = ss.split(',').map((part) => {
        const seg = part.trim().split(/\s+/)
        if (seg[0] && !/^(https?:|\/\/|\/|data:)/i.test(seg[0])) {
          try { seg[0] = new URL(seg[0], fileBase).pathname } catch { /* ignore */ }
        }
        return seg.join(' ')
      }).join(', ')
      el.setAttribute('srcset', fixed)
    }
  })
}

/** Rewrite relative asset paths embedded in inline-script strings (e.g. hero slider). */
export function fixScriptAssetPaths(text: string): string {
  return text.replace(/([\s"'(`,])assets\//g, '$1' + SITE_ROOT + '/assets/')
}
