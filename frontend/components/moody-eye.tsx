"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import type * as THREE_NS from "three";

type Props = {
  /** Called when WebGL is unavailable so the parent can show a static fallback. */
  onUnsupported?: () => void;
};

const PALETTE = {
  lime: "#d6fc81",
  moss: "#7f9655",
  deep: "#1a2411",
  sclera: "#0c0f09",
  pupil: "#040503",
};

function rgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

const NOISE = /* glsl */ `
  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x),
               mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
  }
  float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 5; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; }
    return v;
  }
`;

// The almond-shaped opening the eyeball sits behind. Shared by the eyeball
// (to clip it) and the halo (to draw the lids around it).
const LID = /* glsl */ `
  uniform float uLid;
  uniform vec2 uLidSize;
  float lidEdge(vec2 p) {
    float x = p.x / uLidSize.x;
    float h = uLidSize.y * uLid * max(1.0 - x * x, 0.0);
    return h - abs(p.y);
  }
`;

const EYE_VERTEX = /* glsl */ `
  // The eyeball's own transform, so the lid opening stays fixed while it rolls.
  uniform mat4 uEyeMatrix;
  varying vec3 vObj;
  varying vec3 vSocket;
  varying vec3 vNormalV;
  varying vec3 vViewPos;
  void main() {
    vObj = position;
    vSocket = (uEyeMatrix * vec4(position, 1.0)).xyz;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vViewPos = mv.xyz;
    vNormalV = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * mv;
  }
`;

const EYE_FRAGMENT = /* glsl */ `
  uniform float uTime;
  uniform float uDilate;
  uniform float uGlow;
  uniform vec3 uLime, uMoss, uDeep, uSclera, uPupil;
  varying vec3 vObj;
  varying vec3 vSocket;
  varying vec3 vNormalV;
  varying vec3 vViewPos;
  ${NOISE}
  ${LID}
  void main() {
    float edge = lidEdge(vSocket.xy);
    if (edge < 0.0) discard;

    vec3 p = normalize(vObj);
    float theta = acos(clamp(p.z, -1.0, 1.0));
    float phi = atan(p.y, p.x);

    float irisR = 0.6;
    float pupilR = mix(0.17, 0.33, uDilate);
    float r = theta / irisR;

    // Iris: radial fibres, a bright collarette and a dark limbal ring.
    float fib = fbm(vec2(phi * 5.0, r * 2.5 - uTime * 0.04));
    float strands = noise(vec2(phi * 46.0, r * 3.0 + fib));
    vec3 iris = mix(uDeep, uMoss, smoothstep(1.0, 0.3, r));
    iris = mix(iris, uLime, smoothstep(0.85, 0.3, r) * (0.25 + 0.6 * fib));
    iris *= 0.45 + 0.85 * strands * fib + 0.2 * fib;
    float collar = smoothstep(0.1, 0.0, abs(r - pupilR / irisR * 1.55));
    iris += uLime * collar * 0.35 * (0.4 + fib);
    iris *= mix(1.0, 0.12, smoothstep(0.72, 1.0, r));

    float pr = theta / pupilR;
    vec3 pupil = uPupil + uLime * 0.05 * smoothstep(0.3, 1.0, pr);
    iris = mix(iris, pupil, smoothstep(1.03, 0.93, pr));

    // Sclera: near-black with faint moss veins.
    float vein = fbm(vec2(phi * 3.0, theta * 5.0) + 7.0);
    vec3 sclera = uSclera + uMoss * 0.06 * smoothstep(0.03, 0.0, abs(vein - 0.5));
    sclera *= 1.0 - 0.5 * smoothstep(0.8, 1.6, theta);

    vec3 col = mix(sclera, iris, smoothstep(irisR + 0.025, irisR - 0.025, theta));

    vec3 N = normalize(vNormalV);
    vec3 V = normalize(-vViewPos);
    float fres = pow(1.0 - max(dot(N, V), 0.0), 2.5);
    col += uLime * fres * 0.18 * uGlow;

    // Wet highlights.
    vec3 L = normalize(vec3(-0.45, 0.55, 1.0));
    vec3 H = normalize(L + V);
    float ndh = max(dot(N, H), 0.0);
    col += vec3(0.94, 1.0, 0.84) * (pow(ndh, 220.0) * 1.8 + pow(ndh, 20.0) * 0.05);
    vec3 L2 = normalize(vec3(0.6, -0.4, 1.0));
    col += uLime * pow(max(dot(N, normalize(L2 + V)), 0.0), 400.0) * 0.5;

    // Lid shadow and the glowing rim of the opening.
    col *= 0.2 + 0.8 * smoothstep(0.0, 0.2, edge);
    col += uLime * smoothstep(0.03, 0.0, edge) * 0.8 * uGlow;
    float lx = vSocket.x / uLidSize.x;
    col *= 1.0 - 0.45 * lx * lx;

    gl_FragColor = vec4(col, 1.0);
  }
`;

const HALO_VERTEX = /* glsl */ `
  varying vec2 vPos;
  void main() {
    vPos = position.xy;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const HALO_FRAGMENT = /* glsl */ `
  uniform float uTime;
  uniform float uGlow;
  uniform vec3 uLime, uMoss;
  varying vec2 vPos;
  ${NOISE}
  ${LID}
  void main() {
    float d = -lidEdge(vPos);
    float outline = smoothstep(0.018, 0.0, abs(d - 0.015));
    float crease = smoothstep(0.012, 0.0, abs(lidEdge(vPos * vec2(0.92, 0.78)) + 0.0)) *
      step(0.0, vPos.y) * smoothstep(0.9, 0.2, abs(vPos.x));
    float haze = exp(-max(d, 0.0) * 4.5) * 0.35;
    float shimmer = 0.75 + 0.25 * fbm(vPos * 3.0 + uTime * 0.15);
    float a = (outline * 0.9 + crease * 0.18 + haze * shimmer) * uGlow * step(0.0, d);
    vec3 col = mix(uMoss, uLime, outline);
    gl_FragColor = vec4(col * a, a);
  }
`;

const DUST_VERTEX = /* glsl */ `
  uniform float uTime;
  uniform float uPixelRatio;
  attribute float aSeed;
  varying float vAlpha;
  varying float vTint;
  void main() {
    vec3 p = position;
    p.y += sin(uTime * 0.3 + aSeed * 6.28) * 0.06;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = (2.0 + aSeed * 3.5) * uPixelRatio * (3.0 / -mv.z);
    vAlpha = (0.25 + 0.75 * pow(0.5 + 0.5 * sin(uTime * (0.6 + aSeed) + aSeed * 40.0), 3.0)) * 0.7;
    vTint = aSeed;
  }
`;

const DUST_FRAGMENT = /* glsl */ `
  uniform vec3 uLime, uMoss;
  varying float vAlpha;
  varying float vTint;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    float a = smoothstep(0.5, 0.0, d) * vAlpha;
    gl_FragColor = vec4(mix(uMoss, uLime, vTint) * a, a);
  }
`;

/** The Developer’s Eye: a WebGL eyeball that watches the cursor and blinks. */
export default function MoodyEye({ onUnsupported }: Props) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let disposed = false;
    let cleanup = () => {};

    import("three").then((THREE) => {
      if (disposed) return;
      cleanup = mount(THREE, el, onUnsupported);
    });

    return () => {
      disposed = true;
      cleanup();
    };
  }, [onUnsupported]);

  return <div ref={host} className="eye-canvas" />;
}

function mount(
  THREE: typeof THREE_NS,
  el: HTMLDivElement,
  onUnsupported?: () => void,
) {
  let renderer: THREE_NS.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "low-power",
    });
  } catch {
    onUnsupported?.();
    return () => {};
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  el.appendChild(renderer.domElement);

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 50);

  const colors = {
    uLime: { value: new THREE.Vector3(...rgb(PALETTE.lime)) },
    uMoss: { value: new THREE.Vector3(...rgb(PALETTE.moss)) },
    uDeep: { value: new THREE.Vector3(...rgb(PALETTE.deep)) },
    uSclera: { value: new THREE.Vector3(...rgb(PALETTE.sclera)) },
    uPupil: { value: new THREE.Vector3(...rgb(PALETTE.pupil)) },
  };
  const shared = {
    uTime: { value: 0 },
    uGlow: { value: 0 },
    uLid: { value: reduced ? 1 : 0 },
    uLidSize: { value: new THREE.Vector2(1.0, 0.6) },
    uDilate: { value: reduced ? 0.4 : 1 },
    uPixelRatio: { value: renderer.getPixelRatio() },
  };
  const uniforms = { ...colors, ...shared };

  const world = new THREE.Group();
  scene.add(world);

  const eyeball = new THREE.Mesh(
    new THREE.SphereGeometry(1, 96, 96),
    new THREE.ShaderMaterial({
      uniforms: { ...uniforms, uEyeMatrix: { value: new THREE.Matrix4() } },
      vertexShader: EYE_VERTEX,
      fragmentShader: EYE_FRAGMENT,
    }),
  );
  (eyeball.material as THREE_NS.ShaderMaterial).uniforms.uEyeMatrix.value =
    eyeball.matrix;
  world.add(eyeball);

  const halo = new THREE.Mesh(
    new THREE.PlaneGeometry(4, 3),
    new THREE.ShaderMaterial({
      uniforms,
      vertexShader: HALO_VERTEX,
      fragmentShader: HALO_FRAGMENT,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  halo.position.z = 0.5;
  world.add(halo);

  // Orbit rings echo the original line-art illustration.
  const rings = new THREE.Group();
  rings.rotation.x = 1.08;
  const ringMaterials: THREE_NS.LineDashedMaterial[] = [];
  [1.45, 1.7, 1.98].forEach((radius, i) => {
    const curve = new THREE.EllipseCurve(0, 0, radius, radius, 0, Math.PI * 2);
    const geometry = new THREE.BufferGeometry().setFromPoints(
      curve.getPoints(220),
    );
    const material = new THREE.LineDashedMaterial({
      color: i === 1 ? PALETTE.lime : PALETTE.moss,
      dashSize: i === 2 ? 0.03 : 10,
      gapSize: i === 2 ? 0.09 : 0,
      transparent: true,
      opacity: 0,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    ringMaterials.push(material);
    const line = new THREE.Line(geometry, material);
    line.computeLineDistances();
    line.rotation.y = (i - 1) * 0.12;
    rings.add(line);
  });
  const beacon = new THREE.Mesh(
    new THREE.SphereGeometry(0.035, 16, 16),
    new THREE.MeshBasicMaterial({ color: PALETTE.lime }),
  );
  beacon.position.set(1.7, 0, 0);
  rings.children[1].add(beacon);
  world.add(rings);

  const COUNT = 520;
  const positions = new Float32Array(COUNT * 3);
  const seeds = new Float32Array(COUNT);
  for (let i = 0; i < COUNT; i++) {
    const r = 1.3 + Math.random() * 2.2;
    const a = Math.random() * Math.PI * 2;
    const b = Math.acos(Math.random() * 2 - 1);
    positions[i * 3] = r * Math.sin(b) * Math.cos(a) * 1.3;
    positions[i * 3 + 1] = r * Math.cos(b) * 0.55;
    positions[i * 3 + 2] = r * Math.sin(b) * Math.sin(a) - 0.6;
    seeds[i] = Math.random();
  }
  const dustGeometry = new THREE.BufferGeometry();
  dustGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  dustGeometry.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 1));
  const dust = new THREE.Points(
    dustGeometry,
    new THREE.ShaderMaterial({
      uniforms,
      vertexShader: DUST_VERTEX,
      fragmentShader: DUST_FRAGMENT,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  world.add(dust);

  const resize = () => {
    const { clientWidth: w, clientHeight: h } = el;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    const halfHeight = Math.max(1.25, 2.2 / camera.aspect);
    camera.position.z = halfHeight / Math.tan((camera.fov * Math.PI) / 360);
    camera.updateProjectionMatrix();
    if (reduced) render();
  };

  const render = () => renderer.render(scene, camera);

  // Gaze: where the eye looks, eased with GSAP.
  const gaze = { x: 0, y: 0 };
  const toX = gsap.quickTo(gaze, "x", { duration: 0.9, ease: "power3.out" });
  const toY = gsap.quickTo(gaze, "y", { duration: 0.9, ease: "power3.out" });
  const toDilate = gsap.quickTo(shared.uDilate, "value", {
    duration: 1.2,
    ease: "power2.out",
  });

  let idle: gsap.core.Tween | null = null;
  const wander = () => {
    if (reading) return;
    toX(gsap.utils.random(-0.6, 0.6));
    toY(gsap.utils.random(-0.4, 0.4));
    idle = gsap.delayedCall(gsap.utils.random(1.6, 3.8), wander);
  };

  const onPointer = (event: PointerEvent) => {
    if (reading) return;
    const box = el.getBoundingClientRect();
    const cx = box.left + box.width / 2;
    const cy = box.top + box.height / 2;
    const nx = gsap.utils.clamp(-1, 1, (event.clientX - cx) / (window.innerWidth / 2));
    const ny = gsap.utils.clamp(-1, 1, (event.clientY - cy) / (window.innerHeight / 2));
    toX(nx);
    toY(ny);
    toDilate(0.25 + 0.45 * (1 - Math.min(1, Math.hypot(nx, ny))));
    idle?.kill();
    idle = gsap.delayedCall(4, wander);
  };

  // While someone types in the search box, the eye looks down and reads along.
  let reading = false;
  const isSearch = (target: EventTarget | null) =>
    (target as HTMLElement | null)?.id === "search-input";
  const onFocusIn = (event: FocusEvent) => {
    if (!isSearch(event.target)) return;
    reading = true;
    idle?.kill();
    toX(0);
    toY(0.85);
    toDilate(0.8);
  };
  const onFocusOut = (event: FocusEvent) => {
    if (!isSearch(event.target)) return;
    reading = false;
    toDilate(0.45);
    idle?.kill();
    idle = gsap.delayedCall(1.2, wander);
  };
  const onInput = (event: Event) => {
    if (!reading || !isSearch(event.target)) return;
    const length = (event.target as HTMLInputElement).value.length;
    toX(-0.55 + ((length % 24) / 24) * 1.1);
  };

  const blink = () => {
    gsap
      .timeline({ onComplete: schedule })
      .to(shared.uLid, { value: 0.03, duration: 0.09, ease: "power2.in" })
      .to(shared.uLid, { value: 1, duration: 0.22, ease: "power2.out" });
  };
  let nextBlink: gsap.core.Tween | null = null;
  const schedule = () => {
    nextBlink = gsap.delayedCall(gsap.utils.random(2.5, 6.5), blink);
  };

  let visible = true;
  const tick = (time: number) => {
    if (!visible) return;
    shared.uTime.value = time;
    eyeball.rotation.y = gaze.x * 0.55;
    eyeball.rotation.x = gaze.y * 0.4;
    world.rotation.y = gaze.x * 0.08;
    world.rotation.x = gaze.y * 0.06;
    rings.rotation.z = time * 0.05;
    dust.rotation.y = time * 0.02;
    render();
  };

  const observer = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
  });
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(el);
  resize();

  const intro = gsap.timeline();
  if (reduced) {
    shared.uGlow.value = 1;
    ringMaterials.forEach((m, i) => (m.opacity = [0.22, 0.3, 0.35][i]));
    render();
  } else {
    observer.observe(el);
    intro
      .to(shared.uGlow, { value: 1, duration: 1.6, ease: "sine.inOut" }, 0)
      .to(shared.uLid, { value: 1, duration: 1.4, ease: "expo.out" }, 0.35)
      .to(shared.uDilate, { value: 0.45, duration: 2.2, ease: "power2.out" }, 0.4)
      .to(
        ringMaterials,
        { opacity: (i: number) => [0.22, 0.3, 0.35][i], duration: 1.8, stagger: 0.2 },
        0.2,
      )
      .from(rings.scale, { x: 0.7, y: 0.7, z: 0.7, duration: 2.4, ease: "expo.out" }, 0.1)
      .call(schedule)
      .call(wander, undefined, 1.8);
    gsap.ticker.add(tick);
    window.addEventListener("pointermove", onPointer, { passive: true });
    document.addEventListener("focusin", onFocusIn);
    document.addEventListener("focusout", onFocusOut);
    document.addEventListener("input", onInput);
  }

  return () => {
    gsap.ticker.remove(tick);
    window.removeEventListener("pointermove", onPointer);
    document.removeEventListener("focusin", onFocusIn);
    document.removeEventListener("focusout", onFocusOut);
    document.removeEventListener("input", onInput);
    intro.kill();
    idle?.kill();
    nextBlink?.kill();
    gsap.killTweensOf([shared.uLid, shared.uDilate, shared.uGlow, gaze]);
    observer.disconnect();
    resizeObserver.disconnect();
    scene.traverse((object) => {
      const mesh = object as THREE_NS.Mesh;
      mesh.geometry?.dispose();
      const material = mesh.material as THREE_NS.Material | undefined;
      material?.dispose();
    });
    renderer.dispose();
    renderer.domElement.remove();
  };
}
