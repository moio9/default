#!/data/data/com.termux/files/usr/bin/env python3

import sys
import os
import shutil
import subprocess
import termuxgui as tg
import time
import threading
import json
import re
import requests
import glob
import tempfile
import tarfile
import urllib.request

# Local imports
from app import __version__, __app_name__
from app import config
from app import shortcuts
from app import templates
from app import updater
from app import installers

class FileExplorer:
    def __init__(self, conn, select_file=False, start_dir=None):
        self.conn = conn
        self.dialog = tg.Activity(conn, dialog=True)
        self.entries = []
        self.paths = []
        # Build UI
        root = tg.LinearLayout(self.dialog)
        tg.TextView(self.dialog, 'Select file or folder', root).setmargin(5)
        self.tree_scroll = tg.NestedScrollView(self.dialog, root)
        self.tree = tg.LinearLayout(self.dialog, self.tree_scroll, vertical=True)
        # Start directory
        self.start_dir    = start_dir or os.getenv('HOME')
        self.cwd          = self.start_dir
        self.select_file  = select_file
        self.selected_path = None
        self._load_dir(self.cwd)

    def _load_dir(self, directory):
        try:
            self.cwd = directory
            self.tree.clearchildren()
            self.entries.clear()
            self.paths.clear()

            # If we can select folders, add a "." entry
            if self.select_file:
                self._add_item('.', directory)

            # Add parent
            if directory != "/":
                parent = os.path.dirname(directory.rstrip('/'))
                self._add_item('..', parent)

            # Folder content
            for name in sorted(os.listdir(directory)):
                full_path = os.path.join(directory, name)
                self._add_item(name, full_path)
        except (PermissionError, FileNotFoundError):
            self._load_dir(os.getenv('HOME'))


    def _add_item(self, label, path):
        tv = tg.TextView(self.dialog, label, self.tree)
        tv.sendclickevent(True)
        tv.setmargin(8)
        tv.setheight(tg.View.WRAP_CONTENT)
        self.entries.append(tv)
        self.paths.append(path)

    def run(self):
        """Run the file explorer modal dialog"""
        for ev in self.conn.events():
            # If the dialog is destroyed, return None
            if ev.type == tg.Event.destroy and ev.value.get('aid') == self.dialog.aid:
                return None

            if ev.type == tg.Event.click:
                try:
                    idx = self.entries.index(ev.value['id'])
                    path = self.paths[idx]

                    if os.path.isdir(path):
                        # If we're selecting and they clicked on the current folder again, select it
                        if self.select_file and path == self.cwd:
                            self.selected_path = path
                            self.dialog.finish()
                            return self.selected_path
                        # Otherwise, descend into it
                        else:
                            self._load_dir(path)
                    else:
                        # It's a file, so select it
                        if self.select_file:
                            self.selected_path = path
                            self.dialog.finish()
                            return self.selected_path
                except (ValueError, IndexError):
                    pass
        return None


class ShortcutManager:
    def __init__(self):
        with tg.Connection() as conn:
            self.conn = conn
            self.activity = tg.Activity(conn)
            self.lock = threading.Lock()
            self.current_tab = 0
            self.selected_index = -1
            self.selected_template = -1
            self.selected_prefix = -1
            self.shortcuts = []
            self.short_buttons = []
            self.templates = []
            self.template_buttons = []
            self.prefixes = []
            self.prefix_buttons = []
            # Setup dirs
            self.home = os.getenv('HOME')
            xdg_data = os.getenv('XDG_DATA_HOME', os.path.join(self.home, '.local', 'share'))
            self.applications_dir = os.path.join(xdg_data, 'applications')
            os.makedirs(self.applications_dir, exist_ok=True)

            # XDG desktop (fallback ~/Desktop)
            self.desktop_dir = self._get_xdg_user_dir('DESKTOP') or os.path.join(self.home, 'Desktop')
            os.makedirs(self.desktop_dir, exist_ok=True)
            # Use XDG standard for templates storage
            self.templates_dir = os.path.join(xdg_data, 'shortcut_launcher', 'templates')
            os.makedirs(self.templates_dir, exist_ok=True)
            # Wine prefixes
            self.prefixes_file = os.path.join(self.home, '.wine_prefixes.json')
            if not os.path.exists(self.prefixes_file):
                with open(self.prefixes_file, 'w') as f:
                    json.dump([], f)
            self._setup_ui()
            self._start_scroll_watcher()
            self._event_loop()

    def _get_xdg_user_dir(self, dir_type):
        try:
            return subprocess.check_output(['xdg-user-dir', dir_type]).strip().decode('utf-8')
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None

    def _update_buttons(self):
        is_sc = (self.current_tab == 0)
        is_pf = (self.current_tab == 1)
        is_tm = (self.current_tab == 2)
        has_sc = (self.selected_index    >= 0)
        has_pf = (self.selected_prefix   >= 0)
        has_tm = (self.selected_template >= 0)

        # “Add” only on Prefixes & Templates
        self.btn_add.setvisibility(
            tg.View.VISIBLE if (is_pf or is_tm) else tg.View.GONE
        )
        # “Run” only on Shortcuts when one is selected
        self.btn_run.setvisibility(
            tg.View.VISIBLE if is_sc and has_sc else tg.View.GONE
        )
        # “Edit” & “Delete” when something’s selected in the active tab
        show_ed = (is_sc and has_sc) or (is_pf and has_pf) or (is_tm and has_tm)
        self.btn_edit  .setvisibility(tg.View.VISIBLE if show_ed else tg.View.GONE)
        self.btn_delete.setvisibility(tg.View.VISIBLE if show_ed else tg.View.GONE)


    def _get_shortcuts(self):
        items = []
        apps_dir = os.path.join(os.getenv('XDG_DATA_HOME', os.path.join(self.home, '.local', 'share')), 'applications', 'shortcuts')
        os.makedirs(apps_dir, exist_ok=True)

        for fname in sorted(os.listdir(apps_dir)):
            if not fname.endswith('.desktop'):
                continue
            
            path = os.path.join(apps_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except Exception:
                continue

            # extract display name
            display_name = next((l.lstrip().split("=",1)[1] for l in lines if l.lstrip().startswith("Name=")), None)
            if not display_name:
                display_name = os.path.splitext(fname)[0]

            items.append((display_name, path))
        return items

    def _get_templates(self):
        items = []
        for fname in sorted(os.listdir(self.templates_dir)):
            path = os.path.join(self.templates_dir, fname)
            items.append((fname, path))
        return items

    def _load_prefixes(self):
        return config.load_prefixes()

    def _save_prefixes(self, prefixes):
        config.save_prefixes(prefixes)

    def _setup_ui(self):
        a = self.activity

        # Root layout
        root = tg.LinearLayout(a)

        # Title
        tv_title = tg.TextView(a, f'{__app_name__} {__version__}', root)
        tv_title.settextsize(20)
        tv_title.setmargin(5)

        # Button row
        btns = tg.LinearLayout(a, root, vertical=False)
        self.btn_add    = tg.Button(a, 'Add',    btns)
        self.btn_run    = tg.Button(a, 'Run',    btns)
        self.btn_edit   = tg.Button(a, 'Edit',   btns)
        self.btn_delete = tg.Button(a, 'Delete', btns)

        # Tabs (now including Help)
        self.tabs = tg.TabLayout(a, root)
        self.tabs.setlist(['Shortcuts', 'Prefixes', 'Templates', 'Help'])

        # Horizontal pager
        self.sv = tg.HorizontalScrollView(a, root, fillviewport=True, snapping=True, nobar=True)

        # Compute page width before setwidth()
        start = time.time()
        found = False
        while time.time() - start < 5:
            dims = self.sv.getdimensions()
            if dims and dims[0] > 0:
                self.page_width = dims[0]
                found = True
                break
        if not found:
            self.page_width = 300

        # Container for pages
        pages = tg.LinearLayout(a, self.sv, vertical=False)

        # 1) Shortcuts page
        self.sc_container = tg.LinearLayout(a, tg.NestedScrollView(a, pages))
        self.sc_container.setwidth(self.page_width, True)

        # 2) Prefixes page
        self.pf_container = tg.LinearLayout(a, tg.NestedScrollView(a, pages))
        self.pf_container.setwidth(self.page_width, True)

        # 3) Templates page
        self.tm_container = tg.LinearLayout(a, tg.NestedScrollView(a, pages))
        self.tm_container.setwidth(self.page_width, True)

        # 4) Help page (you can fill this with whatever help text you like)
        self.help_container = tg.LinearLayout(a, tg.NestedScrollView(a, pages), vertical=True)
        self.help_container.setwidth(self.page_width, True)

        # Finally, load the initial data into the real tabs
        self._refresh_content()
        self._update_buttons()

    def _refresh_content(self):
        self.shortcuts = self._get_shortcuts()
        self.short_buttons = []
        self.sc_container.clearchildren()
        for name,_ in self.shortcuts:
            btn = tg.Button(self.activity,name,self.sc_container)
            btn.sendclickevent(True)
            self.short_buttons.append(btn)
        self.selected_index = -1

        self.templates = self._get_templates()
        self.template_buttons = []
        self.tm_container.clearchildren()
        for name,_ in self.templates:
            btn = tg.Button(self.activity,name,self.tm_container)
            btn.sendclickevent(True)
            self.template_buttons.append(btn)
        add_tmp = tg.Button(self.activity,'+ Template',self.tm_container)
        self.template_buttons.append(add_tmp)
        
        add_sc = tg.Button(self.activity, '+ Shortcut', self.sc_container)
        add_sc.sendclickevent(True)
        self.short_buttons.append(add_sc)

        self.prefixes = self._load_prefixes()
        self.prefix_buttons = []
        self.pf_container.clearchildren()
        for pre in self.prefixes:
            btn = tg.Button(self.activity,pre,self.pf_container)
            btn.sendclickevent(True)
            self.prefix_buttons.append(btn)
        add_pf = tg.Button(self.activity,'+ Prefix',self.pf_container)
        self.prefix_buttons.append(add_pf)

    def _start_scroll_watcher(self):
        def watch():
            while True:
                with self.lock:
                    try:
                        pos = self.sv.getscrollposition()[0]
                        tab = round(pos/self.page_width)
                        if tab!=self.current_tab:
                            self.current_tab=tab
                            self.tabs.selecttab(tab)
                            self._update_buttons()
                    except:
                        pass
                time.sleep(0.1)
        threading.Thread(target=watch,daemon=True).start()

    def _prompt_name(self, text):
        dlg = tg.Activity(self.conn, dialog=True)
        root = tg.LinearLayout(dlg)
        tg.TextView(dlg, text, root).setmargin(5)
        et = tg.EditText(dlg, '', root)
        btns = tg.LinearLayout(dlg, root, False)
        ok = tg.Button(dlg, 'OK', btns)
        cancel = tg.Button(dlg, 'Cancel', btns)
        name = None
        for ev in self.conn.events():
            if ev.type == tg.Event.click and ev.value['id'] == ok:
                name = et.gettext().strip()
                dlg.finish()
                break
            if ev.type == tg.Event.click and ev.value['id'] == cancel:
                dlg.finish()
                break
        return name

    def _prompt_template_choice(self):
        dlg = tg.Activity(self.conn, dialog=True)
        root = tg.LinearLayout(dlg)
        tg.TextView(dlg, 'Choose template (or none):', root).setmargin(5)
        spinner = tg.Spinner(dlg, root)
        choices = ['(no template)'] + [t[0] for t in self.templates]
        spinner.setlist(choices)
        btns = tg.LinearLayout(dlg, root, False)
        ok = tg.Button(dlg, 'OK', btns)
        cancel = tg.Button(dlg, 'Cancel', btns)
        selected = '(no template)'
        for ev in self.conn.events():
            if ev.type == tg.Event.itemselected and ev.value['id'] == spinner:
                selected = ev.value['selected']
            if ev.type == tg.Event.click and ev.value['id'] in (ok, cancel):
                dlg.finish()
                break
        return selected
        
    def _prompt_add_template_action(self):
        dlg = tg.Activity(self.conn, dialog=True)
        root = tg.LinearLayout(dlg)
        tg.TextView(dlg, 'What do you want to do?', root).setmargin(5)
        spinner = tg.Spinner(dlg, root)
        options = ['Create local template', 'Download remote templates']
        spinner.setlist(options)
        btns = tg.LinearLayout(dlg, root, False)
        ok     = tg.Button(dlg, 'OK', btns)
        cancel = tg.Button(dlg, 'Cancel', btns)
        choice = options[0]
        for ev in self.conn.events():
            if ev.type == tg.Event.itemselected and ev.value['id'] == spinner:
                choice = ev.value['selected']
            if ev.type == tg.Event.click and ev.value['id'] in (ok, cancel):
                dlg.finish()
                break
        return choice
                        
    def _get_github_releases(self, owner, repo):
        return updater.get_github_releases(owner, repo)

    def _download_template(self, asset, overwrite=False):
        """Download an asset dict {name,url,...} into self.templates_dir."""
        dst = os.path.join(self.templates_dir, asset['name'])
        if os.path.exists(dst) and not overwrite:
            return
        r = requests.get(asset['browser_download_url'], stream=True)
        with open(dst, 'wb') as f:
            for chunk in r.iter_content(16*1024):
                f.write(chunk)
        os.chmod(dst, 0o755)
        self._refresh_content()
        
    def show_available_templates(self):
        dlg = tg.Activity(self.conn, dialog=True)
        scroll = tg.NestedScrollView(dlg)
        container = tg.LinearLayout(dlg, scroll, vertical=True)
        tg.TextView(dlg, 'Available Remote Templates', container).setmargin(5)

        # Fetch GitHub releases
        releases = self._get_github_releases('moio9', 'barrel')
        if not releases:
            tg.TextView(dlg, 'No releases found.', container).setmargin(5)
            ok = tg.Button(dlg, 'OK', tg.LinearLayout(dlg, container, False))
            for ev in self.conn.events():
                if ev.type == tg.Event.click and ev.value['id'] == ok:
                    dlg.finish()
                    return
        assets = releases[0].get('assets', [])

        # Build checkboxes and track selection
        checks = []  # list of (asset, checkbox)
        selected_assets = []  # list of assets to download
        for asset in assets:
            chk = tg.Checkbox(dlg, asset['name'], container, False)
            checks.append((asset, chk))

        # Download / Cancel buttons
        btns = tg.LinearLayout(dlg, container, False)
        btn_download = tg.Button(dlg, 'Download', btns)
        btn_cancel   = tg.Button(dlg, 'Cancel',   btns)

        # Event loop
        for ev in self.conn.events():
            if ev.type == tg.Event.click:
                vid = ev.value['id']
                # Toggle asset in selected_assets
                for asset, chk in checks:
                    if vid == chk:
                        if ev.value.get('set', False):
                            if asset not in selected_assets:
                                selected_assets.append(asset)
                        else:
                            if asset in selected_assets:
                                selected_assets.remove(asset)
                # On Download, pull each checked asset
                if vid == btn_download:
                    for asset in selected_assets:
                        self._download_template(asset, overwrite=True)
                    dlg.finish()
                    break
                # On Cancel just close
                elif vid == btn_cancel:
                    dlg.finish()
                    break
                    
    def _show_create_template_dialog(self):
        dlg = tg.Activity(self.conn, dialog=True)
        root = tg.LinearLayout(dlg)
        # Title
        title_view = tg.TextView(dlg, 'Create Template', root)
        title_view.settextsize(18)
        title_view.setmargin(5)
        scroll = tg.NestedScrollView(dlg, root)
        container = tg.LinearLayout(dlg, scroll, vertical=True)
        
        # Template Name
        tg.TextView(dlg, 'Template Name:', container).setmargin(5)
        et_name = tg.EditText(dlg, '', container)
        
        # Runner
        tg.TextView(dlg, 'Runner:', container).setmargin(5)
        runner_spinner = tg.Spinner(dlg, container)
        runners = [label for label, cmd in self._get_runners()]
        runner_spinner.setlist(runners)
        selected_runner = runners[0]
        
        # Parallel Execution
        parallel_check = tg.Checkbox(dlg, 'Run in Parallel (&)', container, False)
        selected_parallel = False
        
        # EMU Settings
        tg.TextView(dlg, 'EMU Settings:', container).setmargin(5)
        emu_spinner = tg.Spinner(dlg, container)
        emu_choices = ['none'] + [label for label, cmd in self._get_runners()]
        emu_spinner.setlist(emu_choices)
        selected_emu = emu_choices[0]
        
        # WINEPREFIX
        tg.TextView(dlg, 'WINEPREFIX:', container).setmargin(5)
        prefix_spinner = tg.Spinner(dlg, container)
        prefixes = self._load_prefixes()
        prefix_spinner.setlist(prefixes)
        selected_prefix = prefixes[0] if prefixes else ''
        
        # DXVK HUD
        tg.TextView(dlg, 'DXVK HUD:', container).setmargin(5)
        dxvk_spinner = tg.Spinner(dlg, container)
        dxvk_choices = ['none', '1', 'full']
        dxvk_spinner.setlist(dxvk_choices)
        selected_dxvk = dxvk_choices[0]
        
        # Vulkan ICD
        tg.TextView(dlg, 'Vulkan ICD:', container).setmargin(5)
        vk_spinner = tg.Spinner(dlg, container)
        vk_choices = ['', '$PREFIX/share/vulkan/icd.d/wrapper_icd.aarch64.json', '$PREFIX/share/vulkan/icd.d/freedreno_icd.aarch64.json']
        vk_spinner.setlist(vk_choices)
        selected_vk = vk_choices[0]
        
        # Post-Run Actions
        tg.TextView(dlg, 'Post-Run Actions:', container).setmargin(5)
        post_options = [
            'echo "Done"',
            'notify-send "Template Done"',
            'rm -f *.tmp',
            'sync',
            'poweroff',
            'pkill -9 -f services.exe'
        ]
        post_checks = []
        post_state = {opt: False for opt in post_options}
        for opt in post_options:
            chk = tg.Checkbox(dlg, opt, container, False)
            post_checks.append((opt, chk))
            
        # Add Custom Action
        add_custom = tg.Button(dlg, 'Add Custom Action', container)
        custom_actions = []
        
        # Preview
        tg.TextView(dlg, 'Preview Script:', container).setmargin(5)
        preview = tg.EditText(dlg, '', container)
        preview.setclickable(False)
        
        # Buttons
        btns = tg.LinearLayout(dlg, container, False)
        btn_ok = tg.Button(dlg, 'Save', btns)
        btn_cancel = tg.Button(dlg, 'Cancel', btns)
        
        tpl_name = None
        
        # Update preview function with CD and post-exec
        def update_preview():
            # Build script lines
            lines = ['#!/bin/sh', '', '# === Environment Variables ===']
            lines.append(f'export WINEPREFIX={selected_prefix}')
            if selected_dxvk != 'none': 
                lines.append(f'export DXVK_HUD={selected_dxvk}')
            if selected_vk: 
                lines.append(f'export VK_ICD_FILENAMES={selected_vk}')
            if selected_emu != 'none': 
                lines.append(f'export HODLL={selected_emu}')
                
            lines.extend(['', '# === Change to executable directory ==='])
            lines.append('cd "$(dirname "$1")"')
            
            lines.extend(['', '# === Main Runner ==='])
            sym = ' &' if selected_parallel else ''
            lines.append(f'{selected_runner} "$1"{sym}')
            
            # Post-run actions
            pr = [opt for opt, state in post_state.items() if state] + custom_actions
            if pr:
                lines.extend(['', '# === Post-Run Actions ==='] + pr)
                
            # Update preview
            preview.settext("\n".join(lines))
        
        # Initial preview
        update_preview()
        
        # Dialog events
        for ev2 in self.conn.events():
            if ev2.type == tg.Event.itemselected:
                sid = ev2.value['id']
                if sid == runner_spinner:
                    selected_runner = ev2.value['selected']
                elif sid == emu_spinner:
                    selected_emu = ev2.value['selected']
                elif sid == prefix_spinner:
                    selected_prefix = ev2.value['selected']
                elif sid == dxvk_spinner:
                    selected_dxvk = ev2.value['selected']
                elif sid == vk_spinner:
                    selected_vk = ev2.value['selected']
                update_preview()
                    
            if ev2.type == tg.Event.click:
                cid = ev2.value['id']
                if cid == parallel_check:
                    selected_parallel = ev2.value['set']
                    update_preview()
                    
                # Handle post-run checkboxes
                for opt, chk in post_checks:
                    if cid == chk:
                        post_state[opt] = ev2.value['set']
                        update_preview()
                        
                # Add custom action
                if cid == add_custom:
                    # Show custom action dialog
                    cd = tg.Activity(self.conn, dialog=True)
                    croot = tg.LinearLayout(cd)
                    tg.TextView(cd, 'Custom Action:', croot).setmargin(5)
                    cet = tg.EditText(cd, '', croot)
                    cbtns = tg.LinearLayout(cd, croot, False)
                    cok = tg.Button(cd, 'OK', cbtns)
                    ccancel = tg.Button(cd, 'Cancel', cbtns)
                    for ev3 in self.conn.events():
                        if ev3.type == tg.Event.click and ev3.value['id'] == cok:
                            ca = cet.gettext().strip()
                            if ca:
                                custom_actions.append(ca)
                                update_preview()
                            cd.finish()
                            break
                        if ev3.type == tg.Event.click and ev3.value['id'] == ccancel:
                            cd.finish()
                            break
                            
                if cid == btn_ok:
                    tpl_name = et_name.gettext().strip()
                    if not tpl_name:
                        tg.Toast(self.conn, "Template name cannot be empty!").show()
                        continue
                    dlg.finish()
                    break
                    
                if cid == btn_cancel:
                    dlg.finish()
                    return
                    
        if not tpl_name:
            return
            
        # Build final script content
        lines = ['#!/bin/sh', '', '# Environment Variables']
        lines.append(f'export WINEPREFIX={selected_prefix}')
        if selected_dxvk != 'none': 
            lines.append(f'export DXVK_HUD={selected_dxvk}')
        if selected_vk: 
            lines.append(f'export VK_ICD_FILENAMES={selected_vk}')
        if selected_emu != 'none': 
            lines.append(f'export HODLL={selected_emu}')
            
        lines.extend(['', '# Change to executable directory'])
        lines.append('cd "$(dirname "$1")"')
        
        lines.extend(['', '# Main Runner'])
        sym = ' &' if selected_parallel else ''
        lines.append(f'{selected_runner} "$1"{sym}')
        
        # Post-run actions
        pr = [opt for opt, state in post_state.items() if state] + custom_actions
        if pr:
            lines.extend(['', '# Post-Run Actions'] + pr)
            
        content = "\n".join(lines) + "\n"
        
        # Save template
        tpl_path = os.path.join(self.templates_dir, tpl_name)
        try:
            with open(tpl_path, 'w') as f:
                f.write(content)
            os.chmod(tpl_path, 0o755)
            self._refresh_content()
            tg.Toast(self.conn, f"Template created: {tpl_name}").show()
        except Exception as e:
            tg.Toast(self.conn, f"Error creating template: {e}").show()

            
    def _get_runners(self):
        runners = []
        for bin_name in ["wine", "proton", "hangover-wine"]:
            if shutil.which(bin_name):
                runners.append((bin_name, bin_name))
        return runners
        
        
    def _extract_exe_icon(self, exe_path, output_path):
        """
        Use wrestool (and optionally ImageMagick's convert) to pull
        the first icon resource (type 14) from a Windows .exe into a PNG.
        """
        try:
            # wrestool -x -t 14 -o <output> <exe>
            subprocess.run(
                ["wrestool", "-x", "-t", "14", "-o", output_path, exe_path],
                check=True
            )
            # optionally resize to 48×48 if imagemagick is installed
            if shutil.which("convert"):
                subprocess.run(
                    ["convert", output_path, "-resize", "48x48", output_path],
                    check=True
                )
            return os.path.exists(output_path)
        except Exception as e:
            print(f"Error extracting icon: {e}")
            return False

        
    def _show_create_prefix_dialog(self):
        # 1) Build the dialog
        dlg = tg.Activity(self.conn, dialog=True)
        root = tg.LinearLayout(dlg)

        # Title
        tv = tg.TextView(dlg, "Create Wine Prefix", root)
        tv.settextsize(18)
        tv.setmargin(5)

        # Runner selector
        tg.TextView(dlg, "Runner:", root).setmargin(5)
        runner_spinner = tg.Spinner(dlg, root)
        runners = [label for label, cmd in self._get_runners()]
        runner_spinner.setlist(runners)
        selected_runner = runners[0] if runners else "wine"

        # Architecture selector
        tg.TextView(dlg, "Architecture:", root).setmargin(5)
        arch_spinner = tg.Spinner(dlg, root)
        arches = ["win64", "win32"]
        arch_spinner.setlist(arches)
        selected_arch = arches[0]

        # Buttons row
        btns = tg.LinearLayout(dlg, root, False)
        btn_create = tg.Button(dlg, "Choose folder & Create", btns)
        btn_cancel = tg.Button(dlg, "Cancel", btns)

        # 2) Event loop
        for ev in self.conn.events():
            # keep our selection in sync
            if ev.type == tg.Event.itemselected:
                if ev.value["id"] == runner_spinner:
                    selected_runner = ev.value["selected"]
                elif ev.value["id"] == arch_spinner:
                    selected_arch = ev.value["selected"]

            # handle clicks
            if ev.type == tg.Event.click:
                vid = ev.value["id"]

                if vid == btn_create:
                    # 2a) ask for a folder
                    fe = FileExplorer(self.conn, select_file=True)
                    prefix_path = fe.run()
                    if not prefix_path:
                        # user backed out of picker → keep *this* dialog open
                        continue

                    # 2b) close our dialog
                    dlg.finish()

                    # 3) look up the actual command (wine, proton, etc.)
                    runner_cmd = dict(self._get_runners()).get(selected_runner, "wine")

                    # 4) actually create the prefix
                    env = os.environ.copy()
                    env["WINEPREFIX"] = prefix_path
                    env["WINEARCH"]   = selected_arch
                    try:
                        subprocess.run([runner_cmd, "wineboot"], env=env, check=True)
                    except Exception as e:
                        # show a friendly error
                        self._show_message("Error", f"Failed to initialize prefix:\n{e}")
                        return

                    # 5) save it and refresh
                    self.prefixes.append(prefix_path)
                    self._save_prefixes(self.prefixes)
                    self._refresh_content()
                    return

                elif vid == btn_cancel:
                    dlg.finish()
                    return

                    
    def _show_edit_prefix_dialog(self, prefix_path):
        dlg = tg.Activity(self.conn, dialog=True)
        root = tg.LinearLayout(dlg)
        tv = tg.TextView(dlg, f"Edit Prefix: {prefix_path}", root)
        tv.settextsize(18)
        tv.setmargin(5)
        scroll = tg.NestedScrollView(dlg, root)
        container = tg.LinearLayout(dlg, scroll, vertical=True)

        # Buttons for actions
        btn_winetricks = tg.Button(dlg, "Run Winetricks", container)
        btn_dxvk = tg.Button(dlg, "Install DXVK GPLAsync", container)
        btn_script = tg.Button(dlg, "Run Custom Script", container)

        # Registry import (if available)
        reg_dir = os.path.join(self.home, 'registry')
        reg_files = glob.glob(os.path.join(reg_dir, '*.reg')) if os.path.exists(reg_dir) else []
        btn_import = None
        if reg_files:
            tg.TextView(dlg, "Import Registry:", container).setmargin(5)
            reg_spinner = tg.Spinner(dlg, container)
            reg_names = [os.path.basename(f) for f in reg_files]
            reg_spinner.setlist(reg_names)
            btn_import = tg.Button(dlg, "Import Selected", container)

        # Close button
        btn_close = tg.Button(dlg, "Close", container)

        for ev in self.conn.events():
            if ev.type == tg.Event.click:
                vid = ev.value['id']
                if vid == btn_winetricks:
                    try:
                        subprocess.run(['winetricks'], env={'WINEPREFIX': prefix_path}, check=True)
                    except Exception as e:
                        print(f"Winetricks error: {e}")
                elif vid == btn_dxvk:
                    dlg.finish()
                    
                    def show_error_cb(title, message):
                        self._show_message(title, message)

                    def show_info_cb(title, message):
                        self._show_message(title, message)

                    def select_version_cb(options):
                        dialog = tg.Activity(self.conn, dialog=True)
                        root_layout = tg.LinearLayout(dialog)
                        title_view = tg.TextView(dialog, "Choose DXVK Version", root_layout)
                        title_view.settextsize(18)
                        title_view.setmargin(5)
                        spinner = tg.Spinner(dialog, root_layout)
                        spinner.setlist(options)
                        btn_ok = tg.Button(dialog, "OK", root_layout)
                        btn_cancel = tg.Button(dialog, "Cancel", root_layout)
                        
                        selected_version = options[0]
                        for ev_inner in self.conn.events():
                            if ev_inner.type == tg.Event.itemselected and ev_inner.value['id'] == spinner:
                                selected_version = ev_inner.value['selected']
                            elif ev_inner.type == tg.Event.click:
                                if ev_inner.value['id'] == btn_ok:
                                    dialog.finish()
                                    return selected_version
                                elif ev_inner.value['id'] == btn_cancel:
                                    dialog.finish()
                                    return None
                        return None # Should not be reached

                    installers.install_dxvk_gplasync(show_error_cb, show_info_cb, select_version_cb, prefix_path)
                    return                                   

                elif vid == btn_script:
                    fe = FileExplorer(self.conn, select_file=True)
                    script = fe.run()
                    if script:
                        try:
                            subprocess.run(['bash', script], env={'WINEPREFIX': prefix_path}, check=True)
                        except Exception as e:
                            print(f"Script error: {e}")
                elif btn_import is not None and vid == btn_import:
                    selected = reg_spinner.getselected()
                    if selected is not None:
                        reg_file = reg_files[selected]
                        try:
                            subprocess.run(['wine', 'regedit', reg_file], env={'WINEPREFIX': prefix_path}, check=True)
                        except Exception as e:
                            print(f"Registry import error: {e}")
                elif vid == btn_close:
                    dlg.finish()
                    break
                    
    def _show_message(self, title, message):
        dlg = tg.Activity(self.conn, dialog=True)
        root = tg.LinearLayout(dlg)
        tv = tg.TextView(dlg, title, root)
        tv.settextsize(18)
        tv.setmargin(5)
        tg.TextView(dlg, message, root).setmargin(5)
        btn_ok = tg.Button(dlg, "OK", root)
        for ev in self.conn.events():
            if ev.type == tg.Event.click and ev.value['id'] == btn_ok:
                dlg.finish()
                break
                
                
    
        

    def _show_edit_shortcut_dialog(self, name, path):
        """Edit an existing .desktop shortcut."""
        #     parse existing .desktop file     
        with open(path, 'r') as f:
            content = f.read()
        # Name
        m = re.search(r'^Name=(.*)$', content, re.MULTILINE)
        name_val = m.group(1) if m else name.replace('.desktop', '')
        # Exec
        m = re.search(r'^Exec=(.*)$', content, re.MULTILINE)
        exec_val = m.group(1) if m else ''
        # Icon
        m = re.search(r'^Icon=(.*)$', content, re.MULTILINE)
        icon_val = m.group(1) if m else ''
        # Terminal
        m = re.search(r'^Terminal=(.*)$', content, re.MULTILINE)
        term_val = (m.group(1).lower() == 'true') if m else False
        
        # Template detection and executable extraction
        tpl_name = '(no template)'
        executable_path = exec_val
        m = re.match(r'bash\s+"([^"]+)"\s+"([^"]+)"', exec_val)
        if m:
            tpl_name = os.path.basename(m.group(1))
            executable_path = m.group(2)

        #     build dialog UI     
        dlg = tg.Activity(self.conn, dialog=True)
        root = tg.LinearLayout(dlg)
        scroll = tg.NestedScrollView(dlg, root)
        container = tg.LinearLayout(dlg, scroll, vertical=True)

        # Name field
        tg.TextView(dlg, "Name:", container).setmargin(5)
        name_edit = tg.EditText(dlg, name_val, container)

        # Template spinner
        tg.TextView(dlg, "Template:", container).setmargin(5)
        templates = ['(no template)'] + [t[0] for t in self.templates]
        if tpl_name in templates and tpl_name != '(no template)':
            templates.remove(tpl_name)
            templates.insert(1, tpl_name)
        tpl_spinner = tg.Spinner(dlg, container)
        tpl_spinner.setlist(templates)
        selected_tpl = tpl_name if tpl_name in templates else '(no template)'

        # Terminal radio buttons
        tg.TextView(dlg, "Run in Terminal:", container).setmargin(5)
        rg = tg.RadioGroup(dlg, container)
        rb_yes = tg.RadioButton(dlg, "Yes", rg)
        rb_no  = tg.RadioButton(dlg, "No",  rg)
        if term_val:
            rb_yes.setchecked(True)
        else:
            rb_no.setchecked(True)
        selected_term = term_val

        # Buttons row
        btns = tg.LinearLayout(dlg, container, vertical=False)
        btn_save   = tg.Button(dlg, "Save",   btns)
        btn_cancel = tg.Button(dlg, "Cancel", btns)

        #     event loop for this dialog     
        for ev in self.conn.events():
            if ev.type == tg.Event.itemselected and ev.value['id'] == tpl_spinner:
                selected_tpl = ev.value['selected']

            elif ev.type == tg.Event.selected and ev.value['id'] == rg:
                selected_term = (ev.value['selected'] == rb_yes)

            elif ev.type == tg.Event.click:
                vid = ev.value['id']
                if vid == btn_save:
                    new_name = name_edit.gettext().strip() or name_val
                    term_flag = 'true' if selected_term else 'false'
                    
                    if selected_tpl != '(no template)':
                        tpl_path = os.path.join(self.templates_dir, selected_tpl)
                        new_exec = f'bash "{tpl_path}" "{executable_path}"'
                    else:
                        new_exec = executable_path

                    lines = [
                        "[Desktop Entry]", 
                        f"Name={new_name}",
                        f"Exec={new_exec}",
                        f"Icon={icon_val}",
                        f"Terminal={term_flag}",
                        "Type=Application"
                    ]
                    
                    content_to_write = "\n".join(lines) + "\n"

                    if new_name != name_val:
                        new_path = os.path.join(os.path.dirname(path), f"{new_name}.desktop")
                        with open(new_path, 'w') as f:
                            f.write(content_to_write)
                        os.chmod(new_path, 0o755)
                        os.remove(path)

                        old_link = os.path.join(self.desktop_dir, f"{name_val}.desktop")
                        if os.path.lexists(old_link):
                            os.remove(old_link)
                        
                        new_link = os.path.join(self.desktop_dir, f"{new_name}.desktop")
                        try:
                            if os.path.lexists(new_link):
                                os.remove(new_link)
                            os.symlink(new_path, new_link)
                        except:
                            shutil.copy2(new_path, new_link)
                    else:
                        with open(path, 'w') as f:
                            f.write(content_to_write)

                    dlg.finish()
                    self._refresh_content()
                    break

                elif vid == btn_cancel:
                    dlg.finish()
                    break


    def _event_loop(self):
        for ev in self.conn.events():
            if ev.type == tg.Event.destroy:
                sys.exit()

            # Tab switch
            if ev.type == tg.Event.itemselected and ev.value['id'] == self.tabs:
                self.current_tab = ev.value['selected']
                self.sv.setscrollposition(self.current_tab * self.page_width, 0, True)
                self.selected_index    = -1
                self.selected_prefix   = -1
                self.selected_template = -1
                self._update_buttons()
                continue

            if ev.type != tg.Event.click:
                continue
            vid = ev.value['id']

            # === Prefixes & Templates: toolbar “Add” ===
            if vid == self.btn_add:
                if self.current_tab == 1:
                    self._show_create_prefix_dialog()
                elif self.current_tab == 2:
                    action = self._prompt_add_template_action()
                    if action == 'Create local template':
                        self._show_create_template_dialog()
                    else:
                        self.show_available_templates()
                continue

            # === Shortcuts Tab ===
            if self.current_tab == 0:
                # “+ Shortcut” button is last in short_buttons
                if vid == self.short_buttons[-1]:
                    def ask_string_cb(title, prompt, initial_value=None):
                        return self._prompt_name(prompt)

                    def ask_file_cb(title, initial_dir=None, initial_file=None, file_types=None):
                        fe = FileExplorer(self.conn, select_file=True, start_dir=initial_dir)
                        return fe.run()

                    def show_warning_cb(title, message):
                        self._show_message(title, message)

                    def show_info_cb(title, message):
                        self._show_message(title, message)

                    def get_templates_cb():
                        return [t[0] for t in self.templates]

                    def select_template_cb(options):
                        dlg = tg.Activity(self.conn, dialog=True)
                        root = tg.LinearLayout(dlg)
                        tg.TextView(dlg, 'Choose template (or none):', root).setmargin(5)
                        spinner = tg.Spinner(dlg, root)
                        spinner.setlist(options)
                        btns = tg.LinearLayout(dlg, root, False)
                        ok = tg.Button(dlg, 'OK', btns)
                        cancel = tg.Button(dlg, 'Cancel', btns)
                        selected = options[0]
                        for ev_inner in self.conn.events():
                            if ev_inner.type == tg.Event.itemselected and ev_inner.value['id'] == spinner:
                                selected = ev_inner.value['selected']
                            if ev_inner.type == tg.Event.click and ev_inner.value['id'] in (ok, cancel):
                                dlg.finish()
                                break
                        return selected

                    def extract_exe_icon_cb(exe_path, output_path):
                        return self._extract_exe_icon(exe_path, output_path)

                    def refresh_shortcuts_cb():
                        self._refresh_content()

                    shortcuts.create_shortcut_common(
                        None, # preselected_path
                        ask_string_cb,
                        ask_file_cb,
                        show_warning_cb,
                        show_info_cb,
                        get_templates_cb,
                        select_template_cb,
                        extract_exe_icon_cb,
                        refresh_shortcuts_cb,
                        self.templates_dir, # TEMPLATES_DIR
                        self.home # HOME
                    )
                    continue
                # select a shortcut
                if vid in self.short_buttons:
                    self.selected_index = self.short_buttons.index(vid)
                    self._update_buttons()
                    continue
                # toolbar actions
                if self.selected_index >= 0:
                    name, path = self.shortcuts[self.selected_index]
                    if vid == self.btn_run:
                        subprocess.Popen(['bash', path])
                    elif vid == self.btn_edit:
                        self._show_edit_shortcut_dialog(name, path)
                    elif vid == self.btn_delete:
                        os.remove(path)
                        self._refresh_content()
                    continue

            # === Prefixes Tab ===
            if self.current_tab == 1:
                if vid in self.prefix_buttons:
                    idx = self.prefix_buttons.index(vid)
                    if idx < len(self.prefixes):
                        self.selected_prefix = idx
                        self._update_buttons()
                    continue
                if self.selected_prefix >= 0:
                    prefix = self.prefixes[self.selected_prefix]
                    if vid == self.btn_edit:
                        self._show_edit_prefix_dialog(prefix)
                    elif vid == self.btn_delete:
                        del self.prefixes[self.selected_prefix]
                        self._save_prefixes(self.prefixes)
                        self._refresh_content()
                    continue

            # === Templates Tab ===
            if self.current_tab == 2:
                if vid in self.template_buttons[:-1]:
                    self.selected_template = self.template_buttons.index(vid)
                    self._update_buttons()
                    continue
                if self.selected_template >= 0:
                    name, path = self.templates[self.selected_template]
                    if vid == self.btn_edit:
                        new = self._prompt_name('New template name:')
                        if new:
                            shutil.move(path, os.path.join(self.templates_dir, new))
                            self._refresh_content()
                    elif vid == self.btn_delete:
                        os.remove(path)
                        self._refresh_content()
                    continue

            # === Help Tab ===
            # no interactive elements here
            if self.current_tab == 3:
                continue


if __name__ == '__main__':
    ShortcutManager()