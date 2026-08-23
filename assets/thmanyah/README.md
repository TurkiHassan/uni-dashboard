# خطوط ثمانية

المصدر: https://font.thmanyah.com/
تاريخ التحميل: 2026-05-12

تم حفظ خطوط ثمانية بصيغة WOFF2 لاستخدامها في تقارير HTML ولوحات Dashboard والعروض عند الطلب.

## الملفات المهمة

- `thmanyah-fonts.css` — ملف CSS جاهز للاستيراد في تقارير HTML.
- `manifest.json` — خريطة أسماء الخطوط والأوزان والملفات المحلية.
- `named/` — نسخ بأسماء مقروءة من ملفات الخط.

## طريقة الاستخدام في HTML

```html
<link rel="stylesheet" href="assets/fonts/thmanyah/thmanyah-fonts.css">
<style>
  body { font-family: "thmanyah sans Regular", "Segoe UI", Tahoma, sans-serif; }
  h1, h2 { font-family: "thmanyah serif display Bold", "thmanyah sans Bold", serif; }
</style>
```

## العائلات الأساسية

- `thmanyah Sans` / `thmanyah sans Regular` للنصوص الرقمية والواجهات.
- `thmanyah serif display` للعناوين الكبيرة.
- `thmanyah serif text` للنصوص التحريرية.

ملاحظة: الملفات المحمّلة من الموقع بصيغة WOFF2، وهي ممتازة لـ HTML/PDF عبر المتصفح. للعروض التقديمية PPTX قد نحتاج نسخة TTF/OTF إذا توفرت من حزمة التحميل الرسمية أو تضمين الخط بطريقة مناسبة.
