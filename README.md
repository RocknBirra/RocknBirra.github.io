# RocknBirra Festival Gallery

Site for a village festival. Provides the menu and photos of the various evenings. 

The gallery pages are generated using a custom automation script based on [gallery_shell](https://cyclenerd.github.io/gallery_shell/).

**Developed by Federico Calzoni**

---

## How to Add a New Album

### METHOD 2025 (Automated)

**Single command automation** - handles watermarking, upload, gallery generation, and Photos.html update.

```bash
python3 automate_gallery.py /path/to/photos DD-MM-YY "Title" cover_image.jpg
```

#### Example:
```bash
python3 automate_gallery.py ~/Downloads/Safari_Photos 20-07-25 "#Safari" IMG_1234.jpg
```

**Arguments:**
- `input_dir`: Local folder with photos
- `date`: Date in DD-MM-YY format  
- `title`: Album title (use quotes)
- `cover_image`: Filename for gallery cover

**Note:** Run from `RocknBirra.github.io` directory. After completion, review changes and push to deploy.

---

### METHOD 2024 (Manual)

#### 1. Run gallery.py
```bash
python3 scripts/gallery.py '../RocknBirra-Foto2024/28-07-24/' 'images/2024/28-07-24/' '28-07-24 #Playa' 'https://raw.githubusercontent.com/RocknBirra/RocknBirra-Foto2024/main/28-07-24/'
```

#### 2. Update Photos.html
Add new entry manually:
```html
<div class="home-buttons">
   <div class="card">
         <a class="albums" href="images/2024/28-07-24/gallery.html" style="--background-image-url: url(images/2024/28-07-24/406px/IMG_5860.webp);">
            <h2 class="album-title">28/07/24 <Br> #Playa </h2>
         </a>
   </div>
</div>
```

#### 3. Deploy
Push changes to GitHub - automatic workflow deploys the site.