document.addEventListener("DOMContentLoaded", function() {
    const galleryElement = document.getElementById('animated-thumbnails-gallery');    
    
    if (!galleryElement) {
        console.error("Gallery element not found");
        return;
    }

    function calculateRowHeight() {
        var screenWidth = window.innerWidth;
        console.log("Screen width: " + screenWidth);
        var rowHeight;
    
        if (screenWidth < 450) {
            rowHeight = 100; // Example value for small screens
        } else if (screenWidth < 800) {
            rowHeight = 150; // Example value for medium screens
        } else {
            rowHeight = 200; // Example value for large screens
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

        // Check if lightGallery is defined
        if (typeof lightGallery === 'undefined') {
            console.error("lightGallery is not defined");
            return;
        }

        // Initialize lightGallery after justifiedGallery is complete
        lightGallery(galleryElement, {
            plugins: [lgZoom, lgThumbnail],
            speed: 500,
            thumbnail: true,
            animateThumb: true,
            mobileSettings: {
                controls: false,
                showCloseIcon: false,
                download: true,
                rotate: false
            }
        });

        console.log("lightGallery initialization complete");
    });
});