#!/bin/zsh
# Move today's ElevenLabs download pairs into el_dl/NN_g1/_g2.mp3, numbered from $1 in generation order: ./grab.sh 0
# Each Generate downloads two takes: "...v4.mp3" (g1) and "...v4 (1).mp3" (g2).
D=${0:A:h}/el_dl; mkdir -p $D; sleep 2; i=$1; day=$(date +%Y-%m-%d)
for ts in $(ls ~/Downloads/ElevenLabs_${day}T*.mp3 | sed -E "s/.*ElevenLabs_(${day}T[0-9_]+)_.*/\1/" | sort -u); do
  n=$(printf %02d $i)
  for f in ~/Downloads/ElevenLabs_${ts}_*.mp3; do
    [[ $f == *"(1).mp3" ]] && mv "$f" $D/${n}_g2.mp3 || mv "$f" $D/${n}_g1.mp3
  done
  echo "$n <- $ts"; i=$((i+1))
done
