#!/bin/zsh
# Render the film in 6 s film-time chunks: ./render_chunks.sh draft|final [from to]
#   draft: 960x540, 30 fps of output, for the review page.   final: 1920x1080, 60 fps of output, HEVC.
# Frames are sampled every speed/OFPS film seconds and played at OFPS, so the film plays at the speed in episode.json.
# Resumable: a finished chunk has a .done marker; delete it to re-render that chunk.
cd "${0:A:h}"
SPEED=$(python3 -c "import json;print(json.load(open('episode.json'))['speed'])")
END=$(cd phim3d && node -e "import('./film.js').then(m=>console.log(m.SCENES.at(-1).t1))")
case $1 in
  draft) W=960 H=540 OFPS=30 CRF=20 N=exports/chunks-draft ;;
  final) W=1920 H=1080 OFPS=60 CRF=16 N=exports/chunks-1080p60 ;;
  *) echo "usage: $0 draft|final [from to]"; exit 1 ;;
esac
FPS=$(python3 -c "print($OFPS/$SPEED)")
A=${2:-0} B=${3:-$END}
mkdir -p $N
for ((s=A; s<B; s+=6)); do
  e=$(( s+6 < B ? s+6 : B )); f=$N/c_$(printf %03d $s).mp4
  [[ -s $f.done ]] && continue
  node phim3d/render.mjs $f --w $W --h $H --fps $FPS --ofps $OFPS --from $s --to $e --crf $CRF --hevc 1 --ref 1080 >$f.log 2>&1 \
    && echo ok > $f.done
  echo "chunk $s-$e $(date +%H:%M) $([[ -s $f.done ]] && echo ok || echo FAIL: $f.log)"
done
echo ALL_DONE
