# RocknBirra Festival Gallery

Site for a village festival. Provides the menu and photos of the various evenings. 

The gallery pages are generated using a custom automation script based on [gallery_shell](https://cyclenerd.github.io/gallery_shell/).

**Developed by Federico Calzoni**

---

## How to Add a New Album

This script handles everything for you: it adds watermarks, uploads the photos, builds the gallery, and updates the website.

### The Command
Run this command from inside the main `RocknBirra.github.io` folder:

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

After completion, review changes and push to deploy.

---

### Notes

- Repository Creation
  Do not manually create the photo repository on GitHub. The script automatically detects the current year and creates it for you (e.g., RocknBirra-Foto2026).

- Resuming After a Crash or Stop
  If your internet drops or you stop the script halfway through, just run the exact same command again. It remembers what was already uploaded and will skip them, picking up right where it left off.

- Deleting a Photo
  To remove an image from an existing gallery, simply delete the file from your local folder on your computer, then run the script command again. It will detect the missing photo and delete it from the website.

- Fixing Sync Issues
  If the website gets out of sync with your folder (for example, if someone deleted a file directly on GitHub), look for a hidden file named something like `.state_RocknBirra-Foto2026.json` in your main folder and delete it. Run the script again, and it will fix itself.

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