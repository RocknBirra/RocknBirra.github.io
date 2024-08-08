import argparse
import logging
import os
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_thumbnail(image_path, thumbdir, height, quality=85):
    try:
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        thumbnail_path = os.path.join(thumbdir, f"{base_name}.webp")
        image = Image.open(image_path)
        aspect_ratio = image.width / image.height
        new_width = int(aspect_ratio * height)
        
        # Check if the thumbnail already exists
        if os.path.exists(thumbnail_path):
            logging.info(f"Thumbnail already exists: {thumbnail_path}")
            return thumbnail_path, new_width, height
        
        image.thumbnail((new_width, height), Image.LANCZOS)
        image.save(thumbnail_path, 'WEBP', quality=quality)
        logging.info(f"Saved thumbnail as {thumbnail_path}")
        return thumbnail_path, new_width, height
    
    except Exception as e:
        logging.error(f"Error creating thumbnail for {image_path}: {e}")
        raise

def generate_html(imagedir, outputdir, title, repo_url):
    # Create the output directory structure
    title_dir = os.path.join(outputdir, title)
    os.makedirs(title_dir, exist_ok=True)
    thumbdir_406 = os.path.join(title_dir, "406px")
    thumbdir_768 = os.path.join(title_dir, "768px")
    os.makedirs(thumbdir_406, exist_ok=True)
    os.makedirs(thumbdir_768, exist_ok=True)

    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="/style-gallery.css">
    <link rel="icon" type="image/png" href="/assets/birra.png">
    <!-- Include jQuery -->
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <!-- Include justifiedGallery CSS -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/justifiedGallery/3.8.1/css/justifiedGallery.min.css">
    <!-- Include lightGallery CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/lightgallery@2/css/lightgallery-bundle.min.css">
</head>
<header class="menu-header">
    <a href="/photos.html" class="back-link">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="back-arrow" style="padding: 1vw;"> 
            <path fill="#ffffff" d="M12 2 L2 12 L12 22 L12 16 L22 16 L22 8 L12 8 Z"/>
        </svg>
    </a>
    <h1>{title}</h1>
</header>
<body>
<div class="container-sm">
    <div class="row justify-content-center">
        <div class="gallery-container" id="animated-thumbnails-gallery">
"""

    for filename in os.listdir(imagedir):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(imagedir, filename)
            logging.info(f"Processing image: {image_path}")
            try:
                # Create thumbnails
                thumb_406_path, width_406, height_406 = create_thumbnail(image_path, thumbdir_406, 406)
                thumb_768_path, width_768, height_768 = create_thumbnail(image_path, thumbdir_768, 768)
    
                # Adjust paths to be relative to the HTML file's location
                thumb_406_rel_path = os.path.relpath(thumb_406_path, title_dir)
                thumb_768_rel_path = os.path.relpath(thumb_768_path, title_dir)
    
                # Add image details to HTML content
                html_content += f"""
              <a data-lg-size="{width_768}-{height_768}" class="gallery-item" data-src="./{thumb_768_rel_path}" data-download-url="{repo_url}/{filename}">
                <img class="img-responsive" src="./{thumb_406_rel_path}" />
              </a>
    """
    
            except Exception as e:
                logging.error(f"Error processing image {image_path}: {e}")

    html_content += """
            </div>
        </div>
    </div>
    <!-- Include justifiedGallery plugin -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/justifiedGallery/3.8.1/js/jquery.justifiedGallery.min.js"></script>
    <!-- Include lightGallery plugin -->
    <script src="https://cdn.jsdelivr.net/npm/lightgallery@2/lightgallery.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/lightgallery@2/plugins/thumbnail/lg-thumbnail.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/lightgallery@2/plugins/zoom/lg-zoom.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/lightgallery@2/plugins/fullscreen/lg-fullscreen.min.js"></script> 
    <!-- Include your script -->
    <script src="/gallery.js"></script>
</body>
</html>
"""

    # Save the HTML content to a file in the title directory
    html_file_path = os.path.join(title_dir, 'gallery.html')
    with open(html_file_path, 'w') as file:
        file.write(html_content)
    logging.info(f"HTML gallery created successfully at {html_file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a gallery")
    parser.add_argument("imagedir", help="Directory containing the images")
    parser.add_argument("outputdir", help="Directory to save the output")
    parser.add_argument("title", help="Title of the HTML page")
    parser.add_argument("repo_url", help="External repository URL for download links")
    args = parser.parse_args()

    generate_html(args.imagedir, args.outputdir, args.title, args.repo_url)