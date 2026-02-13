# Icon Replacement Instructions

## Overview
The favicon and app icons have been updated to use a rabbit theme. However, due to network restrictions, I was unable to download the actual PNG images from the GitHub issue. I've created an SVG placeholder icon that you can replace with the actual PNG images.

## Current Status
✅ Created SVG placeholder icon (`public/rabbit-icon.svg`)
✅ Created web manifest (`public/site.webmanifest`)
✅ Updated `index.html` to reference new icon and manifest
✅ Build process tested and working

## To Complete the Icon Update

### Step 1: Download the PNG Images
Download the following images from the GitHub issue:

1. **512x512 icon**: https://github.com/user-attachments/assets/ccc997e0-7990-443a-b067-fef566634d6f
2. **Large icon**: https://github.com/user-attachments/assets/581ff0ce-de71-4ed6-964d-508895657388
3. **192x192 icon**: https://github.com/user-attachments/assets/00a31cea-c725-4265-b4d8-1baf16fc7f2a
4. **32x32 icon**: https://github.com/user-attachments/assets/a4f63faa-2a7a-4e42-9109-cd6062e94cd7
5. **16x16 icon**: https://github.com/user-attachments/assets/51dbf82c-34e4-464c-99bd-60c904b3976e

### Step 2: Save the Images
Save the downloaded images to the `public/` directory with these names:
- `rabbit-icon-512.png` (512x512)
- `rabbit-icon-192.png` (192x192)
- `rabbit-icon-180.png` (for Apple touch icon - you may need to resize the 192x192)
- `rabbit-icon-32.png` (32x32)
- `rabbit-icon-16.png` (16x16)
- `favicon.ico` (generated from the 32x32 and 16x16 icons)

### Step 3: Update index.html
Replace the current icon references in `index.html`:

```html
<!-- Current (SVG placeholder) -->
<link rel="icon" type="image/svg+xml" href="/rabbit-icon.svg" />
<link rel="apple-touch-icon" href="/rabbit-icon.svg" />

<!-- Replace with (PNG icons) -->
<link rel="icon" type="image/png" sizes="32x32" href="/rabbit-icon-32.png" />
<link rel="icon" type="image/png" sizes="16x16" href="/rabbit-icon-16.png" />
<link rel="apple-touch-icon" sizes="180x180" href="/rabbit-icon-180.png" />
<link rel="icon" type="image/x-icon" href="/favicon.ico" />
```

### Step 4: Update site.webmanifest
Update `public/site.webmanifest` to reference the PNG icons:

```json
{
  "name": "RabbitMiles",
  "short_name": "RabbitMiles",
  "description": "Track your trail running activities with Strava integration",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#ff6b35",
  "icons": [
    {
      "src": "/rabbit-icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/rabbit-icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

### Step 5: Generate favicon.ico (Optional)
You can use an online tool like [favicon.io](https://favicon.io/favicon-converter/) to convert your PNG images into a multi-size favicon.ico file containing both 16x16 and 32x32 versions.

### Step 6: Clean Up (Optional)
Once you've confirmed the PNG icons are working, you can remove:
- `public/rabbit-icon.svg` (the SVG placeholder)
- `public/vite.svg` (the old Vite icon)

### Step 7: Test
After making these changes:
1. Run `npm run build` to rebuild the project
2. Check the `dist/` folder to ensure all icon files are copied
3. Open the app in a browser and verify the favicon appears in the tab
4. Check the manifest in browser DevTools (Application → Manifest)

## Alternative: Keep Using SVG
If you prefer to use the SVG icon I created (or create your own), you can keep the current setup as-is. SVG icons work well for favicons and are scalable to any size. However, the PNG images from the issue appear to be professionally designed and match the RabbitMiles brand better.

## Need Help?
If you encounter any issues, please refer to this checklist:
- [ ] PNG images downloaded and saved to `public/`
- [ ] `index.html` updated with PNG icon references
- [ ] `site.webmanifest` updated with PNG icon references
- [ ] `favicon.ico` generated and placed in `public/`
- [ ] Project rebuilt with `npm run build`
- [ ] Icons appear correctly in browser tab and manifest
