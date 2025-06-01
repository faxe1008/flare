from typing import List, Dict
from pydantic import BaseModel
import gphoto2 as gp
import usb.core
import usb.util
import os
import time


class CameraInfo(BaseModel):
    index: int
    bus: int
    device: int
    manufacturer_id: str
    product_id: str


class CameraClient:

    def list_connected_cameras(self) -> List[CameraInfo]:
        cameras = gp.Camera.autodetect()
        camera_list: List[CameraInfo] = []

        for idx, (_name, port) in enumerate(cameras):
            if not port.startswith("usb:"):
                continue

            try:
                bus_str, dev_str = port[4:].split(",")
                bus = int(bus_str)
                device = int(dev_str)

                dev = usb.core.find(bus=bus, address=device)
                if dev is not None:
                    manufacturer = (
                        usb.util.get_string(dev, dev.iManufacturer) or "Unknown"
                    )
                    product = usb.util.get_string(dev, dev.iProduct) or "Unknown"

                    camera_list.append(
                        CameraInfo(
                            index=idx,
                            bus=bus,
                            device=device,
                            manufacturer_id=manufacturer,
                            product_id=product,
                        )
                    )
            except Exception as e:
                print(f"Error processing camera at port '{port}': {e}")

        return camera_list

    def list_files(self, camera_info: CameraInfo) -> List[str]:
        cameras = gp.Camera.autodetect()
        if camera_info.index >= len(cameras):
            raise IndexError("Camera index out of range")

        camera = gp.Camera()
        context = gp.Context()
        camera.init(context)

        def _list_files_in_folder(path: str) -> List[str]:
            result = []
            for name, _ in camera.folder_list_files(path):
                result.append(os.path.join(path, name))
            for name, _ in camera.folder_list_folders(path):
                result.extend(_list_files_in_folder(os.path.join(path, name)))
            return result

        try:
            return _list_files_in_folder("/")
        finally:
            camera.exit(context)

    def list_images(self, camera_info: CameraInfo) -> Dict[str, object]:
        """
        Returns a dict mapping each file-path on the camera (e.g. "/DCIM/100CANON/IMG_0001.JPG")
        to its `CameraFileInfo` object (the return value of camera.file_get_info(...)).
        """
        cameras = gp.Camera.autodetect()
        if camera_info.index >= len(cameras):
            raise IndexError("Camera index out of range")

        camera = gp.Camera()
        context = gp.Context()
        camera.init(context)

        images: Dict[str, object] = {}

        def _recurse_and_collect(path: str):
            for fname, _ in camera.folder_list_files(path):
                fullpath = os.path.join(path, fname)
                info = camera.file_get_info(path, fname)
                images[fullpath] = info

            for subfolder, _ in camera.folder_list_folders(path):
                _recurse_and_collect(os.path.join(path, subfolder))

        try:
            _recurse_and_collect("/")
            return images
        finally:
            camera.exit(context)

    def list_new_files(self, camera_info: CameraInfo, days: int) -> Dict[str, object]:
        """
        Returns a dictionary of all files whose `mtime` (camera-side modification time)
        is within the last `days` days. Uses `list_images()` internally.
        """
        all_images = self.list_images(camera_info)
        cutoff = time.time() - (days * 86400)

        new_files: Dict[str, object] = {}
        for path, info in all_images.items():
            # info.file.mtime is a time_t (seconds since epoch)
            if hasattr(info, "file") and getattr(info.file, "mtime", 0) >= cutoff:
                new_files[path] = info

        return new_files

    def download_new_files(
        self, camera_info: CameraInfo, days: int, destination: str
    ) -> List[str]:
        """
        Downloads all camera‐side files modified in the last `days` days into `destination`.
        Returns a list of local file paths that were written.

        - `camera_info`: the CameraInfo for the target camera
        - `days`: look for files whose mtime is within the last `days` days
        - `destination`: local folder where files will be saved (flat structure)
        """
        # 1) Gather all new files on the camera
        new_files = self.list_new_files(camera_info, days)
        if not new_files:
            return []

        # 2) Make sure destination folder exists
        os.makedirs(destination, exist_ok=True)

        # 3) Open the camera
        cameras = gp.Camera.autodetect()
        if camera_info.index >= len(cameras):
            raise IndexError("Camera index out of range")

        camera = gp.Camera()
        context = gp.Context()
        camera.init(context)

        downloaded_paths: List[str] = []

        try:
            for cam_path, info in new_files.items():
                # cam_path is something like "/DCIM/100CANON/IMG_0001.JPG"
                folder, name = os.path.split(cam_path)

                # Retrieve the file data from the camera
                gp_file = camera.file_get(folder, name, gp.GP_FILE_TYPE_NORMAL)

                # Local path to write to
                local_path = os.path.join(destination, name)

                # Save and record
                gp_file.save(local_path)
                downloaded_paths.append(local_path)

            return downloaded_paths

        finally:
            camera.exit(context)
