#!/usr/bin/env bash
# Run once at the start of every session. Idempotent, ~10 seconds.
set -e
cd "$(dirname "$0")"
echo "SLH video engine — preflight"

command -v ffmpeg >/dev/null || { echo "  FAIL: ffmpeg missing"; exit 1; }
echo "  ok  ffmpeg $(ffmpeg -version | head -1 | cut -d' ' -f3)"

python3 -c "import PIL; print('  ok  pillow', PIL.__version__)" || {
  pip install pillow --break-system-packages -q && echo "  ok  pillow installed"; }

for F in NunitoSans-Black.ttf NunitoSans-Light.ttf; do
  [ -f "assets/fonts/$F" ] || { echo "  .. rebuilding fonts from variable source"; \
    python3 tools/make_fonts.py; break; }
done
echo "  ok  Nunito Sans 900 + 300"

[ -f assets/audio/lofi_bg.mp3 ] && echo "  ok  background music" || echo "  WARN no background music"

N=$(find assets/icons -name '*.png' -not -path '*_generated*' 2>/dev/null | wc -l)
if [ "$N" -eq 0 ]; then
  echo "  WARN assets/icons/ is empty — the engine will generate Fluent-style"
  echo "       stand-ins and flag every one. Drop the 22-icon pack in with the"
  echo "       folder names from config/icons.json to use the real art."
else
  echo "  ok  $N icons"
fi
echo "ready. next: python build.py --topic <slug> --preview"
