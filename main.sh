#!/data/data/com.termux/files/usr/bin/bash

SHORTCUTS="$HOME/shortcuts"
TEMPLATES="$HOME/shortcut_templates"
mkdir -p "$SHORTCUTS" "$TEMPLATES"


main_menu() {
	notify_runners
	while true; do
		CHOICE=$(zenity --list --title="Barrel" \
			--column="Opțiune" "Shortcut" "Template-uri" "Ieșire" 2>/dev/null)
		case "$CHOICE" in
			"Shortcut") shortcut_menu ;;
			"Template-uri") templates_menu ;;
			"Ieșire"|"") exit 0 ;;
		esac
	done
}

notify_runners() {
	RUNNERS=""
	for bin in wine proton hangover-wine; do
		if command -v $bin >/dev/null 2>&1; then
			RUNNERS="$RUNNERS $bin"
		fi
	done
	if [ -z "$RUNNERS" ]; then
		zenity --notification \
		  --window-icon="error" \
		  --text="⚠️ Nu am găsit niciun runner instalat (wine, proton, hangover-wine etc)!"	else		zenity --notification \		  --window-icon="info" \		  --text="Runneri detectați:$RUNNERS"
	fi
}


shortcut_menu() {
	while true; do
		OPT=$(zenity --list --title="Shortcut-uri" \
			--column="Opțiune" "Run Shortcut" "Adaugă Shortcut" "Șterge Shortcut" "Înapoi" 2>/dev/null)
		case "$OPT" in
			"Run Shortcut") run_shortcut ;;
			"Adaugă Shortcut") add_shortcut ;;
			"Șterge Shortcut") delete_shortcut ;;
			"Înapoi"|"") return ;;
		esac
	done
}

get_shortcuts() {
	[ -d "$HOME/Desktop" ] && DESKTOP_DIR="$HOME/Desktop" || DESKTOP_DIR="$HOME"
	find "$DESKTOP_DIR" -maxdepth 1 -type f -name "*.desktop" | while read -r f; do
		if grep -q -E '^(Comment|X-Shortcut-Manager)=.*Shortcut Launcher' "$f"; then
			basename "$f"
		fi
	done
}

run_shortcut() {
	[ -d "$HOME/Desktop" ] && DESKTOP_DIR="$HOME/Desktop" || DESKTOP_DIR="$HOME"
	SHORT=$(get_shortcuts | zenity --list --title="Alege Shortcut" --column="Shortcut" 2>/dev/null)
	[ -z "$SHORT" ] && return
	if command -v desktop-file-launch >/dev/null 2>&1; then
		gtk-launch "$DESKTOP_DIR/$SHORT"
	else
		bash "$DESKTOP_DIR/$SHORT"
	fi
}


add_shortcut() {
	PRESELECTED_PATH="$1"

	NAME=$(zenity --entry --title="Nume Shortcut" --text="Introdu numele shortcutului (fără spații):" 2>/dev/null)
	[ -z "$NAME" ] && return

	TEMPLATE=$(ls "$TEMPLATES" 2>/dev/null | zenity --list --title="Alege template (sau lasă gol pt script gol)" --column="Template" 2>/dev/null)

	if [ -n "$PRESELECTED_PATH" ]; then
		TARGET="$PRESELECTED_PATH"
	else
		TARGET=$(zenity --file-selection --title="Alege fișier/script de lansat" 2>/dev/null)
	fi
	[ -z "$TARGET" ] && return

	ICON_PATH=$(zenity --file-selection --title="Alege o iconiță (PNG, SVG, ICO)" 2>/dev/null)
	[ -z "$ICON_PATH" ] && ICON_PATH="application-x-executable"

	[ -d "$HOME/Desktop" ] && DESKTOP_DIR="$HOME/Desktop" || DESKTOP_DIR="$HOME"
	OUT="$DESKTOP_DIR/${NAME}.desktop"

	if [ -n "$TEMPLATE" ]; then
		EXEC_CMD="bash \"$TEMPLATES/$TEMPLATE\" \"$TARGET\""
	else
		EXEC_CMD="sh \"$TARGET\""
	fi

	cat > "$OUT" <<EOF
[Desktop Entry]
Type=Application
Name=$NAME
Exec=$EXEC_CMD
Icon=$ICON_PATH
Terminal=true
Comment=Created with Barrel
X-Barrel-App=Barrel
EOF

	chmod +x "$OUT"
	zenity --info --text="Shortcut creat pe Desktop: $OUT" 2>/dev/null
}


delete_shortcut() {
	[ -d "$HOME/Desktop" ] && DESKTOP_DIR="$HOME/Desktop" || DESKTOP_DIR="$HOME"
	SHORT=$(get_shortcuts | zenity --list --title="Șterge Shortcut" --column="Shortcut" 2>/dev/null)
	[ -z "$SHORT" ] && return
	rm -f "$DESKTOP_DIR/$SHORT"
	zenity --info --text="Shortcut șters de pe Desktop!" 2>/dev/null
}


templates_menu() {
	while true; do
		OPT=$(zenity --list --title="Template-uri" \
			--column="Opțiune" "Vezi/Edit Template" "Adaugă Template" "Șterge Template" "Înapoi" 2>/dev/null)
		case "$OPT" in
			"Vezi/Edit Template") edit_template ;;
			"Adaugă Template") add_template ;;
			"Șterge Template") delete_template ;;
			"Înapoi"|"") return ;;
		esac
	done
}

edit_template() {
	TEMP=$(ls "$TEMPLATES" 2>/dev/null | zenity --list --title="Alege template" --column="Template" 2>/dev/null)
	[ -z "$TEMP" ] && return

	EDITED=$(zenity --text-info --editable --filename="$TEMPLATES/$TEMP" --title="Editează template" 2>/dev/null)
	# Salvează DOAR dacă userul apasă OK (EDITED nu e gol)
	if [ -n "$EDITED" ]; then
		echo "$EDITED" > "$TEMPLATES/$TEMP"
		zenity --info --text="Template actualizat cu succes!" 2>/dev/null
	fi
}


add_template() {
	RUNNERS="wine|proton|hangover-wine"

	RESULT=$(zenity --forms \
		--title="Template nou" \
		--text="Completează fiecare câmp" \
		--add-entry="Nume template" \
		--add-entry="WINEPREFIX (scrie manual, ex: .wine)" \
		--add-entry="VK_ICD_FILENAMES (scrie manual, ex: wrapper_icd.aarch64.json)" \
		--add-list="Runner" \
			--list-values="$RUNNERS" \
		--add-checkbox="Rulează în paralel" \
		2>/dev/null
	)
	[ -z "$RESULT" ] && return

	NAME=$(echo "$RESULT" | cut -d"|" -f1)
	WINEPREFIX=$(echo "$RESULT" | cut -d"|" -f2)
	VKICD=$(echo "$RESULT" | cut -d"|" -f3)
	RUNNER=$(echo "$RESULT" | cut -d"|" -f4)
	PARALLEL=$(echo "$RESULT" | cut -d"|" -f5)

	[ -z "$NAME" ] && zenity --error --text="Numele nu poate fi gol!" && return

	FILE="$TEMPLATES/$NAME"
	cat > "$FILE" <<EOF
#!/bin/sh

export WINEPREFIX=~/$WINEPREFIX
export VK_ICD_FILENAMES=\$PREFIX/share/vulkan/icd.d/$VKICD

cd "\$(dirname \"\$1\")"

if [ "$PARALLEL" = "TRUE" ]; then
	$RUNNER "\$1" &
	wait
else
	$RUNNER "\$1"
fi
EOF

	chmod +x "$FILE"
	zenity --info --text="Template salvat ca: $FILE" 2>/dev/null
}


delete_template() {
	TEMP=$(ls "$TEMPLATES" 2>/dev/null | zenity --list --title="Șterge template" --column="Template" 2>/dev/null)
	[ -z "$TEMP" ] && return
	rm -f "$TEMPLATES/$TEMP"
	zenity --info --text="Template șters!" 2>/dev/null
}

if [ $# -ge 1 ]; then
	PRESELECTED_PATH="$1"
	add_shortcut "$PRESELECTED_PATH"
	exit 0
fi

main_menu

