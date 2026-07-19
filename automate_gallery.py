#!/usr/bin/env python3
"""
Automated Photo Gallery Workflow
"""

import argparse
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator

import git
import git.exc
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import ExifTags, Image

# TODO: Verify if i can use for free Cloudinary for hosting the images


class StateManager:
    def __init__(self, root_dir: Path, repo_name: str) -> None:
        """Initialize the local state tracking system with an in-memory buffer.

        Args:
            root_dir: The resolved absolute path of the workspace.
            repo_name: Target GitHub repository name.
        """
        # Define the dedicated state directory
        state_dir: Path = root_dir / ".states"
        state_dir.mkdir(parents=True, exist_ok=True)
        
        # Assign the file path inside the new directory
        self.state_file: Path = state_dir / f".state_{repo_name}.json"
        self._state: dict[str, dict[str, str]] = self._read_initial_state()

    def _read_initial_state(self) -> dict[str, dict[str, str]]:
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("[Warning] Local state file corrupted. Forcing remote state rebuild.")
        return {}

    def load_remote_state(self, date_str: str) -> dict[str, str]:
        """Load known uploaded files and their remote SHAs for a specific date."""
        return self._state.get(date_str, {})

    def update_file_state(self, date_str: str, filename: str, sha: str = "uploaded") -> None:
        """Update the in-memory manifest with a new successful upload."""
        if date_str not in self._state:
            self._state[date_str] = {}
        self._state[date_str][filename] = sha

    def remove_file_state(self, date_str: str, filename: str) -> None:
        """Remove a deleted file from the in-memory manifest."""
        if date_str in self._state and filename in self._state[date_str]:
            del self._state[date_str][filename]

    def flush(self) -> None:
        """Atomically dump the in-memory buffer to disk."""
        temp_file: Path = self.state_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, indent=2)
            temp_file.replace(self.state_file)
        except OSError as e:
            print(f"✗ Fatal boundary error flushing state: {e}")
            if temp_file.exists():
                temp_file.unlink()

class ImageProcessor:
    def __init__(self, watermark_logo_path: Path, margin_bottom: int) -> None:
        """Initialize the image processor.

        Args:
            watermark_logo_path: Absolute path to the logo file.
            margin_bottom: Pixel distance from the bottom edge for the watermark.
        """
        self.logo_path: Path = watermark_logo_path
        self.margin_bottom: int = margin_bottom

    def _load_watermark_logo(self) -> Image.Image:
        """Load the watermark logo image.

        Returns:
            The loaded logo as an RGBA PIL Image.
        """
        logo: Image.Image = Image.open(self.logo_path)
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        return logo

    def correct_orientation(self, img: Image.Image) -> Image.Image:
        """Correct image orientation based on EXIF data.

        Args:
            img: The PIL Image object to be corrected.

        Returns:
            The orientation-corrected PIL Image object.

        Note:
            EXIF orientation tags (values 2-8) define different states of flipping
            and rotation. The internal logic applies inverse transformations to 
            restore standard viewing orientation.
        """
        exif = img.getexif() if hasattr(img, 'getexif') else None
        if exif is not None:
            orientation_tag = None
            for tag, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag, tag)
                if tag_name == 'Orientation':
                    orientation_tag = value
                    break
            if orientation_tag is not None:
                if orientation_tag == 2:
                    img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                elif orientation_tag == 3:
                    img = img.rotate(180, expand=True)
                elif orientation_tag == 4:
                    img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                elif orientation_tag == 5:
                    img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT).rotate(270, expand=True)
                elif orientation_tag == 6:
                    img = img.rotate(270, expand=True)
                elif orientation_tag == 7:
                    img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT).rotate(90, expand=True)
                elif orientation_tag == 8:
                    img = img.rotate(90, expand=True)
        return img

    def add_watermark(self, image_path: Path, output_path: Path) -> bool:
        """Add logo watermark to bottom center of image.

        Args:
            image_path: Path to the input image file.
            output_path: Path where the watermarked image will be saved.

        Returns:
            True if watermarking succeeds, False on I/O error.

        Note:
            Calculates watermark size dynamically (20% width for landscape, 
            33% width for portrait). Positions at bottom center using pixel margins.
        """
        try:
            with Image.open(image_path) as img:
                img = self.correct_orientation(img)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                width, height = img.size
                is_landscape: bool = width > height
                
                with self._load_watermark_logo() as logo:
                    logo_scale: float = 0.20 if is_landscape else 0.33
                    watermark_width: int = int(width * logo_scale)
                    
                    logo_aspect: float = logo.width / logo.height
                    logo_height: int = int(watermark_width / logo_aspect)
                    logo_resized: Image.Image = logo.resize((watermark_width, logo_height), Image.Resampling.LANCZOS)
                
                x: int = (width - watermark_width) // 2
                y: int = height - logo_height - self.margin_bottom
                
                result: Image.Image = img.convert('RGBA')
                result.paste(logo_resized, (x, y), logo_resized)
                result.convert('RGB').save(output_path, 'JPEG', quality=95)
                
                return True
        except OSError as e:
            print(f"I/O Error watermarking {image_path.name}: {e}")
            return False


class GitHubGateway:
    def __init__(self, token: str, username: str) -> None:
        """Initialize GitHub API Gateway with automated retry logic.

        Args:
            token: Authentication token.
            username: Target repository owner username.
        """
        self.username: str = username
        self.session = requests.Session()
        
        # Configure exponential backoff for transient system boundary errors
        retries = Retry(total=3, backoff_factor=1.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        })

    def create_repo(self, repo_name: str, year: int) -> bool:
        """Create GitHub repository if it doesn't exist.

        Args:
            repo_name: The name of the target repository.
            year: Current year for the description.

        Returns:
            True if successfully created or already exists, False on network error.
        """
        url: str = "https://api.github.com/user/repos"
        data: dict = {
            'name': repo_name,
            'description': f'Photo gallery for {year}',
            'public': True
        }
        
        try:
            response = self.session.post(url, json=data, timeout=10)
            return response.status_code in [201, 422]
        except requests.RequestException as e:
            print(f"Network error creating repo {repo_name}: {e}")
            return False

    def get_existing_files(self, repo_name: str, date_str: str) -> dict[str, str]:
        """Get list of files already in the GitHub repository with their SHA.

        Args:
            repo_name: The target repository name.
            date_str: Date string representing the directory path.

        Returns:
            Dictionary mapping filenames to their GitHub SHA hashes.
        """
        url: str = f"https://api.github.com/repos/{self.username}/{repo_name}/contents/{date_str}"
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                files = response.json()
                return {file['name']: file['sha'] for file in files if file['type'] == 'file'}
            return {}
        except requests.RequestException as e:
            print(f"Network error fetching existing files: {e}")
            return {}

    def delete_file(self, repo_name: str, date_str: str, filename: str, sha: str) -> bool:
        """Delete a file from GitHub repository.

        Args:
            repo_name: Target repository name.
            date_str: Date string representing the directory path.
            filename: Name of the file to delete.
            sha: Current SHA hash of the file.

        Returns:
            True if deletion was successful, False otherwise.
        """
        github_path: str = f"{date_str}/{filename}"
        url: str = f"https://api.github.com/repos/{self.username}/{repo_name}/contents/{github_path}"
        data: dict = {'message': f'Remove {filename}', 'sha': sha}
        
        try:
            response = self.session.delete(url, json=data, timeout=10)
            return response.status_code == 200
        except requests.RequestException as e:
            print(f"Network error deleting {filename}: {e}")
            return False

    def batch_upload(self, files_to_upload: list[tuple[Path, str]], repo_name: str, date_str: str) -> Iterator[str]:
        """Upload multiple files sequentially to GitHub repository.

        Args:
            files_to_upload: List of tuples containing (local_path, filename).
            repo_name: Target GitHub repository name.
            date_str: Date string representing the upload path.

        Yields:
            Filename of each successfully uploaded file.

        Raises:
            PermissionError: If the GitHub API returns a 401 or 403 status code.
        """
        total_files: int = len(files_to_upload)
        
        for idx, (local_path, filename) in enumerate(files_to_upload, 1):
            print(f"[Upload] Processing {idx}/{total_files}: {filename}...", end=" ")
            try:
                with open(local_path, 'rb') as f:
                    content: str = base64.b64encode(f.read()).decode()
                
                github_path: str = f"{date_str}/{filename}"
                url: str = f"https://api.github.com/repos/{self.username}/{repo_name}/contents/{github_path}"
                data: dict = {'message': f'Add {filename}', 'content': content}
                
                response = self.session.put(url, json=data, timeout=30)
                
                if response.status_code in [200, 201]:
                    print("✓ Success")
                    yield filename
                elif response.status_code in [401, 403]:
                    error_msg: str = f"Fatal Auth Error (HTTP {response.status_code}). Aborting pipeline."
                    print(f"✗ {error_msg}")
                    raise PermissionError(error_msg)
                else:
                    print(f"✗ Failed (HTTP {response.status_code})")
                    
            except requests.RequestException as e:
                print(f"✗ Network error: {e}")
            except OSError as e:
                print(f"✗ File read error: {e}")


class FileSystemManager:
    def __init__(self, current_year: int, username: str, root_dir: Path) -> None:
        """Initialize the local file system manager.

        Args:
            current_year: Active year integer.
            username: Target repository owner username.
            root_dir: The resolved absolute path of the workspace.
        """
        self.year: int = current_year
        self.username: str = username
        self.root: Path = root_dir

    def delete_local_thumbnails(self, date_str: str, filename: str) -> bool:
        """Delete corresponding thumbnail files from local resolution directories.

        Args:
            date_str: Date string representing the target directory.
            filename: Original base filename to map to `.webp` thumbnails.

        Returns:
            True if at least one thumbnail was deleted, False otherwise.
        """
        base_name: str = Path(filename).stem
        thumbnail_name: str = f"{base_name}.webp"
        
        outputdir: Path = self.root / "images" / str(self.year) / date_str
        thumb_406: Path = outputdir / "406px" / thumbnail_name
        thumb_768: Path = outputdir / "768px" / thumbnail_name
        
        deleted_count: int = 0
        try:
            for thumb_path in [thumb_406, thumb_768]:
                if thumb_path.exists():
                    thumb_path.unlink()
                    deleted_count += 1
            return deleted_count > 0
        except OSError as e:
            print(f"File system error deleting thumbnails for {filename}: {e}")
            return False

    def clone_or_update_repo(self, repo_name: str) -> Path:
        """Clone or update the photo repository locally, with integrity recovery.

        Args:
            repo_name: Target repository name.

        Returns:
            Absolute path to the local repository directory.
            
        Raises:
            RuntimeError: If the git system boundary entirely fails.
        """
        repo_dir: Path = (self.root.parent / repo_name).resolve()
        repo_url: str = f"https://github.com/{self.username}/{repo_name}.git"
        
        try:
            if repo_dir.exists():
                repo = git.Repo(str(repo_dir))
                origin = repo.remotes.origin
                origin.pull()
            else:
                print(f"[Git] Cloning {repo_url} to {repo_dir}...")
                git.Repo.clone_from(repo_url, str(repo_dir))
            time.sleep(2)
            return repo_dir
            
        except git.exc.GitError as e:
            print(f"[Git] Operation failed: {e}. Attempting clean state recovery.")
            if repo_dir.exists():
                shutil.rmtree(repo_dir, ignore_errors=True)
            try:
                git.Repo.clone_from(repo_url, str(repo_dir))
                return repo_dir
            except git.exc.GitError as fallback_err:
                raise RuntimeError(f"Fatal git boundary failure: {fallback_err}")

    def run_gallery_script(self, gallery_script: Path, date_str: str, title: str, photo_repo: str) -> bool:
        """Run the external gallery generation Python script.

        Args:
            gallery_script: Path to the script execution file.
            date_str: Date string mapped to the gallery folder.
            title: Title of the gallery.
            photo_repo: The mapped repository name.

        Returns:
            True if gallery generation executes with a zero exit code, False otherwise.
        """
        repo_dir: Path = self.clone_or_update_repo(photo_repo)
        imagedir: Path = repo_dir / date_str
        
        for _ in range(3):
            if imagedir.exists() and any(f.suffix.lower() in {'.jpg', '.jpeg', '.png'} for f in imagedir.iterdir()):
                break
            time.sleep(2)
            try:
                git.Repo(str(repo_dir)).remotes.origin.pull()
            except git.exc.GitError:
                pass
        
        outputdir: Path = self.root / "images" / str(self.year) / date_str
        repo_url: str = f"https://raw.githubusercontent.com/{self.username}/{photo_repo}/main/{date_str}/"
        
        print(f"[Subprocess] Running {gallery_script.name} with output to {outputdir}...")
        cmd: list[str] = ['python3', str(gallery_script), str(imagedir), str(outputdir), title, repo_url]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                print("✓ Gallery UI generated")
                return True
            print(f"✗ Gallery failed: {result.stderr}")
            return False
        except OSError as e:
            print(f"✗ Failed to invoke gallery script subprocess: {e}")
            return False

    def update_photos_html(self, photos_html: Path, date_str: str, title: str, cover_image: str) -> bool:
        """Atomically update Photos.html with new gallery DOM entry.

        Args:
            photos_html: Absolute path to the Photos.html file.
            date_str: Formatted date string for paths and title.
            title: The display title for the album UI.
            cover_image: Original filename serving as cover.

        Returns:
            True upon successful HTML file update.
        """
        try:
            content: str = photos_html.read_text(encoding='utf-8')
        except FileNotFoundError:
            print(f"✗ Cannot find {photos_html}")
            return False

        entry_pattern: str = f"images/{self.year}/{date_str}/gallery.html"
        if entry_pattern in content:
            print("ℹ Photos.html entry already exists - skipping update")
            return True
        
        cover_image_webp: str = f"{Path(cover_image).stem}.webp"
        formatted_date: str = date_str.replace('-', '/')
        
        new_entry: str = f'''<div class="home-buttons">
            <div class="card">
                <a class="albums" href="images/{self.year}/{date_str}/gallery.html" style="--background-image-url: url(images/{self.year}/{date_str}/406px/{cover_image_webp});">
                    <h2 class="album-title">{formatted_date} <Br> {title} </h2>
                </a>
            </div>
        </div>'''
        
        year_comment: str = f"<!-- {self.year} -->"
        if year_comment in content:
            insert_pos: int = content.find(year_comment) + len(year_comment)
            content = content[:insert_pos] + '\n        ' + new_entry + content[insert_pos:]
        else:
            container_start: int = content.find('<div class="container">') + len('<div class="container">')
            year_comment_new: str = f"\n        <!-- {self.year} -->"
            content = content[:container_start] + year_comment_new + '\n        ' + new_entry + content[container_start:]
        
        temp_html: Path = photos_html.with_suffix('.tmp')
        try:
            temp_html.write_text(content, encoding='utf-8')
            temp_html.replace(photos_html)
            print("✓ Photos.html updated")
            return True
        except OSError as e:
            print(f"✗ Filesystem boundary error during atomic write: {e}")
            if temp_html.exists():
                temp_html.unlink()
            return False


class PhotoGalleryAutomator:
    def __init__(self, config_path: Path) -> None:
        """Initialize orchestration suite mapping configurations to subsystems.

        Args:
            config_path: Path to JSON configuration.
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config: dict = json.load(f)
            
        self.root: Path = Path.cwd().resolve()
        self.year: int = datetime.now().year
        
        self.processor = ImageProcessor(
            watermark_logo_path=(self.root / self.config.get('watermark_logo_path', 'assets/logo.png')).resolve(),
            margin_bottom=self.config.get('margin_bottom', 30)
        )
        
        self.github = GitHubGateway(
            token=self.config.get('github_token', ''),
            username=self.config.get('github_username', 'RocknBirra')
        )
        
        self.fs_manager = FileSystemManager(
            current_year=self.year,
            username=self.github.username,
            root_dir=self.root
        )

    def process_photos(self, input_dir: Path, date_str: str) -> tuple[str, list[str]]:
        """Process photos and synchronize GitHub repo utilizing local state caching.

        Args:
            input_dir: Directory containing local source images.
            date_str: Date string for categorization.

        Returns:
            A tuple containing the repository name and a list of final active files.
        """
        photo_repo: str = self.config.get('photo_repo_template', 'RocknBirra-Foto{year}').format(year=self.year)
        self.github.create_repo(photo_repo, self.year)
        
        state_manager = StateManager(self.root, photo_repo)
        
        # 1. Local State Fast-Path
        existing_files: dict[str, str] = state_manager.load_remote_state(date_str)
        
        # 2. Remote Fallback
        if not existing_files:
            print("[Sync] Local state missing. Fetching from remote API...")
            existing_files = self.github.get_existing_files(photo_repo, date_str)
            for fname, sha in existing_files.items():
                state_manager.update_file_state(date_str, fname, sha)
        
        image_extensions: set[str] = {'.jpg', '.jpeg', '.png'}
        local_files: set[str] = {f.name for f in input_dir.iterdir() if f.suffix.lower() in image_extensions}
        
        files_to_delete: set[str] = set(existing_files.keys()) - local_files
        files_to_upload_names: set[str] = local_files - set(existing_files.keys())
        
        print(f"\n[Sync] Directory: {input_dir.name}")
        print(f"  Tracked Remote files  : {len(existing_files)}")
        print(f"  Current Local files   : {len(local_files)}")
        print(f"  Files to delete       : {len(files_to_delete)}")
        print(f"  Files to upload       : {len(files_to_upload_names)}\n")
        
        for filename in files_to_delete:
            if self.github.delete_file(photo_repo, date_str, filename, existing_files[filename]):
                self.fs_manager.delete_local_thumbnails(date_str, filename)
                state_manager.remove_file_state(date_str, filename)
                print(f"✗ Deleted from Remote: {filename}")
        
        # Flush deletions immediately to avoid desync if the script crashes before uploads start
        if files_to_delete:
            state_manager.flush()
        
        with tempfile.TemporaryDirectory(dir=self.root, prefix=f"tmp_wm_{date_str}_") as temp_dir_name:
            temp_dir: Path = Path(temp_dir_name)
            files_to_upload: list[tuple[Path, str]] = []
            total_watermarks: int = len(files_to_upload_names)
            
            for idx, filename in enumerate(files_to_upload_names, 1):
                print(f"[Watermark] Processing {idx}/{total_watermarks}: {filename}...", end="\r")
                input_path: Path = input_dir / filename
                watermarked_path: Path = temp_dir / filename
                if self.processor.add_watermark(input_path, watermarked_path):
                    files_to_upload.append((watermarked_path, filename))
            
            if files_to_upload_names:
                print() 
                
            if files_to_upload:
                try:
                    for uploaded_file in self.github.batch_upload(files_to_upload, photo_repo, date_str):
                        state_manager.update_file_state(date_str, uploaded_file)
                except KeyboardInterrupt:
                    print("\n[Interrupt] Caught manual termination. State saved up to last successful upload.")
                    sys.exit(1)
                finally:
                    # Guaranteed execution on success, exception, or KeyboardInterrupt (sys.exit)
                    state_manager.flush()
        
        return photo_repo, list(local_files)

    def run_automation(self, input_dir: Path, date_str: str, title: str, cover_image: str) -> bool:
        """Run the complete sequenced automation workflow.

        Args:
            input_dir: Directory containing local source images.
            date_str: Target date string for organization.
            title: Required gallery title.
            cover_image: Original target filename for the gallery cover UI.

        Returns:
            True if all required pipeline stages complete, False on any subsystem failure.
        """
        print(f"=== Starting Automation: {date_str} - {title} ===")
        
        photo_repo, all_files = self.process_photos(input_dir, date_str)
        
        if not all_files:
            print("No files available. Exiting.")
            return False
            
        script_path: Path = (self.root / self.config.get('gallery_script_path', 'scripts/gallery.py')).resolve()
        if not self.fs_manager.run_gallery_script(script_path, date_str, title, photo_repo):
            return False
            
        html_path: Path = (self.root / self.config.get('photos_html_path', 'Photos.html')).resolve()
        if not self.fs_manager.update_photos_html(html_path, date_str, title, cover_image):
            return False
        
        print(f"\n✅ Pipeline Complete: {date_str}")
        return True


def main() -> None:
    """Entry point parsing standard CLI arguments."""
    parser = argparse.ArgumentParser(description='Automate photo gallery workflow')
    parser.add_argument('input_dir', help='Directory containing photos to process')
    parser.add_argument('date', help='Date string (DD-MM-YY format)')
    parser.add_argument('title', help='Gallery title')
    parser.add_argument('cover_image', help='Filename for cover image (will be converted to .webp)')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    
    args = parser.parse_args()
    
    input_path: Path = Path(args.input_dir).resolve()
    config_path: Path = Path(args.config).resolve()
    
    automator = PhotoGalleryAutomator(config_path)
    
    try:
        success: bool = automator.run_automation(input_path, args.date, args.title, args.cover_image)
        sys.exit(0 if success else 1)
    except PermissionError:
        # Error is already printed by the gateway; fail fast and abort.
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[Interrupt] Pipeline terminated by user.")
        sys.exit(1)

if __name__ == "__main__":
    main()