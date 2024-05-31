Site for a village festival. Provides the menu and photos of the various evenings. Feel free to get some inspiration.

The gallery pages were generated with the script provided by: https://cyclenerd.github.io/gallery_shell/

Developed by Federico Calzoni.


# How to add a new album:
0. Requirements:
   make sure to have installed the following packages:
   - imagemagick
   - jhead
   - jpegoptim
1. create a folder inside images/ and place your pictures
2. create thumbnails and html pages for each picture:
   1. copy gallery.sh in the folder created
   2. run gallery.sh 
   ```bash
   sh gallery.sh -t "My Photos" -d "thumbs"
   ```
   - (replace "My Photos" with the title of the album, a.e.: 29/07/23 #Cumbesa")
   1. delete gallery.sh from the folder
3. compress the images
   ```bash 
   run compress_images.sh
   ``` 
   (It will skip already compressed images)
4. Create a new entry in the phots page:
   1. open photos.html with a text editor:
   2. place a new entry with the following structure:
   ```html
   <div class="home-buttons">
        <div class="card">
            <a class="albums" href="images/29-07-23/index.html" style="--background-image-url: url(images/29-07-23/thumbs/406/IMG_3293.JPG);">
                <h2 class="album-title">29/07/23 <Br> #Cumbesa</h2>
            </a>
        </div>
    </div>
    ```
    - Replace "images/29-07-23/index.html", with the new one.
    - Replace "images/29-07-23/thumbs/406/IMG_3293.JPG" with an image that you like from the new ones
    - Replace "29/07/23 &lt;Br&gt; #Cumbesa" with the new album name

5.  Push changes to github and automatically a workflow will start and deploy the updated website. 

