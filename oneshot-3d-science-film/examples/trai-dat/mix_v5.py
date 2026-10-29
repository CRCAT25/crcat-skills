# Soundtrack v5: the v4 mix with the designed "cinematic" sound effects (whooshes, hums, trailer impacts) replaced by
# real field recordings (Freesound CC0): the Yasur volcano, lava, mud pots, earthquake rumble, rockfall, glacier calving,
# lightning, surf on pebbles, a hydrophone, wildfire, dawn chorus. Dinosaur voices are crocodilian/cassowary calls
# pitched down (the closest living relatives), with real wading, wing beats and footsteps.
# python3 mix_v5.py <out.wav>
import sys
from mix import CUES, M, S, build
from mix_v3 import SPLICE, C, D
from mix_v4 import NEW as V4, SHIFT, END, A

DESIGNED = ('653_', '1177_', '1143_', '2297_', '1486_', '1686_', '788_', '2782_', '3024_', '2343_', '1474_', '1482_',
            '2014_', '1280_', '479814_', '412940_', '578601_', '437968_')
real = lambda cues: [c for c in cues if not any(k in c[0] for k in DESIGNED)]

VOLC = S('freesound-176589_yasur-volcano-eruption_hendrik.mp3')       # blast at 28.8 s, then a long roar
ROAR = S('freesound-385098_volcano_morganpurkis.mp3')                 # deep steady volcano roar
QUAKE = S('freesound-353262_earthquake_thespiderwriter.mp3')         # rumble rising 9-27 s, fading after 50 s
CRACK = S('freesound-222521_cracking-earthquake_uagadugu.mp3')
ROCKS = S('freesound-381645_rockfall_alancat.mp3')                    # falls at 0, 20, 28 s
BOLT = S('freesound-434359_close-lightning-strike_csengeri.mp3')      # strike at 2 s
BOLT2 = S('freesound-243614_thunderstorm-lightning-strike_foad.mp3')  # strike at 7 s
LAVA = S('freesound-618013_bubbling-lava-flowing_jim-bretherick.mp3')
MUD = S('freesound-415608_mud-volcano-field_rtb45.mp3')
SPRING = S('freesound-414762_bubbling-hot-spring_tammarpokk.mp3')
WIND = S('freesound-112296_desert-wind_slugzilla.mp3')
SURF = S('freesound-121102_surf-and-pebbles_odilonmarcenaro.mp3')
LAP = S('freesound-318064_water-lapping-river_ceich93.mp3')
HYDRO = S('freesound-197751_underwater-ambience-lake_wjoojoo.mp3')
CALVE = S('freesound-271008_glacier-calving_cccanary.mp3')            # calving at 11 s
GATOR = S('freesound-527844_alligator-growls_d-jones.mp3')
CASS = S('freesound-867853_cassowary-grunts_thekingofgeeks360.mp3')
WADE = S('freesound-342932_wading-shallow-water_ryansitz.mp3')
RIVER = S('freesound-563555_river-wading-fast_paulprit.mp3')
FLUTTER = S('freesound-651753_large-bird-wing-flutter_anebulafont.mp3')
WINGS = S('freesound-753219_wings-flapping_lsoundaccount.mp3')
FIRE = S('freesound-659951_wildfire-trees-burning_legand569.mp3')
FIRE2 = S('freesound-755366_wild-fire-large_goochiano.mp3')
EMBERS = S('freesound-459392_fire-crackle_samuelgremaud.mp3')
DAWN = S('freesound-573080_dawn-chorus_squashy555.mp3')
DAWN_SEA = S('freesound-518670_dawn-chorus-distant-ocean_jackmichaelking.mp3')
CICADA = S('freesound-272169_cicadas_dethrok.mp3')

far = lambda hz: f'lowpass=f={hz}'
pitch = lambda r, hz=20000: f'asetrate={int(48000 * r)},aresample=48000,lowpass=f={hz}'   # slower + deeper

# old-film time (shifted past the splice by split)
OLD = [
    # dust cloud and Sun: a deep, distant roar instead of synth hums
    (WIND, 0.0, 0.0, 20.0, -15, 3.0, 4.0, far(250)),
    (ROAR, 2.0, 0.0, 22.0, -18, 4.0, 4.0, far(300)),
    (VOLC, 4.4, 28.6, 9.0, -8, 0.0, 4.0, far(600)),            # the supernova shock wave
    (QUAKE, 6.5, 18.0, 7.0, -6, 0.5, 3.0),                       # the cloud collapses
    (BOLT, 12.0, 1.6, 8.0, -12, 0.0, 4.0, far(400)),            # the Sun ignites
    # Theia
    (ROCKS, 22.35, 0.0, 3.0, 2, 0.0, 1.0, far(1500)),
    (QUAKE, 26.0, 10.0, 8.0, -6, 1.0, 2.0),                     # Theia closes in
    (ROAR, 32.6, 20.0, 2.0, -10, 0.5, 1.0),   # then a beat of near-silence
    (VOLC, 36.15, 28.7, 20.0, -6, 0.0, 10.0),                    # the impact
    (BOLT2, 36.2, 6.9, 12.0, -10, 0.0, 4.0),
    (ROCKS, 37.0, 20.0, 3.0, 2, 0.0, 1.0),
    (ROAR, 44.0, 30.0, 16.0, -16, 3.0, 4.0, far(250)),
    (QUAKE, 54.5, 30.0, 6.0, -8, 0.5, 2.0),
    # magma ocean, bombardment, steam
    (LAVA, 52.0, 10.0, 20.0, -16, 3.0, 4.0),
    (ROCKS, 60.8, 28.0, 3.0, 3, 0.0, 1.0),
    (VOLC, 65.2, 29.3, 4.0, -6, 0.0, 1.5),
    (CRACK, 66.9, 0.5, 4.0, -7, 0.0, 1.5),
    (MUD, 60.0, 2.0, 14.0, -13, 3.0, 4.0),
    (SPRING, 64.0, 15.0, 10.0, 10, 2.0, 3.0),
    # rain, lightning
    (BOLT, 73.0, 1.8, 18.0, -6, 0.0, 6.0),
    (BOLT2, 78.0, 6.8, 12.0, -12, 0.0, 4.0),
    # the first ocean, underwater, shallows
    (SURF, 84.0, 55.0, 12.0, -4, 3.0, 3.0),
    (HYDRO, 93.0, 10.0, 11.0, -10, 1.5, 2.0),
    (LAP, 97.0, 5.0, 6.0, -2, 1.0, 2.0),
    # snowball Earth, then the thaw
    (WIND, 110.0, 14.0, 4.0, -12, 0.5, 2.0),
    (WIND, 112.0, 0.0, 5.5, -16, 1.5, 2.0, far(400)),
    (CALVE, 121.0, 10.5, 10.0, -2, 0.1, 3.0),
    (LAP, 124.0, 20.0, 6.0, -2, 1.5, 2.0),                       # meltwater
    # ending
    (DAWN_SEA, 136.0, 20.0, 10.0, 6, 2.0, 3.0),
    (SURF, 140.0, 0.0, 8.0, -8, 2.0, 3.0),
]

NEW = [
    # Cambrian sea: a real hydrophone under the sea bed sounds, the surface at the end
    (HYDRO, C(4.3), 30.0, 20.5, -18, 1.0, 1.5),
    (LAP, C(22.2), 40.0, 3.0, -2, 0.5, 0.6),
    # dinosaur valley: insects, the herd wading, crocodilian bellows, pterosaur wing beats
    (CICADA, D(-0.3), 5.0, 15.0, -14, 2.0, 3.0),
    (RIVER, D(5.0), 20.0, 10.0, -6, 1.0, 2.0, far(3000)),
    (WADE, D(5.5), 0.0, 8.0, -6, 0.5, 2.0),
    (GATOR, D(6.5), 4.5, 5.0, -8, 0.2, 1.5, pitch(0.7, 1200)),     # sauropod bellow at the ford
    (GATOR, D(9.5), 1.0, 3.5, -12, 0.2, 1.5, pitch(0.6, 700)),     # another, further off
    (FLUTTER, D(13.0), 0.5, 3.5, 4, 0.1, 1.0, pitch(0.8)),
    (WINGS, D(13.5), 27.0, 5.0, 8, 0.3, 1.5),
    (CASS, D(18.4), 0.0, 3.0, -2, 0.02, 1.0, pitch(0.55)),         # the tyrannosaur's boom at the sky
    (GATOR, D(18.45), 7.0, 3.0, -4, 0.05, 1.0, pitch(0.62)),
    # the fireball: a rising roar and the ground starting to shake
    (ROAR, D(15.5), 5.0, 7.8, -10, 4.0, 0.2),
    (QUAKE, D(19.0), 14.0, 4.3, -4, 2.0, 0.2),
    # the impact
    (VOLC, D(23.15), 28.7, 7.6, -4, 0.0, 2.5),
    (BOLT, D(23.2), 1.8, 7.0, -8, 0.0, 2.0),
    (QUAKE, D(23.4), 25.0, 7.0, -5, 0.1, 2.0),
    # the shock front, then the valley burns
    (CRACK, D(30.8), 0.5, 6.0, -8, 0.0, 1.5),
    (ROCKS, D(31.0), 28.0, 3.0, 2, 0.0, 1.0),
    (FIRE2, D(31.6), 0.0, 12.0, 2, 0.6, 3.0),
    (FIRE, D(32.0), 2.0, 12.0, 4, 1.5, 3.0),
    (WIND, D(39.0), 8.0, 4.5, -12, 1.5, 1.5),
    # s11: embers in the ash winter, wind into the white, the dawn chorus over the new forest
    (EMBERS, A(0.0), 3.0, 12.0, -4, 1.0, 3.0),
    (DAWN, A(25.0), 10.0, 14.0, 0, 3.0, 2.0),
    (CICADA, A(27.0), 20.0, 11.0, -12, 3.0, 2.0),
    (WIND, A(36.0), 5.0, 3.0, -14, 0.5, 1.0),
]


def split(cues):
    out = []
    for f, st, off, ln, db, fi, fo, *fx in cues:
        if st + ln <= SPLICE:
            out.append((f, st, off, ln, db, fi, fo, *fx))
        elif st >= SPLICE:
            out.append((f, st + SHIFT, off, ln, db, fi, fo, *fx))
        else:
            head = SPLICE - st
            out.append((f, st, off, head + 0.4, db, fi, 0.6, *fx))
            out.append((f, SPLICE + SHIFT - 1.5, off + head - 1.5, ln - head + 1.5, db, 2.5, fo, *fx))
    return out


if __name__ == '__main__':
    import mix
    mix.CUES = split(real(CUES) + OLD) + real(V4) + NEW
    build(sys.argv[1], END)
