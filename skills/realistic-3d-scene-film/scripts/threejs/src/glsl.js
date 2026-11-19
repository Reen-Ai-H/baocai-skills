// 共享 GLSL：噪声、雾（高度雾 + 贴水晨雾，沿视线积分）、天空
export const NOISE = /* glsl */ `
uvec3 pcg3d(uvec3 v){
  v = v * 1664525u + 1013904223u;
  v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
  v ^= v >> 16u;
  v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
  return v;
}
vec3 hash33(vec3 p){ uvec3 u = pcg3d(uvec3(ivec3(floor(p)) + 65536)); return vec3(u) * (2.0 / 4294967295.0) - 1.0; }
vec2 hash22(vec2 p){ uvec3 u = pcg3d(uvec3(ivec2(floor(p)) + 65536, 7)); return vec2(u.xy) * (1.0 / 4294967295.0); }
float gnoise(vec3 p){
  vec3 i = floor(p), f = fract(p);
  vec3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  #define GN(o) dot(hash33(i + o), f - o)
  return mix(mix(mix(GN(vec3(0,0,0)), GN(vec3(1,0,0)), u.x), mix(GN(vec3(0,1,0)), GN(vec3(1,1,0)), u.x), u.y),
             mix(mix(GN(vec3(0,0,1)), GN(vec3(1,0,1)), u.x), mix(GN(vec3(0,1,1)), GN(vec3(1,1,1)), u.x), u.y), u.z);
  #undef GN
}
float fbm(vec3 p, int oct, float g){
  float s = 0.0, a = 1.0, n = 0.0;
  for (int i = 0; i < 8; i++){ if (i >= oct) break; s += a * gnoise(p); n += a; p = p * 2.03 + vec3(1.7, 9.2, 3.1); a *= g; }
  return s / n;
}
// ~ Blender Noise Texture "Fac"
float bnoise(vec3 p, int oct, float g){ return clamp(0.5 + 0.85 * fbm(p, oct, g), 0.0, 1.0); }
`;

export const FOG = /* glsl */ `
uniform float uTime;
uniform vec3 uSunDir;
uniform vec3 uSunE;
uniform vec3 uAmb;
uniform vec3 uFogAlb;
uniform float uHazeA, uHazeH, uMistA, uMistH, uMistScale, uFogJit, uFogOn, uFogPhaseG;
float hg(float mu, float g){ float g2 = g * g; return (1.0 - g2) / (12.566371 * pow(max(1.0 + g2 - 2.0 * g * mu, 1e-4), 1.5)); }
float sunT(float y){
  y = max(y, 0.0);
  return exp(-(uHazeA * uHazeH * exp(-y / uHazeH) + uMistA * uMistH * exp(-y / uMistH) * 0.8) / max(uSunDir.y, 0.02));
}
float mistShape(vec3 p){
  float sh = bnoise(vec3(p.x, -p.z, p.y) * uMistScale + vec3(0.0, 0.0, uTime * 0.096), 3, 0.55);
  return mix(0.15, 1.6, clamp((sh - 0.42) / 0.26, 0.0, 1.0));
}
vec3 applyFog(vec3 col, vec3 wp){
  if (uFogOn < 0.5) return col;
  vec3 ro = cameraPosition;
  vec3 d = wp - ro; float L = length(d); vec3 rd = d / max(L, 1e-4);
  vec3 Ls = uSunE * hg(dot(rd, uSunDir), uFogPhaseG);
  float T = 1.0; vec3 S = vec3(0.0);
  const int N = 20;
  for (int i = 0; i < N; i++){
    float ta = L * pow(float(i) / float(N), 2.0), tb = L * pow(float(i + 1) / float(N), 2.0);
    vec3 p = ro + rd * mix(ta, tb, uFogJit);
    float y = abs(p.y);                       // 倒影光路按镜像高度计算
    float sig = uHazeA * exp(-y / uHazeH);
    if (y < 30.0) sig += uMistA * exp(-y / uMistH) * mistShape(p);
    float tr = exp(-sig * (tb - ta));
    S += T * (1.0 - tr) * (Ls * sunT(y) + uAmb) * uFogAlb;
    T *= tr;
  }
  return col * T + S;
}
`;

export const SKY = /* glsl */ `
uniform float uSunDisc;
uniform float uSkyGain;
uniform vec3 uZenith, uHorizon, uGlow;
vec3 skyRad(vec3 d){
  float e = d.y;
  float mu = dot(d, uSunDir);
  float ang = acos(clamp(mu, -1.0, 1.0));
  float t = pow(1.0 - clamp(e, 0.0, 1.0), 5.0);
  vec3 c = mix(uZenith, uHorizon, t);
  // 朝阳一侧的暖光：低空更强
  float az = clamp(dot(normalize(vec2(d.x, d.z) + 1e-5), normalize(uSunDir.xz)) * 0.5 + 0.5, 0.0, 1.0);
  c += uGlow * (0.7 * pow(az, 3.0) * t + 1.8 * exp(-ang * 2.4) * (0.35 + 0.65 * t) + 7.0 * exp(-ang * 9.0) + 30.0 * exp(-ang * 40.0));
  if (e < 0.0) c *= mix(1.0, 0.35, clamp(-e * 8.0, 0.0, 1.0));
  // 日轮（半径 0.65°）
  float disc = smoothstep(cos(0.0118), cos(0.0108), mu);
  c += uSunDisc * disc * uGlow * 900.0;
  return c * uSkyGain;
}
`;
