import os
import json
import sqlite3
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel
import exiftool


class ImageMetadata(BaseModel):
    file_name: str
    rating: int
    aperture: float
    lens_id: str
    capture_time: str
    focal_length: float
    exposure_time: float
    color_temperature: int

    @staticmethod
    def load(path: str):
        with exiftool.ExifTool() as et:
            output = et.execute(b"-j", path.encode())
            metadata = json.loads(output)[0]

        return ImageMetadata(
            file_name=os.path.basename(path),
            rating=int(metadata.get("XMP:Rating", 0)),
            aperture=float(metadata.get("EXIF:FNumber", 0.0)),
            lens_id=str(metadata.get("Composite:LensSpec", "")),
            capture_time=str(metadata.get("EXIF:DateTimeOriginal", "")),
            focal_length=float(metadata.get("EXIF:FocalLength", 0.0)),
            exposure_time=float(metadata.get("EXIF:ExposureTime", 0.0)),
            color_temperature=int(metadata.get("EXIF:WhiteBalance", 0)),
        )


class ImageDatabase(BaseModel):
    database_path: str

    def connect(self):
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                file_name TEXT PRIMARY KEY,
                rating INTEGER,
                aperture REAL,
                lens_id TEXT,
                capture_time TEXT,
                focal_length REAL,
                exposure_time REAL,
                color_temperature INTEGER
            )
        """
        )
        conn.commit()
        return conn

    def add(self, image_data: List[ImageMetadata]):
        conn = self.connect()
        cursor = conn.cursor()
        for img in image_data:
            cursor.execute(
                """
                INSERT OR REPLACE INTO images (
                    file_name, rating, aperture, lens_id, capture_time,
                    focal_length, exposure_time, color_temperature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    img.file_name,
                    img.rating,
                    img.aperture,
                    img.lens_id,
                    img.capture_time,
                    img.focal_length,
                    img.exposure_time,
                    img.color_temperature,
                ),
            )
        conn.commit()
        conn.close()

    def contains(self, image_data: ImageMetadata) -> bool:
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM images
            WHERE rating = ?
              AND aperture = ?
              AND lens_id = ?
              AND capture_time = ?
              AND focal_length = ?
              AND exposure_time = ?
              AND color_temperature = ?
            """,
            (
                image_data.rating,
                image_data.aperture,
                image_data.lens_id,
                image_data.capture_time,
                image_data.focal_length,
                image_data.exposure_time,
                image_data.color_temperature,
            ),
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def clear(self):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM images")
        conn.commit()
        conn.close()

    def rebuild(self, image_paths: List[str], thread_count: Optional[int] = 4):
        self.clear()

        def process(path: str):
            try:
                return ImageMetadata.load(path)
            except Exception as e:
                print(f"Failed to load {path}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            results = list(executor.map(process, image_paths))

        metadata_list = [md for md in results if md is not None]
        self.add(metadata_list)
