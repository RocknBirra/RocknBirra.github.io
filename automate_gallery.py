#!/usr/bin/env python3
"""
Automated Photo Gallery Workflow
"""

import os
import sys
import argparse
import subprocess
import json
import requests
import base64
from datetime import datetime
from PIL import Image, ExifTags
import git
from typing import List, Tuple
import time
import shutil

class PhotoGalleryAutomator:
    def __init__(self, config_file: str = "config.json"):
        """Initialize with configuration"""
        self.config = self.load_config(config_file)
        self.current_year = datetime.now().year
        self.github_token = self.config.get('github_token')
        self.github_username = self.config.get('github_username', 'RocknBirra')
        
    def load_config(self, config_file: str) -> dict:
        """Load configuration from JSON file"""
        with open(config_file, 'r') as f:
            return json.load(f)

    def load_watermark_logo(self) -> Image.Image:
        """Load the watermark logo image"""
        logo_path = self.config.get('watermark_logo_path', 'assets/logo.png')
        logo = Image.open(logo_path)
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        return logo
    
    def correct_orientation(self, img):
        """Correct image orientation based on EXIF data"""
        exif = img._getexif()
        if exif is not None:
            orientation_tag = None
            for tag, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag, tag)
                if tag_name == 'Orientation':
                    orientation_tag = value
                    break
            if orientation_tag is not None:
                if orientation_tag == 2:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation_tag == 3:
                    img = img.rotate(180, expand=True)
                elif orientation_tag == 4:
                    img = img.transpose(Image.FLIP_TOP_BOTTOM)
                elif orientation_tag == 5:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(270, expand=True)
                elif orientation_tag == 6:
                    img = img.rotate(270, expand=True)
                elif orientation_tag == 7:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(90, expand=True)
                elif orientation_tag == 8:
                    img = img.rotate(90, expand=True)
        return img

    def add_watermark(self, image_path: str, output_path: str) -> bool:
        """Add logo watermark to bottom center of image"""
        try:
            with Image.open(image_path) as img:
                img = self.correct_orientation(img)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                width, height = img.size
                is_landscape = width > height
                logo = self.load_watermark_logo()
                
                # Calculate watermark size based on orientation
                logo_scale = 0.25 if is_landscape else 0.33  # 25% for landscape, 33% for portrait
                watermark_width = int(width * logo_scale)
                
                # Resize logo maintaining aspect ratio
                logo_aspect = logo.width / logo.height
                logo_height = int(watermark_width / logo_aspect)
                logo_resized = logo.resize((watermark_width, logo_height), Image.Resampling.LANCZOS)
                
                # Calculate bottom center position
                margin_bottom = self.config.get('margin_bottom', 30)
                x = (width - watermark_width) // 2  # Center horizontally
                y = height - logo_height - margin_bottom  # Bottom with margin
                
                # Create a copy of the original image
                result = img.convert('RGBA')
                
                # Paste the logo with full opacity at bottom center
                result.paste(logo_resized, (x, y), logo_resized)
                
                # Convert back to RGB and save
                result.convert('RGB').save(output_path, 'JPEG', quality=95)
                
                return True
        except Exception as e:
            print(f"Error watermarking {image_path}: {e}")
            return False

    def create_github_repo(self, repo_name: str) -> bool:
        """Create GitHub repository if it doesn't exist"""
        url = f"https://api.github.com/user/repos"
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        data = {
            'name': repo_name,
            'description': f'Photo gallery for {self.current_year}',
            'public': True
        }
        
        response = requests.post(url, headers=headers, json=data)
        return response.status_code in [201, 422]  # 201 = created, 422 = already exists

    def get_existing_files(self, repo_name: str, date_str: str) -> dict:
        """Get list of files already in the GitHub repository with their SHA"""
        try:
            url = f"https://api.github.com/repos/{self.github_username}/{repo_name}/contents/{date_str}"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                files = response.json()
                return {file['name']: file['sha'] for file in files if file['type'] == 'file'}
            return {}
        except:
            return {}

    def delete_file_from_github(self, repo_name: str, date_str: str, filename: str, sha: str) -> bool:
        """Delete a file from GitHub repository"""
        try:
            github_path = f"{date_str}/{filename}"
            url = f"https://api.github.com/repos/{self.github_username}/{repo_name}/contents/{github_path}"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            data = {
                'message': f'Remove {filename}',
                'sha': sha
            }
            
            response = requests.delete(url, headers=headers, json=data)
            return response.status_code == 200
            
        except Exception as e:
            print(f"Error deleting {filename}: {e}")
            return False
        
    def delete_local_thumbnails(self, date_str: str, filename: str) -> bool:
        """Delete corresponding thumbnail files from local 406px and 768px directories"""
        try:
            base_name = os.path.splitext(filename)[0]
            thumbnail_name = f"{base_name}.webp"
            
            outputdir = f"images/{self.current_year}/{date_str}/"
            thumb_406_path = os.path.join(outputdir, "406px", thumbnail_name)
            thumb_768_path = os.path.join(outputdir, "768px", thumbnail_name)
            
            deleted_count = 0
            for thumb_path in [thumb_406_path, thumb_768_path]:
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
                    deleted_count += 1
            
            return deleted_count > 0
        except Exception as e:
            print(f"Error deleting local thumbnails for {filename}: {e}")
            return False

    def batch_upload_to_github(self, files_to_upload: List[Tuple[str, str]], repo_name: str, date_str: str) -> List[str]:
        """Upload multiple files to GitHub repository"""
        uploaded_files = []
        
        for local_path, filename in files_to_upload:
            try:
                with open(local_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode()
                
                github_path = f"{date_str}/{filename}"
                url = f"https://api.github.com/repos/{self.github_username}/{repo_name}/contents/{github_path}"
                headers = {
                    'Authorization': f'token {self.github_token}',
                    'Accept': 'application/vnd.github.v3+json'
                }
                
                data = {
                    'message': f'Add {filename}',
                    'content': content
                }
                
                response = requests.put(url, headers=headers, json=data)
                
                if response.status_code in [200, 201]:
                    uploaded_files.append(filename)
                    print(f"✓ {filename}")
                    
            except Exception as e:
                print(f"✗ {filename}: {e}")
        
        return uploaded_files

    def clone_or_update_photo_repo(self, repo_name: str) -> str:
        """Clone or update the photo repository locally"""
        repo_dir = f"../{repo_name}"
        repo_url = f"https://github.com/{self.github_username}/{repo_name}.git"
        
        try:
            if os.path.exists(repo_dir):
                repo = git.Repo(repo_dir)
                origin = repo.remotes.origin
                origin.pull()
            else:
                git.Repo.clone_from(repo_url, repo_dir)
            time.sleep(2)
            return repo_dir
            
        except:
            if not os.path.exists(repo_dir):
                os.makedirs(repo_dir, exist_ok=True)
            return repo_dir

    def process_photos(self, input_dir: str, date_str: str) -> Tuple[str, List[str]]:
        """Process photos: sync GitHub repo to match local directory"""
        photo_repo = self.config.get('photo_repo_template', 'RocknBirra-Foto{year}').format(year=self.current_year)
        
        self.create_github_repo(photo_repo)
        
        # Get existing files in GitHub (with SHA for deletion)
        existing_files = self.get_existing_files(photo_repo, date_str)
        print(f"Existing files in GitHub: {len(existing_files)}")
        
        # Get local files
        image_extensions = ('.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG')
        local_files = set(f for f in os.listdir(input_dir) if f.lower().endswith(image_extensions))
        print(f"Local files: {len(local_files)}")
        
        # Files to delete (in GitHub but not in local)
        files_to_delete = set(existing_files.keys()) - local_files
        
        # Files to upload (in local but not in GitHub)
        files_to_upload_names = local_files - set(existing_files.keys())
        
        print(f"Files to delete: {len(files_to_delete)}")
        print(f"Files to upload: {len(files_to_upload_names)}")
        
        # Delete files that are no longer local
        deleted_files = []
        for filename in files_to_delete:
            if self.delete_file_from_github(photo_repo, date_str, filename, existing_files[filename]):
                deleted_files.append(filename)
                self.delete_local_thumbnails(date_str, filename)
                print(f"✗ Deleted: {filename}")
        
        # Process and upload new files
        temp_dir = f"temp_watermarked_{date_str}"
        os.makedirs(temp_dir, exist_ok=True)
        
        files_to_upload = []
        for filename in files_to_upload_names:
            input_path = os.path.join(input_dir, filename)
            watermarked_path = os.path.join(temp_dir, filename)
            
            if self.add_watermark(input_path, watermarked_path):
                files_to_upload.append((watermarked_path, filename))
        
        uploaded_files = []
        if files_to_upload:
            print(f"Uploading {len(files_to_upload)} files...")
            uploaded_files = self.batch_upload_to_github(files_to_upload, photo_repo, date_str)
        
        # Clean up temp directory
        shutil.rmtree(temp_dir)
        
        # Final file list (what should be in GitHub now)
        final_files = list(local_files)
        
        print(f"Sync complete: {len(deleted_files)} deleted, {len(uploaded_files)} uploaded")
        print(f"Total files in repo: {len(final_files)}")
        
        return photo_repo, final_files

    def run_gallery_script(self, date_str: str, title: str, photo_repo: str) -> bool:
        """Run the gallery.py script"""
        repo_dir = self.clone_or_update_photo_repo(photo_repo)
        
        for attempt in range(3):
            imagedir = os.path.join(repo_dir, date_str)
            if os.path.exists(imagedir):
                image_files = [f for f in os.listdir(imagedir) 
                             if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                if image_files:
                    break
            time.sleep(2)
            try:
                repo = git.Repo(repo_dir)
                origin = repo.remotes.origin
                origin.pull()
            except:
                pass
        
        gallery_script = self.config.get('gallery_script_path', 'scripts/gallery.py')
        outputdir = f"images/{self.current_year}/{date_str}/"
        repo_url = f"https://raw.githubusercontent.com/{self.github_username}/{photo_repo}/main/{date_str}/"
        
        print(f"Running gallery script: {gallery_script} with output to {outputdir}...")
        
        cmd = ['python3', gallery_script, imagedir, outputdir, title, repo_url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ Gallery generated")
            return True
        else:
            print(f"✗ Gallery failed: {result.stderr}")
            return False

    def check_photos_html_entry_exists(self, date_str: str, title: str) -> bool:
        """Check if Photos.html already contains an entry for this date/title"""
        photos_html_path = self.config.get('photos_html_path', 'Photos.html')
        
        try:
            with open(photos_html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if an entry with this date already exists
            entry_pattern = f"images/{self.current_year}/{date_str}/gallery.html"
            return entry_pattern in content
        except FileNotFoundError:
            return False

    def update_photos_html(self, date_str: str, title: str, cover_image: str) -> bool:
        """Update Photos.html with new gallery entry (only if not already present)"""
        if self.check_photos_html_entry_exists(date_str, title):
            print("ℹ Photos.html entry already exists - skipping update")
            return True
        
        photos_html_path = self.config.get('photos_html_path', 'Photos.html')
        
        with open(photos_html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Convert cover image to .webp extension
        cover_image_base = os.path.splitext(cover_image)[0]
        cover_image_webp = f"{cover_image_base}.webp"
        
        formatted_date = date_str.replace('-', '/')
        new_entry = f'''<div class="home-buttons">
            <div class="card">
                <a class="albums" href="images/{self.current_year}/{date_str}/gallery.html" style="--background-image-url: url(images/{self.current_year}/{date_str}/406px/{cover_image_webp});">
                    <h2 class="album-title">{formatted_date} <Br> {title} </h2>
                </a>
            </div>
        </div>'''
        
        # Find where to insert: after the comment for current year or at the start of container
        year_comment = f"<!-- {self.current_year} -->"
        if year_comment in content:
            # Insert after the year comment
            insert_pos = content.find(year_comment) + len(year_comment)
            content = content[:insert_pos] + '\n        ' + new_entry + content[insert_pos:]
        else:
            # Find the container div and insert at the beginning
            container_start = content.find('<div class="container">') + len('<div class="container">')
            year_comment_new = f"\n        <!-- {self.current_year} -->"
            content = content[:container_start] + year_comment_new + '\n        ' + new_entry + content[container_start:]
        
        with open(photos_html_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✓ Photos.html updated")
        return True

    def run_automation(self, input_dir: str, date_str: str, title: str, cover_image: str):
        """Run the complete automation workflow"""
        print(f"Starting: {date_str} - {title}")
        
        photo_repo, all_files = self.process_photos(input_dir, date_str)
        
        if not all_files:
            print("No files available")
            return False
        
        if not self.run_gallery_script(date_str, title, photo_repo):
            return False
        
        if not self.update_photos_html(date_str, title, cover_image):
            return False
        
        print(f"✅ Complete: {date_str}")
        return True


def main():
    parser = argparse.ArgumentParser(description='Automate photo gallery workflow')
    parser.add_argument('input_dir', help='Directory containing photos to process')
    parser.add_argument('date', help='Date string (DD-MM-YY format)')
    parser.add_argument('title', help='Gallery title')
    parser.add_argument('cover_image', help='Filename for cover image (will be converted to .webp)')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    
    args = parser.parse_args()
    
    automator = PhotoGalleryAutomator(args.config)
    success = automator.run_automation(args.input_dir, args.date, args.title, args.cover_image)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()