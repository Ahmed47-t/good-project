#!/usr/bin/env python3
"""
BENRO INDUSTRIES — Phase 4 generator
Builds:
  • blog.html             — listing page (grid of all posts)
  • blog/<slug>.html × 18 — individual article pages

Run:  python3 build_blog.py
"""

import html, os, pathlib, re, json

BLOG_DIR = pathlib.Path("blog")
BLOG_DIR.mkdir(exist_ok=True)

# -------------------------------------------------------------------
# Shared CSS post-processing (Task 6)
# -------------------------------------------------------------------
def _strip_css_comments(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)

def _css_units(css):
    css = _strip_css_comments(css)
    units = []
    n = len(css); i = 0
    while i < n:
        while i < n and css[i].isspace():
            i += 1
        if i >= n:
            break
        start = i
        in_str = None; esc = False; j = i; brace_pos = -1; semi_pos = -1
        while j < n:
            ch = css[j]
            if in_str:
                if esc: esc = False
                elif ch == '\\': esc = True
                elif ch == in_str: in_str = None
            else:
                if ch in ('"', "'"): in_str = ch
                elif ch == '{': brace_pos = j; break
                elif ch == ';': semi_pos = j; break
            j += 1
        if brace_pos == -1:
            if semi_pos != -1:
                units.append(css[start:semi_pos+1].strip()); i = semi_pos + 1
            else:
                rest = css[start:].strip()
                if rest: units.append(rest)
                break
        else:
            depth = 0; in_str = None; esc = False; k = brace_pos
            while k < n:
                ch = css[k]
                if in_str:
                    if esc: esc = False
                    elif ch == '\\': esc = True
                    elif ch == in_str: in_str = None
                else:
                    if ch in ('"', "'"): in_str = ch
                    elif ch == '{': depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            units.append(css[start:k+1].strip()); i = k + 1; break
                k += 1
            else:
                units.append(css[start:].strip()); break
    return [u for u in units if u]

def _css_norm(unit):
    return re.sub(r'\s+', ' ', unit).strip()

def apply_shared_css(page_html, href):
    """Link assets/css/shared.css and keep only page-specific inline CSS."""
    link = f'<link rel="stylesheet" href="{href}" />'
    if link not in page_html:
        page_html = re.sub(r'(<link rel="icon"[^>]*>\s*)', r'\1' + link + '\n', page_html, count=1)
        if link not in page_html:
            page_html = page_html.replace('</head>', link + '\n</head>', 1)
    shared_path = pathlib.Path(href.replace('../', '')) if href.startswith('../') else pathlib.Path(href)
    if not shared_path.exists():
        return page_html
    shared_keys = {_css_norm(u) for u in _css_units(shared_path.read_text(encoding='utf-8')) if not _css_norm(u).startswith(':root')}
    def repl(match):
        css = match.group(1)
        remaining = [u for u in _css_units(css) if _css_norm(u) not in shared_keys]
        if not remaining:
            return ''
        return '<style>\n' + '\n\n'.join(remaining).strip() + '\n</style>'
    return re.sub(r'<style>(.*?)</style>', repl, page_html, count=1, flags=re.S|re.I)



# -------------------------------------------------------------------
# Shared JS post-processing (Task 7)
# -------------------------------------------------------------------
def apply_shared_js(page_html, href, marker):
    """Link assets/js/shared.js and keep only page-specific inline JS."""
    tag = f'<script src="{href}"></script>'
    def repl(match):
        attrs = match.group(1) or ''
        if 'application/ld+json' in attrs or 'src=' in attrs:
            return match.group(0)
        script = match.group(2)
        script = re.sub(r'\bconst\s+I18N\s*=', 'window.I18N =', script, count=1)
        script = re.sub(r'\bconst\s+BLOG_I18N\s*=', 'window.BLOG_I18N =', script, count=1)
        script = re.sub(r'\bconst\s+PRODUCT_I18N\s*=', 'window.PRODUCT_I18N =', script, count=1)
        start = script.find('const LANG_LABEL')
        if start != -1:
            end = script.find(marker, start)
            if end != -1:
                script = script[:start].rstrip() + '\n\n' + script[end:].lstrip()
        return '<script>' + script + '</script>'
    page_html = re.sub(r'<script(\s[^>]*)?>(.*?)</script>', repl, page_html, count=0, flags=re.S|re.I)
    if tag not in page_html:
        pos = page_html.rfind('</script>')
        if pos != -1:
            pos += len('</script>')
            page_html = page_html[:pos] + '\n' + tag + page_html[pos:]
        else:
            page_html = page_html.replace('</body>', tag + '\n</body>', 1)
    return page_html


# -------------------------------------------------------------------
# Responsive image post-processing (Task 9)
# -------------------------------------------------------------------
def apply_responsive_images(page_html, output_path):
    """Add srcset/sizes for local content images when generated WebP variants exist."""
    output_path = pathlib.Path(output_path)
    def should_skip(src, tag):
        low = src.lower()
        return (not src or src.startswith(('http:', 'https:', 'data:')) or low.endswith('.svg')
                or 'benro-logo' in low or 'partner-' in low or 'id="lbImg"' in tag or "id='lbImg'" in tag)
    def variant_url(src, width):
        p = pathlib.PurePosixPath(src)
        return str(p.with_name(f'{p.stem}-{width}.webp'))
    def repl(match):
        tag = match.group(0)
        src_m = re.search(r'\bsrc=["\']([^"\']+)["\']', tag, flags=re.I)
        if not src_m:
            return tag
        src = src_m.group(1)
        if should_skip(src, tag):
            return tag
        fs = (output_path.parent / src).resolve()
        try:
            fs = fs.relative_to(pathlib.Path.cwd().resolve())
        except ValueError:
            return tag
        srcset_parts = []
        for w in (400, 800, 1200):
            if fs.with_name(f'{fs.stem}-{w}.webp').exists():
                srcset_parts.append(f'{variant_url(src, w)} {w}w')
        if not srcset_parts:
            return tag
        tag = re.sub(r'\s+srcset=["\'][^"\']*["\']', '', tag, flags=re.I)
        tag = re.sub(r'\s+sizes=["\'][^"\']*["\']', '', tag, flags=re.I)
        src_m = re.search(r'\bsrc=["\']([^"\']+)["\']', tag, flags=re.I)
        sizes = '(max-width: 700px) 100vw, (max-width: 1100px) 50vw, 800px'
        insert = f' srcset="{", ".join(srcset_parts)}" sizes="{sizes}"'
        return tag[:src_m.end()] + insert + tag[src_m.end():]
    return re.sub(r'<img\b[^>]*>', repl, page_html, flags=re.I)

# ════════════════════════════════════════════════════════════════════
# POSTS  (verbatim content extracted from the live site)
# ════════════════════════════════════════════════════════════════════
# Each post:
#   slug, title, date_iso, date_label, category, lang, cover, excerpt, body_blocks, gallery
# body_blocks: list of (kind, payload)
#   ("h2", "text")
#   ("h3", "text")
#   ("h4", "text")
#   ("p",  "html text — strings may contain inline <strong> <em> already-escaped")
#   ("ul", [items])
#   ("ol", [items])
#   ("table", {"headers":[...], "rows":[[...], ...]})
#   ("hr", None)
#   ("img", "src")
#   ("note", "html")  -> highlighted call-out

POSTS = [
  # ───────────────────────────────────────────────────────────── 1
  {
    "slug":"benro-industries-a-trusted-name-in-hvac-solutions",
    "title":"Benro Industries: A Trusted Name in HVAC Solutions",
    "date_iso":"2025-04-12","date_label":"April 12, 2025",
    "category":"Guide","lang":"en",
    "cover":"../assets/images/blog/cover-blog-2025-03-12.png",
    "excerpt":"Why HVAC professionals across Algeria and beyond rely on Benro Industries for premium copper, aluminium and PE-foam components compliant with EN 12735.",
    "body":[
      ("h2","Why Choose Benro Industries for Your HVAC Needs?"),
      ("p","Benro Industries has established itself as a leader in the HVAC industry, offering high-quality air conditioning and refrigeration components. Based in Algeria, the company is committed to providing durable and efficient solutions tailored to both industrial and residential applications."),
      ("h3","What Sets Benro Industries Apart?"),
      ("ul",[
        "<strong>Premium Materials:</strong> copper and aluminium tubing with superior insulation.",
        "<strong>Compliance with International Standards:</strong> products adhere to <strong>EN 12735</strong> specifications.",
        "<strong>Efficient Performance:</strong> reduced BTU losses for better energy savings.",
        "<strong>Global Reach:</strong> serving HVAC manufacturers, distributors and installers worldwide.",
      ]),
      ("hr",None),
      ("h3","EN 12735 Standard and Its Importance"),
      ("p","The <strong>EN 12735 standard</strong> ensures that refrigeration copper tubes meet stringent quality and safety requirements. Compliance with this standard guarantees:"),
      ("ul",[
        "Optimal wall thickness for pressure resistance.",
        "Corrosion resistance for extended lifespan.",
        "Compatibility with modern refrigerants.",
      ]),
      ("hr",None),
      ("h2","Why Benro Industries is the Right Choice for HVAC Professionals"),
      ("h3","Comprehensive Product Range"),
      ("p","Benro Industries offers a variety of HVAC solutions, including:"),
      ("ul",[
        "<strong>Single &amp; Twin Insulated Copper Tubes:</strong> designed for enhanced performance.",
        "<strong>Aluminium Tubes:</strong> lightweight yet durable alternatives to copper.",
        "<strong>Polyethylene Tubes:</strong> excellent thermal insulation properties.",
      ]),
      ("h3","Industry Authority and Reliability"),
      ("p","For further insights, refer to trusted industry sources such as <strong>ASHRAE</strong> (American Society of Heating, Refrigerating, and Air-Conditioning Engineers) and the <strong>International Copper Association</strong>."),
      ("p","By choosing <strong>Benro Industries</strong>, you are investing in <strong>high-quality, energy-efficient and internationally compliant HVAC components</strong> that ensure long-term savings and optimal performance."),
    ],
    "gallery":[],
  },
  # ───────────────────────────────────────────────────────────── 2
  {
    "slug":"en-12735-copper-tube-the-essential-guide",
    "title":"EN 12735 Copper Tube: The Essential Guide for HVAC &amp; Refrigeration Systems",
    "date_iso":"2025-04-10","date_label":"April 10, 2025",
    "category":"Technical","lang":"en",
    "cover":"../assets/images/blog/cover-blog-2025-02-25-cu.png",
    "excerpt":"Everything HVAC contractors need to know about the EN 12735 standard: pressure ratings, comparison with ASTM B280, and BTU-loss benchmarks.",
    "body":[
      ("h2","Understanding the EN 12735 Standard for Copper Tubes"),
      ("p","The <strong>EN 12735</strong> standard defines the requirements for copper tubes used in <strong>air conditioning and refrigeration (ACR) systems</strong>. Designed to ensure durability, efficiency and reliability, this European standard specifies the mechanical and chemical properties of copper tubes, making them ideal for <strong>HVAC and refrigeration applications</strong>."),
      ("h2","Why EN 12735 Copper Tubes Matter"),
      ("p","Copper tubes are a critical component in refrigeration and air-conditioning systems. Using <strong>EN 12735-certified tubes</strong> ensures compliance with industry regulations, preventing leaks, inefficiencies and costly repairs. Unlike generic copper tubing, these tubes are manufactured to meet strict <strong>pressure resistance and corrosion resistance</strong> requirements."),
      ("h2","EN 12735 vs. ASTM B280: Key Differences"),
      ("table",{
        "headers":["Feature","EN 12735","ASTM B280"],
        "rows":[
          ["Region of Use","Europe","United States"],
          ["Application","HVAC &amp; Refrigeration","HVAC &amp; Refrigeration"],
          ["Pressure Rating","Standardised for high pressure","Designed for refrigeration pressures"],
          ["Wall Thickness","Defined by metric sizes","Defined by imperial sizes"],
        ],
      }),
      ("p","Both standards are widely used, but selecting the right one depends on regional compliance and system requirements."),
      ("h2","How to Choose the Right EN 12735 Copper Tube"),
      ("ul",[
        "<strong>Tube Size</strong> — ensure it matches the refrigerant flow requirements.",
        "<strong>Wall Thickness</strong> — select the right thickness for optimal pressure resistance.",
        "<strong>Insulation</strong> — using <strong>insulated copper tubes</strong> can enhance energy efficiency and reduce <strong>BTU loss</strong>.",
      ]),
      ("h2","BTU Loss in Copper Tubes"),
      ("p","A key factor in <strong>HVAC efficiency</strong> is <strong>BTU loss</strong> in copper tubes. Here’s a simplified calculation:"),
      ("table",{
        "headers":["Tube Type","Average BTU Loss (Per Foot)"],
        "rows":[
          ["Standard Copper Tube","3 – 5 BTU/hr"],
          ["Insulated Copper Tube","1 – 2 BTU/hr"],
        ],
      }),
      ("p","Using <strong>insulated copper tubes</strong> significantly reduces BTU loss, improving system performance."),
      ("h2","Where to Buy EN 12735 Copper Tubes"),
      ("p","At <strong>Benro Industries</strong>, we supply premium <strong>EN 12735 copper tubes</strong> designed for maximum performance. Check out our twin and single insulated copper tubes to enhance your <strong>HVAC system efficiency</strong>."),
      ("h2","Conclusion"),
      ("p","Choosing the right <strong>EN 12735 copper tube</strong> ensures compliance, durability and efficiency in <strong>HVAC and refrigeration systems</strong>. Whether you’re a contractor, installer or distributor, selecting the correct tubing can enhance performance and system longevity."),
    ],
    "gallery":[],
  },
  # ───────────────────────────────────────────────────────────── 3
  {
    "slug":"enhancing-hvac-efficiency-with-insulated-aluminum-tubes",
    "title":"Enhancing HVAC Efficiency with Insulated Aluminium Tubes",
    "date_iso":"2025-04-03","date_label":"April 3, 2025",
    "category":"Products","lang":"en",
    "cover":"../assets/images/twin-aluminium.png",
    "excerpt":"How twin insulated aluminium tubes deliver thermal efficiency, lighter installs, and corrosion resistance for modern HVAC systems.",
    "body":[
      ("p","Insulated aluminium tubes are essential components in modern HVAC (Heating, Ventilation and Air-Conditioning) systems, offering a combination of durability, flexibility and thermal efficiency. These tubes are engineered to transport refrigerants and air while minimising thermal losses, thereby ensuring optimal system performance."),
      ("h2","Advantages of Insulated Aluminium Tubes"),
      ("ol",[
        "<strong>Thermal Efficiency</strong> — the insulation minimises heat transfer between the internal fluid and the external environment, enhancing system efficiency.",
        "<strong>Lightweight and Flexible</strong> — aluminium’s inherent lightness facilitates easier installation and reduces structural load, making it ideal for various applications.",
        "<strong>Corrosion Resistance</strong> — aluminium naturally forms a protective oxide layer, offering resistance to corrosion and extending the lifespan of the tubes.",
        "<strong>Cost-Effective</strong> — compared to other metals like copper, aluminium is more affordable, providing economic benefits without compromising quality.",
      ]),
      ("h2","Applications in HVAC Systems"),
      ("p","Insulated aluminium tubes are extensively used in:"),
      ("ul",[
        "<strong>Air Ducts</strong> — transporting conditioned air throughout buildings.",
        "<strong>Refrigerant Lines</strong> — carrying refrigerants between system components.",
        "<strong>Ventilation Systems</strong> — ensuring proper air exchange and quality.",
      ]),
      ("h2","Product Spotlight: Benro Industries’ Twin Insulated Aluminium Tubes"),
      ("p","Benro Industries offers high-quality twin insulated aluminium tubes designed for superior performance in HVAC applications. These tubes feature:"),
      ("ul",[
        "<strong>Double Insulation</strong> — enhanced thermal protection to minimise energy losses.",
        "<strong>Durable Construction</strong> — built to withstand various environmental conditions, ensuring longevity.",
        "<strong>Compliance with Standards</strong> — manufactured adhering to international quality standards for reliability.",
      ]),
      ("h2","Explore More Products from Benro Industries"),
      ("p","In addition to insulated aluminium tubes, Benro Industries offers a diverse range of HVAC components to meet various needs:"),
      ("ul",[
        "<strong>Twin Insulated Copper Tubes</strong> — designed for enhanced performance and durability in HVAC systems.",
        "<strong>Single Insulated Copper Tubes</strong> — ideal for applications requiring single-line insulation.",
        "<strong>Insulated Polyethylene Tubes</strong> — providing excellent thermal insulation properties for various applications.",
        "<strong>Polyethylene Tubes</strong> — versatile and durable tubes suitable for multiple industrial uses.",
      ]),
      ("h2","Conclusion"),
      ("p","Integrating insulated aluminium tubes into HVAC systems is a strategic choice for enhancing efficiency, reducing costs and ensuring long-term reliability. Manufacturers like Benro Industries continue to innovate in this field, offering products that meet the evolving demands of modern HVAC applications."),
    ],
    "gallery":[],
  },
  # ───────────────────────────────────────────────────────────── 4
  {
    "slug":"insulated-copper-vs-standard-copper-tubes",
    "title":"Insulated Copper vs. Standard Copper Tubes: Which One is Best for Your HVAC System?",
    "date_iso":"2025-03-19","date_label":"March 19, 2025",
    "category":"Comparison","lang":"en",
    "cover":"../assets/images/insulated-copper-tubes.png",
    "excerpt":"Side-by-side comparison of insulated vs. standard copper tubes — BTU loss tables, sizing tips, and when to pick each one.",
    "body":[
      ("h2","Understanding the Differences Between Insulated and Standard Copper Tubes"),
      ("p","Copper tubes play a crucial role in HVAC systems, ensuring efficient cooling and heating operations. However, when selecting the right type, many HVAC professionals and installers face a common question: <strong>should you choose insulated copper tubes or standard copper tubes?</strong> In this guide we break down the key differences, benefits and ideal applications of both types."),
      ("h2","What Are Standard Copper Tubes?"),
      ("p","Standard copper tubes are widely used in refrigeration and air-conditioning systems. They come in various sizes and types, including <strong>Type K, Type L and Type M</strong>, each with different wall thicknesses. These tubes are known for their durability, corrosion resistance and excellent thermal conductivity."),
      ("h4","Pros of Standard Copper Tubes"),
      ("ul",[
        "High durability and corrosion resistance.",
        "Excellent heat transfer capabilities.",
        "Compatible with various HVAC applications.",
        "Available in different thicknesses for specific needs.",
      ]),
      ("h2","What Are Insulated Copper Tubes?"),
      ("p","Insulated copper tubes are standard copper tubes covered with <strong>polyethylene (PE) insulation</strong>, which helps reduce condensation and improve energy efficiency. These tubes are commonly used in split air conditioners and refrigeration systems."),
      ("h4","Pros of Insulated Copper Tubes"),
      ("ul",[
        "Prevents condensation build-up.",
        "Enhances energy efficiency by reducing heat loss.",
        "Protects against external damage and UV exposure.",
        "Eases installation with pre-applied insulation.",
      ]),
      ("h2","Energy Efficiency: Insulated vs. Standard Copper Tubes"),
      ("p","One of the most significant advantages of <strong>insulated copper tubes</strong> is energy efficiency. <strong>Uninsulated copper tubes</strong> can lead to energy losses due to heat transfer with the surroundings. Insulated tubes help maintain optimal refrigerant temperatures, leading to lower energy consumption."),
      ("h3","BTU Loss Calculation for Standard vs. Insulated Copper Tubes"),
      ("table",{
        "headers":["Copper Tube Type","Heat Loss (BTU/hr per ft)"],
        "rows":[
          ["Standard Copper Tube (Uninsulated)","150 – 200 BTU/hr per ft"],
          ["Insulated Copper Tube (With PE Insulation)","30 – 50 BTU/hr per ft"],
        ],
      }),
      ("p","<em>Using insulated copper tubes can reduce heat loss by up to <strong>75%</strong>, leading to improved system efficiency and reduced energy costs.</em>"),
      ("h3","BTU Calculation for Proper Tube Sizing"),
      ("table",{
        "headers":["Cooling Capacity (BTU/hr)","Recommended Copper Tube Size (Inches)"],
        "rows":[
          ["9,000 – 12,000","1/4 &amp; 3/8"],
          ["18,000 – 24,000","3/8 &amp; 5/8"],
          ["30,000 – 36,000","1/2 &amp; 3/4"],
          ["42,000 – 48,000","5/8 &amp; 7/8"],
        ],
      }),
      ("p","<em>Selecting the right tube size is crucial for optimising system efficiency and preventing pressure drops.</em>"),
      ("h2","Applications of Each Type"),
      ("h4","When to Use Standard Copper Tubes"),
      ("ul",[
        "For high-temperature HVAC applications.",
        "In commercial refrigeration systems where insulation is externally applied.",
        "In plumbing systems requiring rigid and durable tubing.",
      ]),
      ("h4","When to Use Insulated Copper Tubes"),
      ("ul",[
        "In residential and commercial air-conditioning systems.",
        "When reducing condensation and thermal loss is critical.",
        "For outdoor HVAC installations exposed to varying temperatures.",
      ]),
      ("h2","Choosing the Right Tubing for Your HVAC System"),
      ("p","Both <strong>standard and insulated copper tubes</strong> have their own advantages depending on the application. If you prioritise <strong>energy efficiency and ease of installation</strong>, insulated copper tubes are the best choice. However, if you require <strong>more flexibility in insulation application</strong>, standard copper tubes may be the right fit."),
    ],
    "gallery":[],
  },
  # ───────────────────────────────────────────────────────────── 5
  {
    "slug":"the-ultimate-guide-to-insulated-copper-tubes-for-air-conditioners",
    "title":"The Ultimate Guide to Insulated Copper Tubes for Air Conditioners",
    "date_iso":"2025-03-16","date_label":"March 16, 2025",
    "category":"Guide","lang":"en",
    "cover":"../assets/images/insulated-copper-tubes.png",
    "excerpt":"Insulated copper tubes, BTU sizing tables by room area, copper vs aluminium statistics, and how to pick the right tube for your AC.",
    "body":[
      ("h2","Introduction"),
      ("p","In the world of <strong>air conditioning and refrigeration systems</strong>, the quality of components significantly affects system performance. One of the most essential components is the <strong>insulated copper tube</strong>, which helps maintain efficiency, minimise heat loss and extend the lifespan of HVAC systems."),
      ("p","This guide covers everything you need to know about <strong>insulated copper tubes</strong>, including their benefits, applications and industry insights backed by statistics and calculations."),
      ("hr",None),
      ("h2","What Are Insulated Copper Tubes?"),
      ("p","<strong>Insulated copper tubes</strong> are copper pipes covered with <strong>polyethylene (PE) foam insulation</strong>. The insulation layer prevents heat transfer and condensation, making them essential for <strong>air conditioning, refrigeration and HVAC systems</strong>."),
      ("p","For high-quality options, explore our Twin and Single Insulated Copper Tubes."),
      ("h2","Key Benefits of Insulated Copper Tubes"),
      ("h3","1. Improved Energy Efficiency"),
      ("p","Insulated copper tubes reduce heat loss and maintain refrigerant temperature, improving the energy efficiency of HVAC systems. According to the <strong>U.S. Department of Energy</strong>, proper insulation can reduce energy loss by up to <strong>10%</strong>."),
      ("h3","2. Prevention of Condensation"),
      ("p","Temperature differences between the refrigerant and ambient air can cause <strong>condensation</strong>, leading to corrosion and system failures. Insulated copper tubes prevent moisture build-up, ensuring system longevity."),
      ("h3","3. Extended Equipment Lifespan"),
      ("p","By reducing corrosion and maintaining temperature stability, insulated copper tubes <strong>increase the lifespan of HVAC units</strong>, lowering maintenance and replacement costs."),
      ("h3","4. High-Temperature Resistance"),
      ("p","Copper tubes offer superior heat resistance compared to <strong>aluminium</strong> and other materials, making them ideal for extreme climate conditions."),
      ("h2","BTU Calculation for HVAC Sizing"),
      ("p","When selecting the right insulated copper tubes for air conditioners, it’s essential to calculate the <strong>British Thermal Unit (BTU)</strong> capacity. BTU measures <strong>how much heat an air conditioner can remove from a space per hour</strong>."),
      ("p","Below is a <strong>BTU calculation table</strong> based on <strong>room size</strong>:"),
      ("table",{
        "headers":["Room Size (m²)","Recommended BTU Capacity","Suitable Air Conditioner Type"],
        "rows":[
          ["9 – 14 m²","5,000 – 7,000 BTU","Window AC or Small Split Unit"],
          ["15 – 23 m²","8,000 – 10,000 BTU","Standard Split Unit"],
          ["24 – 35 m²","12,000 – 15,000 BTU","Large Split or Small Ducted System"],
          ["36 – 50 m²","18,000 – 24,000 BTU","Central Air or Multi-Split System"],
          ["51 – 70 m²","30,000 – 36,000 BTU","Large Central Air System"],
        ],
      }),
      ("h4","Additional BTU Considerations"),
      ("ul",[
        "Add <strong>+10% BTU</strong> for <strong>kitchens</strong> due to extra heat from appliances.",
        "Increase BTU by <strong>+20%</strong> for rooms with <strong>large windows</strong> or <strong>high sun exposure</strong>.",
        "Consider <strong>ceiling height</strong> — for rooms higher than <strong>3 m</strong>, increase BTU by <strong>15%</strong>.",
      ]),
      ("h2","Industry Statistics: Copper vs. Aluminium"),
      ("p","Many HVAC professionals debate <strong>Copper vs. Aluminium Tubes</strong> for air conditioning. Here’s how they compare:"),
      ("table",{
        "headers":["Feature","Copper Tubes","Aluminium Tubes"],
        "rows":[
          ["Heat Conductivity","<strong>Higher</strong> (401 W/m·K)","Lower (205 W/m·K)"],
          ["Durability","<strong>More durable</strong>","Prone to corrosion"],
          ["Flexibility","Less flexible","<strong>More flexible</strong>"],
          ["Cost","Higher","<strong>Lower</strong>"],
          ["Repairability","<strong>Easy to repair</strong>","Harder to weld"],
        ],
      }),
      ("p","<strong>Conclusion:</strong> copper tubes provide <strong>better heat conductivity, durability and repairability</strong>, making them the superior choice for HVAC systems. However, <strong>aluminium tubes</strong> are an affordable alternative for budget-conscious projects."),
      ("h2","Why Choose Benro Industries’ Insulated Copper Tubes?"),
      ("p","At <strong>Benro Industries</strong>, we manufacture <strong>high-quality insulated copper tubes</strong> that meet <strong>EN 12735-1</strong> for refrigeration and air conditioning, and <strong>ASTM Standards</strong>, ensuring global quality compliance. We also offer <strong>Insulated Polyethylene Tubes</strong> for additional thermal insulation solutions."),
      ("h2","Final Thoughts"),
      ("p","Choosing the right insulated copper tubes can <strong>maximise energy efficiency, reduce operational costs and extend system lifespan</strong>. Whether you’re an <strong>HVAC installer, distributor or manufacturer</strong>, Benro Industries provides the best solutions tailored to your needs."),
    ],
    "gallery":[],
  },
  # ───────────────────────────────────────────────────────────── 6
  {
    "slug":"insulated-copper-tube-the-ultimate-solution",
    "title":"Insulated Copper Tube: The Ultimate Solution for Efficient HVAC Systems",
    "date_iso":"2025-03-12","date_label":"March 12, 2025",
    "category":"Guide","lang":"en",
    "cover":"../assets/images/blog/cover-blog-2025-03-12.png",
    "excerpt":"Why insulated copper tubes are the backbone of modern HVAC systems — and how to pick the right one against EN12735 / ASTM.",
    "body":[
      ("h2","Why Choose Insulated Copper Tubes for HVAC Applications?"),
      ("p","<strong>Insulated copper tubes</strong> are the backbone of modern <strong>HVAC systems</strong>, ensuring <strong>efficient heat transfer, reduced energy loss and enhanced durability</strong>. These tubes come with a protective layer that minimises condensation, prevents corrosion and improves overall system efficiency."),
      ("h2","Key Benefits of Insulated Copper Tubes"),
      ("h3","1. Superior Thermal Efficiency"),
      ("p","Copper is one of the best conductors of heat, making it the preferred material for <strong>air conditioning and refrigeration</strong>. When combined with high-quality <strong>polyethylene (PE) insulation</strong>, these tubes offer maximum thermal efficiency."),
      ("h3","2. Prevents Condensation and Corrosion"),
      ("p","Uninsulated copper tubes are prone to <strong>moisture build-up</strong>, leading to corrosion and inefficiency. The insulation layer acts as a <strong>barrier against humidity</strong>, preventing water droplets from forming on the surface."),
      ("h3","3. Increases Energy Savings"),
      ("p","By reducing <strong>heat loss and energy consumption</strong>, insulated copper tubes help lower electricity bills. This makes them ideal for <strong>industrial, commercial and residential HVAC systems</strong>."),
      ("h3","4. Longer Lifespan and Durability"),
      ("p","Copper itself is naturally resistant to <strong>oxidation and degradation</strong>. With added insulation, the tubes are <strong>protected from external damage</strong>, extending their service life significantly."),
      ("h2","Applications of Insulated Copper Tubes"),
      ("h3","1. Air-Conditioning Systems"),
      ("p","Used for <strong>refrigerant transportation</strong>, insulated copper tubes maintain <strong>stable temperature flow</strong> without loss of efficiency."),
      ("h3","2. Refrigeration Units"),
      ("p","Commercial refrigerators and freezers rely on these tubes to ensure proper <strong>cooling performance and energy efficiency</strong>."),
      ("h3","3. Heating and Cooling Networks"),
      ("p","In large-scale buildings, <strong>HVAC distribution systems</strong> utilise insulated copper tubing to maintain <strong>consistent temperature regulation</strong>."),
      ("h3","4. Industrial and Medical Applications"),
      ("p","Industries and medical facilities use <strong>insulated copper pipes</strong> for <strong>gas distribution and heat exchange processes</strong>."),
      ("h2","Copper vs. Aluminium Tubing: Which One is Better?"),
      ("ul",[
        "<strong>Higher Heat Conductivity</strong> — copper transfers heat <strong>better than aluminium</strong>, ensuring improved efficiency.",
        "<strong>Easier to Repair</strong> — unlike aluminium, which is harder to weld, <strong>copper tubing can be easily repaired and soldered</strong>.",
        "<strong>More Durable</strong> — copper tubes last <strong>longer</strong> and withstand higher pressures without cracking.",
      ]),
      ("h2","Standards and Quality Assurance: EN12735 vs. ASTM"),
      ("ul",[
        "<strong>EN 12735 (European Standard)</strong> — designed specifically for <strong>refrigeration and air-conditioning applications</strong>, ensuring strength and corrosion resistance.",
        "<strong>ASTM (American Standard)</strong> — covers a wider range of materials, often used in <strong>North America</strong> for various piping systems.",
      ]),
      ("h2","How to Choose the Right Insulated Copper Tube?"),
      ("ol",[
        "<strong>Check the Insulation Material</strong> — ensure it offers <strong>thermal resistance</strong> and prevents condensation.",
        "<strong>Confirm Compliance with HVAC Standards</strong> — always choose <strong>EN12735- or ASTM-certified tubes</strong>.",
        "<strong>Consider the Tube Size and Thickness</strong> — select based on <strong>your system’s pressure and refrigerant type</strong>.",
        "<strong>Look for Reliable Manufacturers</strong> — opt for trusted brands that offer <strong>high-quality and durable products</strong>.",
      ]),
      ("h2","Conclusion"),
      ("p","Investing in <strong>insulated copper tubes</strong> ensures <strong>maximum efficiency, energy savings and long-term reliability</strong> in HVAC systems. Whether for <strong>residential, commercial or industrial use</strong>, these tubes provide <strong>superior performance and durability</strong>."),
    ],
    "gallery":[],
  },
  # ───────────────────────────────────────────────────────────── 7
  {
    "slug":"insulated-aluminium-tubes-lightweight-hvac-solutions-for-north-africa",
    "title":"Insulated Aluminium Tubes: Lightweight HVAC Solutions for North Africa",
    "date_iso":"2025-02-25","date_label":"February 25, 2025",
    "category":"Regional","lang":"en",
    "cover":"../assets/images/blog/cover-blog-2025-02-25-alu.jpg",
    "excerpt":"Why insulated aluminium tubes are the right answer for Algeria, Tunisia and Libya — sizing tables, certifications and installation tips.",
    "body":[
      ("h2","What Are Insulated Aluminium Tubes?"),
      ("p","Insulated aluminium tubes are lightweight, corrosion-resistant pipes used in HVAC and refrigeration systems. They consist of seamless aluminium tubing wrapped in polyethylene (PE) foam or rubber insulation to prevent heat transfer and condensation."),
      ("h4","Why Aluminium?"),
      ("ul",[
        "<strong>Lightweight</strong> — 60% lighter than copper, reducing installation labour and costs.",
        "<strong>Cost-Effective</strong> — 30–50% cheaper than copper tubes.",
        "<strong>Corrosion Resistance</strong> — natural oxide layer protects against humidity and salt (ideal for coastal Libya).",
      ]),
      ("h4","Key Components"),
      ("ol",[
        "<strong>Aluminium Core</strong> — 1070 or 6063 alloy (ASTM B209 / EN 573).",
        "<strong>Insulation Layer</strong> — PE foam (thermal conductivity: <strong>0.0402 W/m·K</strong>) or rubber.",
        "<strong>UV-Resistant Jacket</strong> — protects against North Africa’s harsh sunlight.",
      ]),
      ("h2","Technical Specifications &amp; Standards"),
      ("h3","EN 12735-1 vs. ASTM B209: Which Standard to Follow?"),
      ("table",{
        "headers":["Feature","EN 12735-1 (EU)","ASTM B209 (USA)"],
        "rows":[
          ["Material","Aluminium 1070","Aluminium 6063"],
          ["Wall Thickness","±10% tolerance","±5% tolerance"],
          ["Testing","Tensile + elongation","Eddy current + pressure"],
          ["Best For","Industrial HVAC","Residential AC"],
        ],
      }),
      ("p","<strong>Why EN 12735-1?</strong> Benro Industries’ aluminium tubes meet EN 12735-1 standards, ensuring durability in Algeria’s desert heat and Tunisia’s humid climates."),
      ("h2","Applications of Insulated Aluminium Tubes"),
      ("h3","1. Residential Air Conditioning"),
      ("ul",[
        "<strong>Split AC Systems</strong> — pre-insulated tubes for connecting indoor/outdoor units.",
        "<strong>Heat Pumps</strong> — lightweight design simplifies rooftop installations.",
      ]),
      ("h3","2. Industrial &amp; Commercial Projects"),
      ("ul",[
        "<strong>Cold Storage</strong> — insulated tubes for <strong>غرف تبريد</strong> (cold rooms) in food processing.",
        "<strong>Solar HVAC</strong> — compatible with renewable-energy systems.",
      ]),
      ("h3","3. Automotive &amp; Aerospace"),
      ("ul",[
        "<strong>Cooling Lines</strong> — lightweight tubes for electric-vehicle battery cooling.",
      ]),
      ("h2","5 Benefits of Insulated Aluminium Tubes"),
      ("ol",[
        "<strong>Energy Efficiency</strong> — PE foam reduces heat gain by 40% (ASHRAE Study).",
        "<strong>Easy Installation</strong> — flexible coils cut labour time by 30%.",
        "<strong>Eco-Friendly</strong> — recyclable materials align with Algeria’s sustainability goals.",
        "<strong>Low Maintenance</strong> — resists corrosion and UV damage.",
        "<strong>Cost Savings</strong> — affordable alternative to copper without sacrificing performance.",
      ]),
      ("h2","How to Choose the Right Insulated Aluminium Tube"),
      ("h3","Step 1: Determine Tube Size"),
      ("table",{
        "headers":["AC Capacity (BTU)","Liquid Line (mm)","Suction Line (mm)"],
        "rows":[
          ["9,000–18,000","6.35","9.52"],
          ["24,000–48,000","9.52","12.7"],
        ],
      }),
      ("h3","Step 2: Select Insulation Type"),
      ("ul",[
        "<strong>PE Foam</strong> — ideal for indoor HVAC (R-value: 3.3).",
        "<strong>Rubber</strong> — better flexibility for tight spaces.",
      ]),
      ("h3","Step 3: Verify Certifications"),
      ("ul",[
        "Look for <strong>EN 12735-1</strong> or <strong>ASTM B209</strong> compliance.",
        "Ensure fire ratings (e.g. ASTM E84 Class 1).",
      ]),
      ("h2","Installation Best Practices"),
      ("ol",[
        "<strong>Avoid Bends</strong> — use tube benders to prevent kinks.",
        "<strong>Seal Joints</strong> — apply UV-resistant tape at connections.",
        "<strong>Test for Leaks</strong> — pressure-test with nitrogen before charging refrigerant.",
      ]),
      ("note","Pro Tip: Benro’s pre-insulated tubes come with pre-attached flare nuts (<strong>قطع غيار تكييف</strong>) for faster installation."),
      ("h2","FAQs"),
      ("h4","Q: How does aluminium compare to copper?"),
      ("p","A: Aluminium is lighter and cheaper but less durable under high pressure. Ideal for residential HVAC."),
      ("h4","Q: Can I use aluminium tubes in desert climates?"),
      ("p","A: Yes! Our PE foam insulation withstands temperatures up to 90 °C."),
      ("h4","Q: Where can I buy aluminium insulation tubes in Algeria?"),
      ("p","A: Benro Industries supplies <strong>صناعة جزائرية</strong> tubes nationwide."),
      ("h2","Why Choose Benro Industries?"),
      ("ul",[
        "<strong>Local Manufacturing</strong> — proudly made in Algeria, supporting local industries.",
        "<strong>Quality Assurance</strong> — rigorous ISO 9001-compliant checks.",
        "<strong>Custom Solutions</strong> — tubes tailored for <strong>تكييف صحراوي</strong> (desert AC).",
      ]),
    ],
    "gallery":[],
  },
  # ───────────────────────────────────────────────────────────── 8
  {
    "slug":"insulated-copper-tubes-the-ultimate-guide",
    "title":"Insulated Copper Tubes: The Ultimate Guide for HVAC Efficiency &amp; Durability",
    "date_iso":"2025-02-25","date_label":"February 25, 2025",
    "category":"Guide","lang":"en",
    "cover":"../assets/images/blog/cover-blog-2025-02-25-cu.png",
    "excerpt":"Composition, certifications, applications, sizing, installation best practices, and a desert case study — all about insulated copper tubes.",
    "body":[
      ("h2","What Are Insulated Copper Tubes?"),
      ("p","Insulated copper tubes are the backbone of modern HVAC and refrigeration systems. They consist of a seamless copper pipe wrapped in high-performance insulation (like polyethylene foam) to minimise heat transfer, prevent condensation and enhance energy efficiency."),
      ("h3","Why Copper?"),
      ("ul",[
        "<strong>Superior Thermal Conductivity</strong> — copper transfers heat 20× faster than aluminium.",
        "<strong>Corrosion Resistance</strong> — ideal for harsh climates like North Africa’s desert regions.",
        "<strong>Durability</strong> — withstands extreme temperatures and pressures.",
      ]),
      ("h3","Key Components"),
      ("ol",[
        "<strong>Copper Core</strong> — high-purity C12200 copper (99.9% Cu) compliant with EN 12735-1.",
        "<strong>Insulation Layer</strong> — PE foam (thermal conductivity: <strong>0.0402 W/m·K</strong>) or rubber.",
        "<strong>Protective Jacket</strong> — UV-resistant, chemical-proof outer layer.",
      ]),
      ("h2","Technical Specifications &amp; Standards"),
      ("h3","EN 12735-1 vs. ASTM B280: Which Standard Matters?"),
      ("table",{
        "headers":["Feature","EN 12735-1 (EU)","ASTM B280 (USA)"],
        "rows":[
          ["Material","Phosphorus-deoxidised Cu","Seamless copper"],
          ["Wall Thickness","Tighter tolerances","Slightly relaxed"],
          ["Testing","Hydrostatic + elongation","Eddy current + pressure"],
          ["Best For","Desert climates","General HVAC"],
        ],
      }),
      ("p","<strong>Why EN 12735-1?</strong> Benro Industries’ insulated copper tubes meet EN 12735-1 standards, ensuring reliability in Algeria’s extreme heat and Libya’s coastal humidity."),
      ("h2","Applications of Insulated Copper Tubes"),
      ("h3","1. Residential Air Conditioning"),
      ("ul",[
        "<strong>Split AC Systems</strong> — pre-insulated tubes connect indoor/outdoor units.",
        "<strong>Central HVAC</strong> — minimise energy loss in ductwork.",
      ]),
      ("h3","2. Commercial &amp; Industrial Projects"),
      ("ul",[
        "<strong>Hospitals</strong> — maintain sterile environments with leak-proof connections.",
        "<strong>Cold Storage</strong> — insulated tubes for refrigeration (e.g. <strong>غرف تبريد</strong>).",
      ]),
      ("h3","3. Renewable Energy"),
      ("ul",["<strong>Heat Pumps</strong> — efficient heat transfer in geothermal systems."]),
      ("h2","5 Benefits of Insulated Copper Tubes"),
      ("ol",[
        "<strong>Energy Savings</strong> — reduce cooling costs by up to 30% (ASHRAE Study).",
        "<strong>Condensation Control</strong> — PE foam prevents moisture build-up.",
        "<strong>Longevity</strong> — resists UV, chemicals and abrasion.",
        "<strong>Easy Installation</strong> — pre-insulated coils cut labour time by 50%.",
        "<strong>Eco-Friendly</strong> — recyclable materials align with Algeria’s sustainability goals.",
      ]),
      ("h2","How to Choose the Right Insulated Copper Tube"),
      ("h3","Step 1: Determine Tube Size"),
      ("table",{
        "headers":["AC Capacity (BTU)","Liquid Line (in)","Suction Line (in)"],
        "rows":[
          ["9,000–18,000","1/4″","3/8″"],
          ["24,000–48,000","3/8″","5/8″"],
        ],
      }),
      ("h3","Step 2: Select Insulation Thickness"),
      ("ul",[
        "<strong>PE Foam</strong> — 9 mm (standard) to 25 mm (extreme climates).",
        "<strong>Rubber</strong> — better flexibility for tight spaces.",
      ]),
      ("h3","Step 3: Verify Certifications"),
      ("ul",[
        "Look for EN 12735-1 or ASTM B280 compliance.",
        "Ensure fire ratings (e.g. ASTM E84 Class 1).",
      ]),
      ("h2","Installation Best Practices"),
      ("ol",[
        "<strong>Avoid Kinks</strong> — use tube benders for smooth curves.",
        "<strong>Seal Joints</strong> — apply UV-resistant tape at connections.",
        "<strong>Test for Leaks</strong> — pressure-test with nitrogen before refrigerant charging.",
      ]),
      ("note","Pro Tip: Benro’s pre-insulated tubes come with pre-attached flare nuts (<strong>قطع غيار تكييف</strong>) for faster installation."),
      ("h2","Case Study: Desert Air Conditioning in Algeria"),
      ("p","<strong>Challenge:</strong> a hotel in Ghardaïa faced frequent AC failures due to sandstorms and 50 °C heat."),
      ("p","<strong>Solution:</strong> Benro’s EN 12735-1 insulated copper tubes with 9 mm PE foam."),
      ("h4","Results"),
      ("ul",[
        "40% reduction in energy bills.",
        "Zero leaks over 3 years.",
      ]),
      ("h2","FAQs"),
      ("h4","Q: Can I use aluminium tubes instead?"),
      ("p","A: Aluminium is cheaper but less durable. Copper is preferred for high-pressure systems."),
      ("h4","Q: How long does PE foam insulation last?"),
      ("p","A: 20+ years with proper maintenance."),
      ("h4","Q: Where can I buy certified insulated copper tubes in Algeria?"),
      ("p","A: Benro Industries supplies <strong>صناعة جزائرية</strong> tubes nationwide."),
    ],
    "gallery":[],
  },
  # ───────────────────────────────────────────────────────────── 9
  {
    "slug":"the-role-of-aluminum-tubes-in-modern-hvac-systems",
    "title":"The Role of Aluminium Tubes in Modern HVAC Systems",
    "date_iso":"2025-01-30","date_label":"January 30, 2025",
    "category":"Products","lang":"en",
    "cover":"../assets/images/blog/cover-blog-2025-01-30-alu.jpg",
    "excerpt":"How BENRO INDUSTRIES’ 1070-series aluminium tubes — pre-insulated with PE foam — are reshaping modern HVAC installations.",
    "body":[
      ("h2","Introduction"),
      ("p","In the ever-evolving HVAC industry, the choice of materials plays a critical role in system performance and efficiency. While copper has traditionally been the go-to material for HVAC tubes, aluminium is gaining popularity due to its unique properties and cost-effectiveness. At BENRO INDUSTRIES, we offer high-quality aluminium tubes designed to meet the demands of modern HVAC systems. In this blog we explore the role of aluminium tubes in HVAC systems and why they’re an excellent alternative to copper."),
      ("h2","Why Aluminium Tubes?"),
      ("p","Aluminium tubes offer several advantages that make them suitable for HVAC applications:"),
      ("ul",[
        "<strong>Lightweight and Easy to Handle</strong> — aluminium is significantly lighter than copper, making it easier to transport and install.",
        "<strong>Cost-Effective</strong> — aluminium is more affordable than copper, reducing overall system costs.",
        "<strong>Corrosion Resistance</strong> — aluminium naturally forms a protective oxide layer, making it resistant to corrosion.",
      ]),
      ("h2","BENRO INDUSTRIES’ Aluminium Tubes"),
      ("p","Our aluminium tubes are manufactured to the highest standards, ensuring superior performance and durability. Key features include:"),
      ("ul",[
        "<strong>High-Quality Material</strong> — made from 1070-series aluminium, our tubes offer excellent strength and flexibility.",
        "<strong>PE Insulation</strong> — our aluminium tubes are insulated with high-performance PE foam, providing thermal efficiency and protection against external factors.",
        "<strong>Compatibility</strong> — suitable for a wide range of HVAC systems, including split air conditioners and central cooling units.",
      ]),
      ("h2","Applications in Modern HVAC Systems"),
      ("p","Aluminium tubes are ideal for various HVAC applications, such as:"),
      ("ul",[
        "Connecting indoor and outdoor units in split air conditioners.",
        "Refrigerant lines in commercial and industrial cooling systems.",
        "Heat exchangers and condensers.",
      ]),
      ("h2","Why Choose BENRO INDUSTRIES?"),
      ("p","At BENRO INDUSTRIES, we are committed to providing innovative and reliable HVAC solutions. Our aluminium tubes are designed to:"),
      ("ul",[
        "Deliver optimal performance and energy efficiency.",
        "Reduce installation time and labour costs.",
        "Offer a durable and cost-effective alternative to copper tubes.",
      ]),
      ("h2","Conclusion"),
      ("p","Aluminium tubes are revolutionising the HVAC industry with their lightweight design, cost-effectiveness and excellent performance. BENRO INDUSTRIES’ aluminium tubes, combined with high-quality PE insulation, provide a reliable and efficient solution for modern HVAC systems."),
    ],
    "gallery":[],
  },
  # ──────────────────────────────────────────────────────────── 10
  {
    "slug":"how-benro-industries-pe-foam-insulation-enhances-hvac-efficiency",
    "title":"How BENRO INDUSTRIES’ PE Foam Insulation Enhances HVAC Efficiency",
    "date_iso":"2025-01-30","date_label":"January 30, 2025",
    "category":"Products","lang":"en",
    "cover":"../assets/images/blog/cover-blog-2025-01-30-pe.jpg",
    "excerpt":"Closed-cell PE foam, low thermal conductivity, moisture resistance — how BENRO insulation pushes HVAC efficiency higher.",
    "body":[
      ("h2","Introduction"),
      ("p","In the HVAC industry, energy efficiency is a top priority for both homeowners and businesses. One of the most effective ways to improve the efficiency of HVAC systems is through high-quality insulation. At BENRO INDUSTRIES we specialise in advanced polyethylene (PE) foam insulation, designed to maximise energy savings and system performance. In this blog we explore how our PE foam insulation enhances HVAC efficiency and why it’s the ideal choice for your cooling and refrigeration needs."),
      ("h2","What is PE Foam Insulation?"),
      ("p","Polyethylene (PE) foam is a lightweight, flexible and durable material widely used in HVAC systems for its excellent thermal insulation properties. BENRO INDUSTRIES’ PE foam insulation is manufactured using cutting-edge extrusion technology, ensuring superior performance and durability."),
      ("h2","Key Benefits of PE Foam Insulation"),
      ("ul",[
        "<strong>Superior Thermal Insulation</strong> — with a thermal conductivity of 0.0402 W/m·K, our PE foam minimises heat transfer, ensuring optimal cooling efficiency.",
        "<strong>Moisture and Water Resistance</strong> — the closed-cell structure of PE foam prevents water absorption, reducing the risk of corrosion and mould growth.",
        "<strong>UV and Chemical Resistance</strong> — our insulation is resistant to UV rays and chemicals, making it suitable for both indoor and outdoor applications.",
        "<strong>Eco-Friendly and Recyclable</strong> — we are committed to sustainability, using recyclable materials that minimise environmental impact.",
      ]),
      ("h2","Applications in HVAC Systems"),
      ("p","BENRO INDUSTRIES’ PE foam insulation is versatile and can be used in various HVAC applications, including:"),
      ("ul",[
        "Insulating refrigerant lines in split air conditioners.",
        "Protecting copper and aluminium tubes in central air-conditioning systems.",
        "Enhancing the efficiency of cold-room installations.",
      ]),
      ("h2","Why Choose BENRO INDUSTRIES?"),
      ("p","At BENRO INDUSTRIES we pride ourselves on delivering high-quality products that meet the highest industry standards. Our PE foam insulation is designed to:"),
      ("ul",[
        "Reduce energy consumption and lower utility bills.",
        "Extend the lifespan of HVAC systems by preventing wear and tear.",
        "Provide a cost-effective and eco-friendly solution for insulation needs.",
      ]),
      ("h2","Conclusion"),
      ("p","BENRO INDUSTRIES’ PE foam insulation is a game-changer for HVAC efficiency, offering superior thermal performance, durability and environmental benefits. Whether you’re installing a new system or upgrading an existing one, our insulation solutions ensure optimal performance and energy savings."),
    ],
    "gallery":[],
  },
  # ──────────────────────────────────────────────────────────── 11 — FR
  {
    "slug":"benro-industries-votre-partenaire-pour-des-solutions-hvac-durables",
    "title":"BENRO INDUSTRIES : Votre Partenaire pour des Solutions HVAC Durables et Écoénergétiques",
    "date_iso":"2025-01-30","date_label":"30 janvier 2025",
    "category":"Entreprise","lang":"fr",
    "cover":"../assets/images/blog/cover-blog-2025-01-30-alu.jpg",
    "excerpt":"Pourquoi BENRO INDUSTRIES est le partenaire de référence pour des solutions HVAC durables et écoénergétiques en Algérie.",
    "body":[
      ("h2","Introduction"),
      ("p","Dans un monde où l’efficacité énergétique et la durabilité sont devenues des priorités, choisir les bons produits pour vos systèmes de climatisation est essentiel. BENRO INDUSTRIES, leader dans la fabrication de solutions HVAC en Algérie, s’engage à fournir des produits de haute qualité, respectueux de l’environnement et adaptés aux besoins locaux. Découvrez pourquoi nous sommes le partenaire idéal pour vos projets de climatisation."),
      ("h2","Notre Engagement envers la Qualité et la Durabilité"),
      ("p","Chez BENRO INDUSTRIES, nous mettons un point d’honneur à respecter les normes de qualité les plus strictes. Nos produits, fabriqués selon la norme européenne EN 12735-1, offrent :"),
      ("ul",[
        "<strong>Précision de Fabrication</strong> — chaque produit est conçu avec une précision millimétrique pour garantir des performances optimales.",
        "<strong>Contrôle Qualité Rigoureux</strong> — nous mettons en place des contrôles qualité à chaque étape de la production pour assurer la fiabilité de nos produits.",
        "<strong>Durabilité Accrue</strong> — nos tubes en cuivre et en aluminium sont conçus pour résister aux conditions climatiques extrêmes d’Afrique du Nord.",
      ]),
      ("h2","Des Solutions Écoénergétiques pour un Avenir Durable"),
      ("p","Nos produits sont conçus pour maximiser l’efficacité énergétique et réduire l’impact environnemental. Par exemple :"),
      ("ul",[
        "<strong>Isolation en Polyéthylène (PE)</strong> — notre isolation PE offre une conductivité thermique de 0,0402 W/m·K, réduisant les pertes d’énergie et améliorant l’efficacité du système.",
        "<strong>Matériaux Recyclables</strong> — nous utilisons des matériaux recyclables pour minimiser notre impact sur l’environnement.",
      ]),
      ("h2","Une Couverture Nationale et un Soutien Logistique Complet"),
      ("p","BENRO INDUSTRIES propose une couverture nationale, garantissant la disponibilité de nos produits partout en Algérie. Notre réseau logistique robuste assure une livraison rapide et fiable, même pour les projets les plus urgents."),
      ("h2","Notre Vision pour l’Avenir"),
      ("p","Notre objectif est de devenir le leader des solutions HVAC en Algérie d’ici 2025 et de nous étendre aux marchés internationaux d’ici 2026. Nous continuons à innover et à investir dans des technologies durables pour répondre aux besoins de nos clients."),
      ("h2","Conclusion"),
      ("p","BENRO INDUSTRIES est votre partenaire de confiance pour des solutions HVAC durables, écoénergétiques et de haute qualité. Avec des produits fabriqués en Algérie selon les normes européennes les plus strictes, nous nous engageons à répondre à vos besoins tout en réduisant votre impact environnemental."),
    ],
    "gallery":[],
  },
  # ──────────────────────────────────────────────────────────── 12 — FR
  {
    "slug":"les-avantages-des-tubes-en-cuivre-isoles-benro-industries",
    "title":"Les Avantages des Tubes en Cuivre Isolés BENRO INDUSTRIES pour la Climatisation",
    "date_iso":"2025-01-30","date_label":"30 janvier 2025",
    "category":"Produits","lang":"fr",
    "cover":"../assets/images/blog/cover-blog-2025-01-30-cu-isole.png",
    "excerpt":"Tubes en cuivre isolés EN 12735-1 — conductivité, résistance UV et installation facile pour vos kits de climatisation.",
    "body":[
      ("h2","Introduction"),
      ("p","Dans le domaine de la climatisation, la qualité des composants utilisés joue un rôle crucial dans la performance et la durabilité du système. Les tubes en cuivre isolés sont l’un des éléments les plus importants, assurant une circulation efficace du réfrigérant et une isolation thermique optimale. Chez BENRO INDUSTRIES, nous proposons des tubes en cuivre isolés de haute qualité, fabriqués selon les normes européennes EN 12735-1."),
      ("h2","Pourquoi Choisir les Tubes en Cuivre Isolés ?"),
      ("p","Les tubes en cuivre sont largement utilisés dans les systèmes de climatisation en raison de leurs propriétés uniques :"),
      ("ul",[
        "<strong>Conductivité Thermique Exceptionnelle</strong> — le cuivre transfère la chaleur plus efficacement que d’autres matériaux, ce qui améliore l’efficacité du système.",
        "<strong>Résistance à la Corrosion</strong> — contrairement à l’aluminium, le cuivre résiste à la corrosion, garantissant une longue durée de vie.",
        "<strong>Flexibilité</strong> — les tubes en cuivre sont faciles à installer et à façonner selon les besoins du système.",
      ]),
      ("h2","Les Avantages des Tubes en Cuivre Isolés BENRO INDUSTRIES"),
      ("p","Nos tubes en cuivre isolés sont conçus pour offrir des performances supérieures et une durabilité accrue. Voici ce qui les distingue :"),
      ("ul",[
        "<strong>Normes Européennes Strictes</strong> — nos tubes sont fabriqués selon la norme EN 12735-1.",
        "<strong>Isolation en Polyéthylène (PE)</strong> — conductivité thermique de 0,0402 W/m·K, réduisant les pertes d’énergie.",
        "<strong>Résistance aux UV et aux Agents Chimiques</strong> — l’isolation protège les tubes même dans des conditions extrêmes.",
      ]),
      ("h2","Applications et Compatibilité"),
      ("p","Nos tubes en cuivre isolés sont compatibles avec une large gamme de systèmes de climatisation :"),
      ("ul",[
        "Climatiseurs split (9 000 BTU à 48 000 BTU).",
        "Systèmes de climatisation centrale.",
        "Unités de réfrigération commerciale et industrielle.",
      ]),
      ("h2","Pourquoi Choisir BENRO INDUSTRIES ?"),
      ("ul",[
        "Une performance fiable dans les climats chauds d’Afrique du Nord.",
        "Une installation facile et rapide.",
        "Une garantie de qualité pour votre tranquillité d’esprit.",
      ]),
      ("h2","Conclusion"),
      ("p","Les tubes en cuivre isolés BENRO INDUSTRIES sont la solution idéale pour améliorer l’efficacité et la durabilité de vos systèmes de climatisation. Avec des normes de qualité strictes et une isolation performante, nos produits garantissent des économies d’énergie et une longue durée de vie."),
    ],
    "gallery":[],
  },
  # ──────────────────────────────────────────────────────────── 13 — FR
  {
    "slug":"les-avantages-des-tubes-en-cuivre-europeen-pour-la-climatisation-centrale",
    "title":"Les Avantages des Tubes en Cuivre Européen pour la Climatisation Centrale",
    "date_iso":"2025-01-30","date_label":"30 janvier 2025",
    "category":"Produits","lang":"fr",
    "cover":"../assets/images/blog/cover-blog-2025-01-30-cu-eu.jpg",
    "excerpt":"Les tubes en cuivre européens EN 12735-1 : pourquoi ils restent le choix de référence pour la climatisation centrale.",
    "body":[
      ("h2","Introduction"),
      ("p","Les tubes en cuivre jouent un rôle crucial dans les systèmes de climatisation centrale, assurant une circulation efficace du réfrigérant et une performance optimale. Parmi les options disponibles, les tubes en cuivre européen se distinguent par leur qualité supérieure et leur durabilité."),
      ("h2","Pourquoi le Cuivre est-il Idéal pour la Climatisation ?"),
      ("ul",[
        "<strong>Conductivité Thermique Exceptionnelle</strong> — le cuivre transfère la chaleur plus efficacement que d’autres matériaux.",
        "<strong>Résistance à la Corrosion</strong> — contrairement à l’aluminium, le cuivre résiste à la corrosion.",
        "<strong>Flexibilité</strong> — les tubes en cuivre sont faciles à installer et à façonner.",
      ]),
      ("h2","Les Avantages des Tubes en Cuivre Européen EN 12735-1"),
      ("ul",[
        "<strong>Normes de Fabrication Strictes</strong> — les tubes européens respectent des normes de qualité élevées.",
        "<strong>Compatibilité avec les Réfrigérants Modernes</strong> — conçus pour les réfrigérants respectueux de l’environnement.",
        "<strong>Durabilité Accrue</strong> — moins d’entretien et coûts réduits à long terme.",
      ]),
      ("h2","Comparaison avec les Tubes en Aluminium"),
      ("ul",[
        "Moins résistant à la corrosion.",
        "Conductivité thermique inférieure.",
        "Durée de vie plus courte.",
      ]),
      ("p","En optant pour des tubes en cuivre européen, vous investissez dans un produit durable et performant qui réduit les risques de panne et les coûts de maintenance."),
      ("h2","Les Solutions BENRO Industries"),
      ("ul",[
        "Une performance optimale dans les climats chauds d’Afrique du Nord.",
        "Une compatibilité avec tous les types de réfrigérants.",
        "Une garantie de qualité pour une tranquillité d’esprit totale.",
      ]),
      ("h2","Conclusion"),
      ("p","Les tubes en cuivre européen sont un investissement intelligent pour tout système de climatisation centrale. Leur durabilité, leur efficacité et leur compatibilité avec les réfrigérants modernes en font le choix idéal pour les professionnels et les particuliers."),
    ],
    "gallery":[],
  },
  # ──────────────────────────────────────────────────────────── 14 — FR
  {
    "slug":"comment-choisir-le-meilleur-kit-de-climatisation",
    "title":"Comment Choisir le Meilleur Kit de Climatisation pour Votre Maison en Algérie",
    "date_iso":"2025-01-28","date_label":"28 janvier 2025",
    "category":"Guide","lang":"fr",
    "cover":"../assets/images/blog/cover-blog-2025-01-28-kit.png",
    "excerpt":"Guide complet pour choisir le kit de climatisation adapté à votre maison : BTU, SEER, types de tubes, et conseils BENRO.",
    "body":[
      ("h2","Introduction"),
      ("p","Avec les étés chauds en Algérie, avoir un système de climatisation efficace est essentiel pour rester au frais et confortable chez soi. Cependant, choisir le bon kit de climatisation peut être un défi. Dans ce guide, nous vous aidons à comprendre les critères importants pour choisir le meilleur kit de climatisation pour votre maison."),
      ("h2","Comprendre Vos Besoins en Climatisation"),
      ("p","Avant d’acheter un kit de climatisation, posez-vous ces questions :"),
      ("ul",[
        "Quelle est la taille de la pièce à climatiser ?",
        "Quel est votre budget pour l’achat et l’installation ?",
        "Recherchez-vous un système économe en énergie ?",
      ]),
      ("p","Par exemple, pour une petite chambre, un climatiseur split de 9 000 BTU pourrait suffire, tandis qu’un salon spacieux nécessitera un système de 18 000 BTU ou plus."),
      ("h3","Les Types de Kits de Climatisation"),
      ("ul",[
        "<strong>Single Insulated Tubes</strong> — idéals pour les pièces individuelles, efficaces pour les travaux VRV.",
        "<strong>Twin Insulated Tubes</strong> — faciles à installer et économiques.",
      ]),
      ("p","Chez BENRO Industries, nous proposons une gamme de kits de climatisation adaptés à tous les besoins, garantissant une performance optimale même pendant les étés les plus chauds."),
      ("h2","Les Critères à Considérer"),
      ("ul",[
        "<strong>Capacité de Refroidissement (BTU)</strong> — assurez-vous que le système est adapté à la taille de votre pièce.",
        "<strong>Efficacité Énergétique (SEER)</strong> — optez pour un haut rendement énergétique pour réduire vos factures d’électricité.",
        "<strong>Qualité des Composants</strong> — privilégiez les kits fabriqués avec des matériaux durables, comme les tubes en cuivre européen.",
      ]),
      ("h2","Pourquoi Choisir BENRO Industries ?"),
      ("ul",[
        "Une performance fiable même dans les climats extrêmes.",
        "Une installation facile et rapide.",
        "Une garantie prolongée pour votre tranquillité d’esprit.",
      ]),
      ("h2","Conclusion"),
      ("p","Choisir le bon kit de climatisation pour votre maison en Algérie est une décision importante qui influence votre confort et vos économies d’énergie. Avec les solutions de qualité proposées par BENRO Industries, vous pouvez être sûr de faire le meilleur choix pour votre famille."),
    ],
    "gallery":[],
  },
  # ──────────────────────────────────────────────────────────── 15
  {
    "slug":"recap-of-benro-industries-at-sivecc-2024",
    "title":"Recap of BENRO INDUSTRIES at SIVECC 2024",
    "date_iso":"2024-11-29","date_label":"November 29, 2024",
    "category":"Events","lang":"en",
    "cover":"../assets/images/blog/cover-blog-2024-11-29-sivecc.jpg",
    "excerpt":"BENRO INDUSTRIES’ second SIVECC appearance — new partnerships across Tunisia and Libya, and standout feedback on BENRO-FLEX PE foam.",
    "body":[
      ("h2","Exhibition at SIVECC 2024"),
      ("h3","Unveiling the Latest HVAC Innovations at SIVECC 2024: A BENRO INDUSTRIES Recap"),
      ("p","BENRO INDUSTRIES marked its second successful appearance at the recent SIVECC (Salon International de la Ventilation, Électricité, Chauffage et Climatisation) trade show, held at the Safex Expo Center in Algiers from November 24-28, 2024. As a leading provider of HVAC solutions in Algeria, we were thrilled to once again participate and showcase our ongoing commitment to innovation and sustainability within the industry."),
      ("h4","Expanding Our Reach and Strengthening Partnerships"),
      ("p","SIVECC 2024 proved to be an even more valuable platform than our previous attendance, allowing us to further expand our network and forge new connections. We were delighted to connect with potential clients from Tunisia, Libya, and other neighbouring markets, opening exciting new opportunities for growth and collaboration across the region. Furthermore, we had the pleasure of welcoming many of our existing suppliers and valued clients, who provided invaluable feedback on our products."),
      ("h4","Testimonials Validate Our Commitment to Quality"),
      ("p","The overwhelmingly positive feedback we received at SIVECC further validates our commitment to producing high-quality HVAC solutions. Several clients offered testimonials praising the performance and reliability of our products, particularly our BENRO-FLEX PE foam insulation. These testimonials reinforce our dedication to meeting and exceeding industry standards."),
      ("h4","A Hub for the HVAC Industry"),
      ("p","SIVECC 2024 brought together a wide array of HVAC businesses, showcasing the latest advancements across the entire sector. The event provided a comprehensive overview of current trends and emerging technologies, from energy-efficient systems and sustainable practices to smart-home integration and advanced control mechanisms."),
      ("h4","BENRO INDUSTRIES: Committed to Progress"),
      ("p","At our booth, we had the opportunity to connect with key industry players, architects, engineers and potential partners. We showcased our commitment to industry-wide trends by presenting our latest products and solutions, including:"),
      ("ul",[
        "<strong>High-performance insulation materials</strong> — we highlighted our innovative BENRO-FLEX PE foam insulation, perfect for cooling applications and ensuring optimal energy efficiency.",
        "<strong>Durable and reliable equipment</strong> — top-quality HVAC equipment designed for longevity and optimal performance.",
        "<strong>Expert advice and support</strong> — our team was available to answer questions and provide expert advice on selecting the right HVAC solutions for various applications.",
      ]),
      ("p","SIVECC 2024 was, once again, an invaluable opportunity to stay current with the latest trends and technologies shaping the future of HVAC. We look forward to participating in future events and continuing to contribute to the advancement of the HVAC industry in Algeria and beyond."),
    ],
    "gallery":[
      "../assets/images/blog/sivecc2024-gal-1.jpg",
      "../assets/images/blog/sivecc2024-gal-2.jpg",
      "../assets/images/blog/sivecc2024-gal-3.jpg",
      "../assets/images/blog/sivecc2024-gal-4.jpg",
    ],
  },
  # ──────────────────────────────────────────────────────────── 16
  {
    "slug":"local-authorities-inaugurate-the-new-facility",
    "title":"Local Authorities Inaugurate the New Facility",
    "date_iso":"2024-11-01","date_label":"November 1, 2024",
    "category":"Events","lang":"en",
    "cover":"../assets/images/blog/cover-blog-2024-11-01-inauguration.jpg",
    "excerpt":"The Wali of Ghardaïa and local representatives inaugurated BENRO INDUSTRIES’ expanded plant in the industrial zone on October 27, 2024.",
    "body":[
      ("h2","Local Authorities Inaugurate the New Facility"),
      ("h3","BENRO INDUSTRIES Celebrates Grand Opening of Factory Expansion with Local Authorities of Ghardaïa"),
      ("p","BENRO INDUSTRIES proudly celebrated the grand opening of its newly expanded manufacturing facility in the Ghardaïa industrial zone on October 27, 2024. The momentous occasion was graced by the presence of the Local authorities of Ghardaïa, along with an esteemed delegation, including representatives from the police, gendarmerie, local news outlets, prominent production associations, company investors, employees and their families, and close friends of the company owner, Djaber Benrostom."),
      ("p","The event showcased BENRO INDUSTRIES’ commitment to driving local production and contributing to Algeria’s economic growth within the HVAC sector. During a presentation detailing the company’s manufacturing processes, statistics and market impact, the Wali of Ghardaïa expressed particular interest in BENRO INDUSTRIES’ dedication to replacing imported air-conditioning connecting lines with domestically produced, high-quality alternatives."),
      ("p","BENRO INDUSTRIES highlighted its capacity to meet the entire Algerian market’s demand for these essential HVAC components, adhering to the stringent EN12735-1 European standards. This commitment to quality ensures that Algerian-made products rival European counterparts in performance and reliability. The company emphasised that with improved access to primary and raw materials through government support, BENRO INDUSTRIES can significantly reduce reliance on imports and empower Algerian manufacturing."),
      ("p","Despite their proven quality and adherence to international standards, BENRO INDUSTRIES faces the challenge of larger air-conditioning brands continuing to utilise imported connecting lines. The Local authorities of Ghardaïa expressed strong support for BENRO INDUSTRIES’ mission and pledged to provide assistance in facilitating access to necessary resources, ultimately promoting the success of Algerian-made products and strengthening the national economy. This endorsement underscores the shared vision of BENRO INDUSTRIES and local government to foster a thriving domestic manufacturing sector. This event marks a significant step towards achieving BENRO INDUSTRIES’ vision to be the leading and most trusted provider of quality HVAC products and solutions in Algeria by 2025, expanding our reach to international markets by 2026."),
      ("h3","Let’s Build Something Together"),
      ("p","We’re constantly pushing the boundaries of what’s possible. Let’s collaborate on innovative solutions that shape the future."),
    ],
    "gallery":[
      "../assets/images/blog/inaug-gal-1.jpg",
      "../assets/images/blog/inaug-gal-2.jpg",
      "../assets/images/blog/inaug-gal-3.jpg",
      "../assets/images/blog/inaug-gal-4.jpg",
      "../assets/images/blog/inaug-gal-5.jpg",
    ],
  },
  # ──────────────────────────────────────────────────────────── 17
  {
    "slug":"innovative-hvac-solutions-by-benro-at-sivecc-2023",
    "title":"Innovative HVAC Solutions by BENRO at SIVECC 2023",
    "date_iso":"2023-11-30","date_label":"November 30, 2023",
    "category":"Events","lang":"en",
    "cover":"../assets/images/blog/cover-blog-2023-11-30-sivecc.jpg",
    "excerpt":"BENRO INDUSTRIES’ first SIVECC appearance — introducing BENRO-FLEX PE foam to the Algerian HVAC market and forging new partnerships.",
    "body":[
      ("h2","Exhibition at SIVECC 2023"),
      ("h3","BENRO INDUSTRIES Makes a Splash at SIVECC 2023"),
      ("p","BENRO INDUSTRIES proudly marked its first-ever participation in the SIVECC (Salon International de la Ventilation, Électricité, Chauffage et Climatisation) trade show, held at the Safex Expo Center in Algiers. This inaugural appearance proved to be a significant milestone for our company, providing an invaluable platform to introduce our brand and innovative HVAC solutions to the Algerian market."),
      ("h4","A Strong First Impression"),
      ("p","SIVECC 2023 provided BENRO INDUSTRIES with a unique opportunity to showcase our products and expertise to a wide audience of industry professionals. As a newcomer to the market, we were excited to present our unique offerings and establish our presence within the Algerian HVAC landscape. The response was overwhelmingly positive, with a large number of visitors expressing keen interest in learning more about our brand and products."),
      ("h4","Introducing Innovation to the Market"),
      ("p","At our booth, we focused on highlighting the key features and benefits of our product line, particularly our BENRO-FLEX PE foam insulation. We emphasised its suitability for cooling applications, its energy efficiency and its eco-friendly composition. Given our unique position in the market at the time, we were able to provide a fresh perspective on insulation solutions and generate significant interest among attendees."),
      ("h4","Forging New Connections and Securing Partnerships"),
      ("p","SIVECC 2023 was not only about showcasing our products; it was also about building relationships. We successfully connected with numerous potential clients, leading to several promising deals and laying the foundation for long-term partnerships. This event allowed us to establish a strong initial foothold in the market and build a valuable network of industry contacts."),
      ("h4","A Hub for the HVAC Industry"),
      ("p","SIVECC 2023, as always, brought together a diverse range of HVAC businesses, showcasing the latest advancements across the sector. The event offered attendees a comprehensive overview of current trends and emerging technologies, from energy-efficient systems and sustainable practices to smart-home integration and advanced control mechanisms."),
      ("h4","BENRO INDUSTRIES: A Promising Start"),
      ("p","Our first participation in SIVECC was an undeniable success. The event provided us with invaluable market exposure, allowing us to introduce our brand, connect with key industry players and secure new business opportunities. We’re confident that the connections and momentum gained at SIVECC 2023 will contribute significantly to our future growth and success in the Algerian HVAC market."),
    ],
    "gallery":[
      "../assets/images/blog/sivecc2023-gal-1.jpg",
      "../assets/images/blog/sivecc2023-gal-2.jpg",
      "../assets/images/blog/sivecc2023-gal-3.jpg",
      "../assets/images/blog/sivecc2023-gal-4.jpg",
      "../assets/images/blog/sivecc2023-gal-5.jpg",
    ],
  },
]

# ════════════════════════════════════════════════════════════════════
# Shared CSS + chrome (same brand system as homepage/about/datasheets)
# ════════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════════
# BLOG CONTENT I18N
# Generated cache contains EN/FR/AR translations for blog listing cards
# and article bodies. Keep blog_i18n_cache.json committed with this file.
# ════════════════════════════════════════════════════════════════════
BLOG_I18N_PATH = pathlib.Path("blog_i18n_cache.json")
try:
    BLOG_I18N_CACHE = json.loads(BLOG_I18N_PATH.read_text(encoding="utf-8")) if BLOG_I18N_PATH.exists() else {}
except Exception:
    BLOG_I18N_CACHE = {}
BLOG_I18N_CACHE.pop("_memory", None)

LANGS = ("en", "fr", "ar")

def cat_key(category):
    return "cat." + re.sub(r"[^A-Za-z0-9]+", "_", category).strip("_")

def post_key(post, field):
    return f"post.{post['slug']}.{field}"

def post_tr(post, lang, field, fallback=""):
    return BLOG_I18N_CACHE.get(post["slug"], {}).get(lang, {}).get(field, fallback)

def build_blog_i18n(posts, include_body_for=None):
    """Return a compact JS translation object for the posts used on a page."""
    data = {lang: {} for lang in LANGS}
    include_body_slug = include_body_for["slug"] if include_body_for else None
    for post in posts:
        for lang in LANGS:
            data[lang][post_key(post, "title")] = post_tr(post, lang, "title", post["title"])
            data[lang][post_key(post, "excerpt")] = post_tr(post, lang, "excerpt", post["excerpt"])
            data[lang][post_key(post, "category")] = post_tr(post, lang, "category", post["category"])
            data[lang][post_key(post, "date")] = post_tr(post, lang, "date_label", post["date_label"])
            data[lang][cat_key(post["category"])] = post_tr(post, lang, "category", post["category"])
            if include_body_slug == post["slug"]:
                for i, block in enumerate(post_tr(post, lang, "body", [])):
                    data[lang][post_key(post, f"body.{i}")] = block
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

def search_blob(post):
    parts = [post["title"], post["excerpt"], post["category"]]
    for lang in LANGS:
        parts += [
            post_tr(post, lang, "title", ""),
            post_tr(post, lang, "excerpt", ""),
            post_tr(post, lang, "category", ""),
        ]
    return " ".join(parts).lower()

SHARED_CSS = r"""
  :root{
    --brand:#E45911; --brand-600:#c84a09; --brand-50:#FFF1E9;
    --ink:#1F2937; --ink-2:#3D4F5F; --muted:#5A6577;
    --line:#E7EBEE; --surface:#FBFBFC; --surface-2:#F3F5F7;
    --white:#ffffff;
    --shadow-sm:0 1px 2px rgba(17,24,39,.04), 0 1px 3px rgba(17,24,39,.06);
    --shadow-md:0 8px 24px -8px rgba(17,24,39,.12), 0 4px 8px -4px rgba(17,24,39,.08);
    --shadow-lg:0 24px 48px -16px rgba(17,24,39,.18);
    --container:1240px;
    --font:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  }
  *,*::before,*::after{box-sizing:border-box}
  html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
  body{margin:0;font-family:var(--font);color:var(--ink);background:#fff;line-height:1.65;-webkit-font-smoothing:antialiased;overflow-x:hidden}
  img{max-width:100%;display:block;height:auto}
  a{color:inherit;text-decoration:none}
  button{font-family:inherit;cursor:pointer;border:0;background:none}
  .container{max-width:var(--container);margin:0 auto;padding:0 24px}
  h1,h2,h3,h4{margin:0;line-height:1.18;letter-spacing:-0.02em;font-weight:800;color:var(--ink)}
  h1{font-size:clamp(32px,4.4vw,52px)}
  h2{font-size:clamp(24px,2.6vw,34px)}
  h3{font-size:20px;font-weight:700;letter-spacing:-0.01em}
  h4{font-size:17px;font-weight:700}
  p{margin:0}


  /* Skip to content link */
  .skip-link{
    position:absolute;
    top:-100%;
    left:16px;
    z-index:9999;
    padding:12px 24px;
    background:var(--brand);
    color:#fff;
    border-radius:0 0 8px 8px;
    font-weight:700;
    font-size:14px;
    text-decoration:none;
    transition:top .2s;
  }
  .skip-link:focus{top:0}
  html[dir="rtl"] .skip-link{left:auto;right:16px}

  .btn{display:inline-flex;align-items:center;gap:10px;padding:14px 24px;border-radius:999px;font-weight:700;font-size:15px;transition:transform .15s,box-shadow .2s,background .2s,color .2s;white-space:nowrap}
  .btn--primary{background:var(--brand);color:#fff;box-shadow:0 6px 18px -6px rgba(228,89,17,.55)}
  .btn--primary:hover{background:var(--brand-600);transform:translateY(-1px)}
  .btn--ghost{background:transparent;color:var(--ink);border:1.5px solid var(--line)}
  .btn--ghost:hover{border-color:var(--ink);background:var(--surface-2)}
  .btn--white{background:#fff;color:var(--brand)}
  .btn .ico{width:18px;height:18px;flex:0 0 18px}

  .topbar{background:var(--ink);color:#c8d1da;font-size:13px}
  .topbar__inner{display:flex;align-items:center;justify-content:space-between;gap:16px;height:40px}
  .topbar a{display:inline-flex;align-items:center;gap:6px;color:#c8d1da;transition:color .15s}
  .topbar a:hover{color:#fff}
  .topbar .sep{opacity:.3;margin:0 10px}
  .topbar .right{display:flex;align-items:center;gap:6px}

  .lang-switch{position:relative;display:inline-block}
  .lang-btn{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;border:1px solid #374151;background:transparent;color:#c8d1da;font:inherit;font-size:13px;line-height:1;cursor:pointer;transition:.15s}
  .lang-btn:hover{color:#fff;border-color:#5A6577;background:#1f2937}
  .lang-btn .caret{transition:transform .2s;opacity:.8}
  .lang-switch.open .lang-btn .caret{transform:rotate(180deg)}
  .lang-switch.open .lang-btn{color:#fff;border-color:var(--brand);background:#1f2937}
  .lang-menu{position:absolute;top:calc(100% + 8px);right:0;z-index:70;min-width:170px;margin:0;padding:6px;list-style:none;background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow-md);opacity:0;transform:translateY(-6px);pointer-events:none;transition:.15s}
  .lang-switch.open .lang-menu{opacity:1;transform:none;pointer-events:auto}
  .lang-menu button{width:100%;display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:8px;background:transparent;color:var(--ink);font:inherit;font-size:14px;font-weight:600;text-align:left;cursor:pointer}
  .lang-menu button:hover,.lang-menu button.active{background:var(--brand-50);color:var(--brand)}
  html[dir="rtl"] .lang-menu{right:auto;left:0}
  html[dir="rtl"] .lang-menu button{text-align:right}
  @media (max-width:720px){.topbar .hide-sm{display:none}}
  html[dir="rtl"]{font-family:"Tajawal","Cairo","Noto Sans Arabic",var(--font)}
  html[dir="rtl"] h1,html[dir="rtl"] h2,html[dir="rtl"] h3,html[dir="rtl"] h4{letter-spacing:0}

  .header{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.88);backdrop-filter:saturate(180%) blur(14px);-webkit-backdrop-filter:saturate(180%) blur(14px);border-bottom:1px solid transparent;transition:border-color .2s,box-shadow .2s}
  .header.is-scrolled{border-color:var(--line);box-shadow:var(--shadow-sm)}
  .header__inner{display:flex;align-items:center;justify-content:space-between;gap:24px;height:78px;transition:height .2s}
  .header.is-scrolled .header__inner{height:64px}
  .logo img{height:48px;width:auto;transition:height .2s}
  .header.is-scrolled .logo img{height:40px}
  .nav{display:flex;align-items:center;gap:4px}
  .nav a{padding:10px 14px;border-radius:8px;font-weight:600;color:var(--ink-2);font-size:15px;transition:.15s}
  .nav a:hover,.nav a.is-active{color:var(--brand);background:var(--brand-50)}
  .burger{display:none;width:42px;height:42px;border-radius:10px;border:1px solid var(--line);align-items:center;justify-content:center}
  .burger span{display:block;width:18px;height:2px;background:var(--ink);position:relative}
  .burger span::before,.burger span::after{content:"";position:absolute;left:0;width:18px;height:2px;background:var(--ink)}
  .burger span::before{top:-6px}.burger span::after{top:6px}
  @media (max-width:1024px){.nav{display:none}.burger{display:inline-flex}.header__cta .btn--ghost{display:none}}
  .mnav{position:fixed;inset:0 0 0 auto;width:min(86vw,360px);background:#fff;z-index:60;transform:translateX(100%);transition:transform .25s ease;padding:88px 24px 24px;box-shadow:var(--shadow-lg);display:flex;flex-direction:column;gap:6px}
  .mnav.open{transform:translateX(0)}
  .mnav a{padding:14px 12px;border-radius:10px;font-weight:600;font-size:17px;color:var(--ink)}
  .mnav a:hover{background:var(--surface-2);color:var(--brand)}
  .mnav .btn{margin-top:14px;justify-content:center}
  .mnav-close{position:absolute;top:18px;right:18px;width:40px;height:40px;border-radius:10px;border:1px solid var(--line);display:inline-flex;align-items:center;justify-content:center;font-size:22px;color:var(--ink)}
  .scrim{position:fixed;inset:0;background:rgba(15,23,42,.4);z-index:55;opacity:0;pointer-events:none;transition:opacity .2s}
  .scrim.show{opacity:1;pointer-events:auto}
  html[dir="rtl"] .mnav{right:auto;left:0;transform:translateX(-100%)}
  html[dir="rtl"] .mnav.open{transform:translateX(0)}
  html[dir="rtl"] .mnav-close{right:auto;left:18px}

  .crumbs{background:var(--surface);border-bottom:1px solid var(--line)}
  .crumbs__inner{display:flex;align-items:center;gap:8px;height:46px;font-size:13.5px;color:var(--ink-2);flex-wrap:wrap}
  .crumbs a{color:var(--ink-2);transition:color .15s}
  .crumbs a:hover{color:var(--brand)}
  .crumbs .sep{opacity:.4}
  .crumbs .current{color:var(--ink);font-weight:600}

  /* Footer */
  .footer{background:#0b1220;color:#94a3b8;padding:72px 0 0;margin-top:80px}
  .footer__grid{display:grid;grid-template-columns:1.35fr 1fr 1fr 1.15fr 1.15fr;gap:36px}
  .footer__brand img{height:54px;filter:brightness(0) invert(1);opacity:.95}
  .footer__brand p{margin-top:16px;font-size:14px;line-height:1.75;max-width:340px}
  .footer h4{color:#fff;font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-bottom:20px}
  .footer ul{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:12px}
  .footer ul a{color:#94a3b8;font-size:14.5px;transition:color .15s}
  .footer ul a:hover{color:var(--brand)}
  .footer .contact-li{display:flex;gap:10px;align-items:flex-start;color:#c8d1da;font-size:14.5px;line-height:1.6}
  .footer .contact-li .ico{width:18px;height:18px;color:var(--brand);flex:0 0 18px;margin-top:4px}
  .footer__social{display:flex;gap:10px;flex-wrap:wrap}
  .footer__social a{width:40px;height:40px;border-radius:10px;background:#1f2937;color:#c8d1da;display:inline-flex;align-items:center;justify-content:center;transition:all .2s}
  .footer__social a:hover{background:var(--brand);color:#fff;transform:translateY(-3px)}
  .footer__social svg{width:18px;height:18px}
  .footer__bottom{margin-top:56px;padding:24px 0;border-top:1px solid #1f2937;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;font-size:13px;color:#5A6B7E}
  .footer__bottom a{color:#94a3b8;transition:color .15s}
  .footer__bottom a:hover{color:var(--brand)}
  html[dir="rtl"] .footer h4{letter-spacing:.05em}
  @media (max-width:1100px){.footer__grid{grid-template-columns:1fr 1fr 1fr;gap:32px}}
  @media (max-width:900px){.footer__grid{grid-template-columns:1fr 1fr;gap:40px}}
  @media (max-width:520px){.footer__grid{grid-template-columns:1fr}.footer__bottom{flex-direction:column;text-align:center}}

  .wa{position:fixed;right:22px;bottom:22px;z-index:40;width:56px;height:56px;border-radius:50%;background:#25D366;color:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 12px 24px -6px rgba(37,211,102,.55);transition:transform .2s}
  .wa:hover{transform:scale(1.06)}
  .wa svg{width:28px;height:28px}
  .wa::after{content:"";position:absolute;inset:-6px;border-radius:50%;background:#25D36633;animation:ping 2s ease-out infinite;z-index:-1}
  @keyframes ping{0%{transform:scale(.85);opacity:.7}80%,100%{transform:scale(1.4);opacity:0}}
  html[dir="rtl"] .wa{right:auto;left:22px}

  .reveal{opacity:0;transform:translateY(18px);transition:opacity .6s,transform .6s}
  .reveal.in{opacity:1;transform:none}
  @media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.001ms!important;transition-duration:.001ms!important}.reveal{opacity:1;transform:none}}
"""

# Header / topbar / footer markup for INDIVIDUAL POST pages (paths use ../)
def topbar_html(prefix=""):
  return f"""<div class="topbar">
  <div class="container topbar__inner">
    <div class="left hide-sm">
      <a href="tel:+213554250110"><svg class="ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.86 19.86 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.86 19.86 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/></svg>+213 554 25 01 10</a>
      <span class="sep">•</span>
      <a href="mailto:contact@benroindustries.com"><svg class="ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><path d="m22 6-10 7L2 6"/></svg>contact@benroindustries.com</a>
    </div>
    <div class="right">
      <span class="hide-sm" data-i18n="topbar.tagline">Algeria 🇩🇿 · HVAC&amp;R Manufacturer</span>
      <span class="sep hide-sm">•</span>
      <div class="lang-switch" id="langSwitch">
        <button type="button" class="lang-btn" id="langTrigger" aria-haspopup="listbox" aria-expanded="false" aria-label="Select language">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10A15.3 15.3 0 0 1 8 12 15.3 15.3 0 0 1 12 2z"/></svg>
          <span id="langCurrent">EN</span>
          <svg class="caret" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <ul class="lang-menu" id="langMenu" role="listbox">
          <li><button type="button" role="option" data-lang="en"><span>🇬🇧</span> English</button></li>
          <li><button type="button" role="option" data-lang="fr"><span>🇫🇷</span> Français</button></li>
          <li><button type="button" role="option" data-lang="ar"><span>🇩🇿</span> العربية</button></li>
        </ul>
      </div>
    </div>
  </div>
</div>"""

def header_html(prefix, is_blog_active):
    return f"""<header class="header" id="siteHeader">
  <div class="container header__inner">
    <a href="{prefix}index.html" class="logo"><img src="{prefix}assets/images/benro-logo.png" alt="Benro Industries"/></a>
    <nav class="nav" aria-label="Primary">
      <a href="{prefix}index.html#products" data-i18n="nav.products">Products</a>
      <a href="{prefix}index.html#why" data-i18n="nav.why">Why Benro</a>
      <a href="{prefix}about.html" data-i18n="nav.about">About</a>
      <a href="{prefix}blog.html"{ ' class="is-active"' if is_blog_active else '' } data-i18n="nav.blog">Blog</a>
      <a href="{prefix}index.html#partners" data-i18n="nav.clients">Clients</a>
      <a href="{prefix}contact.html" data-i18n="nav.contact">Contact</a>
    </nav>
    <div class="header__cta">
      <a href="{prefix}index.html#products" class="btn btn--ghost" data-i18n="cta.browse">Browse catalogue</a>
      <a href="{prefix}quote.html" class="btn btn--primary"><span data-i18n="cta.quote">Get a Quote</span><svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></a>
      <button class="burger" id="burger" aria-label="Open menu" aria-expanded="false"><span></span></button>
    </div>
  </div>
</header>
<div class="scrim" id="scrim"></div>
<aside class="mnav" id="mnav" aria-label="Mobile menu">
  <button class="mnav-close" id="mnavClose" aria-label="Close menu">×</button>
  <a href="{prefix}index.html#products" data-i18n="nav.products">Products</a>
  <a href="{prefix}index.html#why" data-i18n="nav.why">Why Benro</a>
  <a href="{prefix}about.html" data-i18n="nav.about">About</a>
  <a href="{prefix}blog.html" data-i18n="nav.blog">Blog</a>
  <a href="{prefix}index.html#partners" data-i18n="nav.clients">Clients</a>
  <a href="{prefix}contact.html" data-i18n="nav.contact">Contact</a>
  <a href="{prefix}quote.html" class="btn btn--primary" data-i18n="cta.quote">Get a Quote</a>
</aside>"""

def footer_html(prefix):
    return f"""<footer class="footer">
  <div class="container">
    <div class="footer__grid">
      <div class="footer__brand">
        <img src="{prefix}assets/images/benro-logo.png" alt="Benro Industries"/>
        <p data-i18n="footer.about">BENRO INDUSTRIES is a vibrant and innovative manufacturer at the forefront of the HVAC&amp;R sector — producing insulated copper &amp; aluminium connecting lines and PE foam insulation in Algeria.</p>
      </div>
      <div>
        <h4 data-i18n="footer.products">Products</h4>
        <ul>
          <li><a href="{prefix}products/twin-insulated-copper.html" data-i18n="footer.prod1">Twin Insulated Copper</a></li>
          <li><a href="{prefix}products/single-insulated-copper.html" data-i18n="footer.prod2">Single Insulated Copper</a></li>
          <li><a href="{prefix}products/twin-insulated-aluminium.html" data-i18n="footer.prod3">Twin Insulated Aluminium</a></li>
          <li><a href="{prefix}products/insulation-polyethylene.html" data-i18n="footer.prod4">PE Insulation Tubes</a></li>
          <li><a href="{prefix}products/copper-tubes.html" data-i18n="footer.prod5">Copper Pancake Coils</a></li>
          <li><a href="{prefix}products/polyethylene-tubes.html" data-i18n="footer.prod6">Polyethylene Tubes</a></li>
        </ul>
      </div>
      <div>
        <h4 data-i18n="footer.quicklinks">Quick Links</h4>
        <ul>
          <li><a href="{prefix}index.html" data-i18n="footer.home">Home</a></li>
          <li><a href="{prefix}about.html" data-i18n="footer.about_link">About us</a></li>
          <li><a href="{prefix}index.html#products" data-i18n="nav.products">Products</a></li>
          <li><a href="{prefix}blog.html" data-i18n="nav.blog">Blog</a></li>
          <li><a href="{prefix}contact.html" data-i18n="nav.contact">Contact</a></li>
          <li><a href="{prefix}quote.html" data-i18n="cta.quote">Get a Quote</a></li>
        </ul>
      </div>
      <div>
        <h4 data-i18n="footer.contact">Contact</h4>
        <ul>
          <li class="contact-li">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            <a href="https://www.google.com/maps/search/?api=1&query=Industrial+Zone%2C+Ghardaia%2C+Algeria" target="_blank" rel="noopener" data-i18n="footer.address">Industrial Zone, Ghardaïa, Algeria</a>
          </li>
          <li class="contact-li">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.86 19.86 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.86 19.86 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
            <a href="tel:+213554250110">+213 554 25 01 10</a>
          </li>
          <li class="contact-li">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><path d="m22 6-10 7L2 6"/></svg>
            <a href="mailto:contact@benroindustries.com">contact@benroindustries.com</a>
          </li>
        </ul>
      </div>
      <div>
        <h4 data-i18n="footer.follow">Follow Us</h4>
        <div class="footer__social">
          <a href="https://www.linkedin.com/company/benro-industries" target="_blank" rel="noopener" aria-label="LinkedIn"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.94v5.67H9.36V9h3.41v1.56h.05a3.74 3.74 0 0 1 3.37-1.85c3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zm-1.78 13.02h3.55V9H3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.72V1.72C24 .77 23.2 0 22.22 0z"/></svg></a>
          <a href="https://www.facebook.com/benroindustries" target="_blank" rel="noopener" aria-label="Facebook"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M22 12a10 10 0 1 0-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.8-3.9 1.1 0 2.3.2 2.3.2v2.5h-1.3c-1.3 0-1.7.8-1.7 1.6V12h2.9l-.5 2.9h-2.5v7A10 10 0 0 0 22 12z"/></svg></a>
          <a href="https://www.instagram.com/benroindustries" target="_blank" rel="noopener" aria-label="Instagram"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5"/><path d="M16 11.4a4 4 0 1 1-8 0 4 4 0 0 1 8 0z"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor"/></svg></a>
          <a href="https://wa.me/213554250110" target="_blank" rel="noopener" aria-label="WhatsApp"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 14.4c-.3-.1-1.8-.9-2-1s-.5-.1-.7.1c-.2.3-.8 1-1 1.2-.2.2-.4.2-.7.1-.3-.1-1.3-.5-2.5-1.5-.9-.8-1.6-1.8-1.7-2.1-.2-.3 0-.5.1-.6.1-.1.3-.4.4-.5.1-.2.2-.3.3-.5.1-.2.1-.4 0-.5-.1-.2-.7-1.6-.9-2.2-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.4 0 1.4 1 2.8 1.2 3 .1.2 2 3.1 4.9 4.3.7.3 1.2.5 1.6.6.7.2 1.3.2 1.8.1.5-.1 1.7-.7 2-1.4.2-.7.2-1.2.2-1.4-.1-.1-.3-.2-.6-.3zM12 0C5.4 0 0 5.4 0 12c0 2.1.6 4.1 1.6 5.9L0 24l6.3-1.6c1.7.9 3.7 1.5 5.7 1.5 6.6 0 12-5.4 12-12S18.6 0 12 0z"/></svg></a>
        </div>
        <p style="margin-top:18px;font-size:13px;color:#5A6B7E;line-height:1.6" data-i18n="footer.response">We typically respond within 2–4 hours.</p>
      </div>
    </div>
    <div class="footer__bottom">
      <div><span data-i18n="footer.copy_prefix">©</span> <span id="yr"></span> <span data-i18n="footer.copy_suffix">Benro Industries — All rights reserved.</span></div>
      <div>
        <a href="{prefix}contact.html" data-i18n="footer.privacy">Privacy Policy</a>
        <span style="margin:0 8px;opacity:.3">•</span>
        <span data-i18n="footer.tagline">HVAC&amp;R Manufacturer · Algeria 🇩🇿</span>
      </div>
    </div>
  </div>
</footer>

<a href="https://wa.me/213554250110" class="wa" aria-label="WhatsApp" target="_blank" rel="noopener">
  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 14.4c-.3-.1-1.8-.9-2-1s-.5-.1-.7.1c-.2.3-.8 1-1 1.2-.2.2-.4.2-.7.1-.3-.1-1.3-.5-2.5-1.5-.9-.8-1.6-1.8-1.7-2.1-.2-.3 0-.5.1-.6.1-.1.3-.4.4-.5.1-.2.2-.3.3-.5.1-.2.1-.4 0-.5-.1-.2-.7-1.6-.9-2.2-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.4 0 1.4 1 2.8 1.2 3 .1.2 2 3.1 4.9 4.3.7.3 1.2.5 1.6.6.7.2 1.3.2 1.8.1.5-.1 1.7-.7 2-1.4.2-.7.2-1.2.2-1.4-.1-.1-.3-.2-.6-.3zM12 0C5.4 0 0 5.4 0 12c0 2.1.6 4.1 1.6 5.9L0 24l6.3-1.6c1.7.9 3.7 1.5 5.7 1.5 6.6 0 12-5.4 12-12S18.6 0 12 0z"/></svg>
</a>"""

# Minimal i18n dict (chrome strings only — article bodies stay as-written)
I18N_JS = r"""
const I18N = {
  en: {
    'a11y.skip':'Skip to main content',
    'topbar.tagline':'Algeria 🇩🇿 · HVAC&R Manufacturer',
    'nav.products':'Products','nav.why':'Why Benro','nav.about':'About','nav.blog':'Blog','nav.clients':'Clients','nav.contact':'Contact',
    'cta.browse':'Browse catalogue','cta.quote':'Get a Quote',
    'crumb.home':'Home','crumb.blog':'Blog',
    'blog.hero.eyebrow':'BENRO Journal','blog.hero.title':'Blogs &amp; Events','blog.hero.lead':'Insights, technical guides and milestones from BENRO INDUSTRIES — HVAC components made in Algeria.',
    'blog.filter.all':'All','blog.search.ph':'Search articles…',
    'blog.empty':'No article matches your search.',
    'blog.readmore':'Read article',
    'blog.recent':'You may also like',
    'blog.back':'Back to blog','blog.share':'Share this article',
    'finalCta.btn1':'Call sales','finalCta.btn2':'Send a message',
    'footer.about':'BENRO INDUSTRIES is a vibrant and innovative manufacturer at the forefront of the HVAC&R sector — producing insulated copper & aluminium connecting lines and PE foam insulation in Algeria.',
    'footer.quicklinks':'Quick Links','footer.home':'Home','footer.about_link':'About us','footer.products':'Products','footer.prod1':'Twin Insulated Copper','footer.prod2':'Single Insulated Copper','footer.prod3':'Twin Insulated Aluminium','footer.prod4':'PE Insulation Tubes','footer.prod5':'Copper Pancake Coils','footer.prod6':'Polyethylene Tubes','footer.contact':'Contact',
    'footer.address':'Industrial Zone, Ghardaïa, Algeria',
    'footer.follow':'Follow Us','footer.response':'We typically respond within 2–4 hours.',
    'footer.copy_prefix':'©','footer.copy_suffix':'Benro Industries — All rights reserved.','footer.tagline':'HVAC&R Manufacturer · Algeria 🇩🇿','footer.privacy':'Privacy Policy'
  },
  fr: {
    'a11y.skip':'Aller au contenu principal',
    'topbar.tagline':'Algérie 🇩🇿 · Fabricant CVC&R',
    'nav.products':'Produits','nav.why':'Pourquoi Benro','nav.about':'À propos','nav.blog':'Blog','nav.clients':'Clients','nav.contact':'Contact',
    'cta.browse':'Voir le catalogue','cta.quote':'Demander un devis',
    'crumb.home':'Accueil','crumb.blog':'Blog',
    'blog.hero.eyebrow':'Journal BENRO','blog.hero.title':'Blog &amp; Événements','blog.hero.lead':"Analyses, guides techniques et étapes-clés de BENRO INDUSTRIES — composants CVC fabriqués en Algérie.",
    'blog.filter.all':'Tous','blog.search.ph':'Rechercher des articles…',
    'blog.empty':'Aucun article ne correspond à votre recherche.',
    'blog.readmore':"Lire l'article",
    'blog.recent':"À lire aussi",
    'blog.back':'Retour au blog','blog.share':'Partager cet article',
    'finalCta.btn1':'Appeler les ventes','finalCta.btn2':'Envoyer un message',
    'footer.about':"BENRO INDUSTRIES est un fabricant dynamique et innovant à la pointe du secteur CVC&R — produisant des lignes de raccordement en cuivre & aluminium isolées et de la mousse PE en Algérie.",
    'footer.quicklinks':'Liens rapides','footer.home':'Accueil','footer.about_link':'À propos','footer.products':'Produits','footer.prod1':'Cuivre isolé jumelé','footer.prod2':'Cuivre isolé simple','footer.prod3':'Aluminium isolé jumelé','footer.prod4':"Tubes d'isolation PE",'footer.prod5':'Couronnes de cuivre','footer.prod6':'Tubes en polyéthylène','footer.contact':'Contact',
    'footer.address':'Zone Industrielle, Ghardaïa, Algérie',
    'footer.follow':'Suivez-nous','footer.response':'Nous répondons généralement sous 2 à 4 heures.',
    'footer.copy_prefix':'©','footer.copy_suffix':'Benro Industries — Tous droits réservés.','footer.tagline':'Fabricant CVC&R · Algérie 🇩🇿','footer.privacy':'Politique de confidentialité'
  },
  ar: {
    'a11y.skip':'انتقل إلى المحتوى الرئيسي',
    'topbar.tagline':'الجزائر 🇩🇿 · صانع تكييف وتبريد',
    'nav.products':'المنتجات','nav.why':'لماذا Benro','nav.about':'من نحن','nav.blog':'المدوّنة','nav.clients':'العملاء','nav.contact':'اتصل بنا',
    'cta.browse':'تصفح الكتالوج','cta.quote':'اطلب عرض سعر',
    'crumb.home':'الرئيسية','crumb.blog':'المدوّنة',
    'blog.hero.eyebrow':'مجلّة BENRO','blog.hero.title':'المدوّنة والفعاليات','blog.hero.lead':'تحليلات وأدلّة تقنية ومحطّات هامّة من بنرو للصناعات — مكوّنات تكييف صنعت في الجزائر.',
    'blog.filter.all':'الكل','blog.search.ph':'ابحث في المقالات…',
    'blog.empty':'لا يوجد مقالٌ يطابق بحثك.',
    'blog.readmore':'قراءة المقال',
    'blog.recent':'قد يعجبك أيضاً',
    'blog.back':'العودة إلى المدوّنة','blog.share':'شارك هذا المقال',
    'finalCta.btn1':'اتصل بالمبيعات','finalCta.btn2':'أرسل رسالة',
    'footer.about':'بنرو للصناعات صانعٌ ديناميكي ومبتكر في طليعة قطاع التكييف والتبريد — ينتج خطوط توصيل نحاسية وألمنيومية معزولة ورغوة PE في الجزائر.',
    'footer.quicklinks':'روابط سريعة','footer.home':'الرئيسية','footer.about_link':'من نحن','footer.products':'المنتجات','footer.prod1':'نحاس مزدوج معزول','footer.prod2':'نحاس مفرد معزول','footer.prod3':'ألمنيوم مزدوج معزول','footer.prod4':'أنابيب عزل PE','footer.prod5':'لفّات نحاسية','footer.prod6':'أنابيب بولي إيثيلين','footer.contact':'تواصل',
    'footer.address':'المنطقة الصناعية، غرداية، الجزائر',
    'footer.follow':'تابعنا','footer.response':'نرد عادةً خلال 2–4 ساعات.',
    'footer.copy_prefix':'©','footer.copy_suffix':'بنرو للصناعات — جميع الحقوق محفوظة.','footer.tagline':'صانع تكييف وتبريد · الجزائر 🇩🇿','footer.privacy':'سياسة الخصوصية'
  }
};
const LANG_LABEL={en:'EN',fr:'FR',ar:'AR'};
function applyLang(lang){
  if(!I18N[lang]) lang='en';
  const dict={...(I18N[lang]||{}), ...((typeof BLOG_I18N!=='undefined'&&BLOG_I18N[lang])?BLOG_I18N[lang]:{})}, h=document.documentElement;
  h.lang=lang; h.dir=(lang==='ar')?'rtl':'ltr';
  document.querySelectorAll('[data-i18n]').forEach(el=>{const k=el.getAttribute('data-i18n'); if(dict[k]!=null) el.textContent=dict[k];});
  document.querySelectorAll('[data-i18n-html]').forEach(el=>{const k=el.getAttribute('data-i18n-html'); if(dict[k]!=null) el.innerHTML=dict[k];});
  document.querySelectorAll('[data-i18n-ph]').forEach(el=>{const k=el.getAttribute('data-i18n-ph'); if(dict[k]!=null) el.placeholder=dict[k];});
  const cur=document.getElementById('langCurrent'); if(cur) cur.textContent=LANG_LABEL[lang];
  document.querySelectorAll('#langMenu [data-lang]').forEach(b=>b.classList.toggle('active',b.dataset.lang===lang));
  try{localStorage.setItem('benroLang',lang)}catch(e){}
}
(function(){
  const wrap=document.getElementById('langSwitch'),trig=document.getElementById('langTrigger'),menu=document.getElementById('langMenu');
  if(!wrap)return;
  const close=()=>{wrap.classList.remove('open');trig.setAttribute('aria-expanded','false')};
  const open =()=>{wrap.classList.add('open');trig.setAttribute('aria-expanded','true')};
  trig.addEventListener('click',e=>{e.stopPropagation();wrap.classList.contains('open')?close():open()});
  menu.querySelectorAll('[data-lang]').forEach(b=>b.addEventListener('click',()=>{applyLang(b.dataset.lang);close()}));
  document.addEventListener('click',e=>{if(!wrap.contains(e.target)) close()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape') close()});
  let saved=null; try{saved=localStorage.getItem('benroLang')}catch(e){}
  const guess=(navigator.language||'en').slice(0,2).toLowerCase();
  applyLang(saved||(['en','fr','ar'].includes(guess)?guess:'en'));
})();
const hdr=document.getElementById('siteHeader');
const onScroll=()=>hdr.classList.toggle('is-scrolled',window.scrollY>8);
window.addEventListener('scroll',onScroll,{passive:true}); onScroll();
const burger=document.getElementById('burger');
const mnav=document.getElementById('mnav');
const scrim=document.getElementById('scrim');
const mclose=document.getElementById('mnavClose');
const toggleMenu=(open)=>{mnav.classList.toggle('open',open);scrim.classList.toggle('show',open);burger.setAttribute('aria-expanded',String(open));document.body.style.overflow=open?'hidden':''};
burger.addEventListener('click',()=>toggleMenu(!mnav.classList.contains('open')));
mclose.addEventListener('click',()=>toggleMenu(false));
scrim.addEventListener('click',()=>toggleMenu(false));
mnav.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>toggleMenu(false)));
const io=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{threshold:.12});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
document.getElementById('yr').textContent=new Date().getFullYear();
"""

# ════════════════════════════════════════════════════════════════════
# BLOG LISTING (blog.html — at site root)
# ════════════════════════════════════════════════════════════════════
LISTING_EXTRA_CSS = r"""
  .bhero{
    padding:72px 0 80px;
    background:
      radial-gradient(1100px 580px at 90% -10%, rgba(228,89,17,.10), transparent 60%),
      radial-gradient(800px 460px at -10% 110%, rgba(11,61,145,.08), transparent 60%),
      linear-gradient(180deg,#fff 0%, var(--surface) 100%);
  }
  .bhero__wrap{text-align:center;max-width:760px;margin:0 auto}
  .badge{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;background:var(--brand-50);color:var(--brand-600);font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;border:1px solid rgba(228,89,17,.18)}
  .bhero h1{margin-top:18px}
  .bhero h1 .accent{background:linear-gradient(90deg,var(--brand) 0%, #f4a045 100%);-webkit-background-clip:text;background-clip:text;color:transparent}
  .bhero p{margin-top:18px;font-size:17.5px;color:var(--ink-2)}

  .toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin:0 0 32px}
  .toolbar__filters{display:flex;flex-wrap:wrap;gap:8px}
  .chip{
    display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:999px;
    background:#fff;border:1.5px solid var(--line);color:var(--ink-2);font-weight:600;font-size:13.5px;cursor:pointer;
    transition:.15s;user-select:none;font:inherit;
  }
  .chip:hover{border-color:var(--ink);color:var(--ink)}
  .chip.is-active{background:var(--brand);color:#fff;border-color:var(--brand);box-shadow:0 6px 16px -6px rgba(228,89,17,.5)}
  .search{position:relative;min-width:260px;flex:1;max-width:380px}
  .search input{
    width:100%;padding:11px 14px 11px 40px;font:inherit;font-size:14.5px;
    border-radius:999px;border:1.5px solid var(--line);background:#fff;color:var(--ink);
    transition:.15s;
  }
  html[dir="rtl"] .search input{padding:11px 40px 11px 14px}
  .search input:focus{outline:none;border-color:var(--brand);box-shadow:0 0 0 4px rgba(228,89,17,.12)}
  .search svg{position:absolute;top:50%;left:14px;transform:translateY(-50%);width:16px;height:16px;color:var(--muted);pointer-events:none}
  html[dir="rtl"] .search svg{left:auto;right:14px}
  @media (max-width:520px){.search{min-width:0;max-width:none;width:100%}}

  .pgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
  @media (max-width:980px){.pgrid{grid-template-columns:repeat(2,1fr)}}
  @media (max-width:640px){.pgrid{grid-template-columns:1fr}}

  .pcard{
    background:#fff;border:1px solid var(--line);border-radius:18px;overflow:hidden;
    transition:transform .25s,box-shadow .25s,border-color .25s;
    display:flex;flex-direction:column;
  }
  .pcard:hover{transform:translateY(-4px);box-shadow:var(--shadow-md);border-color:#dbe2ea}
  .pcard__media{aspect-ratio:16/10;background:var(--surface-2);overflow:hidden;position:relative}
  .pcard__media img{width:100%;height:100%;object-fit:cover;transition:transform .5s}
  .pcard:hover .pcard__media img{transform:scale(1.04)}
  .pcard__cat{
    position:absolute;top:12px;left:12px;
    background:rgba(255,255,255,.95);backdrop-filter:blur(6px);
    color:var(--brand);font-size:11.5px;font-weight:800;letter-spacing:.08em;
    text-transform:uppercase;padding:5px 10px;border-radius:999px;
  }
  html[dir="rtl"] .pcard__cat{left:auto;right:12px}
  .pcard__body{padding:22px 22px 24px;display:flex;flex-direction:column;gap:10px;flex:1}
  .pcard__meta{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--muted)}
  .pcard__meta .sep{opacity:.5}
  .pcard__body h3{font-size:18px;line-height:1.35}
  .pcard__body h3 a{color:inherit}
  .pcard__body h3 a:hover{color:var(--brand)}
  .pcard__body p{color:var(--ink-2);font-size:14.5px;flex:1}
  .pcard__more{
    margin-top:6px;display:inline-flex;align-items:center;gap:6px;font-weight:700;color:var(--brand);font-size:14px;
    align-self:flex-start;border-bottom:2px solid transparent;padding-bottom:2px;transition:.15s gap;
  }
  .pcard__more:hover{gap:10px;border-color:var(--brand)}
  html[dir="rtl"] .pcard__more svg{transform:scaleX(-1)}

  .empty{
    text-align:center;padding:64px 20px;color:var(--muted);
    border:1.5px dashed var(--line);border-radius:18px;display:none;
  }
  .empty.show{display:block}
"""

def render_listing():
    sorted_posts = sorted(POSTS, key=lambda p: p["date_iso"], reverse=True)
    cats = ["All"] + sorted({p["category"] for p in sorted_posts})

    chips_html = "".join(
        f'<button class="chip{ " is-active" if c=="All" else "" }" data-cat="{html.escape(c)}">'
        f'{ "<span data-i18n=\"blog.filter.all\">All</span>" if c=="All" else f"<span data-i18n=\"{cat_key(c)}\">{html.escape(c)}</span>" }'
        f'</button>'
        for c in cats
    )

    cards_html = "\n".join(
        f"""        <article class="pcard reveal" data-cat="{html.escape(p["category"])}" data-search="{html.escape(search_blob(p))}">
          <a href="blog/{p['slug']}.html" class="pcard__media">
            <img src="{p['cover'].replace('../assets/','assets/')}" alt="{html.escape(re.sub(r'<.*?>','',p['title']))}" loading="lazy"/>
            <span class="pcard__cat" data-i18n="{cat_key(p['category'])}">{html.escape(p['category'])}</span>
          </a>
          <div class="pcard__body">
            <div class="pcard__meta">
              <span>BENRO INDUSTRIES</span><span class="sep">·</span><time datetime="{p['date_iso']}" data-i18n="{post_key(p,'date')}">{html.escape(p['date_label'])}</time>
            </div>
            <h3><a href="blog/{p['slug']}.html" data-i18n-html="{post_key(p,'title')}">{p['title']}</a></h3>
            <p data-i18n="{post_key(p,'excerpt')}">{html.escape(p['excerpt'])}</p>
            <a href="blog/{p['slug']}.html" class="pcard__more"><span data-i18n="blog.readmore">Read article</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </a>
          </div>
        </article>"""
        for p in sorted_posts
    )
    listing_i18n = build_blog_i18n(sorted_posts)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Blog &amp; Events — Benro Industries · HVAC Insights</title>
<meta name="description" content="BENRO INDUSTRIES blog — technical guides, product spotlights and event recaps from Algeria's leading HVAC components manufacturer." />
<!-- Social SEO -->
<meta property="og:title" content="Benro Industries Blog — HVAC&amp;R Insights, Products &amp; Events" />
<meta property="og:description" content="BENRO INDUSTRIES blog — technical guides, product spotlights and event recaps from Algeria&#x27;s leading HVAC components manufacturer." />
<meta property="og:image" content="https://www.benroindustries.com/assets/images/benro-logo.png" />
<meta property="og:url" content="https://www.benroindustries.com/blog.html" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="Benro Industries Blog — HVAC&amp;R Insights, Products &amp; Events" />
<meta name="twitter:description" content="BENRO INDUSTRIES blog — technical guides, product spotlights and event recaps from Algeria&#x27;s leading HVAC components manufacturer." />
<meta name="twitter:image" content="https://www.benroindustries.com/assets/images/benro-logo.png" />
<link rel="canonical" href="https://www.benroindustries.com/blog.html" />
<!-- /Social SEO -->
<link rel="icon" type="image/png" href="assets/images/benro-logo.png" />
<style>{SHARED_CSS}{LISTING_EXTRA_CSS}</style>
</head>
<body>
<a href="#main-content" class="skip-link" data-i18n="a11y.skip">Skip to main content</a>

{topbar_html('')}

{header_html('', True)}

<!-- BREADCRUMB -->
<nav class="crumbs" aria-label="Breadcrumb">
  <div class="container crumbs__inner">
    <a href="index.html" data-i18n="crumb.home">Home</a>
    <span class="sep">›</span>
    <span class="current" data-i18n="crumb.blog">Blog</span>
  </div>
</nav>

<!-- BLOG HERO -->
<section class="bhero" id="main-content">
  <div class="container bhero__wrap">
    <span class="badge" data-i18n="blog.hero.eyebrow">BENRO Journal</span>
    <h1 data-i18n-html="blog.hero.title">Blogs <span class="accent">&amp; Events</span></h1>
    <p data-i18n="blog.hero.lead">Insights, technical guides and milestones from BENRO INDUSTRIES — HVAC components made in Algeria.</p>
  </div>
</section>

<!-- LIST -->
<section style="padding:56px 0 96px">
  <div class="container">
    <div class="toolbar">
      <div class="toolbar__filters" id="filters">
        {chips_html}
      </div>
      <label class="search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input id="search" type="search" placeholder="Search articles…" data-i18n-ph="blog.search.ph" aria-label="Search" />
      </label>
    </div>

    <div class="pgrid" id="pgrid">
{cards_html}
    </div>

    <div class="empty" id="empty" data-i18n="blog.empty">No article matches your search.</div>
  </div>
</section>

{footer_html('')}

<script>const BLOG_I18N={listing_i18n};
{I18N_JS}

/* Filter + search */
const filters = document.getElementById('filters');
const searchInput = document.getElementById('search');
const cards = [...document.querySelectorAll('.pcard')];
const empty = document.getElementById('empty');
let activeCat = 'All';
let activeQuery = '';

function refilter(){{
  let shown = 0;
  cards.forEach(c => {{
    const matchCat = activeCat === 'All' || c.dataset.cat === activeCat;
    const matchQ = !activeQuery || c.dataset.search.includes(activeQuery);
    const ok = matchCat && matchQ;
    c.style.display = ok ? '' : 'none';
    if (ok) shown++;
  }});
  empty.classList.toggle('show', shown === 0);
}}
filters.addEventListener('click', e => {{
  const b = e.target.closest('.chip'); if(!b) return;
  filters.querySelectorAll('.chip').forEach(x => x.classList.remove('is-active'));
  b.classList.add('is-active');
  activeCat = b.dataset.cat;
  refilter();
}});
searchInput.addEventListener('input', () => {{
  activeQuery = searchInput.value.trim().toLowerCase();
  refilter();
}});
</script>
</body>
</html>
"""

# ════════════════════════════════════════════════════════════════════
# ARTICLE PAGE (blog/<slug>.html)
# ════════════════════════════════════════════════════════════════════
ARTICLE_EXTRA_CSS = r"""
  .ahero{padding:48px 0 56px;background:radial-gradient(900px 480px at 90% -10%, rgba(228,89,17,.10), transparent 60%),linear-gradient(180deg,#fff 0%, var(--surface) 100%)}
  .ahero__wrap{max-width:820px;margin:0 auto;text-align:center}
  .ahero .badge{display:inline-flex}
  .ahero h1{margin-top:18px;line-height:1.18}
  .ahero .meta{margin-top:18px;color:var(--muted);font-size:14px}
  .ahero .meta .sep{margin:0 10px;opacity:.5}

  .hero-img{max-width:980px;margin:0 auto 0;padding:0 24px}
  .hero-img__inner{aspect-ratio:16/9;border-radius:20px;overflow:hidden;box-shadow:var(--shadow-lg);background:var(--surface-2);border:1px solid var(--line)}
  .hero-img__inner img{width:100%;height:100%;object-fit:cover}

  .article{max-width:820px;margin:0 auto;padding:64px 24px 48px;font-size:17px;color:var(--ink-2);line-height:1.85}
  .article h2{font-size:clamp(22px,2.4vw,30px);margin:48px 0 14px;color:var(--ink);letter-spacing:-.01em}
  .article h3{font-size:21px;margin:34px 0 10px;color:var(--ink)}
  .article h4{font-size:18px;margin:28px 0 8px;color:var(--ink)}
  .article p{margin:14px 0}
  .article p strong{color:var(--ink)}
  .article ul,.article ol{margin:14px 0 14px 0;padding-left:22px}
  html[dir="rtl"] .article ul,html[dir="rtl"] .article ol{padding-left:0;padding-right:22px}
  .article li{margin:8px 0}
  .article li::marker{color:var(--brand)}
  .article hr{border:0;border-top:1px solid var(--line);margin:36px 0}
  .article .note{
    background:linear-gradient(135deg,#fff7f0,#fffaf6);
    border:1px solid rgba(228,89,17,.2);border-left:4px solid var(--brand);
    border-radius:12px;padding:16px 20px;color:var(--ink);margin:24px 0;font-size:15.5px;
  }
  html[dir="rtl"] .article .note{border-left:0;border-right:4px solid var(--brand)}
  .article img.inline{margin:24px auto;border-radius:14px;border:1px solid var(--line);box-shadow:var(--shadow-sm);max-width:100%}

  .table-wrap{margin:24px 0;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--shadow-sm)}
  .table-scroll{overflow-x:auto}
  table.t{width:100%;border-collapse:collapse;min-width:520px}
  table.t th,table.t td{padding:13px 16px;text-align:left;font-size:14.5px;border-bottom:1px solid var(--line);color:var(--ink)}
  table.t th{background:var(--surface);color:var(--ink-2);font-weight:700;text-transform:uppercase;letter-spacing:.05em;font-size:12.5px}
  table.t tr:last-child td{border-bottom:0}
  table.t tr:hover td{background:var(--brand-50)}
  html[dir="rtl"] table.t th,html[dir="rtl"] table.t td{text-align:right}

  .gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;max-width:1100px;margin:0 auto 24px;padding:0 24px}
  .gallery a{display:block;aspect-ratio:4/3;border-radius:14px;overflow:hidden;background:var(--surface-2);border:1px solid var(--line);transition:.25s}
  .gallery a:hover{transform:translateY(-3px);box-shadow:var(--shadow-md)}
  .gallery img{width:100%;height:100%;object-fit:cover}

  .lightbox{position:fixed;inset:0;background:rgba(11,18,32,.92);display:none;align-items:center;justify-content:center;z-index:80;padding:24px}
  .lightbox.open{display:flex}
  .lightbox img{max-width:96vw;max-height:92vh;border-radius:10px;box-shadow:0 30px 80px rgba(0,0,0,.6)}
  .lightbox .close{position:absolute;top:18px;right:22px;width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,.12);color:#fff;display:flex;align-items:center;justify-content:center;font-size:24px;cursor:pointer;transition:.2s background}
  .lightbox .close:hover{background:rgba(255,255,255,.25)}

  .related{background:var(--surface);padding:72px 0 96px;margin-top:48px}
  .related__head{text-align:center;margin-bottom:36px}
  .related__head h2{font-size:26px}
  .rgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
  @media (max-width:900px){.rgrid{grid-template-columns:1fr}}
  .rcard{background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden;transition:.25s;display:flex;flex-direction:column}
  .rcard:hover{transform:translateY(-4px);box-shadow:var(--shadow-md)}
  .rcard__media{aspect-ratio:16/10;overflow:hidden}
  .rcard__media img{width:100%;height:100%;object-fit:cover;transition:transform .5s}
  .rcard:hover .rcard__media img{transform:scale(1.04)}
  .rcard__body{padding:20px 22px;display:flex;flex-direction:column;gap:8px}
  .rcard__meta{font-size:12.5px;color:var(--muted)}
  .rcard__body h3{font-size:16.5px;line-height:1.4}
  .rcard__body h3 a{color:inherit}.rcard__body h3 a:hover{color:var(--brand)}

  .backbar{padding:20px 0;border-bottom:1px solid var(--line)}
  .backbar__inner{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
  .back-link{display:inline-flex;align-items:center;gap:8px;color:var(--ink-2);font-weight:600;transition:color .15s}
  .back-link:hover{color:var(--brand)}
  html[dir="rtl"] .back-link svg{transform:scaleX(-1)}
  .share{display:flex;align-items:center;gap:10px;color:var(--muted);font-size:13.5px}
  .share a{width:36px;height:36px;border-radius:50%;background:var(--surface-2);color:var(--ink-2);display:inline-flex;align-items:center;justify-content:center;transition:.15s;border:1px solid var(--line)}
  .share a:hover{background:var(--brand);color:#fff;border-color:var(--brand);transform:translateY(-2px)}
  .share svg{width:16px;height:16px}
"""

def render_block(kind, payload):
    if kind == "p":
        return f"      <p>{payload}</p>\n"
    if kind in ("h2","h3","h4"):
        return f"      <{kind}>{payload}</{kind}>\n"
    if kind == "ul":
        return "      <ul>\n" + "".join(f"        <li>{i}</li>\n" for i in payload) + "      </ul>\n"
    if kind == "ol":
        return "      <ol>\n" + "".join(f"        <li>{i}</li>\n" for i in payload) + "      </ol>\n"
    if kind == "hr":
        return "      <hr/>\n"
    if kind == "img":
        return f'      <img class="inline" src="{payload}" loading="lazy" alt=""/>\n'
    if kind == "note":
        return f'      <div class="note">{payload}</div>\n'
    if kind == "table":
        thead = "".join(f"<th>{html.escape(h)}</th>" for h in payload["headers"])
        rows = ""
        for row in payload["rows"]:
            rows += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>\n"
        return (
            '      <div class="table-wrap">\n'
            '        <div class="table-scroll">\n'
            f'          <table class="t"><thead><tr>{thead}</tr></thead><tbody>{rows}</tbody></table>\n'
            "        </div>\n"
            "      </div>\n"
        )
    return ""

def render_article(post, all_posts):
    body_html = "".join(
        f'      <div data-i18n-html="{post_key(post, f"body.{i}")}">{render_block(k, v).strip()}</div>\n'
        for i, (k, v) in enumerate(post["body"])
    )

    # Gallery
    gallery_html = ""
    if post["gallery"]:
        items = "".join(
            f'      <a href="{src}" data-full="{src}"><img loading="lazy" src="{src}" alt=""/></a>\n'
            for src in post["gallery"]
        )
        gallery_html = f"""<section style="padding:0 0 16px">
  <div class="gallery">
{items}  </div>
</section>"""

    # Related (3 most recent excluding current, same language preferred)
    others = [p for p in all_posts if p["slug"] != post["slug"]]
    others.sort(key=lambda p: (p["lang"] != post["lang"], p["date_iso"]), reverse=True)
    related = sorted(others[:3], key=lambda p: p["date_iso"], reverse=True)
    related_html = "\n".join(
        f"""      <article class="rcard">
        <a class="rcard__media" href="{p['slug']}.html"><img src="{p['cover']}" alt="{html.escape(p['title'])}" loading="lazy"/></a>
        <div class="rcard__body">
          <div class="rcard__meta"><span data-i18n="{post_key(p,'category')}">{html.escape(p['category'])}</span> · <time datetime="{p['date_iso']}" data-i18n="{post_key(p,'date')}">{html.escape(p['date_label'])}</time></div>
          <h3><a href="{p['slug']}.html" data-i18n-html="{post_key(p,'title')}">{p['title']}</a></h3>
        </div>
      </article>"""
        for p in related
    )

    title_plain = re.sub(r"<.*?>", "", post["title"])
    article_schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": html.unescape(title_plain),
        "description": post["excerpt"],
        "image": "https://www.benroindustries.com/" + post["cover"].replace("../", ""),
        "datePublished": post["date_iso"],
        "dateModified": post["date_iso"],
        "author": {"@type": "Organization", "name": "Benro Industries"},
        "publisher": {
            "@type": "Organization",
            "name": "Benro Industries",
            "logo": {"@type": "ImageObject", "url": "https://www.benroindustries.com/assets/images/benro-logo.png"}
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"https://www.benroindustries.com/blog/{post['slug']}.html"},
        "articleSection": post["category"],
        "inLanguage": post["lang"]
    }
    article_json_ld = '<!-- JSON-LD: BlogPosting -->\n<script type="application/ld+json">\n' + json.dumps(article_schema, ensure_ascii=False, indent=2).replace('</', r'<\/') + '\n</script>'
    article_i18n = build_blog_i18n([post] + related, include_body_for=post)

    return f"""<!doctype html>
<html lang="{post['lang']}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title_plain} — Benro Industries</title>
<meta name="description" content="{html.escape(post['excerpt']).replace('"','&quot;')}" />
<!-- Social SEO -->
<meta property="og:title" content="{html.escape(html.unescape(title_plain) + ' — BENRO INDUSTRIES', quote=True)}" />
<meta property="og:description" content="{html.escape(post['excerpt'], quote=True)}" />
<meta property="og:image" content="https://www.benroindustries.com/assets/images/benro-logo.png" />
<meta property="og:url" content="https://www.benroindustries.com/blog/{post['slug']}.html" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{html.escape(html.unescape(title_plain) + ' — BENRO INDUSTRIES', quote=True)}" />
<meta name="twitter:description" content="{html.escape(post['excerpt'], quote=True)}" />
<meta name="twitter:image" content="https://www.benroindustries.com/assets/images/benro-logo.png" />
<link rel="canonical" href="https://www.benroindustries.com/blog/{post['slug']}.html" />
<!-- /Social SEO -->
{article_json_ld}
<link rel="icon" type="image/png" href="../assets/images/benro-logo.png" />
<style>{SHARED_CSS}{ARTICLE_EXTRA_CSS}</style>
</head>
<body>
<a href="#main-content" class="skip-link" data-i18n="a11y.skip">Skip to main content</a>

{topbar_html('../')}

{header_html('../', True)}

<!-- BREADCRUMB -->
<nav class="crumbs" aria-label="Breadcrumb">
  <div class="container crumbs__inner">
    <a href="../index.html" data-i18n="crumb.home">Home</a>
    <span class="sep">›</span>
    <a href="../blog.html" data-i18n="crumb.blog">Blog</a>
    <span class="sep">›</span>
    <span class="current" data-i18n-html="{post_key(post,'title')}">{title_plain}</span>
  </div>
</nav>

<!-- ARTICLE HERO -->
<section class="ahero" id="main-content">
  <div class="container ahero__wrap reveal">
    <span class="badge" data-i18n="{post_key(post,'category')}">{html.escape(post['category'])}</span>
    <h1 data-i18n-html="{post_key(post,'title')}">{post['title']}</h1>
    <div class="meta">BENRO INDUSTRIES<span class="sep">·</span><time datetime="{post['date_iso']}" data-i18n="{post_key(post,'date')}">{html.escape(post['date_label'])}</time></div>
  </div>
</section>

<!-- HERO IMAGE -->
<div class="hero-img">
  <div class="hero-img__inner reveal">
    <img src="{post['cover']}" alt="{html.escape(title_plain)}"/>
  </div>
</div>

<!-- ARTICLE BODY -->
<article class="article reveal">
{body_html}</article>

{gallery_html}

<!-- BACK / SHARE bar -->
<div class="container">
  <div class="backbar">
    <div class="backbar__inner">
      <a class="back-link" href="../blog.html">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
        <span data-i18n="blog.back">Back to blog</span>
      </a>
      <div class="share">
        <span data-i18n="blog.share">Share this article</span>
        <a href="https://wa.me/?text={html.escape(title_plain).replace(' ','%20')}" target="_blank" rel="noopener" aria-label="WhatsApp"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 14.4c-.3-.1-1.8-.9-2-1s-.5-.1-.7.1c-.2.3-.8 1-1 1.2-.2.2-.4.2-.7.1-.3-.1-1.3-.5-2.5-1.5-.9-.8-1.6-1.8-1.7-2.1-.2-.3 0-.5.1-.6.1-.1.3-.4.4-.5.1-.2.2-.3.3-.5.1-.2.1-.4 0-.5-.1-.2-.7-1.6-.9-2.2-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.4 0 1.4 1 2.8 1.2 3 .1.2 2 3.1 4.9 4.3.7.3 1.2.5 1.6.6.7.2 1.3.2 1.8.1.5-.1 1.7-.7 2-1.4.2-.7.2-1.2.2-1.4-.1-.1-.3-.2-.6-.3zM12 0C5.4 0 0 5.4 0 12c0 2.1.6 4.1 1.6 5.9L0 24l6.3-1.6c1.7.9 3.7 1.5 5.7 1.5 6.6 0 12-5.4 12-12S18.6 0 12 0z"/></svg></a>
        <a href="#" onclick="navigator.clipboard.writeText(location.href).then(()=>{{this.classList.add('done')}});return false" aria-label="Copy link"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg></a>
        <a href="https://www.linkedin.com/sharing/share-offsite/?url={ '' }" target="_blank" rel="noopener" aria-label="LinkedIn"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.94v5.67H9.36V9h3.41v1.56h.05a3.74 3.74 0 0 1 3.37-1.85c3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zm-1.78 13.02h3.55V9H3.56v11.45z"/></svg></a>
      </div>
    </div>
  </div>
</div>

<!-- RELATED -->
<section class="related">
  <div class="container">
    <div class="related__head reveal">
      <h2 data-i18n="blog.recent">You may also like</h2>
    </div>
    <div class="rgrid">
{related_html}
    </div>
  </div>
</section>

{footer_html('../')}

<!-- Lightbox -->
<div class="lightbox" id="lb" role="dialog" aria-modal="true">
  <button class="close" id="lbClose" aria-label="Close">×</button>
  <img id="lbImg" alt=""/>
</div>

<script>const BLOG_I18N={article_i18n};
{I18N_JS}

const lb=document.getElementById('lb'),lbImg=document.getElementById('lbImg'),lbClose=document.getElementById('lbClose');
document.querySelectorAll('.gallery a').forEach(a=>{{
  a.addEventListener('click',e=>{{e.preventDefault();lbImg.src=a.dataset.full||a.querySelector('img').src;lb.classList.add('open');document.body.style.overflow='hidden'}});
}});
const lbExit=()=>{{lb.classList.remove('open');document.body.style.overflow='';lbImg.src=''}};
lbClose.addEventListener('click',lbExit);
lb.addEventListener('click',e=>{{if(e.target===lb) lbExit()}});
document.addEventListener('keydown',e=>{{if(e.key==='Escape') lbExit()}});
</script>
</body>
</html>
"""

# ════════════════════════════════════════════════════════════════════
# WRITE EVERYTHING
# ════════════════════════════════════════════════════════════════════

# Listing
listing_html = apply_responsive_images(apply_shared_js(apply_shared_css(render_listing(), "assets/css/shared.css"), "assets/js/shared.js", "/* Filter + search */"), pathlib.Path("blog.html"))
pathlib.Path("blog.html").write_text(listing_html, encoding="utf-8")
print(f"  ✓ blog.html  ({len(listing_html):,} bytes)")

# Articles
for p in POSTS:
    out = BLOG_DIR / f"{p['slug']}.html"
    out.write_text(apply_responsive_images(apply_shared_js(apply_shared_css(render_article(p, POSTS), "../assets/css/shared.css"), "../assets/js/shared.js", "const lb="), out), encoding="utf-8")
    print(f"  ✓ {out}  ({out.stat().st_size:,} bytes)")

print(f"\nGenerated 1 listing + {len(POSTS)} article pages.")
