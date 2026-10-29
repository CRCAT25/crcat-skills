#!/bin/zsh
# Join the rendered chunks (stream copy) and mux the soundtrack: ./assemble.sh draft|final [audio.wav] [out.mp4]
# Without an audio file the result is the silent cut for the review page.
set -e
cd "${0:A:h}"
case $1 in draft) N=exports/chunks-draft ;; final) N=exports/chunks-1080p60 ;; *) echo "usage: $0 draft|final [audio] [out]"; exit 1 ;; esac
L=$N/list.txt; : > $L
for f in $N/c_*.mp4(n); do [[ -s $f.done ]] || { echo "unfinished $f"; exit 1; }; echo "file '${f:t}'" >> $L; done
OUT=${3:-exports/$1.mp4}
if [[ -n $2 ]]; then
  ffmpeg -y -v error -f concat -safe 0 -i $L -i $2 -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -shortest -movflags +faststart $OUT
else
  ffmpeg -y -v error -f concat -safe 0 -i $L -c:v copy -an -movflags +faststart $OUT
fi
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate:format=duration -of compact $OUT
