# Quick Reference: Completing the Icon Update

## TL;DR
Network restrictions prevented automatic download of PNG images. Follow these steps to complete:

### 1. Download Images (30 seconds)
Open these URLs in your browser and save the images:
- https://github.com/user-attachments/assets/ccc997e0-7990-443a-b067-fef566634d6f → Save as `rabbit-icon-512.png`
- https://github.com/user-attachments/assets/581ff0ce-de71-4ed6-964d-508895657388 → Save as `rabbit-icon-large.png`
- https://github.com/user-attachments/assets/00a31cea-c725-4265-b4d8-1baf16fc7f2a → Save as `rabbit-icon-192.png`
- https://github.com/user-attachments/assets/a4f63faa-2a7a-4e42-9109-cd6062e94cd7 → Save as `rabbit-icon-32.png`
- https://github.com/user-attachments/assets/51dbf82c-34e4-464c-99bd-60c904b3976e → Save as `rabbit-icon-16.png`

### 2. Move to Public Folder (10 seconds)
```bash
mv rabbit-icon-*.png public/
```

### 3. Update index.html (1 minute)
Replace lines 5-7 in `index.html`:
```html
<!-- BEFORE -->
<link rel="icon" type="image/svg+xml" href="/rabbit-icon.svg" />
<link rel="apple-touch-icon" href="/rabbit-icon.svg" />
<link rel="manifest" href="/site.webmanifest" />

<!-- AFTER -->
<link rel="icon" type="image/png" sizes="32x32" href="/rabbit-icon-32.png" />
<link rel="icon" type="image/png" sizes="16x16" href="/rabbit-icon-16.png" />
<link rel="apple-touch-icon" sizes="192x192" href="/rabbit-icon-192.png" />
<link rel="manifest" href="/site.webmanifest" />
```

### 4. Update site.webmanifest (1 minute)
Replace the icons array in `public/site.webmanifest`:
```json
"icons": [
  {
    "src": "/rabbit-icon-192.png",
    "sizes": "192x192",
    "type": "image/png",
    "purpose": "any"
  },
  {
    "src": "/rabbit-icon-512.png",
    "sizes": "512x512",
    "type": "image/png",
    "purpose": "any"
  }
]
```

### 5. Generate favicon.ico (2 minutes)
1. Visit https://favicon.io/favicon-converter/
2. Upload `rabbit-icon-32.png`
3. Download the generated `favicon.ico`
4. Place in `public/` folder
5. Add to `index.html`: `<link rel="icon" type="image/x-icon" href="/favicon.ico" />`

### 6. Test (30 seconds)
```bash
npm run build
# Check dist folder for all icons
ls -la dist/*.png dist/favicon.ico
```

### 7. Clean Up (optional)
```bash
rm public/rabbit-icon.svg public/vite.svg
```

## Total Time: ~5 minutes

For detailed explanations, see `ICON_REPLACEMENT_INSTRUCTIONS.md`
