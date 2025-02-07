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
        
        # Задаём размеры холста, чтобы интерфейс помещался на небольшом экране
        self.canvas_width = 640
        self.canvas_height = 480
        
        # Инициализация переменных
        self.video_path = None
        self.cap = None
        self.current_frame = None
        self.masks = []           # список для хранения масок
        self.undo_stacks = []     # стеки отмены для каждой маски
        self.redo_stacks = []     # стеки повтора для каждой маски
        self.current_mask_index = -1  # текущий индекс маски
        
        self.drawing = False
        self.drawing_started = False  # флаг для сохранения состояния перед рисованием
        self.eraser_mode = False        # режим ластика
        self.zoom_level = 1.0           # масштаб изображения
        self.alpha = 0.5              # прозрачность оверлея маски (от 0 до 1)
        self.playing = False          # состояние воспроизведения видео
        self.play_delay = 30          # задержка в мс для воспроизведения видео
        
        self.create_widgets()
        self.bind_events()
    
    def create_widgets(self):
        # --- Главное меню ---
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Открыть видео", command=self.open_video)
        file_menu.add_command(label="Сохранить маски", command=self.save_masks)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.root.quit)
        menubar.add_cascade(label="Файл", menu=file_menu)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="О программе", command=self.about_dialog)
        menubar.add_cascade(label="Справка", menu=help_menu)
        self.root.config(menu=menubar)
        
        # --- Метка для отображения информации о кадре ---
        self.frame_info_label = tk.Label(self.root, text="Кадр: 0, Время: 0.00 с")
        self.frame_info_label.pack(pady=2)
        
        # --- Холст с прокруткой ---
        self.canvas_container = tk.Frame(self.root)
        self.canvas_container.pack(fill=tk.BOTH, expand=True)
        
        self.v_scroll = tk.Scrollbar(self.canvas_container, orient=tk.VERTICAL)
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll = tk.Scrollbar(self.canvas_container, orient=tk.HORIZONTAL)
        self.h_scroll.grid(row=1, column=0, sticky="ew")
        
        self.canvas = tk.Canvas(self.canvas_container, width=self.canvas_width, height=self.canvas_height, bg='grey',
                                xscrollcommand=self.h_scroll.set,
                                yscrollcommand=self.v_scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        self.canvas_container.grid_rowconfigure(0, weight=1)
        self.canvas_container.grid_columnconfigure(0, weight=1)
        
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        
        # --- Панель управления (разбита на 2 строки) ---
        self.controls_frame = tk.Frame(self.root)
        self.controls_frame.pack(pady=5, fill=tk.X)
        
        # Первая строка элементов управления
        self.prev_frame_btn = tk.Button(self.controls_frame, text="Пред. кадр", command=self.prev_frame)
        self.prev_frame_btn.grid(row=0, column=0, padx=3, pady=2)
        self.next_frame_btn = tk.Button(self.controls_frame, text="След. кадр", command=self.next_frame)
        self.next_frame_btn.grid(row=0, column=1, padx=3, pady=2)
        self.play_pause_btn = tk.Button(self.controls_frame, text="Play", command=self.toggle_play_pause)
        self.play_pause_btn.grid(row=0, column=2, padx=3, pady=2)
        self.new_mask_btn = tk.Button(self.controls_frame, text="Новая маска (n)", command=self.new_mask)
        self.new_mask_btn.grid(row=0, column=3, padx=3, pady=2)
        self.clear_mask_btn = tk.Button(self.controls_frame, text="Очистить маску", command=self.clear_mask)
        self.clear_mask_btn.grid(row=0, column=4, padx=3, pady=2)
        self.prev_mask_btn = tk.Button(self.controls_frame, text="Пред. маска", command=self.prev_mask)
        self.prev_mask_btn.grid(row=0, column=5, padx=3, pady=2)
        self.next_mask_btn = tk.Button(self.controls_frame, text="След. маска", command=self.next_mask)
        self.next_mask_btn.grid(row=0, column=6, padx=3, pady=2)
        self.save_masks_btn = tk.Button(self.controls_frame, text="Сохранить маски", command=self.save_masks)
        self.save_masks_btn.grid(row=0, column=7, padx=3, pady=2)
        
        # Вторая строка элементов управления
        self.undo_btn = tk.Button(self.controls_frame, text="Undo (z)", command=self.undo)
        self.undo_btn.grid(row=1, column=0, padx=3, pady=2)
        self.redo_btn = tk.Button(self.controls_frame, text="Redo (y)", command=self.redo)
        self.redo_btn.grid(row=1, column=1, padx=3, pady=2)
        self.eraser_btn = tk.Button(self.controls_frame, text="Режим ластика (e)", command=self.toggle_eraser)
        self.eraser_btn.grid(row=1, column=2, padx=3, pady=2)
        
        self.brush_size_slider = tk.Scale(self.controls_frame, from_=1, to=50, orient=tk.HORIZONTAL, 
                                          label="Размер кисти", command=self.update_brush_size)
        self.brush_size_slider.set(5)
        self.brush_size_slider.grid(row=1, column=3, padx=3, pady=2)
        
        self.alpha_slider = tk.Scale(self.controls_frame, from_=0, to=100, orient=tk.HORIZONTAL, label="Прозрачность (%)")
        self.alpha_slider.set(int(self.alpha * 100))
        self.alpha_slider.grid(row=1, column=4, padx=3, pady=2)
        
        self.zoom_in_btn = tk.Button(self.controls_frame, text="Zoom In", command=self.zoom_in)
        self.zoom_in_btn.grid(row=1, column=5, padx=3, pady=2)
        self.zoom_out_btn = tk.Button(self.controls_frame, text="Zoom Out", command=self.zoom_out)
        self.zoom_out_btn.grid(row=1, column=6, padx=3, pady=2)
        self.reset_zoom_btn = tk.Button(self.controls_frame, text="Reset Zoom (r)", command=self.reset_zoom)
        self.reset_zoom_btn.grid(row=1, column=7, padx=3, pady=2)
        
        # --- Статусная строка ---
        self.status_bar = tk.Label(self.root, text="Статус: Ожидание", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Привязка событий мыши для рисования
        self.canvas.bind("<Button-1>", self.start_drawing)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drawing)
        self.bind_mouse_wheel()
    
    def bind_events(self):
        self.root.bind("<Left>", lambda event: self.canvas.xview_scroll(-1, "units"))
        self.root.bind("<Right>", lambda event: self.canvas.xview_scroll(1, "units"))
        self.root.bind("<Up>", lambda event: self.canvas.yview_scroll(-1, "units"))
        self.root.bind("<Down>", lambda event: self.canvas.yview_scroll(1, "units"))
        self.root.bind("<z>", lambda event: self.undo())
        self.root.bind("<y>", lambda event: self.redo())
        self.root.bind("<r>", lambda event: self.reset_zoom())
        self.root.bind("<e>", lambda event: self.toggle_eraser())
        self.root.bind("<n>", lambda event: self.new_mask())
        self.root.bind("<space>", lambda event: self.toggle_play_pause())
    
    def bind_mouse_wheel(self):
        os_name = platform.system()
        if os_name in ['Windows', 'Darwin']:
            self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        else:
            self.canvas.bind("<Button-4>", self.on_mousewheel)
            self.canvas.bind("<Button-5>", self.on_mousewheel)
    
    def on_mousewheel(self, event):
        # Если зажат Shift — панорамирование, иначе зумирование
        if event.state & 0x0001:
            if platform.system() in ['Windows', 'Darwin']:
                if event.delta > 0:
                    self.canvas.xview_scroll(-1, "units")
                else:
                    self.canvas.xview_scroll(1, "units")
            else:
                if event.num == 4:
                    self.canvas.xview_scroll(-1, "units")
                elif event.num == 5:
                    self.canvas.xview_scroll(1, "units")
        else:
            if platform.system() in ['Windows', 'Darwin']:
                if event.delta > 0:
                    self.zoom_in()
                else:
                    self.zoom_out()
            else:
                if event.num == 4:
                    self.zoom_in()
                elif event.num == 5:
                    self.zoom_out()
    
    def open_video(self):
        self.video_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv")])
        if self.video_path:
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                messagebox.showerror("Ошибка", "Не удалось открыть видео файл.")
                return
            self.playing = False
            self.play_pause_btn.config(text="Play")
            # Сброс предыдущих масок и состояний
            self.masks = []
            self.undo_stacks = []
            self.redo_stacks = []
            self.current_mask_index = -1
            self.show_frame()
    
    def show_frame(self):
        if self.cap is not None:
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if not self.masks:
                    new_mask = np.zeros(self.current_frame.shape[:2], dtype=np.uint8)
                    self.masks.append(new_mask)
                    self.undo_stacks.append([])
                    self.redo_stacks.append([])
                    self.current_mask_index = 0
                frame_number = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                video_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                self.frame_info_label.config(text=f"Кадр: {frame_number}, Время: {video_time:.2f} с")
                self.update_canvas()
                self.update_status_bar()
            else:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if self.playing:
                    self.playing = False
                    self.play_pause_btn.config(text="Play")
                self.show_frame()
    
    def update_canvas(self):
        if self.current_frame is not None:
            display_frame = self.current_frame.copy()
            self.alpha = self.alpha_slider.get() / 100.0
            for idx, mask in enumerate(self.masks):
                if mask is None:
                    continue
                red_overlay = np.zeros_like(display_frame, dtype=np.uint8)
                if idx == self.current_mask_index:
                    red_overlay[:, :, 0] = 255
                else:
                    red_overlay[:, :, 0] = 200
                mask_bool = mask == 255
                blended = cv2.addWeighted(display_frame, 1 - self.alpha, red_overlay, self.alpha, 0)
                display_frame[mask_bool] = blended[mask_bool]
            
            height, width = display_frame.shape[:2]
            zoomed_width = int(width * self.zoom_level)
            zoomed_height = int(height * self.zoom_level)
            zoomed_frame = cv2.resize(display_frame, (zoomed_width, zoomed_height), interpolation=cv2.INTER_LINEAR)
            
            image = Image.fromarray(zoomed_frame)
            photo = ImageTk.PhotoImage(image)
            
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            self.canvas.image = photo
            self.canvas.config(scrollregion=(0, 0, zoomed_width, zoomed_height))
    
    def update_status_bar(self):
        status_text = f"Маска: {self.current_mask_index+1}/{len(self.masks)} | "
        status_text += "Ластик: ВКЛ" if self.eraser_mode else "Ластик: выкл"
        status_text += f" | Зум: {self.zoom_level:.2f}"
        status_text += f" | Размер кисти: {self.brush_size_slider.get()}"
        self.status_bar.config(text=status_text)
    
    def update_brush_size(self, val):
        self.update_status_bar()
    
    def toggle_play_pause(self):
        if self.cap is None:
            return
        self.playing = not self.playing
        if self.playing:
            self.play_pause_btn.config(text="Pause")
            self.play_video()
        else:
            self.play_pause_btn.config(text="Play")
    
    def play_video(self):
        if self.playing and self.cap is not None:
            self.show_frame()
            self.root.after(self.play_delay, self.play_video)
    
    def next_frame(self):
        if self.cap is not None:
            self.show_frame()
    
    def prev_frame(self):
        if self.cap is not None and self.video_path:
            current_pos = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            new_pos = max(0, current_pos - 2)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_pos)
            self.show_frame()
    
    def new_mask(self):
        if self.current_frame is not None:
            new_mask = np.zeros(self.current_frame.shape[:2], dtype=np.uint8)
            self.masks.append(new_mask)
            self.undo_stacks.append([])
            self.redo_stacks.append([])
            self.current_mask_index = len(self.masks) - 1
            self.update_canvas()
            self.update_status_bar()
    
    def clear_mask(self):
        if self.current_mask_index != -1:
            self.push_undo()
            self.masks[self.current_mask_index].fill(0)
            self.update_canvas()
    
    def prev_mask(self):
        if self.masks:
            self.current_mask_index = (self.current_mask_index - 1) % len(self.masks)
            self.update_canvas()
            self.update_status_bar()
    
    def next_mask(self):
        if self.masks:
            self.current_mask_index = (self.current_mask_index + 1) % len(self.masks)
            self.update_canvas()
            self.update_status_bar()
    
    def push_undo(self):
        if self.current_mask_index != -1:
            mask_copy = self.masks[self.current_mask_index].copy()
            self.undo_stacks[self.current_mask_index].append(mask_copy)
            self.redo_stacks[self.current_mask_index] = []
            if len(self.undo_stacks[self.current_mask_index]) > 20:
                self.undo_stacks[self.current_mask_index].pop(0)
    
    def undo(self):
        if self.current_mask_index != -1 and self.undo_stacks[self.current_mask_index]:
            current_state = self.masks[self.current_mask_index].copy()
            self.redo_stacks[self.current_mask_index].append(current_state)
            last_state = self.undo_stacks[self.current_mask_index].pop()
            self.masks[self.current_mask_index] = last_state
            self.update_canvas()
        else:
            messagebox.showinfo("Undo", "Нет доступных действий для отмены.")
    
    def redo(self):
        if self.current_mask_index != -1 and self.redo_stacks[self.current_mask_index]:
            current_state = self.masks[self.current_mask_index].copy()
            self.undo_stacks[self.current_mask_index].append(current_state)
            next_state = self.redo_stacks[self.current_mask_index].pop()
            self.masks[self.current_mask_index] = next_state
            self.update_canvas()
        else:
            messagebox.showinfo("Redo", "Нет доступных действий для повтора.")
    
    def toggle_eraser(self):
        self.eraser_mode = not self.eraser_mode
        if self.eraser_mode:
            self.eraser_btn.config(relief=tk.SUNKEN, bg='red')
        else:
            self.eraser_btn.config(relief=tk.RAISED, bg='SystemButtonFace')
        self.update_status_bar()
    
    def start_drawing(self, event):
        if self.playing or self.current_frame is None:
            return
        self.drawing = True
        self.drawing_started = False
        self.draw(event)
    
    def draw(self, event):
        if self.drawing and self.current_mask_index != -1:
            x = int(self.canvas.canvasx(event.x) / self.zoom_level)
            y = int(self.canvas.canvasy(event.y) / self.zoom_level)
            brush_size = self.brush_size_slider.get()
            if 0 <= x < self.current_frame.shape[1] and 0 <= y < self.current_frame.shape[0]:
                if not self.drawing_started:
                    self.push_undo()
                    self.drawing_started = True
                if self.eraser_mode:
                    cv2.circle(self.masks[self.current_mask_index], (x, y), brush_size, 0, -1)
                else:
                    cv2.circle(self.masks[self.current_mask_index], (x, y), brush_size, 255, -1)
                self.update_canvas()
    
    def stop_drawing(self, event):
        self.drawing = False
        self.drawing_started = False
    
    def zoom_in(self):
        self.zoom_level *= 1.2
        if self.zoom_level > 5.0:
            self.zoom_level = 5.0
        self.update_canvas()
        self.update_status_bar()
    
    def zoom_out(self):
        self.zoom_level /= 1.2
        if self.zoom_level < 0.2:
            self.zoom_level = 0.2
        self.update_canvas()
        self.update_status_bar()
    
    def reset_zoom(self):
        self.zoom_level = 1.0
        self.update_canvas()
        self.update_status_bar()
    
    def save_masks(self):
        if self.masks and self.cap is not None:
            frame_number = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            video_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            save_dir = filedialog.askdirectory(title="Выберите папку для сохранения масок")
            if not save_dir:
                return
            for i, mask in enumerate(self.masks):
                filename = f"mask_{i}_time_{video_time:.2f}_frame_{frame_number}.png"
                filepath = f"{save_dir}/{filename}"
                cv2.imwrite(filepath, mask)
            messagebox.showinfo("Сохранение масок", f"Маски успешно сохранены в {save_dir}.")
        else:
            messagebox.showwarning("Сохранение масок", "Нет масок для сохранения или видео не загружено.")
    
    def about_dialog(self):
        messagebox.showinfo("О программе", "Video Annotation Tool\nРазработано экспертом по Python\n2025")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoAnnotationTool(root)
    root.mainloop()