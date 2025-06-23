#!/usr/bin/python
import os
from ttkthemes import ThemedTk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import shutil
import subprocess
import json
import glob
import requests
import urllib.request
import tarfile
import tempfile
import zipfile
import re
import sys
import time
import webbrowser
from pathlib import Path

# Current application version
__version__ = "v0.1"

# === XDG Base Directory Spec ===
XDG_CONFIG_HOME = Path(os.getenv('XDG_CONFIG_HOME', Path.home() / '.config'))
CONFIG_DIR     = XDG_CONFIG_HOME / 'shortcut_launcher'
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

XDG_DATA_HOME  = Path(os.getenv('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
DATA_DIR       = XDG_DATA_HOME / 'shortcut_launcher'
DATA_DIR.mkdir(parents=True, exist_ok=True)

XDG_CACHE_HOME = Path(os.getenv('XDG_CACHE_HOME', Path.home() / '.cache'))
CACHE_DIR      = XDG_CACHE_HOME / 'shortcut_launcher'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class ShortcutLauncher:
	def __init__(self, root):
		self.root = root
		self.root.title(f"Shortcut Launcher {__version__}")
		self.root.geometry("900x600")

		# Directoare
		self.HOME = os.path.expanduser("~")
		self.SHORTCUTS_DIR = str(DATA_DIR / 'shortcuts')
		self.TEMPLATES_DIR = str(DATA_DIR / 'templates')
		os.makedirs(self.SHORTCUTS_DIR, exist_ok=True)
		os.makedirs(self.TEMPLATES_DIR, exist_ok=True)
		
		# Hardcoded repository for templates
		self.TEMPLATE_REPO = "https://github.com/moio9/default"
		self.TEMPLATE_RELEASES = f"{self.TEMPLATE_REPO}/releases/tag/TMP"
		self.APP_REPO = "https://github.com/moio9/default"
		self.APP_RELEASES = f"{self.APP_REPO}/releases/tag/Version"
		
		# Stiluri
		self.style = ttk.Style()
		self.current_theme = tk.StringVar(value="dark")
		self.style.configure("Header.TLabel", font=("Arial", 14, "bold"), padding=10)
		self.style.configure("Section.TLabel", font=("Arial", 12, "bold"))
		self.style.configure("Item.TFrame", background="#f5f5f5", relief="groove", borderwidth=1)

		self.create_menu()
		self.create_main_frame()
		self.notify_runners()
		self.apply_theme()
		
		self.PREFIXES_FILE = str(CONFIG_DIR / 'wine_prefixes.json')
		if not os.path.exists(self.PREFIXES_FILE):
		    with open(self.PREFIXES_FILE, 'w') as f:
		        json.dump([], f)
		        
		
		        
	def apply_theme(self):
		t = self.current_theme.get()
		if t == "dark":
			self.root.set_theme("equilux")   # sau orice altă dark theme disponibilă
		else:
			self.root.set_theme("arc")       # sau “default”, “plastik” etc.


	def create_menu(self):
		menubar = tk.Menu(self.root)
		self.root.config(menu=menubar)

		file_menu = tk.Menu(menubar, tearoff=0)
		file_menu.add_command(label="Ieșire", command=self.root.quit)
		menubar.add_cascade(label="Fișier", menu=file_menu)
		
		view_menu = tk.Menu(menubar, tearoff=0)
		theme_menu = tk.Menu(view_menu, tearoff=0)
		theme_menu.add_radiobutton(label="Light", variable=self.current_theme, value="light", command=self.apply_theme)
		theme_menu.add_radiobutton(label="Dark",  variable=self.current_theme, value="dark",  command=self.apply_theme)
		view_menu.add_cascade(label="Tema", menu=theme_menu)
		menubar.add_cascade(label="View", menu=view_menu)
		self.root.config(menu=menubar)

		menubar.add_command(label="Shortcut-uri", command=self.list_shortcuts)
		menubar.add_command(label="Template-uri", command=self.list_templates)
		menubar.add_command(label="Prefixuri", command=self.manage_prefixes)

		help_menu = tk.Menu(menubar, tearoff=0)
		help_menu.add_command(label="Despre", command=self.show_about)
		help_menu.add_command(label="Verifică Actualizări", command=self.check_app_update)
		menubar.add_cascade(label="Ajutor", menu=help_menu)
		


	def create_main_frame(self):
		if hasattr(self, 'main_frame'):
			self.main_frame.destroy()
		self.main_frame = ttk.Frame(self.root)
		self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

		ttk.Label(self.main_frame, style="Header.TLabel",
			text=f"Launcher de Shortcut-uri și Template-uri {__version__}").pack(pady=20)

		ttk.Button(self.main_frame, text="Shortcut-uri", width=30,
			command=self.list_shortcuts).pack(pady=10)
		ttk.Button(self.main_frame, text="Template-uri", width=30,
			command=self.list_templates).pack(pady=10)

	def notify_runners(self):
		self.runners = []
		for bin_name in ["wine", "proton", "hangover-wine"]:
			if shutil.which(bin_name):
				self.runners.append(bin_name)
		if not self.runners:
			messagebox.showwarning(
				"Atenționare",
				"⚠️ Nu am găsit niciun runner instalat (wine, proton, hangover-wine etc)!"
			)

	def clear_main_frame(self):
		for widget in self.main_frame.winfo_children():
			widget.destroy()

	def go_back(self):
		self.create_main_frame()
		
	def _load_icon_for_gui(self, icon_path, size=(32, 32)):
		if not icon_path or not os.path.exists(icon_path):
			return None
		try:
			from PIL import Image, ImageTk
		except ImportError:
			return None  # nu avem Pillow, nu încărcăm iconița

		try:
			img = Image.open(icon_path)
			if getattr(img, 'mode', None) == 'RGBA':
				bg = Image.new('RGB', img.size, (255,255,255))
				bg.paste(img, mask=img.split()[3])
				img = bg
			img.thumbnail(size)
			return ImageTk.PhotoImage(img)
		except Exception:
			return None


			
	def _validate_icon(self, icon_path):
		if not icon_path or icon_path == "application-x-executable":
			return True  # Iconița default este întotdeauna validă
		return os.path.exists(icon_path)
		
	def cleanup_icons(self):
		"""Șterge iconițele nefolosite"""
		icons_dir = os.path.join(self.SHORTCUTS_DIR, "icons")
		if not os.path.exists(icons_dir):
			return
			
		used_icons = set()
		desktop_dir = os.path.join(self.HOME, "Desktop") if os.path.exists(os.path.join(self.HOME, "Desktop")) else self.HOME
		
		# Colectează toate iconițele folosite
		for f in os.listdir(desktop_dir):
			if f.endswith(".desktop"):
				with open(os.path.join(desktop_dir, f), 'r') as file:
					for line in file:
						if line.startswith("Icon="):
							icon_path = line.split("=", 1)[1].strip()
							if os.path.isabs(icon_path):
								used_icons.add(icon_path)
		
		# Șterge iconițele nefolosite
		for icon_file in os.listdir(icons_dir):
			icon_path = os.path.join(icons_dir, icon_file)
			if icon_path not in used_icons:
				try:
					os.remove(icon_path)
				except Exception as e:
					print(f"Eroare la ștergerea iconiței {icon_path}: {e}")

	def list_shortcuts(self):
		self.clear_main_frame()

		header = ttk.Frame(self.main_frame)
		header.pack(fill=tk.X, pady=5)
		ttk.Label(header, text="Shortcut-uri", style="Header.TLabel").pack(side=tk.LEFT)
		ttk.Button(header, text="Adaugă", command=self.add_shortcut).pack(side=tk.RIGHT)

		canvas = tk.Canvas(self.main_frame)
		scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=canvas.yview)
		scrollable_frame = ttk.Frame(canvas)

		scrollable_frame.bind("<Configure>",
			lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
		canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
		canvas.configure(yscrollcommand=scrollbar.set)

		canvas.pack(side="left", fill="both", expand=True)
		scrollbar.pack(side="right", fill="y")

		desktop_dir = os.path.join(self.HOME, "Desktop") if os.path.exists(os.path.join(self.HOME, "Desktop")) else self.HOME
		shortcuts = []

		try:
			for f in os.listdir(desktop_dir):
				if f.endswith(".desktop"):
					file_path = os.path.join(desktop_dir, f)
					with open(file_path, 'r') as file:
						content = file.read()
						if "X-Shortcut-Manager=Shortcut Launcher" in content:
							shortcuts.append(f.replace(".desktop", ""))
		except Exception as e:
			print(f"Eroare la citirea shortcut-urilor: {e}")

		if not shortcuts:
			ttk.Label(scrollable_frame, text="Nu sunt shortcut-uri disponibile.").pack(pady=10)
		else:
			for name in shortcuts:
				self._create_shortcut_item(scrollable_frame, name)

		back_btn = ttk.Button(self.main_frame, text="Înapoi", command=self.go_back)
		back_btn.pack(pady=10)

	def _create_shortcut_item(self, parent, name):
		frame = ttk.Frame(parent, style="Item.TFrame")
		frame.pack(fill=tk.X, pady=5, padx=5)

		desktop_dir = os.path.join(self.HOME, "Desktop")
		desktop_file = os.path.join(desktop_dir, f"{name}.desktop")
		icon_path = self._get_icon_from_desktop(desktop_file)

		# Frame pentru iconiță + nume
		icon_name_frame = ttk.Frame(frame)
		icon_name_frame.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

		# Încarcă direct imaginea (PNG/SVG/XPM/ICO etc.) dacă există
		icon_img = None
		if icon_path and os.path.exists(icon_path):
			try:
				icon_img = tk.PhotoImage(file=icon_path)
			except Exception:
				icon_img = None

		if icon_img:
			lbl_icon = ttk.Label(icon_name_frame, image=icon_img)
			lbl_icon.image = icon_img   # referință pentru garbage collector
			lbl_icon.pack(side=tk.LEFT, padx=(0, 5))

		# Afișează numele shortcut-ului
		ttk.Label(icon_name_frame, text=name, font=("Arial", 12)).pack(side=tk.LEFT, anchor="w")

		# Butoane Run/Edit/Delete
		actions = ttk.Frame(frame)
		actions.pack(side=tk.RIGHT, padx=10)
		ttk.Button(actions, text="Rulează", width=8,
				   command=lambda: self.run_shortcut(name)).pack(side=tk.LEFT, padx=2)
		ttk.Button(actions, text="Editează", width=8,
				   command=lambda: self.edit_shortcut(name)).pack(side=tk.LEFT, padx=2)
		ttk.Button(actions, text="Șterge", width=8,
				   command=lambda: self.delete_shortcut(name)).pack(side=tk.LEFT, padx=2)

		
	def _get_icon_from_desktop(self, desktop_path):
		if not os.path.exists(desktop_path):
			return None
			
		icon_name = None
		with open(desktop_path, 'r') as f:
			for line in f:
				if line.startswith("Icon="):
					icon_name = line.split("=", 1)[1].strip()
					break
		
		if not icon_name:
			return None
		
		# Verifică dacă este cale absolută
		if os.path.isabs(icon_name):
			return icon_name if os.path.exists(icon_name) else None
		
		# Caută în locațiile standard pentru iconițe
		search_paths = [
			os.path.join(self.HOME, ".icons"),
			"/usr/share/pixmaps",
			"/usr/share/icons",
			"/usr/local/share/icons"
		]
		
		for ext in ["", ".png", ".svg", ".xpm", ".ico"]:
			for path in search_paths:
				icon_path = os.path.join(path, icon_name + ext)
				if os.path.exists(icon_path):
					return icon_path
					
		return None
		
		
	def _extract_exe_icon(self, exe_path, output_path):
		try:
			# Convertim în .png pentru compatibilitate
			png_path = output_path.replace('.ico', '.png')
			
			# Extrage iconița cu wrestool și converteste cu ImageMagick
			subprocess.run([
				"wrestool", "-x", "-t", "14", 
				"-o", "-", exe_path
			], stdout=open(png_path, 'wb'), check=True)
			
			# Convertim la dimensiune standard (dacă ImageMagick este disponibil)
			if shutil.which("convert"):
				subprocess.run([
					"convert", png_path, "-resize", "32x32", png_path
				], check=True)
			
			return os.path.exists(png_path)
		except Exception as e:
			print(f"Eroare la extragerea iconiței: {e}")
			return False
			

	def run_shortcut(self, name):
		desktop_dir = os.path.join(self.HOME, "Desktop") if os.path.exists(os.path.join(self.HOME, "Desktop")) else self.HOME
		path = os.path.join(desktop_dir, f"{name}.desktop")
		try:
			subprocess.Popen(["bash", path])
		except Exception as e:
			messagebox.showerror("Eroare", f"Nu s-a putut executa shortcut-ul:\n{str(e)}")

	def edit_shortcut(self, name):
		desktop_dir = os.path.join(self.HOME, "Desktop") if os.path.exists(os.path.join(self.HOME, "Desktop")) else self.HOME
		desktop_path = os.path.join(desktop_dir, f"{name}.desktop")
		try:
			with open(desktop_path, "r") as f:
				content = f.read()
			edit_dialog = tk.Toplevel(self.root)
			edit_dialog.title(f"Editează {name}")
			edit_dialog.geometry("800x600")

			text_area = tk.Text(edit_dialog, wrap=tk.NONE, undo=True)
			text_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
			text_area.insert(tk.END, content)

			def save_changes():
				new_content = text_area.get(1.0, tk.END)
				with open(desktop_path, "w") as f:
					f.write(new_content.rstrip('\n'))
				messagebox.showinfo("Succes", "Shortcut actualizat!")
				edit_dialog.destroy()

			button_frame = ttk.Frame(edit_dialog)
			button_frame.pack(pady=5)
			ttk.Button(button_frame, text="Salvează", command=save_changes).pack(side=tk.LEFT, padx=5)
			ttk.Button(button_frame, text="Anulează", command=edit_dialog.destroy).pack(side=tk.LEFT)

		except Exception as e:
			messagebox.showerror("Eroare", f"Nu s-a putut deschide editorul:\n{str(e)}")

	def delete_shortcut(self, name):
		desktop_dir = os.path.join(self.HOME, "Desktop") if os.path.exists(os.path.join(self.HOME, "Desktop")) else self.HOME
		path = os.path.join(desktop_dir, f"{name}.desktop")
		try:
			os.remove(path)
			messagebox.showinfo("Ștergere", f"Shortcut șters: {name}")
			self.list_shortcuts()
		except Exception as e:
			messagebox.showerror("Eroare", f"Nu s-a putut șterge:\n{str(e)}")

	def add_shortcut(self, preselected_path=None):
		# Dacă s-a transmis un fișier ca argument, folosim calea direct
		if preselected_path:
			file_path = preselected_path
			default_name = os.path.splitext(os.path.basename(file_path))[0]
			name = simpledialog.askstring("Nume", "Nume shortcut:", initialvalue=default_name)
			if not name or " " in name:
				messagebox.showwarning("Atenționare", "Numele nu poate conține spații!")
				return
			path = file_path
		else:
			name = simpledialog.askstring("Nume", "Nume shortcut:")
			if not name or " " in name:
				messagebox.showwarning("Atenționare", "Numele nu poate conține spații!")
				return
			path = filedialog.askopenfilename(title="Alege fișier/script")
			if not path:
				return

		# Extrage iconița automat dacă e .exe
		icon_path = "application-x-executable"  # Iconiță implicită
		if path.lower().endswith('.exe'):
			extracted_icon = os.path.join(tempfile.gettempdir(), f"{os.path.basename(path)}.ico")
			if self._extract_exe_icon(path, extracted_icon):
				icon_path = extracted_icon

		# Permite utilizatorului să aleagă manual o iconiță
		if not icon_path or not os.path.exists(icon_path):
			new_icon = filedialog.askopenfilename(
				title="Selectează o iconiță (opțional)",
				filetypes=[("Imagini", "*.png *.svg *.ico *.xpm")]
			)
			if new_icon:  # Dacă utilizatorul a selectat o iconiță
				icon_path = new_icon
		
		if icon_path and os.path.isabs(icon_path):
			# Salvează iconița în directorul de shortcut-uri pentru acces ușor
			icons_dir = os.path.join(self.SHORTCUTS_DIR, "icons")
			os.makedirs(icons_dir, exist_ok=True)
			try:
				new_icon_path = os.path.join(icons_dir, f"{name}{os.path.splitext(icon_path)[1]}")
				shutil.copy2(icon_path, new_icon_path)
				icon_path = new_icon_path
			except Exception as e:
				print(f"Nu s-a putut copia iconița: {e}")
				icon_path = "application-x-executable"
		# Listăm TOATE fișierele template
		templates = [f for f in os.listdir(self.TEMPLATES_DIR) if os.path.isfile(os.path.join(self.TEMPLATES_DIR, f))]
		selected_template = None

		if templates:
			template_dialog = tk.Toplevel(self.root)
			template_dialog.title("Alege Template")
			template_dialog.geometry("400x300")
			ttk.Label(template_dialog, text="Selectează un template sau închide dacă nu vrei template:", style="Section.TLabel").pack(pady=5)

			listbox = tk.Listbox(template_dialog, width=50, height=10)
			listbox.pack(padx=10, pady=5)
			for t in templates:
				listbox.insert(tk.END, t)
			listbox.selection_set(0)

			def on_select():
				nonlocal selected_template
				selection = listbox.curselection()
				if selection:
					selected_template = listbox.get(selection[0])
				template_dialog.destroy()

			ttk.Button(template_dialog, text="Alege", command=on_select).pack(side=tk.LEFT, padx=10)
			ttk.Button(template_dialog, text="Fără template", command=template_dialog.destroy).pack(side=tk.RIGHT)

			self.root.wait_window(template_dialog)

		desktop_dir = os.path.join(self.HOME, "Desktop") if os.path.exists(os.path.join(self.HOME, "Desktop")) else self.HOME

		if selected_template:
			template_path = os.path.join(self.TEMPLATES_DIR, selected_template)
			exec_cmd = f'bash "{template_path}" "{path}"'
		else:
			exec_cmd = f'sh -c \'{path}; read -p "Apasă Enter..."\''

		desktop_content = f"""[Desktop Entry]
	Type=Application
	Name={name}
	Exec={exec_cmd}
	Icon={icon_path}
	Terminal=true
	Comment=Created with Shortcut Launcher
	X-Shortcut-Manager=Shortcut Launcher
	"""
		desktop_path = os.path.join(desktop_dir, f"{name}.desktop")
		try:
			with open(desktop_path, "w") as f:
				f.write(desktop_content)
			os.chmod(desktop_path, 0o755)
			messagebox.showinfo("Succes", f"Shortcut creat: {desktop_path}")
			self.list_shortcuts()
		except Exception as e:
			messagebox.showerror("Eroare", f"Nu s-a putut crea shortcut-ul:\n{str(e)}")

	def list_templates(self):
		self.clear_main_frame()

		header = ttk.Frame(self.main_frame)
		header.pack(fill=tk.X, pady=5)
		ttk.Label(header, text="Template-uri", style="Header.TLabel").pack(side=tk.LEFT)
		ttk.Button(header, text="Adaugă", command=self.add_template).pack(side=tk.RIGHT)
		ttk.Button(header, text="Descarcă Template-uri", command=self.show_available_templates).pack(side=tk.RIGHT, padx=2)

		canvas = tk.Canvas(self.main_frame)
		scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=canvas.yview)
		scrollable_frame = ttk.Frame(canvas)

		scrollable_frame.bind("<Configure>",
							 lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
		canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
		canvas.configure(yscrollcommand=scrollbar.set)

		canvas.pack(side="left", fill="both", expand=True)
		scrollbar.pack(side="right", fill="y")

		templates = os.listdir(self.TEMPLATES_DIR)
		if not templates:
			ttk.Label(scrollable_frame, text="Nu sunt template-uri disponibile.").pack(pady=10)
		else:
			for template in templates:
				self._create_template_item(scrollable_frame, template)

		back_btn = ttk.Button(self.main_frame, text="Înapoi", command=self.go_back)
		back_btn.pack(pady=10)

	def _create_template_item(self, parent, name):
		frame = ttk.Frame(parent, style="Item.TFrame")
		frame.pack(fill=tk.X, pady=5, padx=5)

		info_frame = ttk.Frame(frame)
		info_frame.pack(side=tk.LEFT, padx=10)

		ttk.Label(info_frame, text=name, font=("Arial", 12)).pack(anchor="w")

		actions = ttk.Frame(frame)
		actions.pack(side=tk.RIGHT, padx=10)

		ttk.Button(actions, text="Editează", width=8,
				  command=lambda: self.edit_template(name)).pack(side=tk.LEFT, padx=2)
		ttk.Button(actions, text="Șterge", width=8,
				  command=lambda: self.delete_template(name)).pack(side=tk.LEFT, padx=2)

	def edit_template(self, name):
		path = os.path.join(self.TEMPLATES_DIR, name)
		try:
			with open(path, "r") as f:
				content = f.read()
			edit_dialog = tk.Toplevel(self.root)
			edit_dialog.title(f"Editează {name}")
			edit_dialog.geometry("800x600")

			text_area = tk.Text(edit_dialog, wrap=tk.NONE, undo=True)
			text_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
			text_area.insert(tk.END, content)

			def save_changes():
				new_content = text_area.get(1.0, tk.END)
				with open(path, "w") as f:
					f.write(new_content.rstrip('\n'))
				messagebox.showinfo("Succes", "Template salvat!")
				edit_dialog.destroy()

			button_frame = ttk.Frame(edit_dialog)
			button_frame.pack(pady=5)
			ttk.Button(button_frame, text="Salvează", command=save_changes).pack(side=tk.LEFT, padx=5)
			ttk.Button(button_frame, text="Anulează", command=edit_dialog.destroy).pack(side=tk.LEFT)

		except Exception as e:
			messagebox.showerror("Eroare", f"Nu s-a putut citi template-ul:\n{str(e)}")

	def delete_template(self, name):
		path = os.path.join(self.TEMPLATES_DIR, name)
		try:
			os.remove(path)
			messagebox.showinfo("Ștergere", f"Template șters: {name}")
			self.list_templates()
		except Exception as e:
			messagebox.showerror("Eroare", f"Nu s-a putut șterge:\n{str(e)}")

	def add_template(self):
		import pathlib

		custom_file = os.path.expanduser("~/.template_postrun_custom")

		# Încarcă comenzi personalizate salvate anterior
		persisted_custom_actions = []
		if os.path.exists(custom_file):
			with open(custom_file) as f:
				persisted_custom_actions = [line.strip() for line in f if line.strip()]

		name = simpledialog.askstring("Nume Template", "Introdu numele noului template:")
		if not name:
			return

		dialog = tk.Toplevel(self.root)
		dialog.title("Creare Template")
		dialog.geometry("800x1000")

		container = tk.Frame(dialog)
		container.pack(fill="both", expand=True)

		ttk.Label(container, text="Alege opțiunile și apoi salvează").pack(pady=10)

		# --- Runner ---
		runner_var = tk.StringVar()
		ttk.Label(container, text="Runner:").pack(anchor="w", padx=10)
		runner_combo = ttk.Combobox(container, textvariable=runner_var, values=self._get_runners())
		runner_combo.pack(padx=10, pady=5)
		runner_combo.current(0)

		# --- Rulare paralelă ---
		parallel_var = tk.BooleanVar()
		tk.Checkbutton(container, text="Rulare în paralel (&)", variable=parallel_var).pack(anchor="w", padx=10)

		# --- EMU ---
		emu_var = tk.StringVar()
		ttk.Label(container, text="EMU Settings:").pack(anchor="w", padx=10)
		emu_combo = ttk.Combobox(container, textvariable=emu_var, values=["libwow64fex.dll"])
		emu_combo.pack(padx=10, pady=5)
		emu_combo.current(0)

		# --- WINEPREFIX ---
		wine_var = tk.StringVar()
		ttk.Label(container, text="WINEPREFIX:").pack(anchor="w", padx=10)
		wine_combo = ttk.Combobox(container, textvariable=wine_var, values=["~/.wine", "~/.proton"])
		wine_combo.pack(padx=10, pady=5)
		wine_combo.current(0)

		# --- DXVK HUD ---
		dxvk_var = tk.StringVar()
		ttk.Label(container, text="DXVK HUD:").pack(anchor="w", padx=10)
		dxvk_combo = ttk.Combobox(container, textvariable=dxvk_var, values=["none", "1", "full"])
		dxvk_combo.pack(padx=10, pady=5)
		dxvk_combo.current(0)

		# --- Vulkan ICD ---
		vk_var = tk.StringVar()
		ttk.Label(container, text="Vulkan ICD:").pack(anchor="w", padx=10)
		vk_combo = ttk.Combobox(container, textvariable=vk_var, values=[
			"$PREFIX/share/vulkan/icd.d/wrapper_icd.aarch64.json",
			"$PREFIX/share/vulkan/icd.d/freedreno_icd.aarch64.json"
		])
		vk_combo.pack(padx=10, pady=5)
		vk_combo.current(0)

		# --- Post-exec multiple ---
		ttk.Label(container, text="Acțiuni după execuție:").pack(anchor="w", padx=10)
		after_vars = []
		after_frame = tk.Frame(container)
		after_frame.pack(anchor="w", padx=10)

		def refresh_after_list():
			for widget in after_frame.winfo_children():
				widget.destroy()
			after_vars.clear()
			available = [
				"echo 'Execuția s-a încheiat'",
				"notify-send 'Template finalizat'",
				"rm -f *.tmp",
				"sync; echo 'Datele au fost sincronizate'",
				"poweroff",
				"pkill -9 -f services.exe"
			] + persisted_custom_actions
			for opt in available:
				var = tk.BooleanVar()
				after_vars.append((opt, var))
				row = tk.Frame(after_frame)
				row.pack(anchor="w", fill="x")
				tk.Checkbutton(row, text=opt, variable=var).pack(side="left")
				if opt in persisted_custom_actions:
					tk.Button(row, text="✖", command=lambda o=opt: delete_after(o)).pack(side="right")

		def delete_after(opt):
			if opt in persisted_custom_actions:
				persisted_custom_actions.remove(opt)
				with open(custom_file, "w") as f:
					f.write("\n".join(persisted_custom_actions) + "\n")
			refresh_after_list()

		refresh_after_list()

		# --- Adaugă acțiune personalizată ---
		def add_custom_post_exec():
			custom = simpledialog.askstring("Adaugă acțiune", "Introdu o acțiune personalizată după execuție:")
			if custom and custom not in persisted_custom_actions:
				persisted_custom_actions.append(custom)
				with open(custom_file, "a") as f:
					f.write(custom + "\n")
				refresh_after_list()

		tk.Button(container, text="Adaugă acțiune personalizată ⨁", command=add_custom_post_exec).pack(anchor="w", padx=10, pady=5)


		custom_after = tk.Text(container, height=4)

		# --- Zona de previzualizare cod ---
		ttk.Label(container, text="Previzualizare Script:").pack(anchor="w", padx=10, pady=(10, 0))
		self.code_preview = tk.Text(container, height=20, width=80, font=("Courier New", 10), wrap="none")
		self.code_preview.pack(padx=10, pady=5, fill='both', expand=True)
		self.code_preview.config(state='normal')  # Doar citire

		# --- Funcție pentru generare cod preview ---
		def update_preview(*_):
			runner = runner_combo.get()
			wine = wine_combo.get()
			dxvk = dxvk_combo.get()
			vk = vk_combo.get()
			emu = emu_combo.get()
			parallel = "&" if parallel_var.get() else ""
			after_lines = [text for text, var in after_vars if var.get()]
			custom_lines = [line.strip() for line in custom_after.get("1.0", tk.END).splitlines() if line.strip()]

			lines = [
				"#!/bin/sh",
				"",
				"# === Exporturi ===",
				f"\texport WINEPREFIX={wine}",
				f"\texport DXVK_HUD={dxvk}" if dxvk != "none" else "",
				f"\texport VK_ICD_FILENAMES={vk}" if vk else "",
				f"\texport HODLL={emu}" if emu else "",
				"",
				"# === Directorul scriptului ===",
				'\tcd "$(dirname \"$1\")"',
				"",
				"# === Rulare principală ===",
				f"\t{runner} \"$1\"{parallel}",
				"",
				"# === După execuție ===",
				*[f"\t{text}" for text in after_lines + custom_lines]
			]

			code = '\n'.join([line for line in lines if line])

			self.code_preview.config(state='normal')
			self.code_preview.delete("1.0", tk.END)
			self.code_preview.insert(tk.END, code)
			self.code_preview.config(state='normal')

		# --- Legăm toate câmpurile la funcția de preview ---
		runner_combo.bind("<<ComboboxSelected>>", lambda e: update_preview())
		parallel_var.trace_add("write", lambda *args: update_preview())
		emu_combo.bind("<<ComboboxSelected>>", lambda e: update_preview())
		wine_combo.bind("<<ComboboxSelected>>", lambda e: update_preview())
		dxvk_combo.bind("<<ComboboxSelected>>", lambda e: update_preview())
		vk_combo.bind("<<ComboboxSelected>>", lambda e: update_preview())

		def on_check_update(*_):
			update_preview()

		for _, var in after_vars:
			var.trace_add("write", on_check_update)

		custom_after.bind("<<Modified>>", lambda e: (
			custom_after.edit_modified(0),
			update_preview()
		))

		# Inițializare preview
		update_preview()

		# --- Butoane salvare / anulare ---
		btn_frame = tk.Frame(container)
		btn_frame.pack(pady=10)

		def save_template():
			runner = runner_combo.get()
			wine = wine_combo.get()
			dxvk = dxvk_combo.get()
			vk = vk_combo.get()
			emu = emu_combo.get()
			parallel = "&" if parallel_var.get() else ""
			after_lines = [text for text, var in after_vars if var.get()]
			custom_lines = [line.strip() for line in custom_after.get("1.0", tk.END).splitlines() if line.strip()]

			lines = [
				"#!/bin/sh",
				"",
				"# === Exporturi ===",
				f"\texport WINEPREFIX={wine}",
				f"\texport DXVK_HUD={dxvk}" if dxvk != "none" else "",
				f"\texport VK_ICD_FILENAMES={vk}" if vk else "",
				f"\texport HODLL={emu}" if emu else "",
				"",
				"# === Directorul scriptului ===",
				'\tcd "$(dirname \"$1\")"',
				"",
				"# === Rulare principală ===",
				f"\t{runner} \"$1\"{parallel}",
				"",
				"# === După execuție ===",
				*[f"\t{text}" for text in after_lines + custom_lines]
			]

			content = '\n'.join([line for line in lines if line])

			template_path = os.path.join(self.TEMPLATES_DIR, name)
			try:
				with open(template_path, "w") as f:
					f.write(content)
				os.chmod(template_path, 0o755)
				messagebox.showinfo("Succes", f"Template salvat: {template_path}")
				dialog.destroy()
			except Exception as e:
				messagebox.showerror("Eroare", f"Nu s-a putut salva template-ul:\n{str(e)}")

		tk.Button(btn_frame, text="Salvează Template", command=save_template).pack(side="left", padx=5)
		tk.Button(btn_frame, text="Anulează", command=dialog.destroy).pack(side="left", padx=5)

		
	def manage_prefixes(self):
		self.clear_main_frame()
		header = ttk.Frame(self.main_frame)
		header.pack(fill=tk.X, pady=5)
		ttk.Label(header, text="Gestionare Prefixuri Wine", style="Header.TLabel").pack(side=tk.LEFT)
		ttk.Button(header, text="Creează Prefix Nou", command=self.create_prefix).pack(side=tk.RIGHT)

		canvas = tk.Canvas(self.main_frame)
		scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=canvas.yview)
		scrollable_frame = ttk.Frame(canvas)
		scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
		canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
		canvas.configure(yscrollcommand=scrollbar.set)

		canvas.pack(side="left", fill="both", expand=True)
		scrollbar.pack(side="right", fill="y")

		prefixes = self.load_prefixes()
		if not prefixes:
			ttk.Label(scrollable_frame, text="Nu sunt prefixuri disponibile.").pack(pady=10)
		else:
			for p in prefixes:
				self._create_prefix_item(scrollable_frame, p)

		ttk.Button(self.main_frame, text="Înapoi", command=self.go_back).pack(pady=10)

	def create_prefix(self):
		runners = self._get_runners()
		if not runners:
			messagebox.showerror("Eroare", "Nu există niciun runner detectat!")
			return

		dialog = tk.Toplevel(self.root)
		dialog.title("Creare Prefix Nou")
		dialog.geometry("420x240")
		
		runners = self._get_runners()
		template_files = [f"[TEMPLATE] {f}" for f in os.listdir(self.TEMPLATES_DIR) if os.path.isfile(os.path.join(self.TEMPLATES_DIR, f))]
		combined_options = runners + template_files

		ttk.Label(dialog, text="Runner sau Template:", style="Section.TLabel").pack(pady=8)
		runner_var = tk.StringVar(value=combined_options[0])
		runner_combo = ttk.Combobox(dialog, textvariable=runner_var, values=combined_options, state="readonly")
		runner_combo.pack(pady=4)
		runner_combo.current(0)

		ttk.Label(dialog, text="Arhitectură:", style="Section.TLabel").pack(pady=8)
		arch_var = tk.StringVar(value="win64")
		arch_entry = ttk.Combobox(dialog, textvariable=arch_var, values=["win32", "win64"], state="readonly")
		arch_entry.pack(pady=4)
		arch_entry.current(1)

		# --- Checkpoint pentru import registry ---
		reg_path = os.path.join(self.HOME, "registry")
		do_import = tk.BooleanVar(value=False)
		if os.path.isfile(reg_path):
			ttk.Checkbutton(dialog, text=f"Importă {reg_path} după inițializare", variable=do_import).pack(pady=10)
		else:
			reg_path = None  # nu există, nu afișezi nimic

		def create():
			dialog.destroy()
			new_prefix = filedialog.askdirectory(title="Alege folder pentru noul prefix")
			if not new_prefix:
				return
			selected = runner_var.get()
			env = os.environ.copy()
			cmd = []

			try:
				if not os.path.exists(new_prefix):
					os.makedirs(new_prefix)

				if selected.startswith("[TEMPLATE] "):
					template_name = selected.replace("[TEMPLATE] ", "")
					template_path = os.path.join(self.TEMPLATES_DIR, template_name)
					cmd = ["bash", template_path, "wineboot"]
				else:
					runner = selected
					cmd = [runner, "wineboot"]
					env["WINEPREFIX"] = new_prefix
					if arch_var.get() == "win32":
						env["WINEARCH"] = "win32"
					elif "WINEARCH" in env:
						del env["WINEARCH"]

				subprocess.run(cmd, env=env, check=True)

				# Salvează prefixul
				prefixes = self.load_prefixes()
				if new_prefix not in prefixes:
					prefixes.append(new_prefix)
					self.save_prefixes(prefixes)

				messagebox.showinfo("Succes", f"Prefix creat cu succes!\nComandă:\n{' '.join(cmd)}")
				self.manage_prefixes()
			except Exception as e:
				messagebox.showerror("Eroare", f"Eroare la creare prefix:\n{str(e)}")

		ttk.Button(dialog, text="Creează Prefix", command=create).pack(pady=15)
		ttk.Button(dialog, text="Anulează", command=dialog.destroy).pack()

			
	def _create_prefix_item(self, parent, path):
		frame = ttk.Frame(parent, style="Item.TFrame")
		frame.pack(fill=tk.X, pady=5, padx=5)

		ttk.Label(frame, text=path, font=("Arial", 11)).pack(side=tk.LEFT, padx=5)

		actions = ttk.Frame(frame)
		actions.pack(side=tk.RIGHT, padx=5)
		ttk.Button(actions, text="Editează", command=lambda: self.edit_prefix(path)).pack(side=tk.LEFT)
		ttk.Button(actions, text="Șterge", command=lambda: self.delete_prefix(path)).pack(side=tk.LEFT, padx=3)

	def edit_prefix(self, prefix_path):
		edit_dialog = tk.Toplevel(self.root)
		edit_dialog.title("Editare Prefix")
		edit_dialog.geometry("420x440")
		ttk.Label(edit_dialog, text=f"Prefix: {prefix_path}", style="Section.TLabel").pack(pady=8)

		# Runner selectabil
		runner_var = tk.StringVar(value="wine")
		ttk.Label(edit_dialog, text="Runner:").pack()
		runner_combo = ttk.Combobox(edit_dialog, textvariable=runner_var, values=self._get_runners())
		runner_combo.pack(pady=4)
		if runner_combo["values"]:
			runner_combo.current(0)

		# Winetricks rapid
		def run_tricks():
			pkg = simpledialog.askstring("Winetricks", "Ce componentă vrei să instalezi? (ex: directx9, corefonts)")
			if pkg:
				try:
					subprocess.run([runner_var.get(), "winetricks"], env={"WINEPREFIX": prefix_path, **os.environ}, check=True)
					messagebox.showinfo("Succes", f"Componenta {pkg} instalată!")
				except Exception as e:
					messagebox.showerror("Eroare", f"Eroare la winetricks:\n{str(e)}")

		ttk.Button(edit_dialog, text="Rulează Winetricks", command=run_tricks).pack(pady=8)
		ttk.Button(edit_dialog, text="Instalează DXVK GPLAsync", command=lambda: self.install_dxvk_gplasync(prefix_path)).pack(pady=8)

		# Rulează script custom
		def run_script_custom():
			script = filedialog.askopenfilename(title="Alege script de rulat")
			if script:
				try:
					subprocess.run([runner_var.get(), script], env={"WINEPREFIX": prefix_path, **os.environ})
					messagebox.showinfo("Script", "Script rulat cu succes!")
				except Exception as e:
					messagebox.showerror("Eroare", f"Eroare la script:\n{str(e)}")

		ttk.Button(edit_dialog, text="Rulează Script Custom", command=run_script_custom).pack(pady=8)
		# === Dropdown import .reg ===
		reg_dir = os.path.join(self.HOME, "registry")
		reg_files = []
		if os.path.isdir(reg_dir):
			reg_files = glob.glob(os.path.join(reg_dir, "*.reg"))
		reg_file_names = [os.path.basename(f) for f in reg_files]

		selected_reg = tk.StringVar(value=reg_file_names[0] if reg_file_names else "")

		if reg_file_names:
			ttk.Label(edit_dialog, text="Alege fișier .reg pentru import:", style="Section.TLabel").pack(pady=8)
			reg_combo = ttk.Combobox(edit_dialog, textvariable=selected_reg, values=reg_file_names, state="readonly")
			reg_combo.pack(pady=4)
			
			def import_registry():
				if not selected_reg.get():
					messagebox.showerror("Eroare", "Nu ai selectat niciun fișier .reg!")
					return
				reg_path = os.path.join(reg_dir, selected_reg.get())
				try:
					subprocess.run([runner_var.get(), "regedit", reg_path], env={"WINEPREFIX": prefix_path, **os.environ}, check=True)
					messagebox.showinfo("Succes", f"Registry importat: {selected_reg.get()}")
				except Exception as e:
					messagebox.showerror("Eroare", f"Eroare la import registry:\n{str(e)}")
			
			ttk.Button(edit_dialog, text="Importă Registry", command=import_registry).pack(pady=8)
		else:
			ttk.Label(edit_dialog, text="Nu există fișiere .reg în ~/registry").pack(pady=8)

		ttk.Button(edit_dialog, text="Închide", command=edit_dialog.destroy).pack(pady=12)


	def load_prefixes(self):
		with open(self.PREFIXES_FILE, "r") as f:
			return json.load(f)

	def save_prefixes(self, prefixes):
		with open(self.PREFIXES_FILE, "w") as f:
			json.dump(prefixes, f)
			
	def install_dxvk_gplasync(self, prefix_path):
		project_id = "43488626"  # ID pentru Ph42oN/dxvk-gplasync
		api_url = f"https://gitlab.com/api/v4/projects/{project_id}/releases"
		download_path = None  # inițializezi aici

		try:
			resp = requests.get(api_url)
			resp.raise_for_status()
			releases = resp.json()
			if not releases:
				messagebox.showerror("Eroare", "Nu am găsit releases pe GitLab!")
				return
			# Fă lista de opțiuni
			options = []
			assets = {}
			for rel in releases:
				title = rel['name']
				for asset in rel['assets']['links']:
					if asset['name'].endswith(".tar.gz"):
						options.append(f"{title} ({asset['name']})")
						assets[f"{title} ({asset['name']})"] = asset['url']
			if not options:
				messagebox.showerror("Eroare", "Nu am găsit arhive .tar.gz în releases!")
				return

			# Alegi versiunea
			vers_var = tk.StringVar(value=options[0])
			vers_dialog = tk.Toplevel(self.root)
			vers_dialog.title("Alege versiunea DXVK GPLAsync")
			ttk.Label(vers_dialog, text="Alege versiunea DXVK GPLAsync:").pack(pady=10)
			vers_combo = ttk.Combobox(vers_dialog, textvariable=vers_var, values=options, state="readonly")
			vers_combo.pack(pady=10)
			ttk.Button(vers_dialog, text="OK", command=vers_dialog.destroy).pack(pady=10)
			self.root.wait_window(vers_dialog)

			selected = vers_var.get()
			if not selected:
				return
			url = assets[selected]

			# Verifică dacă există deja arhiva în home
			home = os.path.expanduser("~")
			download_path = os.path.join(home, os.path.basename(url))
			if os.path.exists(download_path):
				if not messagebox.askyesno("Există deja", "Arhiva există deja. Vrei să o descarci din nou?"):
					pass  # Folosești arhiva deja descărcată
				else:
					os.remove(download_path)  # Ștergi și descarci din nou

			# Descarcă arhiva
			try:
				urllib.request.urlretrieve(url, download_path)
			except Exception as e:
				messagebox.showerror("Eroare", f"Eroare la download:\n{str(e)}")
				return

			# Extrage DLL-urile x64/x32
			system32 = os.path.join(prefix_path, "drive_c", "windows", "system32")
			os.makedirs(system32, exist_ok=True)
			try:
				with tarfile.open(download_path, "r:gz") as tar:
					for member in tar.getmembers():
						if member.name.endswith("x64/d3d11.dll"):
							with open(os.path.join(system32, "d3d11.dll"), "wb") as out:
								out.write(tar.extractfile(member).read())
						if member.name.endswith("x64/dxgi.dll"):
							with open(os.path.join(system32, "dxgi.dll"), "wb") as out:
								out.write(tar.extractfile(member).read())
						# Dacă vrei și x32, adaptează după arhivă
				messagebox.showinfo("Succes", f"DXVK GPLAsync {selected} instalat cu succes!")
			except Exception as e:
				messagebox.showerror("Eroare", f"Eroare la extragere:\n{str(e)}")
		finally:
			if download_path and os.path.exists(download_path):
				os.remove(download_path)

	def _get_runners(self):
		"""Detectează runnerii disponibili"""
		runners = []
		for bin_name in ["wine", "proton-run.sh", "hangover-wine", "hangover-run.sh" "bash", "wine-stable", "proton-wine", "proton-box", "box64", "box86", "box32"]:
			if shutil.which(bin_name):
				runners.append(bin_name)
		return runners or ["wine", "bash"]

	# ===================================================================
	# Funcții pentru descărcare și actualizare
	# ===================================================================
	
	def show_available_templates(self):
		"""Afișează template-urile disponibile pentru descărcare"""
		try:
			# Obține ultimul release
			releases = self._get_github_releases("moio9", "default")
			if not releases:
				messagebox.showinfo("Informație", "Nu s-au găsit release-uri.")
				return
			
			latest_release = releases[0]
			assets = latest_release.get('assets', [])
			
			# Filtrează doar asset-urile care conțin "template" sau au extensii specifice
			template_assets = [a for a in assets if 
							 'template' in a['name'].lower() or 
							 a['name'].endswith(('.sh', '.py', 'tmp'))]
			
			if not template_assets:
				messagebox.showinfo("Informație", "Nu s-au găsit template-uri în acest release.")
				return
			
			# Creează dialogul
			dialog = tk.Toplevel(self.root)
			dialog.title("Template-uri Disponibile")
			dialog.geometry("600x400")
			
			# Frame principal
			main_frame = ttk.Frame(dialog)
			main_frame.pack(fill="both", expand=True, padx=10, pady=10)
			
			# Titlu
			ttk.Label(main_frame, text="Selectează template-urile de descărcat:", 
					 style="Section.TLabel").pack(anchor="w", pady=5)
			
			# Frame pentru lista cu scroll
			list_frame = ttk.Frame(main_frame)
			list_frame.pack(fill="both", expand=True)
			
			# Scrollbar
			scrollbar = ttk.Scrollbar(list_frame)
			scrollbar.pack(side="right", fill="y")
			
			# Listbox pentru template-uri
			listbox = tk.Listbox(
				list_frame, 
				selectmode=tk.MULTIPLE,
				yscrollcommand=scrollbar.set,
				width=60,
				height=15
			)
			listbox.pack(side="left", fill="both", expand=True)
			scrollbar.config(command=listbox.yview)
			
			# Adaugă template-uri în listă
			for asset in template_assets:
				# Verifică dacă template-ul există deja local
				local_path = os.path.join(self.TEMPLATES_DIR, asset['name'])
				exists = os.path.exists(local_path)
				status = " (deja există)" if exists else ""
				listbox.insert(tk.END, f"{asset['name']}{status}")
			
			# Buton de descărcare
			def download_selected():
				selected_indices = listbox.curselection()
				if not selected_indices:
					messagebox.showwarning("Atenție", "Nu ai selectat niciun template!")
					return
				
				overwrite = messagebox.askyesno(
					"Suprascriere", 
					"Dorești să suprascrii template-urile existente?",
					parent=dialog
				)
				
				for index in selected_indices:
					asset = template_assets[index]
					self._download_template(asset, overwrite)
				
				dialog.destroy()
				self.list_templates()  # Reîmprospătează lista
			
			btn_frame = ttk.Frame(main_frame)
			btn_frame.pack(pady=10)
			
			ttk.Button(btn_frame, text="Descarcă Selectate", 
					  command=download_selected).pack(side="left", padx=5)
			ttk.Button(btn_frame, text="Închide", 
					  command=dialog.destroy).pack(side="left", padx=5)
			
		except Exception as e:
			messagebox.showerror("Eroare", f"Nu am putut obține template-urile:\n{str(e)}")

	def _download_template(self, asset, overwrite=False):
		"""Descarcă un template individual"""
		try:
			save_path = os.path.join(self.TEMPLATES_DIR, asset['name'])
			
			# Verifică dacă fișierul există deja
			if os.path.exists(save_path) and not overwrite:
				messagebox.showinfo("Sărit", f"Template-ul {asset['name']} există deja și nu a fost suprascris.")
				return False
			
			# Descarcă asset-ul
			response = requests.get(asset['browser_download_url'], stream=True)
			response.raise_for_status()
			
			with open(save_path, 'wb') as f:
				for chunk in response.iter_content(chunk_size=8192):
					f.write(chunk)
			
			# Setează permisiuni de execuție pentru fișierele .sh
			if asset['name'].endswith('.sh'):
				os.chmod(save_path, 0o755)
			
			messagebox.showinfo("Succes", f"Template descărcat: {asset['name']}")
			return True
		except Exception as e:
			messagebox.showerror("Eroare", f"Eroare la descărcarea {asset['name']}:\n{str(e)}")
			return False

	def _get_github_releases(self, owner, repo, tag=None):
		"""Obține lista de release-uri de pe GitHub"""
		if tag:
			# Use specific tag URL
			url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
		else:
			# General releases URL
			url = f"https://api.github.com/repos/{owner}/{repo}/releases"
			
		headers = {'User-Agent': 'ShortcutLauncher/1.0'}
		try:
			response = requests.get(url, headers=headers)
			response.raise_for_status()
			return response.json()
		except requests.exceptions.HTTPError as e:
			if e.response.status_code == 404:
				messagebox.showerror("Eroare", f"Nu s-a găsit release-ul pentru eticheta: {tag}")
			else:
				messagebox.showerror("Eroare", f"Eroare API GitHub: {str(e)}")
			return []
		except Exception as e:
			messagebox.showerror("Eroare", f"Eroare la conectare: {str(e)}")
			return []

	def show_about(self):
		"""Afișează dialogul 'Despre'"""
		about_dialog = tk.Toplevel(self.root)
		about_dialog.title("Despre Shortcut Launcher")
		about_dialog.geometry("400x300")
		
		ttk.Label(about_dialog, text=f"Shortcut Launcher {__version__}", 
				 font=("Arial", 14, "bold")).pack(pady=10)
		
		ttk.Label(about_dialog, text="Launcher pentru crearea și gestionarea\nshortcut-urilor și template-urilor", 
				 justify="center").pack(pady=10)
		
		ttk.Label(about_dialog, text="Repository:", font=("Arial", 10)).pack(pady=5)
		
		# Buton pentru deschiderea repository-ului
		repo_frame = ttk.Frame(about_dialog)
		repo_frame.pack(pady=5)
		
		def open_template_repo():
			webbrowser.open(self.TEMPLATE_RELEASES)
			
		ttk.Button(repo_frame, text="Template-uri", 
				  command=open_template_repo).pack(side=tk.LEFT, padx=5)
		
		def open_app_repo():
			webbrowser.open(self.APP_RELEASES)
			
		ttk.Button(repo_frame, text="Aplicație", 
				  command=open_app_repo).pack(side=tk.LEFT, padx=5)
		
		# Buton de închidere
		ttk.Button(about_dialog, text="Închide", 
				  command=about_dialog.destroy).pack(pady=15)

	def check_app_update(self):
		"""Verifică dacă există o versiune nouă a aplicației"""
		try:
			# Obține ultimul release
			releases = self._get_github_releases("moio9", "default")
			if not releases:
				messagebox.showinfo("Actualizare", "Nu s-au găsit release-uri.")
				return
			
			latest_release = releases[0]
			latest_version = latest_release['tag_name']
			
			# Compară versiunile
			if self._is_newer_version(latest_version, __version__):
				# Găsește asset-ul principal (presupunem că e .py sau are numele repo-ului)
				app_asset = None
				for asset in latest_release.get('assets', []):
					if 'shortcut' in asset['name'].lower() or asset['name'].endswith('.py', 'txt', 'ver', 'v', ''):
						app_asset = asset
						break
				
				if not app_asset:
					messagebox.showerror("Eroare", "Nu s-a găsit fișierul aplicației în release!")
					return
					
					# Descarcă noua versiune
					temp_dir = tempfile.mkdtemp()
					download_path = os.path.join(temp_dir, app_asset['name'])
					
					try:
						response = requests.get(app_asset['browser_download_url'], stream=True)
						response.raise_for_status()
						
						with open(download_path, 'wb') as f:
							for chunk in response.iter_content(chunk_size=8192):
								f.write(chunk)
						
						# Deschide folderul cu fișierul descărcat
						subprocess.Popen(['xdg-open', temp_dir])
						messagebox.showinfo(
							"Descărcare completă",
							f"Noua versiune a fost descărcată în:\n{download_path}\n\n"
							"Te rugăm să înlocuiești manual fișierul vechi cu cel nou.",
							parent=self.root
						)
					except Exception as e:
						messagebox.showerror("Eroare", f"Eroare la descărcare: {str(e)}", parent=self.root)
			else:
				messagebox.showinfo("Actualizare", "Ai cea mai recentă versiune a aplicației.", parent=self.root)
				
		except Exception as e:
			messagebox.showerror("Eroare", f"Nu am putut verifica actualizările: {str(e)}", parent=self.root)

	def _is_newer_version(self, new_version, current_version):
		"""Compară două versiuni semantic"""
		# Elimină caractere non-numerice
		new_clean = re.sub(r'\D', '', new_version)
		current_clean = re.sub(r'\D', '', current_version)
		
		try:
			# Compară ca numere
			return int(new_clean) > int(current_clean)
		except ValueError:
			# Fallback la compararea lexicografică
			return new_version > current_version

if __name__ == "__main__":
	root = ThemedTk(theme="equilux")
	app = ShortcutLauncher(root)
	if len(sys.argv) > 1:
		app.add_shortcut(preselected_path=sys.argv[1])
	root.mainloop()
