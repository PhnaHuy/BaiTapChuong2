import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from threading import Thread

import cv2
import numpy as np
from PIL import Image, ImageTk


current_image_bgr = None
bitwise_images = [None, None]
bitwise_paths = [None, None]
selected_video_path = None
adjustment_image_bgr = None
canvas_source_image = None
canvas_rotation_degrees = 0
canvas_image_item = None
canvas_image_photo = None
canvas_drag_position = None


def display_image(label, image_array):
	image = Image.fromarray(image_array)
	image.thumbnail((440, 600), Image.Resampling.LANCZOS)
	photo = ImageTk.PhotoImage(image)
	label.configure(image=photo, text="")
	label.image = photo


def choose_image():
	global current_image_bgr

	image_path = filedialog.askopenfilename(
		title="Select an Image",
		filetypes=[
			("Image Files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"),
			("All Files", "*.*"),
		],
	)
	if not image_path:
		return

	try:
		image_data = np.fromfile(image_path, dtype=np.uint8)
		image_bgr = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
	except (OSError, cv2.error) as error:
		messagebox.showerror("Image Read Error", f"Could not read the image:\n{error}")
		return

	if image_bgr is None:
		messagebox.showerror("Image Read Error", "The selected file is not a valid image.")
		return

	current_image_bgr = image_bgr
	display_image(original_label, cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
	gray_label.configure(image="", text="Click 'Convert Colors' to view the grayscale image")
	gray_label.image = None
	hsv_label.configure(image="", text="Click 'Convert Colors' to view the HSV channels")
	hsv_label.image = None
	status_label.configure(text=f"{image_path}  |  {image_bgr.shape[1]} x {image_bgr.shape[0]} px")


	convert_button.configure(state=tk.NORMAL)


def convert_colors():
	if current_image_bgr is None:
		return

	gray_image = cv2.cvtColor(current_image_bgr, cv2.COLOR_BGR2GRAY)
	hsv_image = cv2.cvtColor(current_image_bgr, cv2.COLOR_BGR2HSV)
	hsv_display = hsv_image.copy()
	hsv_display[:, :, 0] = np.round(hsv_display[:, :, 0].astype(np.float32) * 255 / 179).astype(np.uint8)

	display_image(gray_label, gray_image)
	display_image(hsv_label, hsv_display)


def choose_bitwise_image(image_index):
	image_path = filedialog.askopenfilename(
		title=f"Select Image {image_index + 1}",
		filetypes=[
			("Image Files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"),
			("All Files", "*.*"),
		],
	)
	if not image_path:
		return

	try:
		image_data = np.fromfile(image_path, dtype=np.uint8)
		image_bgr = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
	except (OSError, cv2.error) as error:
		messagebox.showerror("Image Read Error", f"Could not read the image:\n{error}")
		return

	if image_bgr is None:
		messagebox.showerror("Image Read Error", "The selected file is not a valid image.")
		return

	bitwise_images[image_index] = image_bgr
	bitwise_paths[image_index] = image_path
	preview_label = bitwise_image1_label if image_index == 0 else bitwise_image2_label
	display_image(preview_label, cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
	bitwise_status_label.configure(
		text=f"Image {image_index + 1}: {image_path}  |  {image_bgr.shape[1]} x {image_bgr.shape[0]} px"
	)
	if all(image is not None for image in bitwise_images):
		bitwise_button.configure(state=tk.NORMAL)


def apply_bitwise_and():
	image1, image2 = bitwise_images
	if image1 is None or image2 is None:
		return

	height, width = image1.shape[:2]
	if image2.shape[:2] != (height, width):
		image2 = cv2.resize(image2, (width, height), interpolation=cv2.INTER_AREA)

	result = cv2.bitwise_and(image1, image2)
	display_image(bitwise_result_label, cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
	bitwise_status_label.configure(
		text=(
			f"Pixel-wise AND | Result size: {width} x {height} px"
			f" | Image 1: {bitwise_paths[0]}"
			f" | Image 2: {bitwise_paths[1]}"
		)
	)


def choose_video():
	global selected_video_path

	video_path = filedialog.askopenfilename(
		title="Select a Video",
		filetypes=[
			("Video Files", "*.mp4 *.avi *.mov *.mkv *.wmv *.m4v *.webm"),
			("All Files", "*.*"),
		],
	)
	if not video_path:
		return

	selected_video_path = video_path
	video_path_label.configure(text=video_path)
	video_export_status.configure(text="Ready to extract one frame every 2 seconds.")
	export_frames_button.configure(state=tk.NORMAL)


def export_video_frames():
	if not selected_video_path:
		return

	output_directory = filedialog.askdirectory(title="Select an Output Folder")
	if not output_directory:
		return

	video_path = selected_video_path
	image_extension = image_format_var.get()
	export_frames_button.configure(state=tk.DISABLED)
	video_export_status.configure(text="Extracting video frames... Please wait.")
	Thread(
		target=extract_video_frames,
		args=(video_path, output_directory, image_extension),
		daemon=True,
	).start()


def extract_video_frames(video_path, output_directory, image_extension):
	video = cv2.VideoCapture(video_path)
	if not video.isOpened():
		video.release()
		root.after(0, finish_video_export, 0, "Could not open the video file.")
		return

	fps = video.get(cv2.CAP_PROP_FPS)
	if not np.isfinite(fps) or fps <= 0:
		video.release()
		root.after(0, finish_video_export, 0, "Could not read the video's frame rate.")
		return

	frame_interval = max(1, int(round(fps * 2)))
	frame_index = 0
	next_frame_index = 0
	saved_count = 0
	error_message = None
	try:
		while True:
			read_success, frame = video.read()
			if not read_success:
				break

			if frame_index >= next_frame_index:
				output_path = f"{output_directory}/frame_{saved_count:04d}{image_extension}"
				encode_success, encoded_image = cv2.imencode(image_extension, frame)
				if not encode_success:
					error_message = f"Could not encode frame {saved_count + 1}."
					break
				encoded_image.tofile(output_path)
				saved_count += 1
				next_frame_index += frame_interval

			frame_index += 1
	except OSError as error:
		error_message = f"Image write error: {error}"
	finally:
		video.release()

	root.after(0, finish_video_export, saved_count, error_message, output_directory)


def finish_video_export(saved_count, error_message, output_directory=None):
	export_frames_button.configure(state=tk.NORMAL)
	if error_message:
		video_export_status.configure(text=f"Exported {saved_count} images. {error_message}")
		messagebox.showerror("Frame Export Error", error_message)
	elif saved_count:
		video_export_status.configure(
			text=f"Exported {saved_count} images to: {output_directory}"
		)
	else:
		video_export_status.configure(text="The video contains no frames to export.")


def choose_adjustment_image():
	global adjustment_image_bgr

	image_path = filedialog.askopenfilename(
		title="Select an Image to Adjust",
		filetypes=[
			("Image Files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"),
			("All Files", "*.*"),
		],
	)
	if not image_path:
		return

	try:
		image_data = np.fromfile(image_path, dtype=np.uint8)
		image_bgr = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
	except (OSError, cv2.error) as error:
		messagebox.showerror("Image Read Error", f"Could not read the image:\n{error}")
		return

	if image_bgr is None:
		messagebox.showerror("Image Read Error", "The selected file is not a valid image.")
		return

	adjustment_image_bgr = image_bgr
	display_image(adjustment_original_label, cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
	adjustment_path_label.configure(
		text=f"{image_path}  |  {image_bgr.shape[1]} x {image_bgr.shape[0]} px"
	)
	update_adjustment_preview()


def update_adjustment_preview(*_):
	if adjustment_image_bgr is None:
		return

	brightness = int(float(brightness_var.get()))
	saturation = float(saturation_var.get()) / 100
	brightened = np.clip(adjustment_image_bgr.astype(np.int16) + brightness, 0, 255).astype(np.uint8)
	hsv_image = cv2.cvtColor(brightened, cv2.COLOR_BGR2HSV)
	hsv_image[:, :, 1] = np.clip(
		hsv_image[:, :, 1].astype(np.float32) * saturation,
		0,
		255,
	).astype(np.uint8)
	adjusted_bgr = cv2.cvtColor(hsv_image, cv2.COLOR_HSV2BGR)
	display_image(adjustment_result_label, cv2.cvtColor(adjusted_bgr, cv2.COLOR_BGR2RGB))
	brightness_value_label.configure(text=f"{brightness:+d}")
	saturation_value_label.configure(text=f"{int(float(saturation_var.get()))}%")


def reset_adjustments():
	brightness_var.set(0)
	saturation_var.set(100)


def choose_canvas_image():
	global canvas_source_image, canvas_rotation_degrees, canvas_image_item, canvas_image_photo

	image_path = filedialog.askopenfilename(
		title="Select an Image for the Canvas",
		filetypes=[
			("Image Files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"),
			("All Files", "*.*"),
		],
	)
	if not image_path:
		return

	try:
		image_data = np.fromfile(image_path, dtype=np.uint8)
		image_bgr = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
	except (OSError, cv2.error) as error:
		messagebox.showerror("Image Read Error", f"Could not read the image:\n{error}")
		return

	if image_bgr is None:
		messagebox.showerror("Image Read Error", "The selected file is not a valid image.")
		return

	canvas_source_image = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
	canvas_rotation_degrees = 0
	canvas_zoom_var.set(100)
	if canvas_image_item is not None:
		canvas_widget.delete(canvas_image_item)
		canvas_image_item = None
	canvas_image_photo = None
	canvas_info_label.configure(text=f"{image_path}  |  {image_bgr.shape[1]} x {image_bgr.shape[0]} px")
	root.after_idle(render_canvas_image)


def render_canvas_image(*_):
	global canvas_image_item, canvas_image_photo
	if canvas_source_image is None:
		return

	rotated_image = canvas_source_image.rotate(
		canvas_rotation_degrees,
		resample=Image.Resampling.BICUBIC,
		expand=True,
	)
	zoom = float(canvas_zoom_var.get()) / 100
	width = max(1, round(rotated_image.width * zoom))
	height = max(1, round(rotated_image.height * zoom))
	displayed_image = rotated_image.resize((width, height), Image.Resampling.LANCZOS)
	canvas_image_photo = ImageTk.PhotoImage(displayed_image)

	if canvas_image_item is None:
		canvas_image_item = canvas_widget.create_image(
			canvas_widget.winfo_width() / 2,
			canvas_widget.winfo_height() / 2,
			image=canvas_image_photo,
			anchor=tk.CENTER,
		)
	else:
		canvas_widget.itemconfigure(canvas_image_item, image=canvas_image_photo)

	canvas_info_label.configure(
		text=(
			f"Image: {width} x {height} px  |  Zoom: {int(float(canvas_zoom_var.get()))}%"
			f"  |  Rotation: {canvas_rotation_degrees % 360} degrees"
		)
	)


def rotate_canvas_image(direction):
	global canvas_rotation_degrees
	if canvas_source_image is None:
		return

	canvas_rotation_degrees = (canvas_rotation_degrees + direction * 90) % 360
	render_canvas_image()


def zoom_canvas_with_wheel(event):
	if canvas_source_image is None or event.delta == 0:
		return "break"

	zoom = float(canvas_zoom_var.get())
	zoom += 10 if event.delta > 0 else -10
	canvas_zoom_var.set(max(10, min(300, zoom)))
	render_canvas_image()
	return "break"


def start_canvas_drag(event):
	global canvas_drag_position
	if canvas_image_item is not None:
		canvas_drag_position = (event.x, event.y)


def drag_canvas_image(event):
	global canvas_drag_position
	if canvas_image_item is None or canvas_drag_position is None:
		return

	delta_x = event.x - canvas_drag_position[0]
	delta_y = event.y - canvas_drag_position[1]
	canvas_widget.move(canvas_image_item, delta_x, delta_y)
	canvas_drag_position = (event.x, event.y)


root = tk.Tk()
root.title("Image Processing Toolkit")
root.geometry("1450x780")
root.minsize(850, 500)

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True)

color_tab = tk.Frame(notebook)
bitwise_tab = tk.Frame(notebook)
video_tab = tk.Frame(notebook)
adjustment_tab = tk.Frame(notebook)
canvas_tab = tk.Frame(notebook)
notebook.add(color_tab, text="Color Conversion")
notebook.add(bitwise_tab, text="Bitwise AND")
notebook.add(video_tab, text="Video Frame Extraction")
notebook.add(adjustment_tab, text="Brightness / Saturation")
notebook.add(canvas_tab, text="Image Canvas")

toolbar = tk.Frame(color_tab)
toolbar.pack(fill=tk.X, padx=12, pady=12)

select_button = tk.Button(toolbar, text="Select Image", command=choose_image, padx=16, pady=8)
select_button.pack(side=tk.LEFT)

convert_button = tk.Button(toolbar, text="Convert Colors", command=convert_colors, padx=16, pady=8, state=tk.DISABLED)
convert_button.pack(side=tk.LEFT, padx=(8, 0))

images_frame = tk.Frame(color_tab)
images_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
for column in range(3):
	images_frame.columnconfigure(column, weight=1, uniform="images")
images_frame.rowconfigure(0, weight=1)

original_frame = tk.LabelFrame(images_frame, text="Original Image")
original_frame.grid(row=0, column=0, sticky="nsew", padx=5)
gray_frame = tk.LabelFrame(images_frame, text="Greyscale")
gray_frame.grid(row=0, column=1, sticky="nsew", padx=5)
hsv_frame = tk.LabelFrame(images_frame, text="HSV Channels (H/S/V)")
hsv_frame.grid(row=0, column=2, sticky="nsew", padx=5)

original_label = tk.Label(original_frame, text="Select an image to get started", bg="#eeeeee")
original_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
gray_label = tk.Label(gray_frame, text="", bg="#eeeeee")
gray_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
hsv_label = tk.Label(hsv_frame, text="", bg="#eeeeee")
hsv_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

status_label = tk.Label(color_tab, text="", anchor="w")
status_label.pack(fill=tk.X, padx=12, pady=(4, 12))

bitwise_toolbar = tk.Frame(bitwise_tab)
bitwise_toolbar.pack(fill=tk.X, padx=12, pady=12)
tk.Button(
	bitwise_toolbar,
	text="Select Image 1",
	command=lambda: choose_bitwise_image(0),
	padx=16,
	pady=8,
).pack(side=tk.LEFT)
tk.Button(
	bitwise_toolbar,
	text="Select Image 2",
	command=lambda: choose_bitwise_image(1),
	padx=16,
	pady=8,
).pack(side=tk.LEFT, padx=(8, 0))
bitwise_button = tk.Button(
	bitwise_toolbar,
	text="Apply AND",
	command=apply_bitwise_and,
	padx=16,
	pady=8,
	state=tk.DISABLED,
)
bitwise_button.pack(side=tk.LEFT, padx=(8, 0))

bitwise_images_frame = tk.Frame(bitwise_tab)
bitwise_images_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
for column in range(3):
	bitwise_images_frame.columnconfigure(column, weight=1, uniform="bitwise_images")
bitwise_images_frame.rowconfigure(0, weight=1)

bitwise_image1_frame = tk.LabelFrame(bitwise_images_frame, text="Image 1")
bitwise_image1_frame.grid(row=0, column=0, sticky="nsew", padx=5)
bitwise_image2_frame = tk.LabelFrame(bitwise_images_frame, text="Image 2")
bitwise_image2_frame.grid(row=0, column=1, sticky="nsew", padx=5)
bitwise_result_frame = tk.LabelFrame(bitwise_images_frame, text="Bitwise AND Result")
bitwise_result_frame.grid(row=0, column=2, sticky="nsew", padx=5)

bitwise_image1_label = tk.Label(bitwise_image1_frame, text="No image selected", bg="#eeeeee")
bitwise_image1_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
bitwise_image2_label = tk.Label(bitwise_image2_frame, text="No image selected", bg="#eeeeee")
bitwise_image2_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
bitwise_result_label = tk.Label(bitwise_result_frame, text="Select two images and apply AND", bg="#eeeeee")
bitwise_result_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

bitwise_status_label = tk.Label(bitwise_tab, text="", anchor="w", justify=tk.LEFT, wraplength=1400)
bitwise_status_label.pack(fill=tk.X, padx=12, pady=(4, 12))

video_toolbar = tk.Frame(video_tab)
video_toolbar.pack(fill=tk.X, padx=12, pady=12)
tk.Button(
	video_toolbar,
	text="Select Video",
	command=choose_video,
	padx=16,
	pady=8,
).pack(side=tk.LEFT)
tk.Label(video_toolbar, text="Image format:").pack(side=tk.LEFT, padx=(16, 6))
image_format_var = tk.StringVar(value=".jpg")
ttk.Combobox(
	video_toolbar,
	textvariable=image_format_var,
	values=(".jpg", ".png", ".bmp"),
	state="readonly",
	width=8,
).pack(side=tk.LEFT)
export_frames_button = tk.Button(
	video_toolbar,
	text="Export Frames",
	command=export_video_frames,
	padx=16,
	pady=8,
	state=tk.DISABLED,
)
export_frames_button.pack(side=tk.LEFT, padx=(12, 0))

video_path_label = tk.Label(video_tab, text="No video selected", anchor="w", justify=tk.LEFT, wraplength=1400)
video_path_label.pack(fill=tk.X, padx=12, pady=(8, 4))
video_export_status = tk.Label(video_tab, text="", anchor="w", justify=tk.LEFT, wraplength=1400)
video_export_status.pack(fill=tk.X, padx=12, pady=4)

adjustment_toolbar = tk.Frame(adjustment_tab)
adjustment_toolbar.pack(fill=tk.X, padx=12, pady=12)
tk.Button(
	adjustment_toolbar,
	text="Select Image",
	command=choose_adjustment_image,
	padx=16,
	pady=8,
).pack(side=tk.LEFT)
tk.Button(
	adjustment_toolbar,
	text="Reset",
	command=reset_adjustments,
	padx=16,
	pady=8,
).pack(side=tk.LEFT, padx=(8, 0))

adjustment_controls = tk.Frame(adjustment_tab)
adjustment_controls.pack(fill=tk.X, padx=18, pady=(0, 8))
brightness_var = tk.DoubleVar(value=0)
saturation_var = tk.DoubleVar(value=100)
tk.Label(adjustment_controls, text="Brightness").grid(row=0, column=0, sticky="w", padx=(0, 8))
tk.Scale(
	adjustment_controls,
	from_=-100,
	to=100,
	orient=tk.HORIZONTAL,
	variable=brightness_var,
	command=update_adjustment_preview,
	showvalue=False,
	resolution=1,
).grid(row=0, column=1, sticky="ew")
brightness_value_label = tk.Label(adjustment_controls, text="+0", width=6, anchor="e")
brightness_value_label.grid(row=0, column=2, padx=(8, 0))
tk.Label(adjustment_controls, text="Saturation").grid(row=1, column=0, sticky="w", padx=(0, 8))
tk.Scale(
	adjustment_controls,
	from_=0,
	to=200,
	orient=tk.HORIZONTAL,
	variable=saturation_var,
	command=update_adjustment_preview,
	showvalue=False,
	resolution=1,
).grid(row=1, column=1, sticky="ew")
saturation_value_label = tk.Label(adjustment_controls, text="100%", width=6, anchor="e")
saturation_value_label.grid(row=1, column=2, padx=(8, 0))
adjustment_controls.columnconfigure(1, weight=1)

adjustment_images_frame = tk.Frame(adjustment_tab)
adjustment_images_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
for column in range(2):
	adjustment_images_frame.columnconfigure(column, weight=1, uniform="adjustment_images")
adjustment_images_frame.rowconfigure(0, weight=1)

adjustment_original_frame = tk.LabelFrame(adjustment_images_frame, text="Original Image")
adjustment_original_frame.grid(row=0, column=0, sticky="nsew", padx=5)
adjustment_result_frame = tk.LabelFrame(adjustment_images_frame, text="Adjusted Image")
adjustment_result_frame.grid(row=0, column=1, sticky="nsew", padx=5)
adjustment_original_label = tk.Label(adjustment_original_frame, text="Select an image to get started", bg="#eeeeee")
adjustment_original_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
adjustment_result_label = tk.Label(adjustment_result_frame, text="", bg="#eeeeee")
adjustment_result_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
adjustment_path_label = tk.Label(adjustment_tab, text="", anchor="w")
adjustment_path_label.pack(fill=tk.X, padx=12, pady=(4, 12))

canvas_toolbar = tk.Frame(canvas_tab)
canvas_toolbar.pack(fill=tk.X, padx=12, pady=12)
tk.Button(
	canvas_toolbar,
	text="Open Image",
	command=choose_canvas_image,
	padx=16,
	pady=8,
).pack(side=tk.LEFT)
tk.Button(
	canvas_toolbar,
	text="Rotate Left (CCW)",
	command=lambda: rotate_canvas_image(1),
	padx=12,
	pady=8,
).pack(side=tk.LEFT, padx=(8, 0))
tk.Button(
	canvas_toolbar,
	text="Rotate Right (CW)",
	command=lambda: rotate_canvas_image(-1),
	padx=12,
	pady=8,
).pack(side=tk.LEFT, padx=(8, 0))
canvas_zoom_var = tk.DoubleVar(value=100)
tk.Label(canvas_toolbar, text="Use the mouse wheel to zoom").pack(side=tk.LEFT, padx=(18, 0))

canvas_widget = tk.Canvas(canvas_tab, bg="#25282c", highlightthickness=0, cursor="fleur")
canvas_widget.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
canvas_widget.bind("<ButtonPress-1>", start_canvas_drag)
canvas_widget.bind("<B1-Motion>", drag_canvas_image)
canvas_widget.bind("<MouseWheel>", zoom_canvas_with_wheel)
canvas_info_label = tk.Label(canvas_tab, text="Select an image to display on the canvas", anchor="w")
canvas_info_label.pack(fill=tk.X, padx=12, pady=(4, 12))

root.mainloop()
