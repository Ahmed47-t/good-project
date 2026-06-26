# نظام إدارة سياق المشروع: إعادة تصميم موقع Benro Industries

## 📌 1. نظرة عامة عن المشروع
- **اسم الشركة:** Benro Industries (شركة جزائرية رائدة في المنطقة الصناعية بغرداية، متخصصة في إنتاج أنابيب النحاس المعزولة، خطوط توصيل الألمنيوم، وأنظمة العزل PE لقطاع التكييف والتبريد العالمي HVAC&R).
- **الأداة المستخدمة:** `npx @opengsd/get-shit-done-redux@latest` لبناء وتطوير واجهات الفرونت إند.
- **الهدف:** إعادة تصميم الموقع الأصلي (`https://www.benroindustries.com/`) وتحسينه بالكامل مع الحفاظ الصارم على الهوية البصرية الأساسية.

---

## 🛠️ 2. الهيكل الحالي للمشروع (Project File Tree)
بنية المجلدات والملفات المكتملة والمستخرجة من نظام الملفات الحالي (`good/`) هي كالتالي:
```text
good/
│
├── .gsd/
│   └── defaults.json         # إعدادات أداة المطور (resolve_model_ids: omit)
│
├── assets/
│   └── images/
│       └── about-event-inauguration.jpg   # صور قسم الأحداث والافتتاح
│
├── blog/                     # صفحات المقالات التفصيلية المكتملة
│   ├── les-avantages-des-tubes-en-cuivre-isoles-benro-industries.html
│   ├── local-authorities-inaugurate-the-new-facility.html
│   ├── recap-of-benro-industries-at-sivecc-2024.html
│   ├── the-role-of-aluminum-tubes-in-modern-hvac-systems.html
│   └── the-ultimate-guide-to-insulated-copper-tubes-for-air-conditioners.html
│
├── about.html                # صفحة "من نحن" (مكتملة التنسيق والتايم لاين)
├── blog.html                 # صفحة المدونة الرئيسية (تجمع المقالات والأخبار)
└── index.html                # الصفحة الرئيسية للموقع