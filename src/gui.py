import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import rawpy
import os


class ImageSelectionDialog:
    def __init__(self, images, preselected=None):
        self.images = images
        self.preselected = set(preselected) if preselected else set()
        self.selected = set(self.preselected)
        self.image_refs = {}
        self.thumb_size = (250, 250)
        self.columns = None      # will be set on the first draw
        self._resize_job = None

    def show(self):
        self.root = tk.Tk()
        self.root.title("Select Images")
        self.root.geometry("800x600")
        self.root.update_idletasks()
        self._center_window()

        # — Scrollable Canvas Setup —
        container = ttk.Frame(self.root)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        # When scrollable_frame’s size changes, update scrollregion
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Force an initial layout pass so we know actual widths
        self.root.update_idletasks()

        # --- Draw thumbnails for the first time ---
        self._draw_images(initial=True)

        # Now that the grid is laid out once, bind <Configure> for resizing
        self.root.bind("<Configure>", self._on_root_resize)

        # Submit Button
        submit_btn = ttk.Button(self.root, text="Submit", command=self.root.quit)
        submit_btn.pack(pady=5)

        self.root.mainloop()
        self.root.destroy()
        return list(self.selected)

    def _draw_images(self, initial=False):
        # Clear previous widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Determine available width for thumbnails
        canvas_width = self.canvas.winfo_width()
        if canvas_width < self.thumb_size[0] + 20:
            # If canvas isn’t yet laid out, fall back to root’s width
            canvas_width = self.root.winfo_width()

        # Compute how many columns fit
        new_columns = max(1, canvas_width // (self.thumb_size[0] + 20))

        # If this is NOT the initial draw, and the column count didn't change, skip redraw
        if not initial and new_columns == self.columns:
            return

        self.columns = new_columns

        for idx, path in enumerate(self.images):
            row = idx // self.columns
            col = idx % self.columns

            frame = tk.Frame(self.scrollable_frame, highlightthickness=3, bd=2)
            frame.grid(row=row, column=col, padx=10, pady=10, sticky="n")

            # Load NEF via rawpy or normal image via PIL
            try:
                if path.lower().endswith(".nef"):
                    with rawpy.imread(path) as raw:
                        thumb = raw.extract_thumb()
                        if thumb.format == rawpy.ThumbFormat.JPEG:
                            from io import BytesIO
                            img_data = BytesIO(thumb.data)
                            img = Image.open(img_data)
                        else:
                            img = Image.fromarray(thumb.data)
                else:
                    img = Image.open(path)
                img.thumbnail(self.thumb_size)
                photo = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Failed to load {path}: {e}")
                continue

            self.image_refs[path] = photo
            label = tk.Label(frame, image=photo)
            label.pack()
            label.bind("<Button-1>", lambda e, f=frame, p=path: self._toggle(f, p))

            # Initial border color based on preselection
            if path in self.selected:
                frame.config(highlightbackground="blue")
            else:
                frame.config(highlightbackground="gray")

    def _toggle(self, frame, path):
        if path in self.selected:
            self.selected.remove(path)
            frame.config(highlightbackground="gray")
        else:
            self.selected.add(path)
            frame.config(highlightbackground="blue")

    def _on_root_resize(self, event):
        # Debounce: only redraw 100ms after the last resize event
        #if self._resize_job:
        #    self.root.after_cancel(self._resize_job)
        #self._resize_job = self.root.after(100, lambda: self._draw_images(initial=False))
        pass

    def _center_window(self):
        w, h = 900, 600
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
