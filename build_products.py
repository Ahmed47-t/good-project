#!/usr/bin/env python3
"""
BENRO INDUSTRIES — Phase 2 generator
Builds 6 technical-datasheet HTML pages under /products/ from a single template
and a structured product catalogue extracted from the live site.

Run:  python3 build_products.py
"""

import json, os, html, re, pathlib

OUT_DIR = pathlib.Path("products")
OUT_DIR.mkdir(exist_ok=True)

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

# -------------------------------------------------------------------
# PRODUCT CATALOGUE  (extracted verbatim from benroindustries.com)
# -------------------------------------------------------------------
PRODUCTS = [
    {
        "slug": "twin-insulated-copper",
        "tag": "HVAC Kit",
        "hero_img": "../assets/images/insulated-copper-tubes.png",
        "title": "Twin Insulated Copper Tubes",
        "short": "This insulated copper tube consists of twin seamless annealed copper with PE insulation.",
        "intro_heading": "BENRO INDUSTRIES®️ Insulated Copper Tubes",
        "intro": (
            "BENRO INDUSTRIES Insulated copper connection lines represent a significant advancement in HVAC "
            "connectivity. Manufactured according to EN 12735-1 (C12200 copper), these high-value products consist "
            "of twin seamless annealed copper tubes with PE insulation, offering superior performance compared to "
            "traditional insulation methods for split air conditioner installations (9000 BTU to 48000 BTU)."
        ),
        "benefits": [
            ("Maximized Energy Efficiency",
             "Continuous energy savings are achieved through the high-performance PE insulation, which effectively "
             "limits energy transfer and maintains proper sub-cooling values. Thermal conductivity 0.0402 W/m·K, "
             "tensile strength 0.36 MPa, tear strength 0.19 N/mm."),
            ("Enhanced Operational Safety",
             "Ensures safe and reliable split air conditioner system operation."),
            ("Reduced Installation Time & Costs",
             "The lightly linked twin tubes allow for easy separation during installation, simplifying the process "
             "and lowering labor expenses."),
            ("Exceptional Durability",
             "The C12200 copper tubing (CuDHP > 99.90%, soft temper) offers high resistance to mechanical stress, "
             "while the PE insulation protects against chemical agents and UV rays. Heat resistance: no obvious color "
             "change or cracking after 6 hours at 70 ℃, elongation at break ≥ 60%."),
            ("Flexible Application",
             "Suitable for connecting various split air conditioner units (9000, 12000, 18000, 24000, 48000 BTU)."),
            ("Weather Resistance",
             "The robust insulation withstands extreme atmospheric conditions."),
        ],
        "spec_groups": [
            ("Copper Tubing", [
                ("Alloy", "Non-alloy"),
                ("Material", "C12200 (CuDHP > 99.90%)"),
                ("Temper", "Soft temper"),
                ("Standard", "EN 12735-1"),
            ]),
            ("Insulation", [
                ("Material", "PE (Polyethylene)"),
                ("Apparent Density", "30 kg/m³"),
                ("Wall Thickness", "8 – 12 mm"),
                ("Thermal Conductivity", "0.0402 W/m·K"),
                ("Tensile Strength", "0.36 MPa"),
                ("Tear Strength", "0.19 N/mm"),
                ("Water Absorption", "33.28%"),
                ("Color", "White"),
                ("Heat Resistance", "No obvious color change or cracking after 6 h at 70 ℃"),
                ("Elongation at Break", "≥ 60%"),
            ]),
        ],
        "tables": [
            {
                "title": "Dimensions",
                "headers": ["Outside Ø (inch)", "Outside Ø (mm)", "Wall Thickness (mm)",
                            "Tube Length (m)", "Type of insulation", "Ending"],
                "rows": [
                    ["1/4 × 3/8", "6.35 × 9.52", "0.6 – 1.25", "2 – 50", "IXPE Covered / Single layer", "Brass nut or cap"],
                    ["1/4 × 1/2", "6.35 × 12.7", "0.6 – 1.25", "2 – 50", "IXPE Covered / Single layer", "Brass nut or cap"],
                    ["1/4 × 5/8", "6.35 × 15.88","0.6 – 1.25", "2 – 50", "IXPE Covered / Single layer", "Brass nut or cap"],
                    ["3/8 × 5/8", "9.52 × 15.88","0.6 – 1.25", "2 – 50", "IXPE Covered / Single layer", "Brass nut or cap"],
                    ["3/8 × 3/4", "9.52 × 19.05","0.6 – 1.25", "2 – 50", "IXPE Covered / Single layer", "Brass nut or cap"],
                    ["1/2 × 3/4", "12.7 × 19.05","0.6 – 1.25", "2 – 50", "IXPE Covered / Single layer", "Brass nut or cap"],
                ],
            },
        ],
        "gallery": [
            "../assets/images/insulated-copper-tubes.png",
            "../assets/images/gallery-coil-roll.jpg",
            "../assets/images/gallery-bundle.jpg",
            "../assets/images/gallery-installed.jpg",
            "../assets/images/quality.jpg",
        ],
    },

    # -------- PRODUCT 2 --------
    {
        "slug": "single-insulated-copper",
        "tag": "HVAC Kit",
        "hero_img": "../assets/images/single-insulated.png",
        "title": "Single Insulated Copper Tubes",
        "short": "This insulated copper tube consists of single seamless annealed copper with PE insulation.",
        "intro_heading": "BENRO INDUSTRIES®️ Single Insulated Copper Tubes",
        "intro": (
            "BENRO INDUSTRIES Insulated copper connection lines represent a significant advancement in HVAC "
            "connectivity. Manufactured according to EN 12735-1 (C12200 copper), these high-value products consist "
            "of single seamless annealed copper tubes with PE/NBR insulation, offering superior performance compared "
            "to traditional insulation methods for split air conditioner installations (9000 BTU to 48000 BTU)."
        ),
        "benefits": [
            ("Maximized Energy Efficiency",
             "High-performance PE insulation effectively limits energy transfer and maintains proper sub-cooling values. "
             "Thermal conductivity 0.0402 W/m·K, tensile strength 0.36 MPa, tear strength 0.19 N/mm."),
            ("Enhanced Operational Safety",
             "Ensures safe and reliable split air conditioner system operation."),
            ("Reduced Installation Time & Costs",
             "Sold per length or custom-cut for installers — simpler logistics, faster commissioning."),
            ("Exceptional Durability",
             "C12200 copper (CuDHP > 99.90%, soft temper) with PE insulation that resists chemicals and UV rays. "
             "Heat resistance: no obvious color change or cracking after 6 h at 70 ℃, elongation at break ≥ 60%."),
            ("Flexible Application",
             "Suitable for 9000 / 12000 / 18000 / 24000 / 48000 BTU split AC units."),
            ("Weather Resistance",
             "Robust insulation withstands extreme atmospheric conditions."),
        ],
        "spec_groups": [
            ("Copper Tubing", [
                ("Alloy", "Non-alloy"),
                ("Material", "C12200 (CuDHP > 99.90%)"),
                ("Temper", "Soft temper"),
                ("Standard", "EN 12735-1"),
            ]),
            ("Insulation", [
                ("Material", "PE (Polyethylene)"),
                ("Apparent Density", "30 kg/m³"),
                ("Wall Thickness", "8 – 12 mm"),
                ("Thermal Conductivity", "0.0402 W/m·K"),
                ("Tensile Strength", "0.36 MPa"),
                ("Tear Strength", "0.19 N/mm"),
                ("Water Absorption", "33.28%"),
                ("Color", "White / Gray"),
                ("Heat Resistance", "No obvious color change or cracking after 6 h at 70 ℃"),
                ("Elongation at Break", "≥ 60%"),
            ]),
        ],
        "tables": [
            {
                "title": "Dimensions",
                "headers": ["Outside Ø (inch)", "Outside Ø (mm)", "Wall Thickness (mm)",
                            "Tube Length (m)", "Type of insulation", "Ending"],
                "rows": [
                    ["1/4", "6.35", "0.6 – 1.25", "1 – 50", "IXPE Covered / Single layer", "Brass nut or cap"],
                    ["3/8", "9.52", "0.6 – 1.25", "1 – 50", "IXPE Covered / Single layer", "Brass nut or cap"],
                    ["1/2", "12.7", "0.6 – 1.25", "1 – 50", "IXPE Covered / Single layer", "Brass nut or cap"],
                    ["5/8", "15.88","0.6 – 1.25", "1 – 50", "IXPE Covered / Single layer", "Brass nut or cap"],
                    ["3/4", "19.05","0.6 – 1.25", "1 – 50", "IXPE Covered / Single layer", "Brass nut or cap"],
                ],
            },
        ],
        "gallery": [
            "../assets/images/single-insulated.png",
            "../assets/images/gallery-coil-roll.jpg",
            "../assets/images/gallery-bundle.jpg",
            "../assets/images/gallery-installed.jpg",
            "../assets/images/quality.jpg",
        ],
    },

    # -------- PRODUCT 3 --------
    {
        "slug": "twin-insulated-aluminium",
        "tag": "Lightweight",
        "hero_img": "../assets/images/twin-aluminium.png",
        "title": "Twin Insulated Aluminium Tubes",
        "short": "This insulated Aluminium tube consists of twin seamless annealed Aluminium with PE insulation.",
        "intro_heading": "BENRO INDUSTRIES®️ Aluminium Tubes",
        "intro": (
            "BENRO INDUSTRIES Insulated Aluminium connection lines represent a significant advancement in HVAC "
            "connectivity. These high-value products consist of twin seamless annealed Aluminium tubes with PE "
            "insulation, offering superior performance compared to traditional insulation methods for split air "
            "conditioner installations (9000 BTU to 48000 BTU)."
        ),
        "benefits": [
            ("Maximized Energy Efficiency",
             "High-performance PE insulation, thermal conductivity 0.0402 W/m·K, tensile strength 0.36 MPa, "
             "tear strength 0.19 N/mm."),
            ("Enhanced Operational Safety",
             "Safe and reliable split AC system operation."),
            ("Reduced Installation Time & Costs",
             "Lightly linked twin tubes allow for easy separation during installation."),
            ("Exceptional Durability",
             "PE insulation protects against chemical agents and UV rays. Heat resistance: no obvious color change or "
             "cracking after 6 h at 70 ℃, elongation at break ≥ 60%."),
            ("Flexible Application",
             "Suitable for 9000 / 12000 / 18000 / 24000 / 48000 BTU split AC units."),
            ("Weather Resistance",
             "Withstands extreme atmospheric conditions."),
        ],
        "spec_groups": [
            ("Aluminium Tubing", [
                ("Alloy", "Non-alloy"),
                ("Material", "1070 series"),
                ("Temper", "Soft temper"),
            ]),
            ("Insulation", [
                ("Material", "PE (Polyethylene)"),
                ("Apparent Density", "30 kg/m³"),
                ("Wall Thickness", "8 – 12 mm"),
                ("Thermal Conductivity", "0.0402 W/m·K"),
                ("Tensile Strength", "0.36 MPa"),
                ("Tear Strength", "0.19 N/mm"),
                ("Water Absorption", "33.28%"),
                ("Color", "White"),
                ("Heat Resistance", "No obvious color change or cracking after 6 h at 70 ℃"),
                ("Elongation at Break", "≥ 60%"),
            ]),
        ],
        "tables": [
            {
                "title": "Dimensions",
                "headers": ["Outside Ø (inch)", "Outside Ø (mm)", "Wall Thickness (mm)",
                            "Tube Length (m)", "Type of insulation", "Ending"],
                "rows": [
                    ["1/4 × 3/8", "6.35 × 9.52", "0.8 – 1.25", "3 – 5", "IXPE Covered / Single layer", "Brass nut"],
                    ["1/4 × 1/2", "6.35 × 12.7", "0.8 – 1.25", "3 – 5", "IXPE Covered / Single layer", "Brass nut"],
                    ["1/4 × 5/8", "6.35 × 15.88","0.8 – 1.25", "3 – 5", "IXPE Covered / Single layer", "Brass nut"],
                    ["3/8 × 5/8", "9.52 × 15.88","0.8 – 1.25", "3 – 5", "IXPE Covered / Single layer", "Brass nut"],
                    ["3/8 × 3/4", "9.52 × 19.05","0.8 – 1.25", "3 – 5", "IXPE Covered / Single layer", "Brass nut"],
                    ["1/2 × 3/4", "12.7 × 19.05","0.8 – 1.25", "3 – 5", "IXPE Covered / Single layer", "Brass nut"],
                ],
            },
        ],
        "gallery": [
            "../assets/images/twin-aluminium.png",
            "../assets/images/gallery-aluminium-detail.png",
            "../assets/images/gallery-coil-roll.jpg",
            "../assets/images/gallery-bundle.jpg",
            "../assets/images/quality.jpg",
        ],
    },

    # -------- PRODUCT 4 --------
    {
        "slug": "insulation-polyethylene",
        "tag": "Insulation",
        "hero_img": "../assets/images/twin-pe-tubes.png",
        "title": "Insulation Polyethylene Tubes",
        "short": "BENRO INDUSTRIES offers its range of refrigeration insulation for ACR tubes.",
        "intro_heading": "Twin Insulation Polyethylene Tubes",
        "intro": (
            "BENRO INDUSTRIES specializes in the manufacturing of polyethylene foam tubes for the insulation of ACR "
            "(Air Conditioning and Refrigeration) tubes and other industrial applications. Polyethylene foam has a "
            "straight-bond structure and is produced through an extrusion method with chemical and inflator-gas "
            "addition. PE foam features low thermal conductivity and a closed-cell structure, giving it high water-vapor "
            "diffusion resistance."
        ),
        "secondary_heading": "BENRO-FLEX Insulation",
        "secondary": (
            "While the well-known Arma-flex brand primarily uses elastomeric nitrile rubber foam, polyethylene (PE) foam "
            "is a versatile and widely used material in pipe insulation, particularly for cooling systems. Our "
            "BENRO-FLEX product line is proudly produced using high-quality PE foam, offering a cost-effective and "
            "environmentally responsible solution for cooling insulation. BENRO-FLEX PE foam provides excellent thermal "
            "performance, minimizing energy loss in refrigerant lines and maximizing efficiency. Its closed-cell "
            "structure ensures resistance to moisture and water vapor, preventing condensation and corrosion."
        ),
        "benefits": [
            ("Ease and Speed of Application",
             "Highly flexible material allows for quick and easy installation, reducing labor time and costs."),
            ("Water and Moisture Resistance",
             "Closed-cell structure prevents water and moisture absorption — long-term performance, no corrosion or mold."),
            ("Chemical and Environmental Resistance",
             "Unaffected by chemicals and environmental conditions — durability and longevity across applications."),
            ("Eco-Friendly & Hygienic Solution",
             "Manufactured from recyclable PE, without HCFCs or harmful chemicals. Prevents fungi, bacteria and mold; odorless."),
            ("Superior Thermal Insulation",
             "Low thermal conductivity provides excellent insulation — minimizes energy loss and maximizes efficiency."),
            ("Impact Resistance & Condensation Prevention",
             "Recovers after impact, preventing damage and condensation buildup."),
            ("Sound and Heat Insulation",
             "Provides both thermal and acoustic insulation."),
            ("Oil Resistance",
             "Good resistance to oils, suitable where oil exposure is a concern."),
        ],
        "spec_groups": [
            ("Insulation", [
                ("Material", "PE (Polyethylene)"),
                ("Apparent Density", "30 kg/m³"),
                ("Wall Thickness", "8 – 12 mm"),
                ("Thermal Conductivity", "0.0402 W/m·K"),
                ("Tensile Strength", "0.36 MPa"),
                ("Tear Strength", "0.19 N/mm"),
                ("Water Absorption", "33.28%"),
                ("Color", "White / Gray"),
                ("Heat Resistance", "No obvious color change or cracking after 6 h at 70 ℃"),
                ("Elongation at Break", "≥ 60%"),
            ]),
        ],
        "tables": [
            {
                "title": "Dimensions — Twin Insulation Polyethylene Tubes",
                "headers": ["Size", "Inside Ø (mm)", "Thickness (mm)", "Tube Length (m)", "Type of insulation", "Packaging"],
                "rows": [
                    ["1/4 × 3/8", "8 × 12", "8 – 19", "1 – 200", "IXPE Covered / Single layer", "Plastic Bag"],
                    ["1/4 × 1/2", "8 × 15", "8 – 19", "1 – 200", "IXPE Covered / Single layer", "Plastic Bag"],
                    ["1/4 × 5/8", "8 × 18", "8 – 19", "1 – 200", "IXPE Covered / Single layer", "Plastic Bag"],
                    ["3/8 × 5/8", "12 × 18","8 – 19", "1 – 200", "IXPE Covered / Single layer", "Plastic Bag"],
                    ["3/8 × 3/4", "12 × 22","8 – 19", "1 – 200", "IXPE Covered / Single layer", "Plastic Bag"],
                    ["1/2 × 3/4", "15 × 22","8 – 19", "1 – 200", "IXPE Covered / Single layer", "Plastic Bag"],
                ],
            },
            {
                "title": "Dimensions — BENRO-FLEX",
                "headers": ["Size", "Inside Ø (mm)", "Thickness (mm)", "Tube Length (m)", "Packaging"],
                "rows": [
                    ["1/4", "8",  "8 – 19", "50", "Carton"],
                    ["3/8", "12", "8 – 19", "45", "Carton"],
                    ["1/2", "15", "8 – 19", "40", "Carton"],
                    ["5/8", "18", "8 – 19", "30", "Carton"],
                    ["3/4", "22", "8 – 19", "26", "Carton"],
                ],
            },
        ],
        "gallery": [
            "../assets/images/twin-pe-tubes.png",
            "../assets/images/gallery-pe-ixpe.png",
            "../assets/images/gallery-pe-coil.png",
            "../assets/images/gallery-benroflex.png",
            "../assets/images/gallery-benroflex-2.png",
            "../assets/images/gallery-pe-bundle.png",
        ],
    },

    # -------- PRODUCT 5 --------
    {
        "slug": "copper-tubes",
        "tag": "Raw material",
        "hero_img": "../assets/images/copper-tubes.png",
        "title": "Copper Tubes (Pancake)",
        "short": "This seamless drawn copper tube is commonly used in ACR installations.",
        "intro_heading": "BENRO INDUSTRIES®️ Copper Tubes",
        "intro": (
            "BENRO INDUSTRIES copper connection lines represent a significant advancement in HVAC connectivity, "
            "manufactured according to EN 12735-1 (C12200 copper). This seamless drawn copper tube is commonly used "
            "in ACR installations. Coiled in helical form and protected with caps at the ends, it is available in "
            "different sizes, thicknesses and lengths."
        ),
        "benefits": [
            ("Enhanced Operational Safety",
             "Ensures safe and reliable split air conditioner system operation."),
            ("Exceptional Durability",
             "C12200 copper tubing (CuDHP > 99.90%, soft temper) offers high resistance to mechanical stress; PE/NBR "
             "insulation protects against chemical agents and UV rays. Heat resistance: no obvious color change or "
             "cracking after 6 h at 70 ℃, elongation at break ≥ 60%."),
            ("Flexible Application",
             "Suitable for 9000 / 12000 / 18000 / 24000 / 48000 BTU split AC units."),
        ],
        "spec_groups": [
            ("Copper Tubing", [
                ("Alloy", "Non-alloy"),
                ("Material", "C12200 (CuDHP > 99.90%)"),
                ("Temper", "Soft temper"),
                ("Standard", "EN 12735-1"),
            ]),
        ],
        "tables": [
            {
                "title": "Dimensions",
                "headers": ["Outside Ø (inch)", "Outside Ø (mm)", "Wall Thickness (mm)", "Tube Length (m)", "Ending"],
                "rows": [
                    ["1/4", "6.35", "0.6 – 1.25", "10 – 50", "Cap"],
                    ["3/8", "9.52", "0.6 – 1.25", "10 – 50", "Cap"],
                    ["1/2", "12.7", "0.6 – 1.25", "10 – 50", "Cap"],
                    ["5/8", "15.88","0.6 – 1.25", "10 – 50", "Cap"],
                    ["3/4", "19.05","0.6 – 1.25", "10 – 50", "Cap"],
                ],
            },
        ],
        "gallery": [
            "../assets/images/copper-tubes.png",
            "../assets/images/gallery-copper-coils.jpg",
            "../assets/images/gallery-coil-roll.jpg",
            "../assets/images/gallery-bundle.jpg",
            "../assets/images/quality.jpg",
        ],
    },

    # -------- PRODUCT 6 --------
    {
        "slug": "polyethylene-tubes",
        "tag": "PE Foam",
        "hero_img": "../assets/images/pe-tubes.png",
        "title": "Polyethylene Tubes (PE Foam)",
        "short": "BENRO INDUSTRIES offers its range of insulation PE tubes.",
        "intro_heading": "BENRO INDUSTRIES®️ Polyethylene Rod Tubes",
        "intro": (
            "BENRO INDUSTRIES manufactures extruded polyethylene tubes — commonly known as backer rods — used in "
            "construction to fill expansion and sealant joints. They provide support for sealants, ensuring uniform "
            "application and optimal joint performance."
        ),
        "secondary_heading": "BENRO INDUSTRIES®️ Polyethylene Net",
        "secondary": (
            "Extruded from polyethylene resin, BENRO INDUSTRIES' PE net tubes are manufactured using a continuous "
            "extrusion process that creates a seamless tubular mesh. This structure provides cushioning, ventilation "
            "and visibility for packaged products. The netting's flexibility lets it conform to the shape of the "
            "product, providing a secure and protective fit."
        ),
        "benefits": [
            ("Ease and Speed of Application",
             "Highly flexible material allows for quick and easy installation, reducing labor time and costs."),
            ("Water and Moisture Resistance",
             "Closed-cell structure prevents water and moisture absorption — long-term performance, no corrosion or mold."),
            ("Chemical and Environmental Resistance",
             "Unaffected by chemicals and environmental conditions."),
            ("Eco-Friendly & Hygienic Solution",
             "Recyclable PE, manufactured without HCFCs or harmful chemicals; prevents fungi, bacteria and mold; odorless."),
            ("Superior Thermal Insulation",
             "Low thermal conductivity — minimizes energy loss and maximizes efficiency."),
            ("Impact Resistance & Condensation Prevention",
             "Recovers after impact, preventing damage and condensation buildup."),
            ("Sound and Heat Insulation",
             "Provides both thermal and acoustic insulation."),
            ("Oil Resistance",
             "Good resistance to oils."),
        ],
        "spec_groups": [
            ("Insulation", [
                ("Material", "PE (Polyethylene)"),
                ("Apparent Density", "30 kg/m³"),
                ("Wall Thickness", "8 – 12 mm"),
                ("Thermal Conductivity", "0.0402 W/m·K"),
                ("Tensile Strength", "0.36 MPa"),
                ("Tear Strength", "0.19 N/mm"),
                ("Water Absorption", "33.28%"),
                ("Color", "White / Gray"),
                ("Heat Resistance", "No obvious color change or cracking after 6 h at 70 ℃"),
                ("Elongation at Break", "≥ 60%"),
            ]),
        ],
        "tables": [
            {
                "title": "Dimensions — Polyethylene Tubes",
                "headers": ["Type", "Outside Ø (mm)", "Inside Ø (mm)", "Length (m)", "Packaging"],
                "rows": [
                    ["PE Pipe", "10 – 100", "0 – 80", "1 – 200", "Plastic Bag"],
                    ["PE Rod",  "10 – 80",  "/",     "1 – 200", "Plastic Bag"],
                    ["PE Neon", "33",       "28",    "/",       "Plastic Bag"],
                    ["PE Net",  "47",       "/",     "1 – 200", "Plastic Bag"],
                ],
            },
        ],
        "gallery": [
            "../assets/images/pe-tubes.png",
            "../assets/images/gallery-pe-foam-stack.png",
            "../assets/images/gallery-pe-neon.png",
            "../assets/images/gallery-pe-net.png",
            "../assets/images/gallery-pe-net-2.png",
        ],
    },
]


# -------------------------------------------------------------------
# PRODUCT CONTENT I18N CACHE (EN/FR/AR)
# -------------------------------------------------------------------
PRODUCT_I18N_PATH = pathlib.Path("product_i18n_cache.json")
try:
    PRODUCT_I18N_CACHE = json.loads(PRODUCT_I18N_PATH.read_text(encoding="utf-8")) if PRODUCT_I18N_PATH.exists() else {}
except Exception:
    PRODUCT_I18N_CACHE = {}
PRODUCT_I18N_CACHE.pop("_memory", None)
LANGS = ("en", "fr", "ar")

def prod_key(product, field):
    return f"prod.{product['slug']}.{field}"

def product_i18n(product):
    data={lang:{} for lang in LANGS}
    slug=product['slug']
    for lang in LANGS:
        d=PRODUCT_I18N_CACHE.get(slug,{}).get(lang,{})
        for f in ['tag','title','short','intro_heading','intro','secondary_heading','secondary']:
            data[lang][prod_key(product,f)] = d.get(f, product.get(f,''))
        for i,(t,desc) in enumerate(product['benefits']):
            bt = d.get('benefits', [])
            data[lang][prod_key(product,f'benefits.{i}.title')] = bt[i][0] if i < len(bt) else t
            data[lang][prod_key(product,f'benefits.{i}.desc')] = bt[i][1] if i < len(bt) else desc
        sg = d.get('spec_groups', [])
        for gi,(gt,rows) in enumerate(product['spec_groups']):
            data[lang][prod_key(product,f'spec_groups.{gi}.title')] = sg[gi][0] if gi < len(sg) else gt
            trans_rows = sg[gi][1] if gi < len(sg) else []
            for ri,(k,v) in enumerate(rows):
                data[lang][prod_key(product,f'spec_groups.{gi}.rows.{ri}.key')] = trans_rows[ri][0] if ri < len(trans_rows) else k
                data[lang][prod_key(product,f'spec_groups.{gi}.rows.{ri}.val')] = trans_rows[ri][1] if ri < len(trans_rows) else v
        tb = d.get('tables', [])
        for ti,t in enumerate(product['tables']):
            tt = tb[ti] if ti < len(tb) else {}
            data[lang][prod_key(product,f'tables.{ti}.title')] = tt.get('title', t['title'])
            headers = tt.get('headers', [])
            for hi,h in enumerate(t['headers']):
                data[lang][prod_key(product,f'tables.{ti}.headers.{hi}')] = headers[hi] if hi < len(headers) else h
            rows = tt.get('rows', [])
            for ri,row in enumerate(t['rows']):
                for ci,c in enumerate(row):
                    data[lang][prod_key(product,f'tables.{ti}.rows.{ri}.{ci}')] = rows[ri][ci] if ri < len(rows) and ci < len(rows[ri]) else c
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

# -------------------------------------------------------------------
# HTML TEMPLATE
# -------------------------------------------------------------------
TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title} — Benro Industries · Technical Datasheet</title>
<meta name="description" content="{short_meta}" />
<!-- Social SEO -->
<meta property="og:title" content="{seo_title}" />
<meta property="og:description" content="{seo_desc}" />
<meta property="og:image" content="https://www.benroindustries.com/assets/images/benro-logo.png" />
<meta property="og:url" content="{canonical_url}" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{seo_title}" />
<meta name="twitter:description" content="{seo_desc}" />
<meta name="twitter:image" content="https://www.benroindustries.com/assets/images/benro-logo.png" />
<link rel="canonical" href="{canonical_url}" />
<!-- /Social SEO -->
{product_json_ld}
<link rel="icon" type="image/png" href="../assets/images/benro-logo.png" />
<style>
  :root{{
    --brand:#E45911; --brand-600:#c84a09; --brand-50:#FFF1E9;
    --ink:#1F2937; --ink-2:#3D4F5F; --muted:#5A6577;
    --line:#E7EBEE; --surface:#FBFBFC; --surface-2:#F3F5F7;
    --white:#fff;
    --shadow-sm:0 1px 2px rgba(17,24,39,.04), 0 1px 3px rgba(17,24,39,.06);
    --shadow-md:0 8px 24px -8px rgba(17,24,39,.12), 0 4px 8px -4px rgba(17,24,39,.08);
    --shadow-lg:0 24px 48px -16px rgba(17,24,39,.18);
    --container:1240px;
    --font:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  }}
  *,*::before,*::after{{box-sizing:border-box}}
  html{{scroll-behavior:smooth;-webkit-text-size-adjust:100%}}
  body{{margin:0;font-family:var(--font);color:var(--ink);background:#fff;line-height:1.65;-webkit-font-smoothing:antialiased;overflow-x:hidden}}
  img{{max-width:100%;display:block;height:auto}}
  a{{color:inherit;text-decoration:none}}
  button{{font-family:inherit;cursor:pointer;border:0;background:none}}
  .container{{max-width:var(--container);margin:0 auto;padding:0 24px}}
  h1,h2,h3,h4{{margin:0;line-height:1.18;letter-spacing:-0.02em;font-weight:800;color:var(--ink)}}
  h1{{font-size:clamp(32px,4.4vw,52px)}}
  h2{{font-size:clamp(24px,2.6vw,34px)}}
  h3{{font-size:18px;font-weight:700;letter-spacing:-0.01em}}
  p{{margin:0}}


  /* Skip to content link */
  .skip-link{{
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
  }}
  .skip-link:focus{{top:0}}
  html[dir="rtl"] .skip-link{{left:auto;right:16px}}

  /* buttons (same as homepage) */
  .btn{{display:inline-flex;align-items:center;gap:10px;padding:14px 24px;border-radius:999px;font-weight:700;font-size:15px;transition:transform .15s,box-shadow .2s,background .2s,color .2s;white-space:nowrap}}
  .btn--primary{{background:var(--brand);color:#fff;box-shadow:0 6px 18px -6px rgba(228,89,17,.55)}}
  .btn--primary:hover{{background:var(--brand-600);transform:translateY(-1px)}}
  .btn--ghost{{background:transparent;color:var(--ink);border:1.5px solid var(--line)}}
  .btn--ghost:hover{{border-color:var(--ink);background:var(--surface-2)}}
  .btn--white{{background:#fff;color:var(--brand)}}
  .btn .ico{{width:18px;height:18px;flex:0 0 18px}}

  /* topbar */
  .topbar{{background:var(--ink);color:#c8d1da;font-size:13px}}
  .topbar__inner{{display:flex;align-items:center;justify-content:space-between;gap:16px;height:40px}}
  .topbar a{{display:inline-flex;align-items:center;gap:6px;color:#c8d1da;transition:color .15s}}
  .topbar a:hover{{color:#fff}}
  .topbar .sep{{opacity:.3;margin:0 10px}}
  .topbar .right{{display:flex;align-items:center;gap:6px}}
  .lang-switch{{position:relative;display:inline-block}}
  .lang-btn{{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;border:1px solid #374151;background:transparent;color:#c8d1da;font:inherit;font-size:13px;line-height:1;cursor:pointer;transition:.15s}}
  .lang-btn:hover{{color:#fff;border-color:#5A6577;background:#1f2937}}
  .lang-btn .caret{{transition:transform .2s;opacity:.8}}
  .lang-switch.open .lang-btn .caret{{transform:rotate(180deg)}}
  .lang-switch.open .lang-btn{{color:#fff;border-color:var(--brand);background:#1f2937}}
  .lang-menu{{position:absolute;top:calc(100% + 8px);right:0;z-index:70;min-width:170px;margin:0;padding:6px;list-style:none;background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow-md);opacity:0;transform:translateY(-6px);pointer-events:none;transition:.15s}}
  .lang-switch.open .lang-menu{{opacity:1;transform:none;pointer-events:auto}}
  .lang-menu button{{width:100%;display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:8px;background:transparent;color:var(--ink);font:inherit;font-size:14px;font-weight:600;text-align:left;cursor:pointer}}
  .lang-menu button:hover,.lang-menu button.active{{background:var(--brand-50);color:var(--brand)}}
  html[dir="rtl"] .lang-menu{{right:auto;left:0}}
  html[dir="rtl"] .lang-menu button{{text-align:right}}
  @media (max-width:720px){{.topbar .hide-sm{{display:none}}}}
  html[dir="rtl"]{{font-family:"Tajawal","Cairo","Noto Sans Arabic",var(--font)}}

  /* header */
  .header{{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.88);backdrop-filter:saturate(180%) blur(14px);-webkit-backdrop-filter:saturate(180%) blur(14px);border-bottom:1px solid transparent;transition:border-color .2s, box-shadow .2s}}
  .header.is-scrolled{{border-color:var(--line);box-shadow:var(--shadow-sm)}}
  .header__inner{{display:flex;align-items:center;justify-content:space-between;gap:24px;height:78px;transition:height .2s}}
  .header.is-scrolled .header__inner{{height:64px}}
  .logo img{{height:48px;width:auto;transition:height .2s}}
  .header.is-scrolled .logo img{{height:40px}}
  .nav{{display:flex;align-items:center;gap:4px}}
  .nav a{{padding:10px 14px;border-radius:8px;font-weight:600;color:var(--ink-2);font-size:15px;transition:.15s}}
  .nav a:hover,.nav a.is-active{{color:var(--brand);background:var(--brand-50)}}
  .burger{{display:none;width:42px;height:42px;border-radius:10px;border:1px solid var(--line);align-items:center;justify-content:center}}
  .burger span{{display:block;width:18px;height:2px;background:var(--ink);position:relative}}
  .burger span::before,.burger span::after{{content:"";position:absolute;left:0;width:18px;height:2px;background:var(--ink)}}
  .burger span::before{{top:-6px}}.burger span::after{{top:6px}}
  @media (max-width:1024px){{.nav{{display:none}}.burger{{display:inline-flex}}.header__cta .btn--ghost{{display:none}}}}
  .mnav{{position:fixed;inset:0 0 0 auto;width:min(86vw,360px);background:#fff;z-index:60;transform:translateX(100%);transition:transform .25s ease;padding:88px 24px 24px;box-shadow:var(--shadow-lg);display:flex;flex-direction:column;gap:6px}}
  .mnav.open{{transform:translateX(0)}}
  .mnav a{{padding:14px 12px;border-radius:10px;font-weight:600;font-size:17px;color:var(--ink)}}
  .mnav a:hover{{background:var(--surface-2);color:var(--brand)}}
  .mnav .btn{{margin-top:14px;justify-content:center}}
  .mnav-close{{position:absolute;top:18px;right:18px;width:40px;height:40px;border-radius:10px;border:1px solid var(--line);display:inline-flex;align-items:center;justify-content:center;font-size:22px;color:var(--ink)}}
  .scrim{{position:fixed;inset:0;background:rgba(15,23,42,.4);z-index:55;opacity:0;pointer-events:none;transition:opacity .2s}}
  .scrim.show{{opacity:1;pointer-events:auto}}
  html[dir="rtl"] .mnav{{right:auto;left:0;transform:translateX(-100%)}}
  html[dir="rtl"] .mnav.open{{transform:translateX(0)}}
  html[dir="rtl"] .mnav-close{{right:auto;left:18px}}

  /* breadcrumb */
  .crumbs{{background:var(--surface);border-bottom:1px solid var(--line)}}
  .crumbs__inner{{display:flex;align-items:center;gap:8px;height:46px;font-size:13.5px;color:var(--ink-2);flex-wrap:wrap}}
  .crumbs a{{color:var(--ink-2);transition:color .15s}}
  .crumbs a:hover{{color:var(--brand)}}
  .crumbs .sep{{opacity:.4}}
  .crumbs .current{{color:var(--ink);font-weight:600}}

  /* product hero */
  .phero{{padding:48px 0 72px;background:radial-gradient(900px 480px at 90% -10%, rgba(228,89,17,.10), transparent 60%),linear-gradient(180deg,#fff 0%, var(--surface) 100%)}}
  .phero__grid{{display:grid;grid-template-columns:1.05fr .95fr;gap:48px;align-items:center}}
  .badge{{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;background:var(--brand-50);color:var(--brand-600);font-size:12.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;border:1px solid rgba(228,89,17,.18)}}
  .phero h1{{margin-top:18px}}
  .phero p.lead{{margin-top:18px;font-size:18px;color:var(--ink-2);max-width:560px}}
  .phero__ctas{{display:flex;gap:14px;margin-top:28px;flex-wrap:wrap}}
  .phero__media{{position:relative;border-radius:24px;overflow:hidden;background:linear-gradient(135deg,#fff,#f3f5f7);box-shadow:var(--shadow-lg);aspect-ratio:4/5;border:1px solid var(--line);display:flex;align-items:center;justify-content:center;padding:28px}}
  .phero__media img{{max-width:100%;max-height:100%;object-fit:contain}}
  @media (max-width:900px){{.phero__grid{{grid-template-columns:1fr;gap:36px}}.phero__media{{order:-1;max-width:440px;margin:0 auto;aspect-ratio:1/1;padding:18px}}}}

  /* shared sections */
  .section{{padding:72px 0}}
  .section--alt{{background:var(--surface)}}
  .section__head{{max-width:760px;margin:0 auto 36px;text-align:center}}
  .eyebrow{{display:inline-block;font-size:12.5px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--brand);margin-bottom:10px}}
  .section__head p{{color:var(--ink-2);margin-top:10px;font-size:16px}}

  /* intro block */
  .intro{{padding:64px 0;border-bottom:1px solid var(--line)}}
  .intro__wrap{{max-width:900px;margin:0 auto;text-align:center}}
  .intro p{{margin-top:18px;font-size:17px;color:var(--ink-2);line-height:1.75}}

  /* benefits */
  .benefits__grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}}
  .benefit{{display:flex;gap:16px;padding:22px;background:#fff;border:1px solid var(--line);border-radius:14px;transition:.2s}}
  .benefit:hover{{border-color:var(--brand);transform:translateY(-2px);box-shadow:var(--shadow-sm)}}
  .benefit__ico{{flex:0 0 40px;width:40px;height:40px;border-radius:10px;background:var(--brand-50);color:var(--brand);display:flex;align-items:center;justify-content:center}}
  .benefit__ico svg{{width:20px;height:20px}}
  .benefit h3{{margin-bottom:4px;font-size:16px}}
  .benefit p{{color:var(--ink-2);font-size:14.5px}}
  @media (max-width:780px){{.benefits__grid{{grid-template-columns:1fr}}}}

  /* specs */
  .specs__grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}}
  .spec-card{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:28px;box-shadow:var(--shadow-sm)}}
  .spec-card h3{{font-size:16px;color:var(--brand);text-transform:uppercase;letter-spacing:.08em;margin-bottom:18px;padding-bottom:12px;border-bottom:1px solid var(--line)}}
  .spec-card dl{{margin:0;display:grid;grid-template-columns:auto 1fr;column-gap:16px;row-gap:10px}}
  .spec-card dt{{font-size:14px;color:var(--ink-2);font-weight:600}}
  .spec-card dd{{margin:0;font-size:14.5px;color:var(--ink);font-weight:600;text-align:right}}
  html[dir="rtl"] .spec-card dd{{text-align:left}}

  /* tables */
  .table-wrap{{margin-top:32px;background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:var(--shadow-sm)}}
  .table-title{{padding:18px 24px;background:var(--surface);border-bottom:1px solid var(--line);font-weight:700;font-size:15px;letter-spacing:.02em}}
  .table-scroll{{overflow-x:auto}}
  table.dim{{width:100%;border-collapse:collapse;min-width:720px}}
  table.dim th,table.dim td{{padding:14px 18px;text-align:left;font-size:14px;border-bottom:1px solid var(--line)}}
  table.dim th{{background:#fff;color:var(--ink-2);font-weight:700;text-transform:uppercase;letter-spacing:.06em;font-size:12.5px}}
  table.dim tr:last-child td{{border-bottom:0}}
  table.dim tr:hover td{{background:var(--brand-50)}}
  table.dim td:first-child{{font-weight:700;color:var(--brand)}}
  html[dir="rtl"] table.dim th,html[dir="rtl"] table.dim td{{text-align:right}}
  .customizable-note{{margin-top:14px;font-size:13.5px;color:var(--ink-2);text-align:center;font-style:italic}}

  /* gallery */
  .gallery{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}
  .gallery a{{display:block;aspect-ratio:1/1;border-radius:14px;overflow:hidden;background:var(--surface-2);border:1px solid var(--line);transition:transform .25s,box-shadow .25s}}
  .gallery a:hover{{transform:translateY(-3px);box-shadow:var(--shadow-md)}}
  .gallery img{{width:100%;height:100%;object-fit:cover}}

  /* lightbox */
  .lightbox{{position:fixed;inset:0;background:rgba(11,18,32,.92);display:none;align-items:center;justify-content:center;z-index:80;padding:24px}}
  .lightbox.open{{display:flex}}
  .lightbox img{{max-width:96vw;max-height:92vh;border-radius:10px;box-shadow:0 30px 80px rgba(0,0,0,.6)}}
  .lightbox .close{{position:absolute;top:18px;right:22px;width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,.12);color:#fff;display:flex;align-items:center;justify-content:center;font-size:24px;cursor:pointer;transition:background .2s}}
  .lightbox .close:hover{{background:rgba(255,255,255,.25)}}

  /* CTA band */
  .cta-band{{margin:0 24px;border-radius:24px;background:linear-gradient(135deg,var(--brand) 0%, #c84a09 100%);color:#fff;padding:56px 56px;display:grid;grid-template-columns:1.4fr 1fr;gap:32px;align-items:center;box-shadow:0 30px 60px -20px rgba(228,89,17,.4);position:relative;overflow:hidden}}
  .cta-band::before{{content:"";position:absolute;inset:0;background:radial-gradient(600px 300px at 100% 0%, rgba(255,255,255,.18), transparent 60%);pointer-events:none}}
  .cta-band h2{{color:#fff}}
  .cta-band p{{margin-top:10px;color:#ffe9d9;font-size:16px;max-width:560px}}
  .cta-band .actions{{display:flex;gap:14px;justify-content:flex-end;flex-wrap:wrap;position:relative}}
  @media (max-width:780px){{.cta-band{{grid-template-columns:1fr;padding:42px 28px;margin:0 16px;text-align:center}}.cta-band .actions{{justify-content:center}}}}

  /* Footer */
  .footer{{background:#0b1220;color:#94a3b8;padding:72px 0 0;margin-top:80px}}
  .footer__grid{{display:grid;grid-template-columns:1.35fr 1fr 1fr 1.15fr 1.15fr;gap:36px}}
  .footer__brand img{{height:54px;filter:brightness(0) invert(1);opacity:.95}}
  .footer__brand p{{margin-top:16px;font-size:14px;line-height:1.75;max-width:340px}}
  .footer h4{{color:#fff;font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-bottom:20px}}
  .footer ul{{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:12px}}
  .footer ul a{{color:#94a3b8;font-size:14.5px;transition:color .15s}}
  .footer ul a:hover{{color:var(--brand)}}
  .footer .contact-li{{display:flex;gap:10px;align-items:flex-start;color:#c8d1da;font-size:14.5px;line-height:1.6}}
  .footer .contact-li .ico{{width:18px;height:18px;color:var(--brand);flex:0 0 18px;margin-top:4px}}
  .footer__social{{display:flex;gap:10px;flex-wrap:wrap}}
  .footer__social a{{width:40px;height:40px;border-radius:10px;background:#1f2937;color:#c8d1da;display:inline-flex;align-items:center;justify-content:center;transition:all .2s}}
  .footer__social a:hover{{background:var(--brand);color:#fff;transform:translateY(-3px)}}
  .footer__social svg{{width:18px;height:18px}}
  .footer__bottom{{margin-top:56px;padding:24px 0;border-top:1px solid #1f2937;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;font-size:13px;color:#5A6B7E}}
  .footer__bottom a{{color:#94a3b8;transition:color .15s}}
  .footer__bottom a:hover{{color:var(--brand)}}
  html[dir="rtl"] .footer h4{{letter-spacing:.05em}}
  @media (max-width:1100px){{.footer__grid{{grid-template-columns:1fr 1fr 1fr;gap:32px}}}}
  @media (max-width:900px){{.footer__grid{{grid-template-columns:1fr 1fr;gap:40px}}}}
  @media (max-width:520px){{.footer__grid{{grid-template-columns:1fr}}.footer__bottom{{flex-direction:column;text-align:center}}}}

  /* WA fab */
  .wa{{position:fixed;right:22px;bottom:22px;z-index:40;width:56px;height:56px;border-radius:50%;background:#25D366;color:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 12px 24px -6px rgba(37,211,102,.55);transition:transform .2s}}
  .wa:hover{{transform:scale(1.06)}}
  .wa svg{{width:28px;height:28px}}
  .wa::after{{content:"";position:absolute;inset:-6px;border-radius:50%;background:#25D36633;animation:ping 2s ease-out infinite;z-index:-1}}
  @keyframes ping{{0%{{transform:scale(.85);opacity:.7}}80%,100%{{transform:scale(1.4);opacity:0}}}}
  html[dir="rtl"] .wa{{right:auto;left:22px}}

  /* reveal */
  .reveal{{opacity:0;transform:translateY(18px);transition:opacity .6s,transform .6s}}
  .reveal.in{{opacity:1;transform:none}}
  @media (prefers-reduced-motion:reduce){{*,*::before,*::after{{animation-duration:.001ms!important;transition-duration:.001ms!important}}.reveal{{opacity:1;transform:none}}}}
</style>
</head>
<body>
<a href="#main-content" class="skip-link" data-i18n="a11y.skip">Skip to main content</a>

<!-- TOP BAR -->
<div class="topbar">
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
</div>

<!-- HEADER -->
<header class="header" id="siteHeader">
  <div class="container header__inner">
    <a href="../index.html" class="logo"><img src="../assets/images/benro-logo.png" alt="Benro Industries"/></a>
    <nav class="nav" aria-label="Primary">
      <a href="../index.html#products" class="is-active" data-i18n="nav.products">Products</a>
      <a href="../index.html#why" data-i18n="nav.why">Why Benro</a>
      <a href="../index.html#about" data-i18n="nav.about">About</a>
      <a href="../index.html#partners" data-i18n="nav.clients">Clients</a>
      <a href="../contact.html" data-i18n="nav.contact">Contact</a>
    </nav>
    <div class="header__cta">
      <a href="../index.html#products" class="btn btn--ghost" data-i18n="ds.back">Back to products</a>
      <a href="../quote.html" class="btn btn--primary"><span data-i18n="cta.quote">Get a Quote</span><svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></a>
      <button class="burger" id="burger" aria-label="Open menu" aria-expanded="false"><span></span></button>
    </div>
  </div>
</header>

<div class="scrim" id="scrim"></div>
<aside class="mnav" id="mnav" aria-label="Mobile menu">
  <button class="mnav-close" id="mnavClose" aria-label="Close menu">×</button>
  <a href="../index.html#products" data-i18n="nav.products">Products</a>
  <a href="../index.html#why" data-i18n="nav.why">Why Benro</a>
  <a href="../about.html" data-i18n="nav.about">About</a>
  <a href="../blog.html" data-i18n="nav.blog">Blog</a>
  <a href="../index.html#partners" data-i18n="nav.clients">Clients</a>
  <a href="../contact.html" data-i18n="nav.contact">Contact</a>
  <a href="../quote.html" class="btn btn--primary" data-i18n="cta.quote">Get a Quote</a>
</aside>

<!-- BREADCRUMB -->
<nav class="crumbs" aria-label="Breadcrumb">
  <div class="container crumbs__inner">
    <a href="../index.html" data-i18n="ds.crumb_home">Home</a>
    <span class="sep">›</span>
    <a href="../index.html#products" data-i18n="ds.crumb_products">Products</a>
    <span class="sep">›</span>
    <span class="current" data-i18n="{title_key}">{title}</span>
  </div>
</nav>

<!-- PRODUCT HERO -->
<section class="phero" id="main-content">
  <div class="container phero__grid">
    <div class="phero__copy reveal">
      <span class="badge" data-i18n="{tag_key}">{tag}</span>
      <h1 data-i18n="{title_key}">{title}</h1>
      <p class="lead" data-i18n="{short_key}">{short}</p>
      <div class="phero__ctas">
        <a href="#specs" class="btn btn--primary"><span data-i18n="ds.specs_cta">View specifications</span>
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></svg>
        </a>
        <a href="../quote.html" class="btn btn--ghost"><svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span data-i18n="hero.cta2">Request a quote</span></a>
      </div>
    </div>
    <div class="phero__media reveal"><img src="{hero_img}" alt="{title}"/></div>
  </div>
</section>

<!-- INTRO -->
<section class="intro">
  <div class="container intro__wrap reveal">
    <h2 data-i18n="{intro_heading_key}">{intro_heading}</h2>
    <p data-i18n="{intro_key}">{intro}</p>
{secondary_block}  </div>
</section>

<!-- BENEFITS -->
<section class="section section--alt">
  <div class="container">
    <div class="section__head reveal">
      <span class="eyebrow" data-i18n="ds.benefits_eyebrow">Key product benefits</span>
      <h2 data-i18n="ds.benefits_title">Engineered for performance &amp; durability</h2>
      <p data-i18n="ds.benefits_desc">Optimal performance, easy installation, and an extended product lifetime.</p>
    </div>
    <div class="benefits__grid">
{benefits_html}    </div>
  </div>
</section>

<!-- TECHNICAL SPECS -->
<section class="section" id="specs">
  <div class="container">
    <div class="section__head reveal">
      <span class="eyebrow" data-i18n="ds.specs_eyebrow">Technical specifications</span>
      <h2 data-i18n="ds.specs_title">Materials &amp; performance figures</h2>
    </div>
    <div class="specs__grid">
{spec_groups_html}    </div>

{tables_html}
    <p class="customizable-note" data-i18n="ds.customizable">These specifications are fully customizable to meet your specific requirements.</p>
  </div>
</section>

<!-- GALLERY -->
<section class="section section--alt">
  <div class="container">
    <div class="section__head reveal">
      <span class="eyebrow" data-i18n="ds.gallery_eyebrow">Product gallery</span>
      <h2 data-i18n="ds.gallery_title">See it in production</h2>
    </div>
    <div class="gallery">
{gallery_html}    </div>
  </div>
</section>

<!-- CTA -->
<section style="padding:48px 0">
  <div class="cta-band reveal">
    <div>
      <h2 data-i18n="finalCta.title">Let's build something together.</h2>
      <p data-i18n="ds.cta_desc">Get a custom quote on this product. Our sales team replies within hours.</p>
    </div>
    <div class="actions">
      <a href="tel:+213554250110" class="btn btn--white"><svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.86 19.86 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.86 19.86 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/></svg><span data-i18n="finalCta.btn1">Call sales</span></a>
      <a href="mailto:contact@benroindustries.com" class="btn" style="background:rgba(255,255,255,.15);color:#fff;border:1.5px solid rgba(255,255,255,.4)"><span data-i18n="finalCta.btn2">Send a message</span><svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></a>
    </div>
  </div>
</section>

<!-- FOOTER -->
<footer class="footer">
  <div class="container">
    <div class="footer__grid">
      <div class="footer__brand">
        <img src="../assets/images/benro-logo.png" alt="Benro Industries"/>
        <p data-i18n="footer.about">BENRO INDUSTRIES is a vibrant and innovative manufacturer at the forefront of the HVAC&amp;R sector — producing insulated copper &amp; aluminium connecting lines and PE foam insulation in Algeria.</p>
      </div>
      <div>
        <h4 data-i18n="footer.products">Products</h4>
        <ul>
          <li><a href="twin-insulated-copper.html" data-i18n="footer.prod1">Twin Insulated Copper</a></li>
          <li><a href="single-insulated-copper.html" data-i18n="footer.prod2">Single Insulated Copper</a></li>
          <li><a href="twin-insulated-aluminium.html" data-i18n="footer.prod3">Twin Insulated Aluminium</a></li>
          <li><a href="insulation-polyethylene.html" data-i18n="footer.prod4">PE Insulation Tubes</a></li>
          <li><a href="copper-tubes.html" data-i18n="footer.prod5">Copper Pancake Coils</a></li>
          <li><a href="polyethylene-tubes.html" data-i18n="footer.prod6">Polyethylene Tubes</a></li>
        </ul>
      </div>
      <div>
        <h4 data-i18n="footer.quicklinks">Quick Links</h4>
        <ul>
          <li><a href="../index.html" data-i18n="footer.home">Home</a></li>
          <li><a href="../about.html" data-i18n="footer.about_link">About us</a></li>
          <li><a href="../index.html#products" data-i18n="nav.products">Products</a></li>
          <li><a href="../blog.html" data-i18n="nav.blog">Blog</a></li>
          <li><a href="../contact.html" data-i18n="nav.contact">Contact</a></li>
          <li><a href="../quote.html" data-i18n="cta.quote">Get a Quote</a></li>
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
        <a href="../contact.html" data-i18n="footer.privacy">Privacy Policy</a>
        <span style="margin:0 8px;opacity:.3">•</span>
        <span data-i18n="footer.tagline">HVAC&amp;R Manufacturer · Algeria 🇩🇿</span>
      </div>
    </div>
  </div>
</footer>

<!-- WA -->
<a href="https://wa.me/213554250110" class="wa" aria-label="WhatsApp" target="_blank" rel="noopener">
  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 14.4c-.3-.1-1.8-.9-2-1s-.5-.1-.7.1c-.2.3-.8 1-1 1.2-.2.2-.4.2-.7.1-.3-.1-1.3-.5-2.5-1.5-.9-.8-1.6-1.8-1.7-2.1-.2-.3 0-.5.1-.6.1-.1.3-.4.4-.5.1-.2.2-.3.3-.5.1-.2.1-.4 0-.5-.1-.2-.7-1.6-.9-2.2-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.4 0 1.4 1 2.8 1.2 3 .1.2 2 3.1 4.9 4.3.7.3 1.2.5 1.6.6.7.2 1.3.2 1.8.1.5-.1 1.7-.7 2-1.4.2-.7.2-1.2.2-1.4-.1-.1-.3-.2-.6-.3zM12 0C5.4 0 0 5.4 0 12c0 2.1.6 4.1 1.6 5.9L0 24l6.3-1.6c1.7.9 3.7 1.5 5.7 1.5 6.6 0 12-5.4 12-12S18.6 0 12 0z"/></svg>
</a>

<!-- Lightbox -->
<div class="lightbox" id="lb" role="dialog" aria-modal="true">
  <button class="close" id="lbClose" aria-label="Close">×</button>
  <img id="lbImg" alt=""/>
</div>

<script>const PRODUCT_I18N={product_i18n_js};

/* ===== i18n (shared keys with homepage; only datasheet-specific keys are added under "ds.*") ===== */
const I18N = {{
  en: {{
    'a11y.skip':'Skip to main content',
    'topbar.tagline':'Algeria 🇩🇿 · HVAC&R Manufacturer',
    'nav.products':'Products','nav.why':'Why Benro','nav.about':'About','nav.blog':'Blog','nav.clients':'Clients','nav.contact':'Contact',
    'cta.quote':'Get a Quote','hero.cta2':'Request a quote',
    'ds.back':'Back to products','ds.crumb_home':'Home','ds.crumb_products':'Products',
    'ds.specs_cta':'View specifications','ds.benefits_eyebrow':'Key product benefits',
    'ds.benefits_title':'Engineered for performance & durability',
    'ds.benefits_desc':'Optimal performance, easy installation, and an extended product lifetime.',
    'ds.specs_eyebrow':'Technical specifications','ds.specs_title':'Materials & performance figures',
    'ds.gallery_eyebrow':'Product gallery','ds.gallery_title':'See it in production',
    'ds.customizable':'These specifications are fully customizable to meet your specific requirements.',
    'ds.cta_desc':"Get a custom quote on this product. Our sales team replies within hours.",
    'finalCta.title':"Let's build something together.",'finalCta.btn1':'Call sales','finalCta.btn2':'Send a message',
    'footer.about':'BENRO INDUSTRIES is a vibrant and innovative manufacturer at the forefront of the HVAC&R sector — producing insulated copper & aluminium connecting lines and PE foam insulation in Algeria.',
    'footer.quicklinks':'Quick Links','footer.home':'Home','footer.about_link':'About us','footer.products':'Products','footer.prod1':'Twin Insulated Copper','footer.prod2':'Single Insulated Copper','footer.prod3':'Twin Insulated Aluminium','footer.prod4':'PE Insulation Tubes','footer.prod5':'Copper Pancake Coils','footer.prod6':'Polyethylene Tubes','footer.contact':'Contact',
    'footer.address':'Industrial Zone, Ghardaïa, Algeria',
    'footer.follow':'Follow Us','footer.response':'We typically respond within 2–4 hours.',
    'footer.copy_prefix':'©','footer.copy_suffix':'Benro Industries — All rights reserved.',
    'footer.tagline':'HVAC&R Manufacturer · Algeria 🇩🇿','footer.privacy':'Privacy Policy'
  }},
  fr: {{
    'a11y.skip':'Aller au contenu principal',
    'topbar.tagline':'Algérie 🇩🇿 · Fabricant CVC&R',
    'nav.products':'Produits','nav.why':'Pourquoi Benro','nav.about':'À propos','nav.blog':'Blog','nav.clients':'Clients','nav.contact':'Contact',
    'cta.quote':'Demander un devis','hero.cta2':'Demander un devis',
    'ds.back':'Retour aux produits','ds.crumb_home':'Accueil','ds.crumb_products':'Produits',
    'ds.specs_cta':'Voir les spécifications','ds.benefits_eyebrow':'Principaux avantages',
    'ds.benefits_title':'Conçu pour la performance & la durabilité',
    'ds.benefits_desc':'Performances optimales, installation facile et longue durée de vie.',
    'ds.specs_eyebrow':'Spécifications techniques','ds.specs_title':'Matériaux & performances',
    'ds.gallery_eyebrow':'Galerie produit','ds.gallery_title':'Voir le produit en production',
    'ds.customizable':"Ces spécifications sont entièrement personnalisables selon vos besoins.",
    'ds.cta_desc':"Obtenez un devis personnalisé pour ce produit. Notre équipe répond en quelques heures.",
    'finalCta.title':"Construisons ensemble.",'finalCta.btn1':'Appeler les ventes','finalCta.btn2':'Envoyer un message',
    'footer.about':"BENRO INDUSTRIES est un fabricant dynamique et innovant à la pointe du secteur CVC&R — produisant des lignes de raccordement en cuivre & aluminium isolées et de la mousse PE en Algérie.",
    'footer.quicklinks':'Liens rapides','footer.home':'Accueil','footer.about_link':'À propos','footer.products':'Produits','footer.prod1':'Cuivre isolé jumelé','footer.prod2':'Cuivre isolé simple','footer.prod3':'Aluminium isolé jumelé','footer.prod4':"Tubes d'isolation PE",'footer.prod5':'Couronnes de cuivre','footer.prod6':'Tubes en polyéthylène','footer.contact':'Contact',
    'footer.address':'Zone Industrielle, Ghardaïa, Algérie',
    'footer.follow':'Suivez-nous','footer.response':'Nous répondons généralement sous 2 à 4 heures.',
    'footer.copy_prefix':'©','footer.copy_suffix':'Benro Industries — Tous droits réservés.',
    'footer.tagline':'Fabricant CVC&R · Algérie 🇩🇿','footer.privacy':'Politique de confidentialité'
  }},
  ar: {{
    'a11y.skip':'انتقل إلى المحتوى الرئيسي',
    'topbar.tagline':'الجزائر 🇩🇿 · صانع تكييف وتبريد',
    'nav.products':'المنتجات','nav.why':'لماذا Benro','nav.about':'من نحن','nav.blog':'المدوّنة','nav.clients':'العملاء','nav.contact':'اتصل بنا',
    'cta.quote':'اطلب عرض سعر','hero.cta2':'اطلب عرض سعر',
    'ds.back':'العودة إلى المنتجات','ds.crumb_home':'الرئيسية','ds.crumb_products':'المنتجات',
    'ds.specs_cta':'عرض المواصفات','ds.benefits_eyebrow':'أهم مميزات المنتج',
    'ds.benefits_title':'مُصمَّم للأداء والمتانة',
    'ds.benefits_desc':'أداء أمثل، تركيب سهل، وعمر خدمة طويل.',
    'ds.specs_eyebrow':'المواصفات التقنية','ds.specs_title':'المواد ومؤشّرات الأداء',
    'ds.gallery_eyebrow':'معرض المنتج','ds.gallery_title':'اعرضه في الإنتاج',
    'ds.customizable':'هذه المواصفات قابلة للتخصيص الكامل لتلبية متطلباتك المحددة.',
    'ds.cta_desc':'احصل على عرض سعر مخصّص لهذا المنتج. يردّ فريق المبيعات خلال ساعات.',
    'finalCta.title':'لِنبنِ شيئاً معاً.','finalCta.btn1':'اتصل بالمبيعات','finalCta.btn2':'أرسل رسالة',
    'footer.about':'بنرو للصناعات صانعٌ ديناميكي ومبتكر في طليعة قطاع التكييف والتبريد — ينتج خطوط توصيل نحاسية وألمنيومية معزولة ورغوة PE في الجزائر.',
    'footer.quicklinks':'روابط سريعة','footer.home':'الرئيسية','footer.about_link':'من نحن','footer.products':'المنتجات','footer.prod1':'نحاس مزدوج معزول','footer.prod2':'نحاس مفرد معزول','footer.prod3':'ألمنيوم مزدوج معزول','footer.prod4':'أنابيب عزل PE','footer.prod5':'لفّات نحاسية','footer.prod6':'أنابيب بولي إيثيلين','footer.contact':'تواصل',
    'footer.address':'المنطقة الصناعية، غرداية، الجزائر',
    'footer.follow':'تابعنا','footer.response':'نرد عادةً خلال 2–4 ساعات.',
    'footer.copy_prefix':'©','footer.copy_suffix':'بنرو للصناعات — جميع الحقوق محفوظة.',
    'footer.tagline':'صانع تكييف وتبريد · الجزائر 🇩🇿','footer.privacy':'سياسة الخصوصية'
  }}
}};
const LANG_LABEL={{en:'EN',fr:'FR',ar:'AR'}};

function applyLang(lang){{
  if(!I18N[lang]) lang='en';
  const dict={{...(I18N[lang]||{{}}), ...((typeof PRODUCT_I18N!=='undefined'&&PRODUCT_I18N[lang])?PRODUCT_I18N[lang]:{{}})}}, h=document.documentElement;
  h.lang=lang; h.dir=(lang==='ar')?'rtl':'ltr';
  document.querySelectorAll('[data-i18n]').forEach(el=>{{
    const k=el.getAttribute('data-i18n');
    if(dict[k]!=null) el.textContent=dict[k];
  }});
  const cur=document.getElementById('langCurrent'); if(cur) cur.textContent=LANG_LABEL[lang];
  document.querySelectorAll('#langMenu [data-lang]').forEach(b=>b.classList.toggle('active',b.dataset.lang===lang));
  try{{localStorage.setItem('benroLang',lang)}}catch(e){{}}
}}
(function(){{
  const wrap=document.getElementById('langSwitch'),trig=document.getElementById('langTrigger'),menu=document.getElementById('langMenu');
  if(!wrap)return;
  const close=()=>{{wrap.classList.remove('open');trig.setAttribute('aria-expanded','false')}};
  const open =()=>{{wrap.classList.add('open');trig.setAttribute('aria-expanded','true')}};
  trig.addEventListener('click',e=>{{e.stopPropagation();wrap.classList.contains('open')?close():open()}});
  menu.querySelectorAll('[data-lang]').forEach(b=>b.addEventListener('click',()=>{{applyLang(b.dataset.lang);close()}}));
  document.addEventListener('click',e=>{{if(!wrap.contains(e.target)) close()}});
  document.addEventListener('keydown',e=>{{if(e.key==='Escape') close()}});
  let saved=null; try{{saved=localStorage.getItem('benroLang')}}catch(e){{}}
  const guess=(navigator.language||'en').slice(0,2).toLowerCase();
  applyLang(saved||(['en','fr','ar'].includes(guess)?guess:'en'));
}})();

// sticky header
const hdr=document.getElementById('siteHeader');
const onScroll=()=>hdr.classList.toggle('is-scrolled',window.scrollY>8);
window.addEventListener('scroll',onScroll,{{passive:true}}); onScroll();
const burger=document.getElementById('burger');
const mnav=document.getElementById('mnav');
const scrim=document.getElementById('scrim');
const mclose=document.getElementById('mnavClose');
const toggleMenu=(open)=>{{mnav.classList.toggle('open',open);scrim.classList.toggle('show',open);burger.setAttribute('aria-expanded',String(open));document.body.style.overflow=open?'hidden':''}};
burger.addEventListener('click',()=>toggleMenu(!mnav.classList.contains('open')));
mclose.addEventListener('click',()=>toggleMenu(false));
scrim.addEventListener('click',()=>toggleMenu(false));
mnav.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>toggleMenu(false)));

// reveal
const io=new IntersectionObserver(es=>{{es.forEach(e=>{{if(e.isIntersecting){{e.target.classList.add('in');io.unobserve(e.target)}}}})}},{{threshold:.12}});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));

// lightbox
const lb=document.getElementById('lb'),lbImg=document.getElementById('lbImg'),lbClose=document.getElementById('lbClose');
document.querySelectorAll('.gallery a').forEach(a=>{{
  a.addEventListener('click',e=>{{e.preventDefault();lbImg.src=a.dataset.full||a.querySelector('img').src;lb.classList.add('open');document.body.style.overflow='hidden'}});
}});
const lbExit=()=>{{lb.classList.remove('open');document.body.style.overflow='';lbImg.src=''}};
lbClose.addEventListener('click',lbExit);
lb.addEventListener('click',e=>{{if(e.target===lb) lbExit()}});
document.addEventListener('keydown',e=>{{if(e.key==='Escape') lbExit()}});

// year
document.getElementById('yr').textContent=new Date().getFullYear();
</script>
</body>
</html>
"""

# -------- benefit icons (varied set) --------
BENEFIT_ICONS = [
    # bolt
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    # shield
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    # timer
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2"/><path d="M9 2h6"/></svg>',
    # diamond
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12l4 6-10 12L2 9z"/><path d="M2 9h20M8 9l4-6 4 6"/></svg>',
    # tool
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>',
    # sun
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>',
    # leaf
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19.2 2.96c.91 5.41-.92 12.04-7.2 17.04"/><path d="M2 21c.5-4.5 2.5-8 7-10"/></svg>',
    # droplet
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/></svg>',
]

def benefits_html(items, product):
    out = []
    for i, (title, desc) in enumerate(items):
        ico = BENEFIT_ICONS[i % len(BENEFIT_ICONS)]
        out.append(
            f'      <div class="benefit reveal">\n'
            f'        <div class="benefit__ico">{ico}</div>\n'
            f'        <div><h3 data-i18n="{prod_key(product, f"benefits.{i}.title")}">{html.escape(title)}</h3><p data-i18n="{prod_key(product, f"benefits.{i}.desc")}">{html.escape(desc)}</p></div>\n'
            f'      </div>\n'
        )
    return ''.join(out)

def spec_groups_html(groups, product):
    out = []
    for gi, (group_title, rows) in enumerate(groups):
        items = ''.join(
            f'          <dt data-i18n="{prod_key(product, f"spec_groups.{gi}.rows.{ri}.key")}">{html.escape(k)}</dt><dd data-i18n="{prod_key(product, f"spec_groups.{gi}.rows.{ri}.val")}">{html.escape(v)}</dd>\n'
            for ri, (k, v) in enumerate(rows)
        )
        out.append(
            f'      <div class="spec-card reveal">\n'
            f'        <h3 data-i18n="{prod_key(product, f"spec_groups.{gi}.title")}">{html.escape(group_title)}</h3>\n'
            f'        <dl>\n{items}        </dl>\n'
            f'      </div>\n'
        )
    return ''.join(out)

def tables_html(tables, product):
    if not tables: return ''
    out = []
    for ti, t in enumerate(tables):
        thead = ''.join(f'<th data-i18n="{prod_key(product, f"tables.{ti}.headers.{hi}")}">{html.escape(h)}</th>' for hi, h in enumerate(t["headers"]))
        body  = ''.join(
            '<tr>' + ''.join(f'<td data-i18n="{prod_key(product, f"tables.{ti}.rows.{ri}.{ci}")}">{html.escape(c)}</td>' for ci, c in enumerate(row)) + '</tr>\n'
            for ri, row in enumerate(t["rows"])
        )
        out.append(
            f'    <div class="table-wrap reveal">\n'
            f'      <div class="table-title" data-i18n="{prod_key(product, f"tables.{ti}.title")}">{html.escape(t["title"])}</div>\n'
            f'      <div class="table-scroll">\n'
            f'        <table class="dim"><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>\n'
            f'      </div>\n'
            f'    </div>\n'
        )
    return ''.join(out)

def gallery_html(imgs):
    return ''.join(
        f'      <a href="{src}" data-full="{src}"><img loading="lazy" src="{src}" alt=""/></a>\n'
        for src in imgs
    )

def secondary_block(p):
    if "secondary_heading" not in p: return ''
    return (
        f'    <h2 style="margin-top:32px" data-i18n="{prod_key(p,"secondary_heading")}">{html.escape(p["secondary_heading"])}</h2>\n'
        f'    <p data-i18n="{prod_key(p,"secondary")}">{html.escape(p["secondary"])}</p>\n'
    )

def product_json_ld(p):
    url = f'https://www.benroindustries.com/products/{p["slug"]}.html'
    image = 'https://www.benroindustries.com/' + p["hero_img"].replace('../', '')
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": p["title"],
        "description": p["short"],
        "image": image,
        "brand": {"@type": "Brand", "name": "BENRO INDUSTRIES"},
        "manufacturer": {
            "@type": "Organization",
            "name": "Benro Industries",
            "url": "https://www.benroindustries.com"
        },
        "category": "HVAC&R components",
        "url": url
    }
    js = json.dumps(data, ensure_ascii=False, indent=2).replace('</', r'<\/')
    return '<!-- JSON-LD: Product -->\n<script type="application/ld+json">\n' + js + '\n</script>'

# -------- render --------
for p in PRODUCTS:
    html_out = TEMPLATE.format(
        title=html.escape(p["title"]),
        title_key=prod_key(p,"title"),
        short=html.escape(p["short"]),
        short_key=prod_key(p,"short"),
        short_meta=html.escape(p["short"]).replace('"', '&quot;'),
        seo_title=html.escape(f'{p["title"]} — BENRO INDUSTRIES', quote=True),
        seo_desc=html.escape(f'{p["short"]} Technical datasheet from BENRO INDUSTRIES.', quote=True),
        canonical_url=f'https://www.benroindustries.com/products/{p["slug"]}.html',
        product_json_ld=product_json_ld(p),
        tag=html.escape(p["tag"]),
        tag_key=prod_key(p,"tag"),
        hero_img=p["hero_img"],
        intro_heading=html.escape(p["intro_heading"]),
        intro_heading_key=prod_key(p,"intro_heading"),
        intro=html.escape(p["intro"]),
        intro_key=prod_key(p,"intro"),
        product_i18n_js=product_i18n(p),
        secondary_block=secondary_block(p),
        benefits_html=benefits_html(p["benefits"], p),
        spec_groups_html=spec_groups_html(p["spec_groups"], p),
        tables_html=tables_html(p["tables"], p),
        gallery_html=gallery_html(p["gallery"]),
    )
    out = OUT_DIR / f'{p["slug"]}.html'
    out.write_text(apply_responsive_images(apply_shared_js(apply_shared_css(html_out, '../assets/css/shared.css'), '../assets/js/shared.js', '// lightbox'), out), encoding='utf-8')
    print(f"  ✓ {out}  ({len(html_out):,} bytes)")

print(f"\nGenerated {len(PRODUCTS)} datasheet pages in ./{OUT_DIR}/")
