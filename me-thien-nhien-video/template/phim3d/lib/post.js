// HDR post chain: scene -> half-float target -> bloom -> grade (ACES, colour, vignette, chroma, grain, flash).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

// soft HDR ceiling before bloom: extreme additive pile-ups otherwise flood the bloom mips (boxy halos, white-outs)
const CEIL = {
  uniforms: { tDiffuse: { value: null }, uMax: { value: 1e4 } },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float uMax; varying vec2 vUv;
    void main(){ vec3 c = texture2D(tDiffuse, vUv).rgb; float m = max(max(c.r, c.g), c.b);
      c *= m > 0.0 ? uMax * (1.0 - exp(-m / uMax)) / m : 1.0; gl_FragColor = vec4(c, 1.0); }`,
};

const GRADE = {
  uniforms: {
    tDiffuse: { value: null }, uTime: { value: 0 }, uRes: { value: new THREE.Vector2() },
    uExposure: { value: 1 }, uContrast: { value: 1.05 }, uSat: { value: 1.08 },
    uLift: { value: new THREE.Vector3(0, 0, 0) }, uGain: { value: new THREE.Vector3(1, 1, 1) },
    uVignette: { value: 0.35 }, uChroma: { value: 0.0015 }, uGrain: { value: 0.035 },
    uFlash: { value: new THREE.Vector4(1, 1, 1, 0) }, // rgb + amount: light-driven white/colour-out
  },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse; uniform float uTime, uExposure, uContrast, uSat, uVignette, uChroma, uGrain;
    uniform vec2 uRes; uniform vec3 uLift, uGain; uniform vec4 uFlash; varying vec2 vUv;
    vec3 aces(vec3 x){ const float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14; return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0); }
    float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
    void main(){
      vec2 d = vUv - 0.5; float r2 = dot(d, d);
      vec3 col;
      col.r = texture2D(tDiffuse, vUv - d * uChroma * (1.0 + 4.0 * r2) * 2.0).r;
      col.g = texture2D(tDiffuse, vUv).g;
      col.b = texture2D(tDiffuse, vUv + d * uChroma * (1.0 + 4.0 * r2) * 2.0).b;
      col *= uExposure;
      col = mix(col, uFlash.rgb * 6.0, uFlash.a);
      col = aces(col);
      col = col * uGain + uLift * (1.0 - col);
      float l = dot(col, vec3(0.2126, 0.7152, 0.0722));
      col = mix(vec3(l), col, uSat);
      col = (col - 0.5) * uContrast + 0.5;
      col *= 1.0 - uVignette * smoothstep(0.08, 0.75, r2 * 1.6);
      col = clamp(col, 0.0, 1.0);
      col = pow(col, vec3(1.0 / 2.2));
      float g = h(vUv * uRes + fract(uTime * 7.31) * 113.0) + h(vUv * uRes * 1.37 + fract(uTime * 3.17) * 71.0) - 1.0;
      col += g * uGrain * (0.6 + 0.4 * (1.0 - l));
      gl_FragColor = vec4(col, 1.0);
    }`,
};

export function makePost(renderer, W, H) {
  const rt = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 });
  const composer = new EffectComposer(renderer, rt);
  composer.setPixelRatio(1);
  composer.setSize(W, H);
  const rp = new RenderPass(new THREE.Scene(), new THREE.PerspectiveCamera());
  const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.6, 0.6, 0.85);
  // the bloom blur is measured in pixels: run its mip chain at 1080p-equivalent size so glows keep their reach at 4K
  const bs = (globalThis.PXREF || 1080) / H, bloomSize = bloom.setSize.bind(bloom);
  bloom.setSize = (w, h) => bloomSize(Math.round(w * bs), Math.round(h * bs));
  const ceil = new ShaderPass(CEIL);
  const grade = new ShaderPass(GRADE);
  grade.uniforms.uRes.value.set(W, H);
  composer.addPass(rp); composer.addPass(ceil); composer.addPass(bloom); composer.addPass(grade);
  const DEF = { exposure: 1, contrast: 1.05, sat: 1.08, lift: [0, 0, 0], gain: [1, 1, 1], vignette: 0.35, chroma: 0.0015,
    grain: 0.035, flash: [1, 1, 1, 0], bloom: 0.6, bloomRadius: 0.6, bloomThreshold: 0.85, hdrMax: 1e4 };
  return {
    composer, rp, bloom, grade,
    // custom(fn): scenes that composite several layers draw into the composer's read buffer themselves
    render(S, t, g = {}) {
      const o = { ...DEF, ...g }, u = grade.uniforms;
      u.uTime.value = t; u.uExposure.value = o.exposure; u.uContrast.value = o.contrast; u.uSat.value = o.sat;
      u.uLift.value.set(...o.lift); u.uGain.value.set(...o.gain); u.uVignette.value = o.vignette;
      u.uChroma.value = o.chroma; u.uGrain.value = o.grain; u.uFlash.value.set(...o.flash);
      ceil.uniforms.uMax.value = o.hdrMax; bloom.strength = o.bloom; bloom.radius = o.bloomRadius; bloom.threshold = o.bloomThreshold;
      if (S.draw) {
        rp.enabled = false;
        renderer.setRenderTarget(composer.readBuffer);
        S.draw(renderer);
      } else {
        rp.enabled = true; rp.scene = S.scene; rp.camera = S.camera;
      }
      composer.render();
    },
  };
}
