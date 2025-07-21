#!/usr/bin/python
import os
from ttkthemes import ThemedTk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from ttkthemes import ThemedTk, ThemedStyle
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
from shutil import SameFileError

# Local imports
from app import __version__, __app_name__
from app import config
from app import shortcuts
from app import templates
from app import updater
from app import installers


# === XDG Base Directory Spec ===
XDG_CONFIG_HOME = Path(os.getenv('XDG_CONFIG_HOME', Path.home() / '.config'))
CONFIG_DIR = XDG_CONFIG_HOME / 'shortcut_launcher'
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

XDG_DATA_HOME = Path(os.getenv('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
DATA_DIR = XDG_DATA_HOME / 'shortcut_launcher'
DATA_DIR.mkdir(parents=True, exist_ok=True)

XDG_CACHE_HOME = Path(os.getenv('XDG_CACHE_HOME', Path.home() / '.cache'))
CACHE_DIR = XDG_CACHE_HOME / 'shortcut_launcher'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class ShortcutLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{__app_name__} {__version__}")
        self.root.geometry("900x600")
        
        # Setup theme variables
        self.bg_color = "#333333"
        self.fg_color = "#ffffff"
        self.accent_color = "#4a6baf"
        self.error_color = "#ff4444"
        
        # Directories
        self.HOME = os.path.expanduser("~")
        self.SHORTCUTS_DIR = str(DATA_DIR / 'shortcuts')
        self.TEMPLATES_DIR = str(DATA_DIR / 'templates')
        os.makedirs(self.SHORTCUTS_DIR, exist_ok=True)
        os.makedirs(self.TEMPLATES_DIR, exist_ok=True)
        
        # Repository URLs
        self.TEMPLATE_RELEASES = f"{config.TEMPLATE_REPO}/releases/tag/TMP"
        self.APP_RELEASES = f"{config.APP_REPO}/releases/tag/Version"
        
        # Setup styles and theme
        self.style = ThemedStyle(self.root)
        self.current_theme = tk.StringVar(value="dark")
        self.apply_theme()
        
        # Ensure prefixes file exists
        if not config.PREFIXES_FILE.exists():
            config.save_prefixes([])
        
        self.create_menu()
        self.root.configure(bg=self.bg_color)
        self.root.option_add('*Menu.background', self.bg_color)
        self.root.option_add('*Menu.foreground', self.fg_color)
        self.root.option_add('*Menu.activeBackground', '#555555')
        self.root.option_add('*Menu.activeForeground', self.accent_color)
        self.create_main_frame()
        self.notify_runners()

    def setup_styles(self):
        """Configure all ttk styles"""
        self.style.configure('.', font=('Arial', 10))
        
        # Main styles
        self.style.configure('TFrame', background=self.bg_color)
        self.style.configure('TLabel', background=self.bg_color, foreground=self.fg_color)
        self.style.configure('TButton', padding=5)
        self.style.configure('TEntry', fieldbackground='#555555')
        self.style.configure('TCombobox', fieldbackground='#555555')
        
        # Custom styles
        self.style.configure('Header.TLabel', 
                           font=('Arial', 14, 'bold'), 
                           padding=10,
                           background=self.bg_color,
                           foreground=self.accent_color)
        
        self.style.configure('Section.TLabel',
                           font=('Arial', 12, 'bold'),
                           background=self.bg_color,
                           foreground=self.fg_color)
        
        self.style.configure('Item.TFrame',
                           background='#444444',
                           relief='groove',
                           borderwidth=1)
        
        self.style.configure('Error.TLabel',
                           foreground=self.error_color)
        
        self.style.map('TButton',
                      background=[('active', '#555555')],
                      foreground=[('active', self.accent_color)])

    def apply_theme(self):
        """Apply the selected theme"""
        t = self.current_theme.get()
        if t == "dark":
            self.style.set_theme("equilux")
            self.bg_color = "#333333"
            self.fg_color = "#ffffff"
            self.accent_color = "#4a6baf"
        else:
            self.style.set_theme("arc")
            self.bg_color = "#f5f5f5"
            self.fg_color = "#000000"
            self.accent_color = "#4a6baf"
         
        self.setup_styles()

    def create_menu(self):
        """Create the main menu bar"""
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        theme_menu = tk.Menu(view_menu, tearoff=0)
        theme_menu.add_radiobutton(label="Light", variable=self.current_theme, value="light", command=self.apply_theme)
        theme_menu.add_radiobutton(label="Dark", variable=self.current_theme, value="dark", command=self.apply_theme)
        view_menu.add_cascade(label="Theme", menu=theme_menu)
        menubar.add_cascade(label="View", menu=view_menu)
        
        # Main functions
        menubar.add_command(label="Shortcuts", command=self.list_shortcuts)
        menubar.add_command(label="Templates", command=self.list_templates)
        menubar.add_command(label="Prefixes", command=self.manage_prefixes)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        help_menu.add_command(label="Check for Updates", command=self.check_app_update)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)

    def create_main_frame(self):
        """Create the main application frame"""
        if hasattr(self, 'main_frame'):
            self.main_frame.destroy()
        
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        ttk.Label(self.main_frame, 
                 text=f"{__app_name__} {__version__}",
                 style="Header.TLabel").pack(pady=20)
        
        # Main buttons
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, 
                  text="Shortcuts", 
                  width=20,
                  command=self.list_shortcuts).pack(pady=10, padx=10)
        
        ttk.Button(btn_frame, 
                  text="Templates", 
                  width=20,
                  command=self.list_templates).pack(pady=10, padx=10)
        
        ttk.Button(btn_frame,
                  text="Wine Prefixes",
                  width=20,
                  command=self.manage_prefixes).pack(pady=10, padx=10)

    # ... [restul metodelor rămân la fel ca în codul original]
    # List shortcuts, templates, manage prefixes etc.

    def notify_runners(self):
        """Check for available runners and notify if none found"""
        self.runners = []
        for bin_name in ["wine", "proton", "hangover-wine"]:
            if shutil.which(bin_name):
                self.runners.append(bin_name)
        
        if not self.runners:
            messagebox.showwarning(
                "Warning",
                "⚠️ No installed runners found (wine, proton, hangover-wine, etc.)!"
            )

    def clear_main_frame(self):
        """Clear the main frame"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def go_back(self):
        """Return to main screen"""
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
        """Delete unused icons"""
        icons_dir = os.path.join(self.SHORTCUTS_DIR, "icons")
        if not os.path.exists(icons_dir):
            return
            
        used_icons = set()
        desktop_dir = os.path.join(self.HOME, "Desktop") if os.path.exists(os.path.join(self.HOME, "Desktop")) else self.HOME
        
        # Collect all used icons
        for f in os.listdir(desktop_dir):
            if f.endswith(".desktop"):
                with open(os.path.join(desktop_dir, f), 'r') as file:
                    for line in file:
                        if line.startswith("Icon="):
                            icon_path = line.split("=", 1)[1].strip()
                            if os.path.isabs(icon_path):
                                used_icons.add(icon_path)
        
        # Delete unused icons
        for icon_file in os.listdir(icons_dir):
            icon_path = os.path.join(icons_dir, icon_file)
            if icon_path not in used_icons:
                try:
                    os.remove(icon_path)
                except Exception as e:
                    print(f"Error deleting icon {icon_path}: {e}")

    def list_shortcuts(self):
        self.clear_main_frame()

        header = ttk.Frame(self.main_frame)
        header.pack(fill=tk.X, pady=5)
        ttk.Label(header, text="Shortcuts", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="Add", command=self.add_shortcut).pack(side=tk.RIGHT)

        canvas = tk.Canvas(self.main_frame, bg=self.bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        apps_dir = Path(os.getenv('XDG_DATA_HOME', Path.home()/'.local'/'share')) / 'applications' / 'shortcuts'
        apps_dir.mkdir(parents=True, exist_ok=True)
        shortcuts = []  # will contain (display_name, filename)

        for fname in os.listdir(apps_dir):
            if not fname.endswith(".desktop"):
                continue
            path = os.path.join(apps_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except:
                continue

            # extract display name
            display = next((l.lstrip().split("=",1)[1] for l in lines if l.lstrip().startswith("Name=")), None)
            if not display:
                display = os.path.splitext(fname)[0]

            shortcuts.append((display, fname))

        # display
        if not shortcuts:
            ttk.Label(scrollable_frame, text="No shortcuts available.").pack(pady=10)
        else:
            for display, fname in shortcuts:
                # send display and filename
                self._create_shortcut_item(scrollable_frame, display, fname)


    # Definirea corectă:
    def _create_shortcut_item(self, parent, display_name, filename):
        frame = ttk.Frame(parent, style="Item.TFrame")
        frame.pack(fill=tk.X, pady=5, padx=5)

        # Încarcă iconița (aici nu modifici)
        desktop_dir = (
            os.path.join(self.HOME, "Desktop")
            if os.path.exists(os.path.join(self.HOME, "Desktop"))
            else self.HOME
        )
        desktop_file = os.path.join(desktop_dir, filename)
        icon_path = self._get_icon_from_desktop(desktop_file)

        # Frame icon + nume
        icon_name_frame = ttk.Frame(frame)
        icon_name_frame.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # Icon
        icon_img = None
        if icon_path and os.path.exists(icon_path):
            try:
                icon_img = tk.PhotoImage(file=icon_path)
            except Exception:
                icon_img = None
        if icon_img:
            lbl_icon = ttk.Label(icon_name_frame, image=icon_img)
            lbl_icon.image = icon_img
            lbl_icon.pack(side=tk.LEFT, padx=(0,5))

        # Afișăm display_name, nu filename
        ttk.Label(icon_name_frame, text=display_name, font=("Arial", 12)).pack(side=tk.LEFT, anchor="w")

        # Buttons
        actions = ttk.Frame(frame)
        actions.pack(side=tk.RIGHT, padx=10)
        ttk.Button(actions, text="Run", width=8,
                   command=lambda f=filename: self.run_shortcut(f)).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text="Edit", width=8,
                   command=lambda f=filename: self.edit_shortcut(f)).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text="Delete", width=8,
                   command=lambda f=filename: self.delete_shortcut(f)).pack(side=tk.LEFT, padx=2)

        
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
            # Pregătim calea de output în PNG
            png_path = output_path.replace('.ico', '.png')

            # Extragem iconița cu wrestool direct în png_path
            subprocess.run([
                "wrestool", "-x", "-t", "14",
                "-o", png_path,
                exe_path
            ], check=True)

            # Convertim la dimensiune standard (dacă ImageMagick e disponibil)
            if shutil.which("convert"):
                subprocess.run([
                    "convert", png_path, "-resize", "32x32", png_path
                ], check=True)

            return os.path.exists(png_path)
        except Exception as e:
            print(f"Error extracting icon: {e}")
            return False
            

    def run_shortcut(self, filename):
        shortcuts.run_shortcut(filename)

    def edit_shortcut(self, filename):
        desktop_dir = (
            os.path.join(self.HOME, "Desktop")
            if os.path.exists(os.path.join(self.HOME, "Desktop"))
            else self.HOME
        )
        desktop_path = os.path.join(desktop_dir, filename)

        with open(desktop_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        # Safely extract values, providing defaults if they don't exist
        config = {}
        for line in lines:
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

        display_name = config.get("Name", os.path.splitext(filename)[0])
        raw_exec_val = config.get("Exec", "")
        icon_val = config.get("Icon", "application-x-executable")
        term_val = config.get("Terminal", "true").lower() == "true"

        edit_dialog = tk.Toplevel(self.root)
        edit_dialog.title(f"Edit {display_name}")
        edit_dialog.geometry("600x400")

        container = ttk.Frame(edit_dialog)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(container, text="Name:").pack(anchor="w")
        name_var = tk.StringVar(value=display_name)
        name_entry = ttk.Entry(container, textvariable=name_var)
        name_entry.pack(fill="x", pady=2)

        ttk.Label(container, text="Template (pre-run script):").pack(anchor="w", pady=(10, 0))
        template_var = tk.StringVar()
        templates = os.listdir(self.TEMPLATES_DIR)
        choices = ["(no template)"] + templates
        template_combo = ttk.Combobox(container, textvariable=template_var, values=choices, state="readonly")
        template_combo.pack(fill="x", pady=2)

        match = re.match(r'bash\s+"([^"]+)"', raw_exec_val)
        if match:
            template_var.set(os.path.basename(match.group(1)))
        else:

            template_var.set("(no template)")

        ttk.Label(container, text="Open in Terminal:").pack(anchor="w", pady=(10, 0))
        term_var = tk.BooleanVar(value=term_val)
        term_frame = ttk.Frame(container)
        term_frame.pack(anchor="w")
        ttk.Radiobutton(term_frame, text="Yes", variable=term_var, value=True).pack(side="left")
        ttk.Radiobutton(term_frame, text="No", variable=term_var, value=False).pack(side="left")

        def save_changes():
            new_name = name_var.get().strip() or display_name
            tpl = template_var.get().strip()

            # Correctly extract the actual executable path
            quoted_parts = re.findall(r'"([^"]+)"', raw_exec_val)
            if quoted_parts:
                # The last quoted part is the executable
                actual_executable_path = quoted_parts[-1]
            else:
                # Fallback for non-quoted paths
                actual_executable_path = raw_exec_val.split()[-1]

            if tpl and tpl != "(no template)":
                tpl_path = os.path.join(self.TEMPLATES_DIR, tpl)
                new_exec = f'bash "{tpl_path}" "{actual_executable_path}"'
            else:
                # If no template, just use the executable path
                new_exec = f'"{actual_executable_path}"'

            new_term = 'true' if term_var.get() else 'false'

            # Rebuild the .desktop file content
            config["Name"] = new_name
            config["Exec"] = new_exec
            config["Terminal"] = new_term
            config["Icon"] = icon_val # Preserve original icon

            new_content = "[Desktop Entry]\n" + "\n".join([f"{k}={v}" for k, v in config.items() if k != "Type"])
            
            with open(desktop_path, "w", encoding="utf-8") as f:
                f.write(new_content + "\n")

            messagebox.showinfo("Success", "Shortcut updated!")
            edit_dialog.destroy()
            self.list_shortcuts()

        btn_frame = ttk.Frame(container)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Save", command=save_changes).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=edit_dialog.destroy).pack(side="left")

    def delete_shortcut(self, filename):
        shortcuts.delete_shortcut(filename)
        self.list_shortcuts()

    def add_shortcut(self, preselected_path=None):
        def ask_string_cb(title, prompt, initial_value=None):
            return simpledialog.askstring(title, prompt, initialvalue=initial_value)

        def ask_file_cb(title, initial_dir=None, initial_file=None, file_types=None):
            return filedialog.askopenfilename(title=title, initialdir=initial_dir, initial_file=initial_file, filetypes=file_types)

        def show_warning_cb(title, message):
            messagebox.showwarning(title, message)

        def show_info_cb(title, message):
            messagebox.showinfo(title, message)

        def get_templates_cb():
            return os.listdir(self.TEMPLATES_DIR)

        def select_template_cb(options):
            dialog = tk.Toplevel(self.root)
            dialog.title("Choose Template")
            dialog.geometry("300x150")

            frame = ttk.Frame(dialog, padding=10)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text="Choose template (or none):").pack(anchor="w")
            template_var = tk.StringVar(value=options[0])
            cb = ttk.Combobox(frame, textvariable=template_var, values=options, state="readonly")
            cb.pack(fill="x", pady=5)
            cb.current(0)

            def on_ok():
                dialog.destroy()

            btns = ttk.Frame(frame)
            btns.pack(fill="x", pady=10)
            ttk.Button(btns, text="OK", command=on_ok).pack(side="right", padx=5)
            ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side="right")

            self.root.wait_window(dialog)
            return template_var.get() if template_var.get() != "" else None

        def extract_exe_icon_cb(exe_path, output_path):
            return self._extract_exe_icon(exe_path, output_path)

        def refresh_shortcuts_cb():
            self.list_shortcuts()

        shortcuts.create_shortcut_common(
            preselected_path,
            ask_string_cb,
            ask_file_cb,
            show_warning_cb,
            show_info_cb,
            get_templates_cb,
            select_template_cb,
            extract_exe_icon_cb,
            refresh_shortcuts_cb,
            self.TEMPLATES_DIR,
            self.HOME
        )

    
    def list_templates(self):
        self.clear_main_frame()

        header = ttk.Frame(self.main_frame)
        header.pack(fill=tk.X, pady=5)
        ttk.Label(header, text="Templates", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="Add", command=self.add_template).pack(side=tk.RIGHT)
        ttk.Button(header, text="Download Templates", command=self.show_available_templates).pack(side=tk.RIGHT, padx=2)

        canvas = tk.Canvas(self.main_frame, bg=self.bg_color, highlightthickness=0)
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
            ttk.Label(scrollable_frame, text="No templates available.").pack(pady=10)
        else:
            for template in templates:
                self._create_template_item(scrollable_frame, template)

        back_btn = ttk.Button(self.main_frame, text="Back", command=self.go_back)
        back_btn.pack(pady=10)

    def _create_template_item(self, parent, name):
        frame = ttk.Frame(parent, style="Item.TFrame")
        frame.pack(fill=tk.X, pady=5, padx=5)

        info_frame = ttk.Frame(frame)
        info_frame.pack(side=tk.LEFT, padx=10)

        ttk.Label(info_frame, text=name, font=("Arial", 12)).pack(anchor="w")

        actions = ttk.Frame(frame)
        actions.pack(side=tk.RIGHT, padx=10)

        ttk.Button(actions, text="Edit", width=8,
                  command=lambda: self.edit_template(name)).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text="Delete", width=8,
                  command=lambda: self.delete_template(name)).pack(side=tk.LEFT, padx=2)

    def edit_template(self, name):
        path = os.path.join(self.TEMPLATES_DIR, name)
        try:
            with open(path, "r") as f:
                content = f.read()
            edit_dialog = tk.Toplevel(self.root)
            edit_dialog.title(f"Edit {name}")
            edit_dialog.geometry("800x600")

            text_area = tk.Text(edit_dialog, wrap=tk.NONE, undo=True)
            text_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            text_area.insert(tk.END, content)

            def save_changes():
                new_content = text_area.get(1.0, tk.END)
                with open(path, "w") as f:
                    f.write(new_content.rstrip('\n'))
                messagebox.showinfo("Success", "Template saved!")
                edit_dialog.destroy()

            button_frame = ttk.Frame(edit_dialog)
            button_frame.pack(pady=5)
            ttk.Button(button_frame, text="Save", command=save_changes).pack(side="left", padx=5)
            ttk.Button(button_frame, text="Cancel", command=edit_dialog.destroy).pack(side="left")

        except Exception as e:
            messagebox.showerror("Error", f"Could not read template:\n{str(e)}")

    def delete_template(self, name):
        templates.delete_template(name)
        self.list_templates()

    def add_template(self):
        name = simpledialog.askstring("Template Name", "Enter new template name:")
        if not name:
            return

        # Load persistent custom actions
        self.custom_file = os.path.expanduser("~/.template_postrun_custom")
        if os.path.exists(self.custom_file):
            with open(self.custom_file) as f:
                self.persisted_custom_actions = [line.strip() for line in f if line.strip()]
        else:
            self.persisted_custom_actions = []

        # Create scrollable dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Template")
        dialog.geometry("800x600")
        dialog.rowconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=0)
        dialog.columnconfigure(0, weight=1)

        # Canvas + scrollbar
        canvas = tk.Canvas(dialog, bg=self.bg_color, highlightthickness=0)
        vsb = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Scrollable frame
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable, anchor="nw")

        # Title
        ttk.Label(scrollable, text="Choose options and then save").pack(pady=10)

        # Runner
        runner_var = tk.StringVar()
        ttk.Label(scrollable, text="Runner:").pack(anchor="w", padx=10)
        runner_combo = ttk.Combobox(scrollable, textvariable=runner_var, values=self._get_runners())
        runner_combo.pack(fill="x", padx=10, pady=5)
        runner_combo.current(0)

        # Parallel execution
        parallel_var = tk.BooleanVar()
        ttk.Checkbutton(scrollable, text="Run in parallel (&)", variable=parallel_var).pack(anchor="w", padx=10)

        # EMU
        emu_var = tk.StringVar()
        ttk.Label(scrollable, text="EMU Settings:").pack(anchor="w", padx=10)
        emu_combo = ttk.Combobox(scrollable, textvariable=emu_var, values=["libwow64fex.dll"])
        emu_combo.pack(fill="x", padx=10, pady=5)
        emu_combo.current(0)

        # WINEPREFIX
        wine_var = tk.StringVar()
        ttk.Label(scrollable, text="WINEPREFIX:").pack(anchor="w", padx=10)
        wine_combo = ttk.Combobox(scrollable, textvariable=wine_var, values=["~/.wine", "~/.proton"])
        wine_combo.pack(fill="x", padx=10, pady=5)
        wine_combo.current(0)

        # DXVK HUD
        dxvk_var = tk.StringVar()
        ttk.Label(scrollable, text="DXVK HUD:").pack(anchor="w", padx=10)
        dxvk_combo = ttk.Combobox(scrollable, textvariable=dxvk_var, values=["none", "1", "full"])
        dxvk_combo.pack(fill="x", padx=10, pady=5)
        dxvk_combo.current(0)

        # Vulkan ICD
        vk_var = tk.StringVar()
        ttk.Label(scrollable, text="Vulkan ICD:").pack(anchor="w", padx=10)
        vk_combo = ttk.Combobox(scrollable, textvariable=vk_var, values=[
            "$PREFIX/share/vulkan/icd.d/wrapper_icd.aarch64.json",
            "$PREFIX/share/vulkan/icd.d/freedreno_icd.aarch64.json"
        ])
        vk_combo.pack(fill="x", padx=10, pady=5)
        vk_combo.current(0)

        # Post-exec
        ttk.Label(scrollable, text="Post-execution actions:").pack(anchor="w", padx=10)
        after_vars = []
        after_frame = ttk.Frame(scrollable)
        after_frame.pack(fill="x", padx=10, pady=5)

        def refresh_after_list():
            for w in after_frame.winfo_children():
                w.destroy()
            after_vars.clear()

            available = [
                "echo 'Execution finished'",
                "notify-send 'Template finished'",
                "rm -f *.tmp",
                "sync; echo 'Data synchronized'",
                "poweroff",
                "pkill -9 -f services.exe"
            ] + self.persisted_custom_actions

            for opt in available:
                var = tk.BooleanVar()
                after_vars.append((opt, var))
                row = ttk.Frame(after_frame)
                row.pack(fill="x", pady=2)
                ttk.Checkbutton(row, text=opt, variable=var).pack(side="left", fill="x", expand=True)
                if opt in self.persisted_custom_actions:
                    ttk.Button(row, text="✖", width=2, command=lambda o=opt: delete_after(o)).pack(side="right")

        def delete_after(opt):
            if opt in self.persisted_custom_actions:
                self.persisted_custom_actions.remove(opt)
                with open(self.custom_file, "w") as f:
                    f.write("\n".join(self.persisted_custom_actions))
            refresh_after_list()

        def add_custom_post_exec():
            custom = simpledialog.askstring("Add action", "Enter a custom post-execution action:")
            if custom and custom not in self.persisted_custom_actions:
                self.persisted_custom_actions.append(custom)
                with open(self.custom_file, "a") as f:
                    f.write(custom + "\n")
            refresh_after_list()

        refresh_after_list()
        ttk.Button(scrollable, text="Add custom action ⨁", command=add_custom_post_exec).pack(anchor="w", padx=10, pady=5)

        # Preview area
        ttk.Label(scrollable, text="Script Preview:").pack(anchor="w", padx=10, pady=(10,0))
        self.code_preview = tk.Text(scrollable, height=15, wrap="none",
                                    bg=self.bg_color, fg=self.fg_color,
                                    insertbackground=self.fg_color)
        self.code_preview.pack(fill="both", expand=True, padx=10, pady=5)

        def update_preview(*_):
            runner = runner_combo.get()
            wine = wine_combo.get()
            dxvk = dxvk_combo.get()
            vk = vk_combo.get()
            emu = emu_combo.get()
            parallel = "&" if parallel_var.get() else ""
            after_lines = [opt for opt, var in after_vars if var.get()]

            lines = [
                "#!/bin/sh", "", "# === Exports ===",
                f"\texport WINEPREFIX={wine}",
                (f"\texport DXVK_HUD={dxvk}" if dxvk!="none" else ""),
                (f"\texport VK_ICD_FILENAMES={vk}" if vk else ""),
                (f"\texport HODLL={emu}" if emu else ""),
                "", "# === Script Directory ===",
                '\tcd "$(dirname "$1")"', "", "# === Main Run ===",
                f'\t{runner} "$1"{parallel}', "", "# === Post-execution ===",
                *[f"\t{cmd}" for cmd in after_lines]
            ]

            self.code_preview.config(state='normal')
            self.code_preview.delete("1.0", tk.END)
            self.code_preview.insert(tk.END, "\n".join([l for l in lines if l]))
            self.code_preview.config(state='disabled')

        def save_template():
            runner = runner_combo.get()
            wine = wine_combo.get()
            dxvk = dxvk_combo.get()
            vk = vk_combo.get()
            emu = emu_combo.get()
            parallel = "&" if parallel_var.get() else ""
            after_lines = [opt for opt,var in after_vars if var.get()]
            custom_lines = []

            lines = [
                "#!/bin/sh",
                "",
                "# === Exports ===",
                f"\texport WINEPREFIX={wine}",
                f"\texport DXVK_HUD={dxvk}" if dxvk != "none" else "",
                f"\texport VK_ICD_FILENAMES={vk}" if vk else "",
                f"\texport HODLL={emu}" if emu else "",
                "",
                "# === Script Directory ===",
                '\tcd "$(dirname "$1")"',
                "",
                "# === Main Run ===",
                f'\t{runner} "$1"{parallel}',
                "",
                "# === Post-execution ===",
                *[f"\t{text}" for text in after_lines + custom_lines]
            ]

            content = '\n'.join([line for line in lines if line])

            template_path = os.path.join(self.TEMPLATES_DIR, name)
            try:
                with open(template_path, "w") as f:
                    f.write(content)
                os.chmod(template_path, 0o755)
                messagebox.showinfo("Success", f"Template saved: {template_path}")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Could not save template:\n{str(e)}")

        # Fixed button bar
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Button(btn_frame, text="Save Template", command=save_template).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left")

        # Legări preview
        runner_combo.bind("<<ComboboxSelected>>", update_preview)
        parallel_var.trace_add("write", lambda *_: update_preview())
        emu_combo.bind("<<ComboboxSelected>>", update_preview)
        wine_combo.bind("<<ComboboxSelected>>", update_preview)
        dxvk_combo.bind("<<ComboboxSelected>>", update_preview)
        vk_combo.bind("<<ComboboxSelected>>", update_preview)
        for _, var in after_vars:
            var.trace_add("write", lambda *_: update_preview())

        update_preview()


        
    def manage_prefixes(self):
        self.clear_main_frame()
        header = ttk.Frame(self.main_frame)
        header.pack(fill=tk.X, pady=5)
        ttk.Label(header, text="Manage Wine Prefixes", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="Create New Prefix", command=self.create_prefix).pack(side=tk.RIGHT)

        canvas = tk.Canvas(self.main_frame, bg=self.bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        prefixes = self.load_prefixes()
        if not prefixes:
            ttk.Label(scrollable_frame, text="No prefixes available.").pack(pady=10)
        else:
            for p in prefixes:
                self._create_prefix_item(scrollable_frame, p)

        ttk.Button(self.main_frame, text="Back", command=self.go_back).pack(pady=10)

    def create_prefix(self):
        runners = self._get_runners()
        if not runners:
            messagebox.showerror("Error", "No runners detected!")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Create New Prefix")
        dialog.geometry("420x240")
        
        runners = self._get_runners()
        template_files = [f"[TEMPLATE] {f}" for f in os.listdir(self.TEMPLATES_DIR) if os.path.isfile(os.path.join(self.TEMPLATES_DIR, f))]
        combined_options = runners + template_files

        ttk.Label(dialog, text="Runner or Template:", style="Section.TLabel").pack(pady=8)
        runner_var = tk.StringVar(value=combined_options[0])
        runner_combo = ttk.Combobox(dialog, textvariable=runner_var, values=combined_options, state="readonly")
        runner_combo.pack(pady=4)
        runner_combo.current(0)

        ttk.Label(dialog, text="Architecture:", style="Section.TLabel").pack(pady=8)
        arch_var = tk.StringVar(value="win64")
        arch_entry = ttk.Combobox(dialog, textvariable=arch_var, values=["win32", "win64"], state="readonly")
        arch_entry.pack(pady=4)
        arch_entry.current(1)

        # --- Checkpoint for registry import ---
        reg_path = os.path.join(self.HOME, "registry")
        do_import = tk.BooleanVar(value=False)
        if os.path.isfile(reg_path):
            ttk.Checkbutton(dialog, text=f"Import {reg_path} after initialization", variable=do_import).pack(pady=10)
        else:
            reg_path = None  # does not exist, do not display anything

        def create():
            dialog.destroy()
            new_prefix = filedialog.askdirectory(title="Choose folder for new prefix")
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

                # Save prefix
                prefixes = self.load_prefixes()
                if new_prefix not in prefixes:
                    prefixes.append(new_prefix)
                    self.save_prefixes(prefixes)

                messagebox.showinfo("Success", f"Prefix created successfully!\nCommand:\n{' '.join(cmd)}")
                self.manage_prefixes()
            except Exception as e:
                messagebox.showerror("Error", f"Error creating prefix:\n{str(e)}")

        ttk.Button(dialog, text="Create Prefix", command=create).pack(pady=15)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack()

            
    def _create_prefix_item(self, parent, path):
        frame = ttk.Frame(parent, style="Item.TFrame")
        frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(frame, text=path, font=("Arial", 11)).pack(side=tk.LEFT, padx=5)

        actions = ttk.Frame(frame)
        actions.pack(side=tk.RIGHT, padx=5)
        ttk.Button(actions, text="Edit", command=lambda: self.edit_prefix(path)).pack(side=tk.LEFT)
        ttk.Button(actions, text="Delete", command=lambda: self.delete_prefix(path)).pack(side=tk.LEFT, padx=3)

    def edit_prefix(self, prefix_path):
        edit_dialog = tk.Toplevel(self.root)
        edit_dialog.title("Edit Prefix")
        edit_dialog.geometry("420x440")
        ttk.Label(edit_dialog, text=f"Prefix: {prefix_path}", style="Section.TLabel").pack(pady=8)

        # Selectable runner
        runner_var = tk.StringVar(value="wine")
        ttk.Label(edit_dialog, text="Runner:").pack()
        runner_combo = ttk.Combobox(edit_dialog, textvariable=runner_var, values=self._get_runners())
        runner_combo.pack(pady=4)
        if runner_combo["values"]:
            runner_combo.current(0)

        # Quick Winetricks
        runner = runner_var.get() 
        def run_tricks():
            subprocess.run(["winetricks"], env={"WINEPREFIX": prefix_path, "WINE": runner,**os.environ}, check=True)

        ttk.Button(edit_dialog, text="Run Winetricks", command=run_tricks).pack(pady=8)
        ttk.Button(edit_dialog, text="Install DXVK GPLAsync", command=lambda: self.install_dxvk_gplasync(prefix_path)).pack(pady=8)

        # Run custom script
        def run_script_custom():
            script = filedialog.askopenfilename(title="Choose script to run")
            if script:
                try:
                    subprocess.run([runner_var.get(), script], env={"WINEPREFIX": prefix_path, **os.environ})
                    messagebox.showinfo("Script", "Script run successfully!")
                except Exception as e:
                    messagebox.showerror("Error", f"Script error:\n{str(e)}")

        ttk.Button(edit_dialog, text="Run Custom Script", command=run_script_custom).pack(pady=8)
        # === Dropdown import .reg ===
        reg_dir = os.path.join(self.HOME, "registry")
        reg_files = []
        if os.path.isdir(reg_dir):
            reg_files = glob.glob(os.path.join(reg_dir, "*.reg"))
        reg_file_names = [os.path.basename(f) for f in reg_files]

        selected_reg = tk.StringVar(value=reg_file_names[0] if reg_file_names else "")

        if reg_file_names:
            ttk.Label(edit_dialog, text="Choose .reg file to import:", style="Section.TLabel").pack(pady=8)
            reg_combo = ttk.Combobox(edit_dialog, textvariable=selected_reg, values=reg_file_names, state="readonly")
            reg_combo.pack(pady=4)
            
            def import_registry():
                if not selected_reg.get():
                    messagebox.showerror("Error", "No .reg file selected!")
                    return
                reg_path = os.path.join(reg_dir, selected_reg.get())
                try:
                    subprocess.run([runner_var.get(), "regedit", reg_path], env={"WINEPREFIX": prefix_path, **os.environ}, check=True)
                    messagebox.showinfo("Success", f"Registry imported: {selected_reg.get()}")
                except Exception as e:
                    messagebox.showerror("Error", f"Error importing registry:\n{str(e)}")
            
            ttk.Button(edit_dialog, text="Import Registry", command=import_registry).pack(pady=8)
        else:
            ttk.Label(edit_dialog, text="No .reg files in ~/registry").pack(pady=8)

        ttk.Button(edit_dialog, text="Close", command=edit_dialog.destroy).pack(pady=12)


    def load_prefixes(self):
        return config.load_prefixes()

    def save_prefixes(self, prefixes):
        config.save_prefixes(prefixes)
            


    def install_dxvk_gplasync(self, prefix_path):
        def show_error_cb(title, message):
            messagebox.showerror(title, message)

        def show_info_cb(title, message):
            messagebox.showinfo(title, message)

        def select_version_cb(options):
            vers_var = tk.StringVar(value=options[0])
            vers_dialog = tk.Toplevel(self.root)
            vers_dialog.title("Choose DXVK GPLAsync version")
            ttk.Label(vers_dialog, text="Choose DXVK GPLAsync version:").pack(pady=10)
            vers_combo = ttk.Combobox(vers_dialog, textvariable=vers_var, values=options, state="readonly")
            vers_combo.pack(pady=10, padx=10)
            ttk.Button(vers_dialog, text="OK", command=vers_dialog.destroy).pack(pady=10)
            self.root.wait_window(vers_dialog)
            return vers_var.get()

        installers.install_dxvk_gplasync(show_error_cb, show_info_cb, select_version_cb, prefix_path)

    def _get_runners(self):
        """Detect available runners"""
        runners = []
        for bin_name in ["wine", "proton-run.sh", "hangover-wine", "hangover-run.sh" "bash", "wine-stable", "proton-wine", "proton-box", "box64", "box86", "box32"]:
            if shutil.which(bin_name):
                runners.append(bin_name)
        return runners or ["wine", "bash"]

    # ===================================================================
    # Funcții pentru descărcare și actualizare
    # ===================================================================
    
    def show_available_templates(self):
        """Display available templates for download"""
        try:
            # Get latest release
            releases = self._get_github_releases("moio9", "default")
            if not releases:
                messagebox.showinfo("Information", "No releases found.")
                return
            
            latest_release = releases[0]
            assets = latest_release.get('assets', [])
            
            # Filter only assets containing "template" or with specific extensions
            template_assets = [a for a in assets if 
                             'template' in a['name'].lower() or 
                             a['name'].endswith(('.sh', '.py', 'tmp'))]
            
            if not template_assets:
                messagebox.showinfo("Information", "No templates found in this release.")
                return
            
            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Available Templates")
            dialog.geometry("600x400")
            
            # Main frame
            main_frame = ttk.Frame(dialog)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Title
            ttk.Label(main_frame, text="Select templates to download:", 
                     style="Section.TLabel").pack(anchor="w", pady=5)
            
            # Frame for list with scroll
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill="both", expand=True)
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side="right", fill="y")
            
            # Listbox for templates
            listbox = tk.Listbox(
                list_frame, 
                selectmode=tk.MULTIPLE,
                yscrollcommand=scrollbar.set,
                width=60,
                height=15
            )
            listbox.pack(side="left", fill="both", expand=True)
            scrollbar.config(command=listbox.yview)
            
            # Add templates to list
            for asset in template_assets:
                # Check if template already exists locally
                local_path = os.path.join(self.TEMPLATES_DIR, asset['name'])
                exists = os.path.exists(local_path)
                status = " (already exists)" if exists else ""
                listbox.insert(tk.END, f"{asset['name']}{status}")
            
            # Download button
            def download_selected():
                selected_indices = listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("Attention", "No template selected!")
                    return
                
                overwrite = messagebox.askyesno(
                    "Overwrite", 
                    "Do you want to overwrite existing templates?",
                    parent=dialog
                )
                
                for index in selected_indices:
                    asset = template_assets[index]
                    self._download_template(asset, overwrite)
                
                dialog.destroy()
                self.list_templates()  # Refresh list
            
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(pady=10)
            
            ttk.Button(btn_frame, text="Download Selected", 
                      command=download_selected).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Close", 
                      command=dialog.destroy).pack(side="left", padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not get templates:\n{str(e)}")

    def _download_template(self, asset, overwrite=False):
        """Download an individual template"""
        try:
            save_path = os.path.join(self.TEMPLATES_DIR, asset['name'])
            
            # Check if file already exists
            if os.path.exists(save_path) and not overwrite:
                messagebox.showinfo("Skipped", f"Template {asset['name']} already exists and was not overwritten.")
                return False
            
            # Download asset
            response = requests.get(asset['browser_download_url'], stream=True)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Set execute permissions for .sh files
            if asset['name'].endswith('.sh'):
                os.chmod(save_path, 0o755)
            
            messagebox.showinfo("Success", f"Template downloaded: {asset['name']}")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error downloading {asset['name']}:\n{str(e)}")
            return False

    def _get_github_releases(self, owner, repo, tag=None):
        return updater.get_github_releases(owner, repo, tag)

    def show_about(self):
        """Display 'About' dialog"""
        about_dialog = tk.Toplevel(self.root)
        about_dialog.title(f"About {__app_name__}")
        about_dialog.geometry("400x300")
        
        ttk.Label(about_dialog, text=f"{__app_name__} {__version__}", 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        ttk.Label(about_dialog, text="Launcher for creating and managing shortcuts and templates", 
                 justify="center").pack(pady=10)
        
        ttk.Label(about_dialog, text="Repository:", font=("Arial", 10)).pack(pady=5)
        
        # Button for opening repository
        repo_frame = ttk.Frame(about_dialog)
        repo_frame.pack(pady=5)
        
        def open_template_repo():
            webbrowser.open(self.TEMPLATE_RELEASES)
            
        ttk.Button(repo_frame, text="Templates", 
                  command=open_template_repo).pack(side=tk.LEFT, padx=5)
        
        def open_app_repo():
            webbrowser.open(self.APP_RELEASES)
            
        ttk.Button(repo_frame, text="Application", 
                  command=open_app_repo).pack(side=tk.LEFT, padx=5)
        
        # Close button
        ttk.Button(about_dialog, text="Close", 
                  command=about_dialog.destroy).pack(pady=15)

    def check_app_update(self):
        """Check for new application version"""
        try:
            # Get latest release
            releases = self._get_github_releases("moio9", "default")
            if not releases:
                messagebox.showinfo("Update", "No releases found.")
                return
            
            latest_release = releases[0]
            latest_version = latest_release['tag_name']
            
            # Compare versions
            if self._is_newer_version(latest_version, __version__):
                # Find main asset (assume it's .py or has repo name)
                app_asset = None
                for asset in latest_release.get('assets', []):
                    if 'shortcut' in asset['name'].lower() or asset['name'].endswith(('.py', 'txt', 'ver', 'v', '')):
                        app_asset = asset
                        break
                
                if not app_asset:
                    messagebox.showerror("Error", "Application file not found in release!")
                    return
                    
                    # Download new version
                    temp_dir = tempfile.mkdtemp()
                    download_path = os.path.join(temp_dir, app_asset['name'])
                    
                    try:
                        response = requests.get(app_asset['browser_download_url'], stream=True)
                        response.raise_for_status()
                        
                        with open(download_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        # Open folder with downloaded file
                        subprocess.Popen(['xdg-open', temp_dir])
                        messagebox.showinfo(
                            "Download complete",
                            f"New version downloaded to:\n{download_path}\n\n"
                            "Please manually replace the old file with the new one.",
                            parent=self.root
                        )
                    except Exception as e:
                        messagebox.showerror("Error", f"Download error: {str(e)}", parent=self.root)
            else:
                messagebox.showinfo("Update", "You have the latest version of the application.", parent=self.root)
                
        except Exception as e:
            messagebox.showerror("Error", f"Could not check for updates: {str(e)}", parent=self.root)

    def _is_newer_version(self, new_version, current_version):
        return updater.is_newer_version(new_version, current_version)

if __name__ == "__main__":
    root = ThemedTk(theme="equilux")
    app = ShortcutLauncher(root)
    if len(sys.argv) > 1:
        app.add_shortcut(preselected_path=sys.argv[1])
    root.mainloop()