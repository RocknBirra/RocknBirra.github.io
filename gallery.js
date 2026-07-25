window.addEventListener("load", function() {
    const galleryElement = document.getElementById('animated-thumbnails-gallery');    
    
    if (!galleryElement) {
        console.error("Gallery element not found");
        return;
    }

    const $gallery = jQuery(galleryElement);
    let lightGalleryInitialized = false;
    let currentRowHeight = 0;

    function calculateRowHeight() {
        const screenWidth = window.innerWidth;
        if (screenWidth < 450) return 90; // small screens
        if (screenWidth < 800) return 110; // medium screens
        return 200;                        // large screens
    }

    // Set initial state
    currentRowHeight = calculateRowHeight();
    console.log("Initial row height set to:", currentRowHeight);

    // Initialize justifiedGallery
    $gallery.justifiedGallery({
        captions: false,
        lastRow: "nojustify",
        margins: 5,
        border: 0,
        waitThumbnailsLoad: true,
        rowHeight: currentRowHeight
    }).on("jg.complete", function () {
        if (!lightGalleryInitialized) {
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
            lightGalleryInitialized = true;
        }
    });
});