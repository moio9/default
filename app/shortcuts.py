import os
import subprocess
import shutil
from pathlib import Path
import re

# === XDG Base Directory Spec ===
XDG_CONFIG_HOME = Path(os.getenv('XDG_CONFIG_HOME', Path.home() / '.config'))
CONFIG_DIR = XDG_CONFIG_HOME / 'shortcut_launcher'

XDG_DATA_HOME = Path(os.getenv('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
DATA_DIR = XDG_DATA_HOME / 'shortcut_launcher'

XDG_CACHE_HOME = Path(os.getenv('XDG_CACHE_HOME', Path.home() / '.cache'))
CACHE_DIR = XDG_CACHE_HOME / 'shortcut_launcher'

HOME = os.path.expanduser("~")
SHORTCUTS_DIR = str(DATA_DIR / 'shortcuts')

def run_shortcut(filename):
    desktop_dir = (
        os.path.join(HOME, "Desktop")
        if os.path.exists(os.path.join(HOME, "Desktop"))
        else HOME
    )
    path = os.path.join(desktop_dir, filename)
    subprocess.Popen(["bash", path])

def delete_shortcut(filename):
    # — 1) .desktop from Applications —
    xdg = Path(os.getenv('XDG_DATA_HOME', Path.home()/'.local'/'share'))
    apps_dir = xdg/'applications' / 'shortcuts'
    desktop_file = apps_dir/filename
    if desktop_file.exists():
        desktop_file.unlink()

    # — 2) symlink from Desktop —
    desk = Path.home()/"Desktop"
    link = desk/filename
    if link.is_symlink() or link.exists():
        link.unlink()

    # — 3) icon from global theme —
    icon_base = Path(filename).stem
    icons_dir = xdg/'icons'/'hicolor'/'48x48'/'apps'
    for ext in ('.png','.svg','.ico','.xpm'):
        ico = icons_dir/f"{icon_base}{ext}"
        if ico.exists():
            ico.unlink()

def create_shortcut_common(
    preselected_path,
    ask_string_cb,
    ask_file_cb,
    show_warning_cb,
    show_info_cb,
    get_templates_cb,
    select_template_cb,
    extract_exe_icon_cb,
    refresh_shortcuts_cb,
    TEMPLATES_DIR,
    HOME
):
    # 1. Ask for name and path
    if preselected_path:
        default_name = Path(preselected_path).stem
        name = ask_string_cb("Name", "Shortcut name:", default_name)
        path = preselected_path
    else:
        name = ask_string_cb("Name", "Shortcut name:")
        path = ask_file_cb("Choose file/script")

    if not name or " " in name or not path:
        show_warning_cb("Warning", "Name cannot contain spaces and you must select a file!")
        return

    # 2. Build base_exec command
    base_exec = f'sh -c \'{path}; read -p "Apasă Enter..."\''

    # 3. Get template choice
    templates = ["(fără template)"] + get_templates_cb()
    tpl = select_template_cb(templates)

    if tpl and tpl != "(fără template)":
        tpl_path = Path(TEMPLATES_DIR) / tpl
        exec_cmd = f'bash "{tpl_path}" "{path}"'
    else:
        exec_cmd = base_exec

    # 4. Prepare icon directories
    icons_cache = CACHE_DIR / 'icons'
    icons_data = XDG_DATA_HOME / 'icons' / 'hicolor' / '48x48' / 'apps'
    icons_cache.mkdir(parents=True, exist_ok=True)
    icons_data.mkdir(parents=True, exist_ok=True)

    # 5. Extract icon from EXE or prompt for one
    icon_path = "application-x-executable"
    if path.lower().endswith('.exe'):
        tmpico = icons_data / f"{Path(path).stem}.png"
        if extract_exe_icon_cb(path, str(tmpico)):
            icon_path = str(tmpico)
        else:
            chosen = ask_file_cb(
                "Selectează o iconiță (opțional)",
                initial_dir=str(icons_data),
                initial_file=tmpico.name,
                file_types=[("Imagini", "*.png *.svg *.ico *.xpm")]
            )
            if chosen:
                icon_path = chosen

    used_icon = icon_path

    # 6. Build and save .desktop file
    desktop_content = f"""[Desktop Entry]
Type=Application
Name={name}
Exec={exec_cmd}
Icon={used_icon}
Terminal=true
Comment=Created with Shortcut Launcher
X-Shortcut-Manager=Shortcut Launcher
"""
    apps_dir = XDG_DATA_HOME / 'applications' / 'shortcuts'
    apps_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = apps_dir / f"{name}.desktop"
    with open(desktop_file, "w", encoding="utf-8") as f:
        f.write(desktop_content)
    os.chmod(desktop_file, 0o755)

    # 7. Create symlink on Desktop
    desktop_dir = Path(HOME) / "Desktop"
    desktop_link = desktop_dir / f"{name}.desktop"
    try:
        desktop_dir.mkdir(exist_ok=True)
        if desktop_link.exists():
            desktop_link.unlink()
        desktop_link.symlink_to(desktop_file)
    except Exception:
        shutil.copy2(desktop_file, desktop_link)

    show_info_cb("Success", f"Shortcut created and on Desktop:\n{desktop_link}")
    refresh_shortcuts_cb()