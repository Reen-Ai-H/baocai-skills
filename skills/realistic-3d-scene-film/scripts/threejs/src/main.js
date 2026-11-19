// 西湖·晨 —— three.js 离线渲染器
// 几何来自 Blender 导出；光照/天空/雾/水面/材质在这里重建。
// 每帧累积多次抖动采样：子像素抗锯齿 + 薄透镜景深 + 快门运动模糊 + 软阴影 + 雾的抖动步进。
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { Reflector } from "three/addons/objects/Reflector.js";
import { RectAreaLightUniformsLib } from "three/addons/lights/RectAreaLightUniformsLib.js";
import { NOISE, FOG, SKY } from "./glsl.js";

const log = (...a) => console.log(...a);
window.READY = false;

// ------------------------------------------------------------------ 镜头参数
const SHOT = {
  S1: { near: 0.004, shadowAt: 0.4, shadowHalf: 1.2, env: 1.0, fill: 2.6, warm: [1.12, 1.0, 0.78], sat: 0.95 },
  S2: { near: 0.05, shadowAt: 30, shadowHalf: 60 },
  S3: { near: 0.5, shadowAt: 900, shadowHalf: 160 },
  S4: { near: 0.2, shadowAt: 30, shadowHalf: 14 },
  S5: { near: 0.004, shadowAt: 0.9, shadowHalf: 1.6, fill: 1.5 },
  S6: { near: 0.2, shadowAt: 42, shadowHalf: 16 },
  S7: { near: 0.02, shadowAt: 8, shadowHalf: 30 },
  S8: { near: 0.05, shadowAt: 35, shadowHalf: 80 },
};

// ------------------------------------------------------------------ 全局 uniforms（雾/天空/时间共用）
const U = {
  uTime: { value: 0 },
  uSunDir: { value: new THREE.Vector3() },
  uSunE: { value: new THREE.Vector3() },
  uAmb: { value: new THREE.Vector3(0.17, 0.15, 0.135) },
  uFogAlb: { value: new THREE.Vector3(0.80, 0.88, 1.0) },
  uHazeA: { value: 0.00038 }, uHazeH: { value: 160 },
  uMistA: { value: 0.0042 }, uMistH: { value: 4.5 }, uMistScale: { value: 0.018 },
  uFogJit: { value: 0.5 }, uFogOn: { value: 1 }, uFogPhaseG: { value: 0.7 },
  uSunDisc: { value: 1 }, uSkyGain: { value: 1.3 },
  uZenith: { value: new THREE.Vector3(0.085, 0.09, 0.105) },
  uHorizon: { value: new THREE.Vector3(0.52, 0.40, 0.28) },
  uGlow: { value: new THREE.Vector3(1.0, 0.52, 0.20) },
};
const shared = (names) => Object.fromEntries(names.map((n) => [n, U[n]]));
const FOG_UNI = shared(["uTime", "uSunDir", "uSunE", "uAmb", "uFogAlb", "uHazeA", "uHazeH", "uMistA", "uMistH",
  "uMistScale", "uFogJit", "uFogOn", "uFogPhaseG"]);

// ------------------------------------------------------------------ 渲染器
const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "high-performance", logarithmicDepthBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(800, 450);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.NoToneMapping;
document.body.appendChild(renderer.domElement);
const gl = renderer.getContext();
const dbg = gl.getExtension("WEBGL_debug_renderer_info");
log("GPU:", dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : "?");
RectAreaLightUniformsLib.init();

// ------------------------------------------------------------------ 数据
const info = await (await fetch("public/scene.json")).json();
const ANIM = new Float32Array(await (await fetch("public/anim.bin")).arrayBuffer());
const F0 = info.frames[0], NF = info.frames[1] - info.frames[0] + 1;
const gltf = await new GLTFLoader().loadAsync("public/scene.glb");
const scene = new THREE.Scene();
const world = gltf.scene;
scene.add(world);
const san = (n) => THREE.PropertyBinding.sanitizeNodeName(n);
const byName = (n) => world.getObjectByName(san(n));

const sunDir = new THREE.Vector3(...info.sun.dir).normalize();       // 指向太阳
U.uSunDir.value.copy(sunDir);
const SUN_COL = new THREE.Vector3(1.0, 0.52, 0.24), SUN_E = 6.0;
U.uSunE.value.copy(SUN_COL).multiplyScalar(SUN_E);

// ------------------------------------------------------------------ 材质
const VCOMMON = /* glsl */ `
uniform float uTime;
uniform vec4 uSway;
attribute float sway;
varying vec3 vWPf;
varying vec3 vOP;
varying vec3 vCtr;
${NOISE}
`;
const lightsChunk = (() => {
  const src = THREE.ShaderChunk.lights_fragment_begin;
  const k = src.indexOf("#if ( NUM_DIR_LIGHTS > 0 )");
  const call = "RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );";
  const tail = src.slice(k).replace(call, call + `
    #ifdef USE_TRANS
    reflectedLight.directDiffuse += uTrans * RECIPROCAL_PI * directLight.color * saturate( -dot( geometryNormal, directLight.direction ) );
    #endif`);
  return src.slice(0, k) + tail;
})();

const PHYS_NO_AREA_SPEC = THREE.ShaderChunk.lights_physical_pars_fragment.replace(
  "reflectedLight.directSpecular += lightColor * fresnel * LTC_Evaluate( normal, viewDir, position, mInv, rectCoords );", "");
const BEAD_BELOW = { value: new THREE.Vector3(0.05, 0.075, 0.02) };
const BEAD_OUT = /* glsl */ `
  {
    vec3 C = vCtr; vec3 P = vWPf; vec3 n = normalize(P - C);
    vec3 V = normalize(cameraPosition - P);
    float F = 0.02 + 0.98 * pow(1.0 - max(dot(n, V), 0.0), 5.0);
    vec3 d = refract(-V, n, 1.0 / 1.333);
    float t = -2.0 * dot(P - C, d);
    vec3 Q = P + d * t; vec3 nq = normalize(Q - C);
    vec3 dOut = refract(d, -nq, 1.333);
    if (dot(dOut, dOut) < 1e-4) dOut = reflect(d, -nq);
    dOut = normalize(dOut);
    vec3 envDir = dOut;
    #ifdef USE_ENVMAP
    vec3 skyC = textureCubeUV(envMap, envMapRotation * envDir, 0.0).rgb * envMapIntensity;
    #else
    vec3 skyC = vec3(0.3);
    #endif
    vec3 below = uBeadBelow * (0.6 + 0.8 * max(dot(-dOut, vec3(0.0, 1.0, 0.0)), 0.0));
    vec3 T = mix(skyC, below, smoothstep(0.05, -0.15, dOut.y));
    float c = dot(dOut, uSunDir);
    T += uSunE * sunT(0.2) * 60.0 * smoothstep(0.9990, 0.99985, c);   // 透镜把太阳聚成的亮点
    vec3 outgoingLight = totalSpecular + (1.0 - F) * T * 0.96;
    gl_FragColor = vec4(outgoingLight, 1.0);
  }`;
const PROC = {
  noise: /* glsl */ `
    { float f = bnoise(vOP * uNScale, 6, 0.5); diffuseColor.rgb = mix(uN1, uN2, clamp((f - 0.35) / 0.35, 0.0, 1.0)); }`,
  hero: /* glsl */ `
    { vec2 q = vOP.xy; float ang = atan(q.y, q.x); float r = length(vOP);
      float vein = pow(1.0 - abs(sin(ang * 11.0)), 14.0), vein2 = pow(1.0 - abs(sin(ang * 44.0)), 30.0);
      float veins = (vein + vein2 * 0.35) * min(r * 12.0, 1.0);
      float navel = 1.0 - min(r * 28.0, 1.0);
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.2, 0.32, 0.1), max(navel, vein * 0.3 * min(r * 12.0, 1.0)));
      pHeight = (vein * min(r * 12.0, 1.0) + bnoise(vOP * 260.0, 2, 0.5) * 0.25) * 0.0008 * 0.25; }`,
  petal: /* glsl */ `
    { float y = 1.0 - vUv.y; vec3 c;
      if (y < 0.35) c = mix(vec3(0.95, 0.90, 0.78), vec3(0.96, 0.66, 0.72), y / 0.35);
      else if (y < 0.75) c = mix(vec3(0.96, 0.66, 0.72), vec3(0.90, 0.30, 0.45), (y - 0.35) / 0.4);
      else c = mix(vec3(0.90, 0.30, 0.45), vec3(0.72, 0.06, 0.24), (y - 0.75) / 0.25);
      diffuseColor.rgb = c * (1.0 - uTransMix); transCol = c;
      pHeight = (0.5 + 0.5 * sin(vUv.x * 18.0 * 6.2831 + 1.5 * fbm(vec3(vUv * 18.0, 0.0), 2, 0.5))) * 0.00012; }`,
  wing: /* glsl */ `
    { vec2 x = vUv * vec2(1.0, 3.5) * 22.0; vec2 n = floor(x), f = fract(x); vec2 mg, mr; float md = 8.0;
      for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) { vec2 g = vec2(i, j); vec2 r = g + hash22(n + g) - f; float d = dot(r, r); if (d < md) { md = d; mr = r; mg = g; } }
      md = 8.0;
      for (int j = -2; j <= 2; j++) for (int i = -2; i <= 2; i++) { vec2 g = mg + vec2(i, j); vec2 r = g + hash22(n + g) - f;
        if (dot(mr - r, mr - r) > 1e-5) md = min(md, dot(0.5 * (mr + r), normalize(r - mr))); }
      float vein = 1.0 - clamp(md / 0.06, 0.0, 1.0);
      diffuseColor.rgb = mix(vec3(0.95), vec3(0.08, 0.05, 0.03), vein);
      diffuseColor.a = mix(0.22, 1.0, vein); }`,
  duck: /* glsl */ `
    { float x = clamp((vOP.x + 0.28) / 0.58, 0.0, 1.0) + (bnoise(vOP * 90.0, 2, 0.5) - 0.5) * 0.03;
      x = clamp(x, 0.0, 1.0); vec3 c = uRampC[0];
      for (int i = 1; i < 9; i++) { if (i >= uRampN) break;
        float t = clamp((x - uRampP[i - 1]) / max(uRampP[i] - uRampP[i - 1], 1e-4), 0.0, 1.0);
        if (x >= uRampP[i - 1]) c = mix(uRampC[i - 1], uRampC[i], smoothstep(0.0, 1.0, t)); }
      diffuseColor.rgb = c; }`,
};
const BUMP = {
  _: "",
  stone: "pHeight = bnoise(vOP * 3.0, 8, 0.5) * 0.1 * 0.18;",
  bark: "pHeight = bnoise(vOP * 6.0, 8, 0.5) * 0.1 * 0.6;",
};

function patch(mat, o = {}) {
  mat.userData.o = o;
  const key = JSON.stringify([o.trans ? 1 : 0, o.sway ? 1 : 0, o.proc || "", o.bump || "", o.hue ? 1 : 0, o.bead ? 1 : 0, mat.type]);
  mat.customProgramCacheKey = () => key;
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, FOG_UNI);
    sh.uniforms.uSway = { value: new THREE.Vector4(...(o.sway || [0, 0, 0, 0])) };
    sh.uniforms.uTrans = { value: new THREE.Color(...(o.trans || [0, 0, 0])) };
    sh.uniforms.uTransMix = { value: o.transMix || 0 };
    sh.uniforms.uHue = { value: o.hue || 0 };
    sh.uniforms.uBeadBelow = BEAD_BELOW;
    sh.uniforms.uNScale = { value: o.nscale || 1 };
    sh.uniforms.uN1 = { value: new THREE.Color(...(o.n1 || [0, 0, 0])) };
    sh.uniforms.uN2 = { value: new THREE.Color(...(o.n2 || [0, 0, 0])) };
    const rc = (o.ramp || [[0, [0, 0, 0]]]).map((s) => new THREE.Vector3(...s[1]));
    while (rc.length < 9) rc.push(new THREE.Vector3());
    const rp = (o.ramp || [[0]]).map((s) => s[0]);
    while (rp.length < 9) rp.push(1);
    sh.uniforms.uRampC = { value: rc }; sh.uniforms.uRampP = { value: rp }; sh.uniforms.uRampN = { value: (o.ramp || []).length };
    let defs = "";
    if (o.trans) defs += "#define USE_TRANS\n";
    if (o.sway) defs += "#define USE_SWAY\n";
    sh.vertexShader = defs + sh.vertexShader
      .replace("#include <common>", "#include <common>\n" + VCOMMON)
      .replace("#include <begin_vertex>", `#include <begin_vertex>
        vOP = vec3(position.x, -position.z, position.y);
        vCtr = (modelMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
        #ifdef USE_SWAY
        { vec3 wq = (modelMatrix * vec4(position, 1.0)).xyz;
          vec3 bq = vec3(wq.x, -wq.z, wq.y) - vec3(uTime * 24.0 * 0.011, uTime * 24.0 * 0.004, 0.0);
          float n1 = bnoise(bq / 1.6, 2, 0.5) - 0.5;
          transformed.x += n1 * uSway.x * sway; transformed.z -= n1 * uSway.y * sway; }
        #endif`)
      .replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\n vWPf = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    sh.fragmentShader = defs + sh.fragmentShader
      .replace("#include <common>", `#include <common>
        ${NOISE}
        ${FOG}
        varying vec3 vWPf; varying vec3 vOP; varying vec3 vCtr;
        uniform vec3 uBeadBelow;
        uniform vec3 uTrans; uniform float uTransMix; uniform float uHue;
        uniform float uNScale; uniform vec3 uN1, uN2;
        uniform vec3 uRampC[9]; uniform float uRampP[9]; uniform int uRampN;
        vec3 hueShift(vec3 c, float h){ const vec3 k = vec3(0.57735); float a = h * 6.2831853;
          return c * cos(a) + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - cos(a)); }
        vec3 bumpN(vec3 n, vec3 pos, float h){ vec3 dpx = dFdx(pos), dpy = dFdy(pos); float dhx = dFdx(h), dhy = dFdy(h);
          vec3 r1 = cross(dpy, n), r2 = cross(n, dpx); float det = dot(dpx, r1);
          return normalize(abs(det) * n - sign(det) * (dhx * r1 + dhy * r2)); }`)
      .replace("#include <color_fragment>", `#include <color_fragment>
        float pHeight = 0.0; vec3 transCol = uTrans;
        diffuseColor.rgb = hueShift(diffuseColor.rgb, uHue);
        #ifdef USE_TRANS
        diffuseColor.rgb *= (1.0 - uTransMix);
        #endif
        ${o.proc ? PROC[o.proc] : ""}
        ${o.bump ? BUMP[o.bump] : ""}`)
      .replace("#include <normal_fragment_maps>", `#include <normal_fragment_maps>
        if (pHeight != 0.0) normal = bumpN(normal, -vViewPosition, pHeight);`)
      .replace("#include <lights_fragment_begin>", lightsChunk.replaceAll("uTrans *", "transCol * uTransMix *"))
      .replace("#include <fog_fragment>", "gl_FragColor.rgb = applyFog(gl_FragColor.rgb, vWPf);")
      .replace("#include <lights_physical_pars_fragment>", PHYS_NO_AREA_SPEC)
      .replace("#include <opaque_fragment>", o.bead ? BEAD_OUT : "#include <opaque_fragment>");
  };
  return mat;
}

const D = info.materials;
const col = (c) => new THREE.Color(c[0], c[1], c[2]);
const hashStr = (s) => { let h = 2166136261; for (const ch of s) h = Math.imul(h ^ ch.charCodeAt(0), 16777619); return ((h >>> 0) % 10000) / 10000; };
const DUCK_RAMPS = {
  mallard_m: [[0.0, [0.02, 0.02, 0.02]], [0.12, [0.85, 0.85, 0.82]], [0.2, [0.42, 0.42, 0.40]], [0.6, [0.45, 0.44, 0.42]],
    [0.66, [0.22, 0.08, 0.04]], [0.78, [0.25, 0.09, 0.05]], [0.8, [0.9, 0.9, 0.9]], [0.83, [0.02, 0.18, 0.06]], [1.0, [0.01, 0.12, 0.05]]],
  mallard_f: [[0.0, [0.15, 0.10, 0.06]], [0.5, [0.33, 0.22, 0.12]], [0.82, [0.30, 0.20, 0.11]], [0.85, [0.20, 0.13, 0.07]], [1.0, [0.24, 0.16, 0.09]]],
};
const matCache = new Map();
function makeMaterial(name, objName) {
  const d = D[name] || { color: [0.5, 0.5, 0.5], rough: 0.5 };
  const foliageHue = d.translucent && !["petal", "plume"].includes(name);
  const cacheKey = foliageHue ? name + "|" + objName : name;
  if (matCache.has(cacheKey)) return matCache.get(cacheKey);
  const m = new THREE.MeshPhysicalMaterial({
    name, color: col(d.color || [0.5, 0.5, 0.5]), roughness: d.rough ?? 0.5, metalness: d.metal || 0,
    specularIntensity: (d.spec ?? 0.5) * 2, clearcoat: d.coat || 0, clearcoatRoughness: 0.1,
    sheen: d.sheen || 0, sheenRoughness: 0.4, sheenColor: new THREE.Color(1, 1, 1), side: THREE.DoubleSide,
  });
  const o = {};
  if (d.translucent) { o.trans = d.translucent; o.transMix = d.mix ?? 0.35; }
  if (foliageHue) o.hue = (hashStr(objName) - 0.5) * 0.06;
  if ((d.emitStrength || 0) > 0) { m.emissive = col(d.emit); m.emissiveIntensity = d.emitStrength; }
  if (d.noise) { o.proc = "noise"; o.n1 = d.noise[0]; o.n2 = d.noise[1]; o.nscale = d.noiseScale; }
  if (name === "stone") o.bump = "stone";
  if (name === "bark") o.bump = "bark";
  if (name === "lotus_hero") o.proc = "hero";
  if (name === "petal") { o.proc = "petal"; m.defines = { USE_UV: "" }; m.sheen = 0.3; }
  if (name === "dragonfly_wing") {
    o.proc = "wing"; m.defines = { USE_UV: "" }; m.transparent = true; m.depthWrite = false;
    m.roughness = 0.04; m.iridescence = 1; m.iridescenceIOR = 1.5; m.iridescenceThicknessRange = [420, 420];
  }
  if (DUCK_RAMPS[name]) { o.proc = "duck"; o.ramp = DUCK_RAMPS[name]; }
  if (name === "droplet") { m.color.setRGB(0, 0, 0); m.roughness = 0.0; m.ior = 1.333; m.specularIntensity = 1; o.bead = true; }
  if (name === "feather") { o.trans = [0.92, 0.88, 0.8]; o.transMix = 0.3; }
  if (name === "lotus_bud") { o.trans = [0.95, 0.45, 0.55]; o.transMix = 0.4; }
  if (name === "seedpod") { o.trans = [0.6, 0.7, 0.2]; o.transMix = 0.2; }
  patch(m, o);
  matCache.set(cacheKey, m);
  return m;
}

// ------------------------------------------------------------------ 网格处理
let lakeMesh = null;
const meshes = [];
world.traverse((ob) => {
  if (!ob.isMesh) return;
  meshes.push(ob);
});
for (const ob of meshes) {
  const objName = ob.name;
  const mname = ob.material?.name || "";
  if (mname === "water") { lakeMesh = ob; ob.visible = false; continue; }
  ob.material = makeMaterial(mname, objName);
  ob.castShadow = true; ob.receiveShadow = true;
  const nm = (ob.name.match(/_leaves|_twigs/) ? ob.name : ob.parent?.name || "");
  if (/_leaves$|_twigs$/.test(ob.name) || /_leaves$|_twigs$/.test(nm)) {
    const pos = ob.geometry.attributes.position;
    let ztop = -1e9;
    for (let i = 0; i < pos.count; i++) ztop = Math.max(ztop, pos.getY(i));
    const sw = new Float32Array(pos.count);
    for (let i = 0; i < pos.count; i++) sw[i] = Math.pow(Math.min(1, Math.max(0, (ztop - pos.getY(i)) / 3.5)), 1.3);
    ob.geometry.setAttribute("sway", new THREE.BufferAttribute(sw, 1));
    const near = ob.name.startsWith("willow_fg");
    const o = { ...ob.material.userData.o, sway: near ? [0.16, 0.08, 0, 0] : [0.25, 0.12, 0, 0] };
    const m2 = ob.material.clone(); patch(m2, o); ob.material = m2;
  }
  if (ob.material.transparent) ob.castShadow = false;
}
for (const ob of meshes) if (!ob.geometry.attributes.sway) {
  ob.geometry.setAttribute("sway", new THREE.BufferAttribute(new Float32Array(ob.geometry.attributes.position.count), 1));
}
log("meshes", meshes.length, "materials", matCache.size);

// ------------------------------------------------------------------ 动画对象（世界矩阵逐帧）
const animIdx = new Map(info.anim.map((n, i) => [n, i]));
const animObjs = [];
for (const [name, i] of animIdx) {
  const ob = byName(name);
  if (!ob) continue;
  animObjs.push([ob, i]);
}
world.updateMatrixWorld(true);
for (const [ob] of animObjs) { scene.attach(ob); ob.matrixAutoUpdate = false; }
const tmpM = new THREE.Matrix4();
function animMatrix(i, t, out) {
  const f = Math.min(Math.max(t - F0, 0), NF - 1);
  const a = Math.floor(f), b = Math.min(a + 1, NF - 1), w = f - a;
  const pa = (i * NF + a) * 12, pb = (i * NF + b) * 12;
  const e = new Array(12);
  for (let k = 0; k < 12; k++) e[k] = ANIM[pa + k] * (1 - w) + ANIM[pb + k] * w;
  out.set(e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], e[9], e[10], e[11], 0, 0, 0, 1);
  return out;
}
const visObjs = Object.entries(info.vis).map(([n, spans]) => [byName(n), spans, n]).filter(([o]) => o);

// ------------------------------------------------------------------ 天空
const skyMat = new THREE.ShaderMaterial({
  uniforms: { ...FOG_UNI, ...shared(["uSunDisc", "uSkyGain", "uZenith", "uHorizon", "uGlow"]) },
  vertexShader: /* glsl */ `
    #include <common>
    #include <logdepthbuf_pars_vertex>
    varying vec3 vWP;
    void main(){ vec4 wp = modelMatrix * vec4(position, 1.0); vWP = wp.xyz; gl_Position = projectionMatrix * viewMatrix * wp;
      #include <logdepthbuf_vertex>
    }`,
  fragmentShader: /* glsl */ `
    #include <common>
    #include <logdepthbuf_pars_fragment>
    ${NOISE}
    ${FOG}
    ${SKY}
    varying vec3 vWP;
    void main(){
      #include <logdepthbuf_fragment>
      vec3 d = normalize(vWP - cameraPosition);
      vec3 c = skyRad(d);
      gl_FragColor = vec4(applyFog(c, cameraPosition + d * 5500.0), 1.0);
    }`,
  side: THREE.BackSide, depthWrite: false,
});
const sky = new THREE.Mesh(new THREE.SphereGeometry(5000, 64, 32), skyMat);
sky.frustumCulled = false; sky.renderOrder = -10;
scene.add(sky);

// 环境光（IBL）：同一天空，不含日轮
function buildEnv() {
  const envScene = new THREE.Scene();
  const s2 = new THREE.Mesh(new THREE.SphereGeometry(50, 64, 32), skyMat);
  envScene.add(s2);
  const pm = new THREE.PMREMGenerator(renderer);
  U.uSunDisc.value = 0;
  const rt = pm.fromScene(envScene, 0.0, 0.1, 200);
  U.uSunDisc.value = 1;
  scene.environment = rt.texture;
  pm.dispose();
}

// ------------------------------------------------------------------ 水面
const EMIT_MAX = 96;
const waterUniforms = {
  color: { value: new THREE.Color(1, 1, 1) }, tDiffuse: { value: null }, textureMatrix: { value: new THREE.Matrix4() },
  uDeep: { value: new THREE.Vector3(0.010, 0.016, 0.014) },
  uEm: { value: Array.from({ length: EMIT_MAX }, () => new THREE.Vector4()) }, uEmN: { value: 0 },
  uDistort: { value: 0.35 }, uSunSpec: { value: 1.0 },
};
const waterShader = {
  name: "LakeShader",
  uniforms: waterUniforms,
  vertexShader: /* glsl */ `
    #include <common>
    #include <logdepthbuf_pars_vertex>
    uniform mat4 textureMatrix; varying vec4 vUvR; varying vec3 vWP;
    void main(){ vUvR = textureMatrix * vec4(position, 1.0); vec4 wp = modelMatrix * vec4(position, 1.0); vWP = wp.xyz;
      gl_Position = projectionMatrix * viewMatrix * wp;
      #include <logdepthbuf_vertex>
    }`,
  fragmentShader: /* glsl */ `
    #include <common>
    #include <logdepthbuf_pars_fragment>
    ${NOISE}
    ${FOG}
    uniform sampler2D tDiffuse; uniform vec3 color; uniform vec3 uDeep;
    uniform vec4 uEm[${EMIT_MAX}]; uniform int uEmN; uniform float uDistort, uSunSpec;
    varying vec4 vUvR; varying vec3 vWP;
    float baseH(vec2 xz){
      vec2 b = vec2(xz.x, -xz.y * 2.6);                      // Blender 映射: Y 方向拉伸 2.6
      float sw = bnoise(vec3(b * 0.35, uTime * 0.24), 4, 0.5);
      float rp = bnoise(vec3(b * 3.0, uTime * 0.96) + vec3(5.2, 1.3, 0.0), 3, 0.5);
      return rp * 0.18 + sw;
    }
    float ringH(vec2 xz){
      float h = 0.0;
      for (int i = 0; i < ${EMIT_MAX}; i++){
        if (i >= uEmN) break;
        vec4 e = uEm[i];
        float age = e.z; float front = 0.34 * age; float r = length(xz - e.xy);
        float x = r - front;
        if (x > 0.15 || x < -0.9 - 0.2 * age) continue;
        float w = 0.10 + 0.10 * age;
        h += e.w * exp(-1.1 * age) * sin(x * 62.0) * exp(-x * x / (w * w)) / sqrt(r + 0.08);
      }
      return h;
    }
    void main(){
      #include <logdepthbuf_fragment>
      vec3 V = cameraPosition - vWP; float dist = length(V); V /= dist;
      float e = 0.01 + dist * 0.0015;
      vec2 g = vec2(baseH(vWP.xz + vec2(e, 0.0)) - baseH(vWP.xz - vec2(e, 0.0)),
                    baseH(vWP.xz + vec2(0.0, e)) - baseH(vWP.xz - vec2(0.0, e))) / (2.0 * e);
      g *= mix(0.6, 0.025, clamp((dist - 5.0) / 255.0, 0.0, 1.0)) * 0.05;
      if (uEmN > 0) { float er = 0.006;
        g += vec2(ringH(vWP.xz + vec2(er, 0.0)) - ringH(vWP.xz - vec2(er, 0.0)), ringH(vWP.xz + vec2(0.0, er)) - ringH(vWP.xz - vec2(0.0, er))) / (2.0 * er); }
      vec3 N = normalize(vec3(-g.x, 1.0, -g.y));
      float NV = max(dot(N, V), 1e-3);
      float F = 0.02 + 0.98 * pow(1.0 - NV, 5.0);
      vec2 uv = vUvR.xy / vUvR.w + N.xz * uDistort * (1.0 / (1.0 + dist * 0.01));
      vec3 refl = texture2D(tDiffuse, uv).rgb;
      // 太阳在波面上的闪光（GGX，日轮张角当作粗糙度下限）
      vec3 L = uSunDir; vec3 H = normalize(L + V);
      float NH = max(dot(N, H), 0.0), NL = max(dot(N, L), 0.0);
      float a2 = 0.026 * 0.026; float dd = NH * NH * (a2 - 1.0) + 1.0; float Dg = a2 / (3.14159 * dd * dd);
      float k = 0.006; float G = (NV / (NV * (1.0 - k) + k)) * (NL / (NL * (1.0 - k) + k));
      float Fs = 0.02 + 0.98 * pow(1.0 - max(dot(V, H), 0.0), 5.0);
      vec3 spec = uSunE * sunT(0.5) * Dg * G * Fs / (4.0 * NV) * uSunSpec;
      vec3 c = refl * F + (1.0 - F) * uDeep * (uAmb * 3.0 + uSunE * sunT(0.5) * NL) + spec;
      gl_FragColor = vec4(applyFog(c, vWP), 1.0);
    }`,
};
let lake = null;
function buildLake(W, H) {
  if (lake) { lake.getRenderTarget().dispose(); scene.remove(lake); }
  lake = new Reflector(new THREE.PlaneGeometry(8000, 4500), { textureWidth: W, textureHeight: H, clipBias: 0.0005, multisample: 0, shader: waterShader });
  lake.rotation.x = -Math.PI / 2;
  lake.position.set(0, 0, -1750);
  lake.material.uniforms = Object.assign(lake.material.uniforms, FOG_UNI);
  for (const k of ["uEm", "uEmN", "uDistort", "uSunSpec", "uDeep"]) lake.material.uniforms[k] = waterUniforms[k];
  const orig = lake.onBeforeRender;
  lake.onBeforeRender = function (r, s, c) { U.uSunDisc.value = 0; orig.call(this, r, s, c); U.uSunDisc.value = 1; };
  scene.add(lake);
}

// ------------------------------------------------------------------ 灯光
const sun = new THREE.DirectionalLight(new THREE.Color(...SUN_COL), 1);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
sun.shadow.bias = -0.0002;
scene.add(sun, sun.target);
const fills = [];
for (const L of info.lights) {
  if (L.type !== "AREA") continue;
  const A = L.size * L.size;
  const rl = new THREE.RectAreaLight(new THREE.Color(...L.color), 1.5 * L.energy / (Math.PI * A), L.size, L.size);
  rl.position.set(...L.pos);
  rl.lookAt(rl.position.clone().add(new THREE.Vector3(...L.dir)));
  rl.userData.name = L.name; rl.userData.base = rl.intensity;
  scene.add(rl);
  fills.push(rl);
}
const PARAMS = { sunScale: 1.0, envIntensity: 0.55, lookSat: 1.18, lookContrast: 1.08, exposure: Math.pow(2, info.exposure) };
function updateSunIntensity() {
  sun.intensity = SUN_E * PARAMS.sunScale * Math.exp(-(0.00038 * 160 * Math.exp(-1 / 160) + 0.0024 * 3.5 * Math.exp(-1 / 3.5) * 0.8) / sunDir.y);
}

// ------------------------------------------------------------------ 相机
const camera = new THREE.PerspectiveCamera(40, 16 / 9, 0.1, 6000);
camera.matrixAutoUpdate = false;
scene.add(camera);

// ------------------------------------------------------------------ 累积/输出
const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2));
const quadScene = new THREE.Scene(); quadScene.add(quad);
const quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
const accMat = new THREE.ShaderMaterial({
  uniforms: { tPrev: { value: null }, tNew: { value: null }, w: { value: 1 } },
  vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }",
  fragmentShader: `uniform sampler2D tPrev, tNew; uniform float w; varying vec2 vUv;
    void main(){ vec4 n = texture2D(tNew, vUv); n.rgb = min(n.rgb, vec3(4000.0)); if (any(isnan(n.rgb))) n.rgb = vec3(0.0);
      gl_FragColor = w >= 1.0 ? n : mix(texture2D(tPrev, vUv), n, w); }`,
  depthTest: false, depthWrite: false,
});
const outMat = new THREE.ShaderMaterial({
  uniforms: { tAcc: { value: null }, exposure: { value: 1 }, toneMappingExposure: { value: 1 }, lookSat: { value: 1.18 }, lookContrast: { value: 1.08 }, warm: { value: new THREE.Vector3(1, 1, 1) } },
  vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }",
  fragmentShader: `
    #include <common>
    #include <tonemapping_pars_fragment>
    uniform sampler2D tAcc; uniform float exposure; varying vec2 vUv;
    uniform float lookSat, lookContrast; uniform vec3 warm;
    void main(){ vec3 c = texture2D(tAcc, vUv).rgb * exposure * warm;
      float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); c = max(vec3(0.0), mix(vec3(l), c, lookSat));
      c = AgXToneMapping(c);
      vec3 d = sRGBTransferOETF(vec4(clamp(c, 0.0, 1.0), 1.0)).rgb;
      d = clamp(0.5 + (d - 0.5) * lookContrast, 0.0, 1.0);
      gl_FragColor = vec4(d, 1.0); }`,
  depthTest: false, depthWrite: false,
});
let RT = null;
function allocTargets(W, H) {
  if (RT && RT.W === W && RT.H === H) return;
  if (RT) for (const k of ["scene", "a", "b", "out"]) RT[k].dispose();
  const opt = { type: THREE.FloatType, depthBuffer: false, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter };
  RT = {
    W, H,
    scene: new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, depthBuffer: true, samples: 0 }),
    a: new THREE.WebGLRenderTarget(W, H, opt), b: new THREE.WebGLRenderTarget(W, H, opt),
    out: new THREE.WebGLRenderTarget(W, H, opt),
  };
  buildLake(W, H);
}

// ------------------------------------------------------------------ 帧状态
const halton = (i, b) => { let f = 1, r = 0; while (i > 0) { f /= b; r += f * (i % b); i = Math.floor(i / b); } return r; };
function concentric(u, v) {
  const a = 2 * u - 1, b = 2 * v - 1;
  if (a === 0 && b === 0) return [0, 0];
  let r, phi;
  if (Math.abs(a) > Math.abs(b)) { r = a; phi = (Math.PI / 4) * (b / a); } else { r = b; phi = Math.PI / 2 - (Math.PI / 4) * (a / b); }
  return [r * Math.cos(phi), r * Math.sin(phi)];
}
const bl2gl = (x, y, z = 0) => new THREE.Vector3(x, z, -y);
const EGRET_T = [8.45, 19.5];
function updateEmitters(t, shot) {
  const em = waterUniforms.uEm.value; let n = 0;
  const push = (x, y, age, amp) => { if (n < EMIT_MAX && age >= 0) em[n++].set(x, -y, age, amp); };
  if (shot === "S6") {
    for (const nm of ["duck_m", "duck_f"]) {
      const i = animIdx.get(nm); if (i === undefined) continue;
      for (let k = 0; k < 40; k++) {
        const te = Math.floor(t / 2) * 2 - k * 2;               // 每 2 帧发一圈
        const m = animMatrix(i, te, tmpM); const p = new THREE.Vector3().setFromMatrixPosition(m);
        push(p.x, -p.z, (t - te) / 24, 0.0016);
      }
    }
  }
  if (shot === "S4") {
    for (const [fr, amp] of [[411, 0.006], [450, 0.005]]) push(7.75, 19.6, (t - fr) / 24, amp);
    for (let k = 0; k < 6; k++) { const te = Math.floor(t / 37) * 37 - k * 37; push(EGRET_T[0] + 0.05, EGRET_T[1], (t - te) / 24, 0.0007); }
  }
  waterUniforms.uEmN.value = n;
}

let curShot = null; let curSat = 1.18;
function setShot(shot) {
  if (curShot === shot) return;
  curShot = shot;
  const c = SHOT[shot];
  camera.near = c.near; camera.far = 6000;
  scene.environmentIntensity = PARAMS.envIntensity * (c.env ? c.env / PARAMS.envIntensity : 1);
  for (const rl of fills) rl.intensity = rl.userData.base * (c.fill || 1);
  outMat.uniforms.warm.value.set(...(c.warm || [1, 1, 1])); curSat = c.sat || PARAMS.lookSat;
}
const camInfo = (shot) => info.cameras["cam_" + shot];
function setFrame(shot, t, jit) {
  U.uTime.value = t / 24;
  for (const [ob, i] of animObjs) { animMatrix(i, t, ob.matrix); ob.matrixWorldNeedsUpdate = true; }
  const fr = Math.round(t);
  for (const [ob, spans] of visObjs) ob.visible = spans.some(([a, b]) => fr >= a && fr <= b);
  for (const rl of fills) { const s = info.vis[rl.userData.name]; rl.visible = s ? s.some(([a, b]) => fr >= a && fr <= b) : true; }
  // 相机
  const ci = camInfo(shot);
  const idx = animIdx.get("cam_" + shot);
  const M = idx !== undefined ? animMatrix(idx, t, new THREE.Matrix4()) : new THREE.Matrix4().set(...ci.static, 0, 0, 0, 1);
  const f = Math.min(Math.max(t - F0, 0), NF - 1), a = Math.floor(f), b = Math.min(a + 1, NF - 1), w = f - a;
  const [lens, focus, fstop] = [0, 1, 2].map((k) => ci.track[a][k] * (1 - w) + ci.track[b][k] * w);
  const aspect = RT.W / RT.H;
  const hfov = 2 * Math.atan(ci.sensor / 2 / lens);
  camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(hfov / 2) / aspect));
  camera.aspect = aspect;
  camera.updateProjectionMatrix();
  // 薄透镜：在光圈上偏移相机，同时斜切投影，使焦平面不动
  const R = (lens / 1000) / (2 * fstop) * jit.apertureScale;
  const dx = jit.lens[0] * R, dy = jit.lens[1] * R;
  const P = camera.projectionMatrix.elements;
  P[8] = -P[0] * dx / focus - (2 * jit.px[0]) / RT.W;
  P[9] = -P[5] * dy / focus - (2 * jit.px[1]) / RT.H;
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  camera.matrix.copy(M).multiply(new THREE.Matrix4().makeTranslation(dx, dy, 0));
  camera.matrixWorldNeedsUpdate = true;
  scene.updateMatrixWorld();
  sky.position.setFromMatrixPosition(camera.matrixWorld); sky.updateMatrixWorld();
  // 阳光：日轮张角内抖动 → 软阴影；阴影盒跟随镜头
  const cfg = SHOT[shot];
  const fwd = new THREE.Vector3(0, 0, -1).transformDirection(camera.matrixWorld);
  const center = new THREE.Vector3().setFromMatrixPosition(camera.matrixWorld).addScaledVector(fwd, cfg.shadowAt);
  const ang = 0.0052;
  const sd = sunDir.clone().add(new THREE.Vector3(jit.sun[0] * ang, jit.sun[1] * ang * 0.5, jit.sun[0] * ang * 0.3)).normalize();
  sun.target.position.copy(center);
  sun.position.copy(center).addScaledVector(sd, cfg.shadowHalf * 4);
  const sc = sun.shadow.camera;
  sc.left = -cfg.shadowHalf; sc.right = cfg.shadowHalf; sc.top = cfg.shadowHalf; sc.bottom = -cfg.shadowHalf;
  sc.near = 0.01; sc.far = cfg.shadowHalf * 8; sc.updateProjectionMatrix();
  sun.shadow.normalBias = cfg.shadowHalf * 0.00015;
  sun.target.updateMatrixWorld(); sun.updateMatrixWorld();
  U.uFogJit.value = jit.fog;
  updateEmitters(t, shot);
}

// ------------------------------------------------------------------ 单帧：累积 spp 次
async function renderFrame(shot, frame, spp, shutter, apertureScale = 1) {
  setShot(shot);
  renderer.autoClear = true;
  let src = RT.a, dst = RT.b;
  for (let i = 0; i < spp; i++) {
    const k = i + 1;
    const jit = {
      px: [halton(k, 2) - 0.5, halton(k, 3) - 0.5],
      lens: concentric(halton(k, 5), halton(k, 7)),
      sun: concentric(halton(k, 11), halton(k, 13)),
      fog: halton(k, 17), apertureScale,
    };
    const t = frame + (shutter ? (halton(k, 19) - 0.5) * shutter : 0);
    setFrame(shot, t, jit);
    renderer.setRenderTarget(RT.scene);
    renderer.render(scene, camera);
    accMat.uniforms.tPrev.value = src.texture; accMat.uniforms.tNew.value = RT.scene.texture; accMat.uniforms.w.value = 1 / k;
    quad.material = accMat;
    renderer.setRenderTarget(dst);
    renderer.render(quadScene, quadCam);
    [src, dst] = [dst, src];
    if (i % 8 === 7) await new Promise((r) => setTimeout(r, 0));
  }
  outMat.uniforms.tAcc.value = src.texture; outMat.uniforms.exposure.value = PARAMS.exposure;
  outMat.uniforms.lookSat.value = curSat; outMat.uniforms.lookContrast.value = PARAMS.lookContrast;
  quad.material = outMat;
  renderer.setRenderTarget(RT.out);
  renderer.render(quadScene, quadCam);
  const W = RT.W, H = RT.H;
  const px = new Float32Array(W * H * 4);
  await renderer.readRenderTargetPixelsAsync(RT.out, 0, 0, W, H, px);
  renderer.setRenderTarget(null);
  // 预览画布
  quad.material = outMat; renderer.render(quadScene, quadCam);
  const u16 = new Uint16Array(8 / 2 + W * H * 3);
  new Uint32Array(u16.buffer, 0, 2).set([W, H]);
  for (let y = 0; y < H; y++) {
    const sy = H - 1 - y;
    for (let x = 0; x < W; x++) {
      const s = (sy * W + x) * 4, d = 4 + (y * W + x) * 3;
      u16[d] = px[s] * 65535 + 0.5; u16[d + 1] = px[s + 1] * 65535 + 0.5; u16[d + 2] = px[s + 2] * 65535 + 0.5;
    }
  }
  return u16;
}

window.renderJob = async (job) => {
  if (job.params) { for (const [k, v] of Object.entries(job.params)) window.setParam(k, v); buildEnv(); }
  curShot = null;
  allocTargets(job.w, job.h);
  const t0 = performance.now();
  for (const fr of job.frames) {
    const t1 = performance.now();
    const data = await renderFrame(job.shot, fr, job.spp, job.shutter ?? 0.5, job.aperture ?? 1);
    const name = `${job.out}/f_${String(fr).padStart(4, "0")}.u16`;
    await fetch(`/save?path=${encodeURIComponent(name)}`, { method: "POST", body: data });
    log(`${job.shot} f${fr} spp${job.spp} ${((performance.now() - t1) / 1000).toFixed(2)}s`);
  }
  log(`job ${job.shot} done ${((performance.now() - t0) / 1000).toFixed(1)}s`);
};
window.PARAMS = PARAMS; window.U = U; window.THREE = THREE;
window.setParam = (k, v) => { if (k in PARAMS) PARAMS[k] = v; else if (U[k]) { if (Array.isArray(v)) U[k].value.set(...v); else U[k].value = v; }
  updateSunIntensity(); scene.environmentIntensity = PARAMS.envIntensity; };

try {
  updateSunIntensity();
  buildEnv();
  scene.environmentIntensity = PARAMS.envIntensity;
  allocTargets(1920, 1080);
  // 预编译
  setShot("S2"); setFrame("S2", 109, { px: [0, 0], lens: [0, 0], sun: [0, 0], fog: 0.5, apertureScale: 1 });
  renderer.setRenderTarget(RT.scene); renderer.compile(scene, camera); renderer.render(scene, camera); renderer.setRenderTarget(null);
  window.READY = true;
  log("READY");
} catch (e) {
  console.error(e); window.FAILED = String(e);
}
