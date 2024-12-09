document.addEventListener("DOMContentLoaded", function() {
    const galleryElement = document.getElementById('animated-thumbnails-gallery');    
    
    if (!galleryElement) {
        console.error("Gallery element not found");
        return;
    }

    let lightGalleryInitialized = false;

    function calculateRowHeight() {
        var screenWidth = window.innerWidth;
        console.log("Screen width: " + screenWidth);
        var rowHeight;
    
        if (screenWidth < 450) {
            rowHeight = 110; // small screens
        } else if (screenWidth < 800) {
            rowHeight = 150; // medium screens
        } else {
            rowHeight = 200; // large screens
        }
    
        return rowHeight;
    }

    console.log("Gallery element found");

    // Initialize justifiedGallery
    jQuery(galleryElement).justifiedGallery({
        captions: false,
        lastRow: "nojustify",
        margins: 5,
        border: 0,
        waitThumbnailsLoad: true,
        rowHeight: calculateRowHeight()
    }).on("jg.resize", function () {
        var newRowHeight = calculateRowHeight();
        jQuery(galleryElement).justifiedGallery('norewind').justifiedGallery({
            rowHeight: newRowHeight
        });
    }).on("jg.complete", function () {
        console.log("justifiedGallery initialization complete");

        if (!lightGalleryInitialized) {
            // Initialize lightGallery after justifiedGallery is complete
            lightGallery(galleryElement, {
                plugins: [lgZoom, lgThumbnail, lgFullscreen],
                speed: 500,
                thumbnail: true,
                animateThumb: true,
                showZoomInOutIcons: true,
                actualSize: false,
                hideScrollbar: true,
                mobileSettings: {
                    controls: false,
                    showCloseIcon: true,
                    download: true,
                    rotate: false,
                    fullScreen: true
                }
            });
            console.log("lightGallery initialization complete");
            lightGalleryInitialized = true;
        }
    });
});