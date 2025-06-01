import tempfile
import os

from camera_client import CameraClient, CameraInfo
from image_database import ImageMetadata, ImageDatabase
from gui import ImageSelectionDialog

DAYS_SINCE_SYNC = 2


def download_new_images(path, days):
    camera_client = CameraClient()
    cams = camera_client.list_connected_cameras()
    download_files = camera_client.download_new_files(cams[-1], days, path)
    print(f"Downloaded {len(download_files)} files")
    return download_files


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmpdir:
        downloaded_files = {
            x: ImageMetadata.load(x)
            for x in download_new_images(tmpdir, DAYS_SINCE_SYNC)
        }


        preselected_files = []
        for image, metadata in downloaded_files.items():
            if metadata.rating > 0:
                print(f"## {image}")
                preselected_files.append(image)
            else:
                print(f"   {image}")

        
        dialog = ImageSelectionDialog(downloaded_files.keys(), preselected=preselected_files)
        dialog.show()
