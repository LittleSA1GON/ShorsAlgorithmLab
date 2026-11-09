#!/usr/bin/env bash
# encode.sh <render_dir> <media_dir>
# PNG sequence (24 fps) -> 48 fps MP4 with motion-interpolated in-between frames, every frame a
# keyframe so the site can seek to any step instantly. Also writes a poster JPG (last frame).
set -e
R="$1"; O="$2"; mkdir -p "$O"
for d in "$R"/*/; do
  n=$(basename "$d"); ls "$d"/f_*.png >/dev/null 2>&1 || continue
  ffmpeg -y -loglevel error -framerate 24 -i "$d/f_%04d.png" \
    -vf "minterpolate=fps=48:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" \
    -c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p -g 1 -bf 0 -movflags +faststart "$O/$n.mp4"
  ffmpeg -y -loglevel error -i "$(ls "$d"/f_*.png | tail -1)" -q:v 4 "$O/$n.jpg"
  echo "$n $(du -h "$O/$n.mp4" | cut -f1)"
done
