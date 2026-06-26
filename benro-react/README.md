# Benro Industries — React SPA

تحويل موقع Benro Industries الثابت (HTML/CSS/JS) إلى تطبيق **React صفحة واحدة (SPA)** للحصول على تنقّل سلس بين الصفحات بدون إعادة تحميل.

## التقنيات
- **Vite + React + TypeScript**
- **React Router** — تنقّل من جانب العميل (client-side) بلا إعادة تحميل كامل للصفحة
- الترجمة (EN / FR / AR) ودعم RTL والتفاعلية (سلايدرات، widgets) مُعاد استخدامها من الموقع الأصلي

## المعمارية
نمط ترحيل تدريجي يحافظ على التصميم والمحتوى والترجمات الأصلية 100%:

- ملفات الموقع الأصلية موجودة في `public/site/` (الصفحات + assets + blog + products).
- `src/components/HtmlPage.tsx`: مكوّن عام يُحمّل صفحة HTML المطابقة للمسار الحالي ديناميكيًا، يحقن أنماطها ومحتواها، يُشغّل سكربتاتها، ويصحّح مسارات الأصول النسبية.
- يعترض النقرات على الروابط الداخلية ويوجّهها عبر React Router → تنقّل سلس.
- `src/App.tsx`: موجّه بمسار شامل `*` يربط أي رابط نظيف بملف الموقع المقابل.

### خريطة المسارات
| المسار النظيف | الملف المصدر |
|---|---|
| `/` | `public/site/index.html` |
| `/about` | `about.html` |
| `/contact` | `contact.html` |
| `/quote` | `quote.html` |
| `/blog` | `blog.html` |
| `/blog/:slug` | `blog/<slug>.html` |
| `/products/:slug` | `products/<slug>.html` |

## التشغيل
```bash
npm install
npm run dev      # خادم التطوير على http://localhost:5173
npm run build    # بناء الإنتاج إلى dist/
npm run preview  # معاينة بناء الإنتاج
```

> ملاحظة نشر: عند النشر على خادم ثابت، فعّل SPA fallback (توجيه كل المسارات إلى index.html) حتى تعمل الروابط المباشرة مثل /products/copper-tubes.
