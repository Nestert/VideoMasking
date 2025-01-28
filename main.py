import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from PIL import Image, ImageTk
import platform
import json
from datetime import timedelta

class VideoAnnotationTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Video Annotation Tool")
        self.root.geometry("1200x800")
        
        # Инициализация переменных
        self.video_path = None
        self.cap = None
        self.total_frames = 0
        self.current_frame = None
        self.masks = []
        self.undo_stacks = []
        self.redo_stacks = []
        self.current_mask_index = -1
        self.drawing = False
        self.last_x = 0
        self.last_y = 0
        self.zoom_level = 1.0
        self.pan_start = None
        self.cached_frame = None
        self.last_zoom = 1.0
        self.tools = {
            "brush": {"size": 5, "color": (255, 0, 0)},
            "rectangle": {"color": (0, 255, 0)},
            "eraser": {"size": 10}
        }
        self.current_tool = "brush"
        
        # Создание интерфейса
        self.create_widgets()
        self.setup_bindings()
        self.setup_menus()
        
    def create_widgets(self):
        # Главный контейнер
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Панель инструментов
        tool_frame = ttk.Frame(main_frame)
        tool_frame.pack(side=tk.TOP, fill=tk.X)
        
        self.tool_buttons = {}
        for tool in ["brush", "rectangle", "eraser"]:
            btn = ttk.Button(tool_frame, text=tool.capitalize(), 
                           command=lambda t=tool: self.set_tool(t))
            btn.pack(side=tk.LEFT, padx=2)
            self.tool_buttons[tool] = btn
            
        ttk.Separator(tool_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        
        self.brush_size = tk.IntVar(value=5)
        ttk.Scale(tool_frame, from_=1, to=50, variable=self.brush_size,
                 command=lambda v: self.update_brush_size()).pack(side=tk.LEFT, padx=5)
        self.brush_label = ttk.Label(tool_frame, text="Size: 5")
        self.brush_label.pack(side=tk.LEFT)
        
        # Основная область
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Холст с прокруткой
        self.canvas = tk.Canvas(canvas_frame, bg="gray", cursor="cross")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Панель масок
        mask_panel = ttk.Frame(canvas_frame, width=200)
        mask_panel.pack(side=tk.RIGHT, fill=tk.Y)
        
        ttk.Button(mask_panel, text="New Mask", command=self.create_mask).pack(pady=5)
        ttk.Button(mask_panel, text="Delete Mask", command=self.delete_mask).pack(pady=5)
        
        self.mask_list = tk.Listbox(mask_panel)
        self.mask_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.mask_list.bind("<<ListboxSelect>>", self.select_mask)
        
        # Временная шкала
        self.timeline = ttk.Scale(main_frame, command=self.on_timeline_change)
        self.timeline.pack(fill=tk.X, padx=10, pady=5)
        
        # Статус бар
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def setup_bindings(self):
        self.canvas.bind("<Button-1>", self.start_action)
        self.canvas.bind("<B1-Motion>", self.perform_action)
        self.canvas.bind("<ButtonRelease-1>", self.end_action)
        self.canvas.bind("<Motion>", self.update_cursor_position)
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-s>", lambda e: self.save_project())
        self.root.bind("<MouseWheel>", self.zoom_handler)
        self.root.bind("<Control-MouseWheel>", self.zoom_handler)
        
    def setup_menus(self):
        menu_bar = tk.Menu(self.root)
        
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open Video", command=self.open_video)
        file_menu.add_command(label="Save Project", command=self.save_project)
        file_menu.add_command(label="Export Masks", command=self.export_masks)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        
        menu_bar.add_cascade(label="File", menu=file_menu)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)
        
        self.root.config(menu=menu_bar)
        
    def open_video(self):
        path = filedialog.askopenfilename(filetypes=[
            ("Video Files", "*.mp4 *.avi *.mov *.mkv"),
            ("All Files", "*.*")
        ])
        if path:
            self.video_path = path
            self.cap = cv2.VideoCapture(path)
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.timeline.config(to=self.total_frames)
            self.show_frame()
            self.update_status()
            
    def show_frame(self):
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.cached_frame = None
            self.draw_overlays()
            
    def draw_overlays(self):
        if self.current_frame is None:
            return
        
        display_frame = self.current_frame.copy()
        
        # Рисование всех масок
        for idx, mask in enumerate(self.masks):
            color = (255, 0, 0) if idx == self.current_mask_index else (0, 0, 255)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(display_frame, contours, -1, color, 2)
            
        # Применение масштаба
        h, w = display_frame.shape[:2]
        zoomed_size = (int(w * self.zoom_level), int(h * self.zoom_level))
        
        if self.cached_frame is None or zoomed_size != self.cached_frame.size:
            self.cached_frame = ImageTk.PhotoImage(
                Image.fromarray(display_frame).resize(zoomed_size, Image.LANCZOS)
            )
            
        self.canvas.config(
            scrollregion=(0, 0, zoomed_size[0], zoomed_size[1]),
            width=zoomed_size[0],
            height=zoomed_size[1]
        )
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.cached_frame, anchor=tk.NW)
        
    def create_mask(self):
        new_mask = np.zeros(self.current_frame.shape[:2], dtype=np.uint8)
        self.masks.append(new_mask)
        self.undo_stacks.append([])
        self.redo_stacks.append([])
        self.mask_list.insert(tk.END, f"Mask {len(self.masks)}")
        self.current_mask_index = len(self.masks) - 1
        self.mask_list.selection_clear(0, tk.END)
        self.mask_list.selection_set(self.current_mask_index)
        self.update_status()
        
    def delete_mask(self):
        if self.current_mask_index >= 0:
            del self.masks[self.current_mask_index]
            del self.undo_stacks[self.current_mask_index]
            del self.redo_stacks[self.current_mask_index]
            self.mask_list.delete(self.current_mask_index)
            self.current_mask_index = max(0, self.current_mask_index - 1)
            self.draw_overlays()
            
    def select_mask(self, event):
        selection = self.mask_list.curselection()
        if selection:
            self.current_mask_index = selection[0]
            self.draw_overlays()
            
    def set_tool(self, tool):
        self.current_tool = tool
        for t, btn in self.tool_buttons.items():
            btn.state(["!pressed" if t != tool else "pressed"])
        self.update_cursor()
        
    def update_brush_size(self):
        size = self.brush_size.get()
        self.tools["brush"]["size"] = size
        self.tools["eraser"]["size"] = size
        self.brush_label.config(text=f"Size: {size}")
        
    def start_action(self, event):
        self.drawing = True
        x = self.canvas.canvasx(event.x) / self.zoom_level
        y = self.canvas.canvasy(event.y) / self.zoom_level
        self.last_x, self.last_y = x, y
        
        if self.current_mask_index >= 0:
            self.push_undo()
            
    def perform_action(self, event):
        if not self.drawing or self.current_mask_index < 0:
            return
            
        x = self.canvas.canvasx(event.x) / self.zoom_level
        y = self.canvas.canvasy(event.y) / self.zoom_level
        
        mask = self.masks[self.current_mask_index]
        
        if self.current_tool == "brush":
            cv2.line(mask, 
                    (int(self.last_x), int(self.last_y)),
                    (int(x), int(y)),
                    255, self.tools["brush"]["size"])
            
        elif self.current_tool == "eraser":
            cv2.line(mask, 
                    (int(self.last_x), int(self.last_y)),
                    (int(x), int(y)),
                    0, self.tools["eraser"]["size"])
            
        elif self.current_tool == "rectangle":
            if not hasattr(self, 'rect_start'):
                self.rect_start = (x, y)
            self.temp_rect = (self.rect_start[0], self.rect_start[1], x, y)
            self.draw_temp_overlay()
            
        self.last_x, self.last_y = x, y
        self.draw_overlays()
        
    def end_action(self, event):
        if self.current_tool == "rectangle" and hasattr(self, 'rect_start'):
            x = self.canvas.canvasx(event.x) / self.zoom_level
            y = self.canvas.canvasy(event.y) / self.zoom_level
            x1, y1 = self.rect_start
            x2, y2 = x, y
            cv2.rectangle(self.masks[self.current_mask_index],
                         (int(min(x1, x2)), int(min(y1, y2))),
                         (int(max(x1, x2)), int(max(y1, y2))),
                         255, -1)
            del self.rect_start
            self.canvas.delete("temp")
            self.draw_overlays()
            
        self.drawing = False
        
    def push_undo(self):
        if self.current_mask_index >= 0:
            self.undo_stacks[self.current_mask_index].append(
                self.masks[self.current_mask_index].copy()
            )
            self.redo_stacks[self.current_mask_index].clear()
            
    def undo(self):
        if self.current_mask_index >= 0 and self.undo_stacks[self.current_mask_index]:
            self.redo_stacks[self.current_mask_index].append(
                self.masks[self.current_mask_index].copy()
            )
            self.masks[self.current_mask_index] = self.undo_stacks[self.current_mask_index].pop()
            self.draw_overlays()
            
    def redo(self):
        if self.current_mask_index >= 0 and self.redo_stacks[self.current_mask_index]:
            self.undo_stacks[self.current_mask_index].append(
                self.masks[self.current_mask_index].copy()
            )
            self.masks[self.current_mask_index] = self.redo_stacks[self.current_mask_index].pop()
            self.draw_overlays()
            
    def zoom_handler(self, event):
        if event.state & 0x4:  # Ctrl key
            delta = event.delta if platform.system() == 'Darwin' else -event.delta
            self.zoom_level *= 1.1 if delta > 0 else 0.9
            self.zoom_level = max(0.1, min(5.0, self.zoom_level))
            self.draw_overlays()
            
    def on_timeline_change(self, value):
        frame_num = int(float(value))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        self.show_frame()
        self.update_status()
        
    def update_status(self):
        if self.cap:
            pos = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            time_str = str(timedelta(seconds=pos)).split(".")[0]
            frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            status = f"Frame: {frame}/{self.total_frames} | Time: {time_str} | Tool: {self.current_tool}"
            self.status_bar.config(text=status)
            
    def update_cursor_position(self, event):
        x = self.canvas.canvasx(event.x) / self.zoom_level
        y = self.canvas.canvasy(event.y) / self.zoom_level
        self.status_bar.config(text=f"X: {int(x)}, Y: {int(y)}")
        
    def save_project(self):
        project = {
            "video_path": self.video_path,
            "current_frame": int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)),
            "masks": [mask.tolist() for mask in self.masks]
        }
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if path:
            with open(path, "w") as f:
                json.dump(project, f)
                
    def export_masks(self):
        path = filedialog.askdirectory()
        if path and self.masks:
            for idx, mask in enumerate(self.masks):
                cv2.imwrite(f"{path}/mask_{idx}.png", mask)
            messagebox.showinfo("Export", f"Exported {len(self.masks)} masks")
            
if __name__ == "__main__":
    root = tk.Tk()
    app = VideoAnnotationTool(root)
    root.mainloop()