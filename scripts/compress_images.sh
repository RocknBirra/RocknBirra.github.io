#!/bin/bash

IMAGE_DIR="images"
CHECKSUM_FILE="image_checksums.txt"

# Create the checksum file if it doesn't exist
if [ ! -f "$CHECKSUM_FILE" ]; then
  touch "$CHECKSUM_FILE"
fi

# Function to get the MD5 checksum of a file
get_checksum() {
  md5sum "$1" | awk '{ print $1 }'
}

# Loop through all JPG images in the directory
find "$IMAGE_DIR" -type f -name '*.JPG' | while read -r IMAGE; do
  # Get the current checksum of the image
  CURRENT_CHECKSUM=$(get_checksum "$IMAGE")

  # Check if the image has been compressed before
  if grep -q "$CURRENT_CHECKSUM" "$CHECKSUM_FILE"; then
    echo "Skipping already compressed image: $IMAGE"
  else
    # Compress the image
    jpegoptim --max=85 --strip-all "$IMAGE"

    # Get the new checksum after compression
    NEW_CHECKSUM=$(get_checksum "$IMAGE")

    # Update the checksum file
    echo "$NEW_CHECKSUM" >> "$CHECKSUM_FILE"
    echo "Compressed and logged checksum for image: $IMAGE"
  fi
done