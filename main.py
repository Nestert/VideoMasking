import cv2
import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
from PIL import Image, ImageTk
import platform

class VideoAnnotationTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Annotation Tool")
        
        # Initialize variables
        self.video_path = None
        self.cap = None
        self.current_frame = None
        self.masks = []  # List to store multiple masks
        self.undo_stacks = []  # List of undo stacks corresponding to each mask
        self.current_mask_index = -1  # Index to track the current mask
        self.drawing = False
        self.drawing_started = False  # Flag to prevent multiple undo pushes
        self.eraser_mode = False  # Initialize eraser mode
        self.brush_size = 5  # Default brush size
        self.zoom_level = 1.0  # Initialize zoom level
        
        # Create GUI elements
        self.create_widgets()
        
        # Bind arrow keys for panning
        self.bind_arrow_keys()
        
    def create_widgets(self):
        # Upload button
        self.upload_btn = tk.Button(self.root, text="Upload Video", command=self.upload_video)
        self.upload_btn.pack(pady=10)
        
        # Frame for canvas and scrollbars
        self.canvas_container = tk.Frame(self.root)
        self.canvas_container.pack(fill=tk.BOTH, expand=True)
        
        # Vertical scrollbar
        self.v_scroll = tk.Scrollbar(self.canvas_container, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Horizontal scrollbar
        self.h_scroll = tk.Scrollbar(self.canvas_container, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Canvas for video display
        self.canvas = tk.Canvas(self.canvas_container, width=800, height=600, bg='grey',
                                xscrollcommand=self.h_scroll.set,
                                yscrollcommand=self.v_scroll.set)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Configure scrollbars
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        
        # Control buttons
        self.controls_frame = tk.Frame(self.root)
        self.controls_frame.pack(pady=10, fill=tk.X)  # Ensure the control frame fills horizontally
        
        self.prev_btn = tk.Button(self.controls_frame, text="Previous Frame", command=self.prev_frame)
        self.prev_btn.pack(side=tk.LEFT, padx=5)
        
        self.next_btn = tk.Button(self.controls_frame, text="Next Frame", command=self.next_frame)
        self.next_btn.pack(side=tk.LEFT, padx=5)
        
        self.new_mask_btn = tk.Button(self.controls_frame, text="New Mask", command=self.new_mask)
        self.new_mask_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_btn = tk.Button(self.controls_frame, text="Save Mask", command=self.save_mask)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_mask_btn = tk.Button(self.controls_frame, text="Clear Mask", command=self.clear_mask)
        self.clear_mask_btn.pack(side=tk.LEFT, padx=5)
        
        self.undo_btn = tk.Button(self.controls_frame, text="Undo", command=self.undo)
        self.undo_btn.pack(side=tk.LEFT, padx=5)
        
        self.eraser_btn = tk.Button(self.controls_frame, text="Toggle Eraser", command=self.toggle_eraser)
        self.eraser_btn.pack(side=tk.LEFT, padx=5)
        
        # Brush size slider
        self.brush_size_slider = tk.Scale(self.controls_frame, from_=1, to=20, orient=tk.HORIZONTAL, label="Brush Size")
        self.brush_size_slider.set(self.brush_size)
        self.brush_size_slider.pack(side=tk.LEFT, padx=5)
        
        # Zoom in and out buttons
        self.zoom_in_btn = tk.Button(self.controls_frame, text="Zoom In", command=self.zoom_in)
        self.zoom_in_btn.pack(side=tk.LEFT, padx=5)
        
        self.zoom_out_btn = tk.Button(self.controls_frame, text="Zoom Out", command=self.zoom_out)
        self.zoom_out_btn.pack(side=tk.LEFT, padx=5)
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self.start_drawing)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drawing)
        self.bind_mouse_wheel()
    
    def bind_mouse_wheel(self):
        # Detect the operating system to bind mouse wheel correctly
        os_name = platform.system()
        if os_name == 'Windows' or os_name == 'Darwin':
            self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        else:  # Linux or other
            self.canvas.bind("<Button-4>", self.on_mousewheel)
            self.canvas.bind("<Button-5>", self.on_mousewheel)
    
    def on_mousewheel(self, event):
        # Detect if Shift key is held for panning
        if event.state & 0x0001:
            # Shift is held: perform panning
            if platform.system() == 'Windows' or platform.system() == 'Darwin':
                if event.delta > 0:
                    self.canvas.xview_scroll(-1, "units")  # Scroll left
                else:
                    self.canvas.xview_scroll(1, "units")  # Scroll right
            else:
                if event.num == 4:
                    self.canvas.xview_scroll(-1, "units")
                elif event.num == 5:
                    self.canvas.xview_scroll(1, "units")
        else:
            # No modifier: perform zooming
            if platform.system() == 'Windows' or platform.system() == 'Darwin':
                if event.delta > 0:
                    self.zoom_in()
                else:
                    self.zoom_out()
            else:
                if event.num == 4:
                    self.zoom_in()
                elif event.num == 5:
                    self.zoom_out()
    
    def bind_arrow_keys(self):
        self.root.bind("<Left>", lambda event: self.canvas.xview_scroll(-1, "units"))
        self.root.bind("<Right>", lambda event: self.canvas.xview_scroll(1, "units"))
        self.root.bind("<Up>", lambda event: self.canvas.yview_scroll(-1, "units"))
        self.root.bind("<Down>", lambda event: self.canvas.yview_scroll(1, "units"))
    
    def upload_video(self):
        self.video_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv")])
        if self.video_path:
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                messagebox.showerror("Error", "Не удалось открыть видео файл.")
                return
            self.show_frame()
    
    def show_frame(self):
        if self.cap is not None:
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Initialize the first mask if no masks exist
                if not self.masks:
                    new_mask = np.zeros(self.current_frame.shape[:2], dtype=np.uint8)
                    self.masks.append(new_mask)
                    self.undo_stacks.append([])  # Initialize undo stack for the new mask
                    self.current_mask_index = 0
                self.update_canvas()
            else:
                # Если достигнут конец видео, сбросить позицию на начало
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.show_frame()
    
    def clear_mask(self):
        if self.current_mask_index != -1:
            # Push current mask to undo stack before clearing
            self.push_undo()
            self.masks[self.current_mask_index].fill(0)  # Clear the current mask
            self.update_canvas()
    
    def new_mask(self):
        # Create a new mask and set it as the current mask
        if self.current_frame is not None:
            new_mask = np.zeros(self.current_frame.shape[:2], dtype=np.uint8)
            self.masks.append(new_mask)
            self.undo_stacks.append([])  # Initialize undo stack for the new mask
            self.current_mask_index = len(self.masks) - 1
            self.update_canvas()
    
    def push_undo(self):
        if self.current_mask_index != -1:
            # Make a copy of the current mask and push to the corresponding undo stack
            mask_copy = self.masks[self.current_mask_index].copy()
            self.undo_stacks[self.current_mask_index].append(mask_copy)
            # Limit the undo stack size if necessary (optional)
            if len(self.undo_stacks[self.current_mask_index]) > 20:
                self.undo_stacks[self.current_mask_index].pop(0)
    
    def undo(self):
        if self.current_mask_index != -1 and self.undo_stacks[self.current_mask_index]:
            # Pop the last state from the undo stack and set it as the current mask
            last_state = self.undo_stacks[self.current_mask_index].pop()
            self.masks[self.current_mask_index] = last_state
            self.update_canvas()
        else:
            messagebox.showinfo("Undo", "Нет доступных действий для отмены.")
    
    def draw(self, event):
        if self.drawing and self.current_mask_index != -1:
            # Adjust for zoom to get the correct position on the original image
            x = int(self.canvas.canvasx(event.x) / self.zoom_level)
            y = int(self.canvas.canvasy(event.y) / self.zoom_level)
            brush_size = self.brush_size_slider.get()  # Get the current brush size from the slider
            
            # Ensure coordinates are within image bounds
            if 0 <= x < self.current_frame.shape[1] and 0 <= y < self.current_frame.shape[0]:
                # Push the current mask state before modification
                if not self.drawing_started:
                    self.push_undo()
                    self.drawing_started = True
                
                if self.eraser_mode:
                    cv2.circle(self.masks[self.current_mask_index], (x, y), brush_size, 0, -1)  # Erase part of the mask
                else:
                    cv2.circle(self.masks[self.current_mask_index], (x, y), brush_size, 255, -1)  # Draw on the mask
                self.update_canvas()
    
    def start_drawing(self, event):
        self.drawing = True
        self.drawing_started = False  # Flag to ensure undo is pushed once per drawing action
        self.draw(event)
    
    def stop_drawing(self, event):
        self.drawing = False
        self.drawing_started = False  # Reset the flag
    
    def toggle_eraser(self):
        self.eraser_mode = not self.eraser_mode  # Toggle eraser mode
        if self.eraser_mode:
            self.eraser_btn.config(relief=tk.SUNKEN, bg='red')
        else:
            self.eraser_btn.config(relief=tk.RAISED, bg='SystemButtonFace')
    
    def update_canvas(self):
        if self.current_frame is not None:
            # Overlay all masks on frame
            display_frame = self.current_frame.copy()
            for mask in self.masks:
                # Create a red overlay where mask is present
                red_overlay = np.zeros_like(display_frame, dtype=np.uint8)
                red_overlay[:, :, 0] = 255  # Red channel
                mask_bool = mask == 255
                # Blend the red overlay with the original frame
                display_frame[mask_bool] = cv2.addWeighted(display_frame, 0.5, red_overlay, 0.5, 0)[mask_bool]
            
            # Apply zoom only to the image
            height, width = display_frame.shape[:2]
            zoomed_width = int(width * self.zoom_level)
            zoomed_height = int(height * self.zoom_level)
            zoomed_frame = cv2.resize(display_frame, (zoomed_width, zoomed_height), interpolation=cv2.INTER_LINEAR)
            
            # Convert to PhotoImage
            image = Image.fromarray(zoomed_frame)
            photo = ImageTk.PhotoImage(image)
            
            # Update canvas with zoomed image
            self.canvas.delete("all")  # Clear previous image
            self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            self.canvas.image = photo  # Keep a reference to prevent garbage collection
            
            # Update scrollregion
            self.canvas.config(scrollregion=(0, 0, zoomed_width, zoomed_height))
    
    def zoom_in(self):
        self.zoom_level *= 1.2  # Increase zoom level
        if self.zoom_level > 5.0:  # Maximum zoom level
            self.zoom_level = 5.0
        self.update_canvas()
    
    def zoom_out(self):
        self.zoom_level /= 1.2  # Decrease zoom level
        if self.zoom_level < 0.2:  # Minimum zoom level
            self.zoom_level = 0.2
        self.update_canvas()
    
    def save_mask(self):
        if self.masks and self.cap is not None:
            # Get the current frame number and time
            frame_number = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            video_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000  # Convert milliseconds to seconds
            
            # Select directory to save masks
            save_dir = filedialog.askdirectory(title="Выберите папку для сохранения масок")
            if not save_dir:
                return  # Если пользователь отменил выбор папки
            
            # Save each mask with a unique filename
            for i, mask in enumerate(self.masks):
                filename = f"mask_{i}_time_{video_time:.2f}_frame_{frame_number}.png"
                filepath = f"{save_dir}/{filename}"
                cv2.imwrite(filepath, mask)
            
            messagebox.showinfo("Save Mask", f"Маски успешно сохранены в {save_dir}.")
        else:
            messagebox.showwarning("Save Mask", "Нет масок для сохранения или видео не загружено.")
    
    def next_frame(self):
        if self.cap is not None:
            self.show_frame()
    
    def prev_frame(self):
        if self.cap is not None and self.video_path:
            current_pos = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            # Move back two frames: one to go to the previous frame, another because read() moves forward
            new_pos = max(0, current_pos - 2)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_pos)
            self.show_frame()

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoAnnotationTool(root)
    root.mainloop()