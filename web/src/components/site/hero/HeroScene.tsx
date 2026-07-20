"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { buildLattice } from "./latticeData";
import type { GatePhase } from "./phase";

/**
 * "The Gate & the Lattice" — the hero scene.
 *
 * An instanced lattice of luminous reasoning-surface nodes in slow parallax
 * drift, wired by chain edges that pulse light along their length (the hash
 * chain). On a loop, an action particle streams toward the gate plane, is HELD
 * (desaturated-red flash), then passes through VERIFIED (warm amber).
 *
 * Design constraints honoured here:
 * - No per-frame React state. The timeline lives entirely in useFrame and only
 *   emits a callback on phase TRANSITIONS (~4 per 8.5s loop), which the DOM
 *   overlay consumes.
 * - Pointer parallax reads a window-level listener rather than R3F's canvas
 *   pointer, so the canvas can stay `pointer-events: none` and never swallow a
 *   click meant for a CTA.
 * - `frameloop` is driven by the parent's IntersectionObserver: off-viewport the
 *   canvas stops rendering entirely.
 */

const NODE_VERT = /* glsl */ `
  uniform float uTime;
  uniform float uSize;
  attribute float aScale;
  attribute float aPhase;
  attribute float aTone;
  varying float vTone;
  varying float vTw;
  void main() {
    vTone = aTone;
    vec3 p = position;
    p.y += sin(uTime * 0.12 + aPhase * 6.2831) * 0.26;
    p.x += cos(uTime * 0.10 + aPhase * 6.2831) * 0.22;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    float tw = 0.62 + 0.38 * sin(uTime * 0.85 + aPhase * 12.0);
    vTw = tw;
    // The attenuation constant is deliberately small: these are pinpoint nodes
    // in a lattice, not bokeh. At mid-field depth this lands around 5-6 device
    // pixels. A larger constant reads as an out-of-focus particle field and
    // swallows the chain edges entirely.
    gl_PointSize = uSize * aScale * tw * (30.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`;

const NODE_FRAG = /* glsl */ `
  precision mediump float;
  uniform vec3 uColorA;
  uniform vec3 uColorB;
  varying float vTone;
  varying float vTw;
  void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    if (d > 0.5) discard;
    float core = smoothstep(0.5, 0.0, d);
    float glow = pow(core, 1.8);
    vec3 col = mix(uColorA, uColorB, vTone);
    gl_FragColor = vec4(col, glow * (0.45 + 0.55 * vTw));
  }
`;

const EDGE_VERT = /* glsl */ `
  attribute float aAlong;
  attribute float aEdgePhase;
  varying float vAlong;
  varying float vEdgePhase;
  void main() {
    vAlong = aAlong;
    vEdgePhase = aEdgePhase;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const EDGE_FRAG = /* glsl */ `
  precision mediump float;
  uniform float uTime;
  uniform vec3 uColor;
  uniform vec3 uPulse;
  varying float vAlong;
  varying float vEdgePhase;
  void main() {
    float p = fract(uTime * 0.14 + vEdgePhase);
    float d = abs(vAlong - p);
    d = min(d, 1.0 - d);
    float pulse = smoothstep(0.13, 0.0, d);
    vec3 col = mix(uColor, uPulse, pulse);
    float a = 0.14 + pulse * 0.85;
    gl_FragColor = vec4(col, a);
  }
`;

const GATE_VERT = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const GATE_FRAG = /* glsl */ `
  precision mediump float;
  uniform float uTime;
  uniform vec3 uColor;
  uniform float uIntensity;
  varying vec2 vUv;
  void main() {
    vec2 uv = vUv;
    vec2 c = uv - 0.5;
    float border = min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y));
    // Crisp rim plus a wider soft bloom, so the gate reads as a defined plane
    // rather than a haze once the lattice behind it is pinpoint-scale.
    float rim = 1.0 - smoothstep(0.0, 0.006, border);
    float edge = 1.0 - smoothstep(0.0, 0.07, border);
    float scan = 0.5 + 0.5 * sin(uv.y * 46.0 - uTime * 1.4);
    scan = pow(scan, 3.0) * 0.13;
    float fill = 0.06 * (1.0 - length(c));
    float a = clamp(rim * 0.85 + edge * 0.4 + scan + fill, 0.0, 0.95) * (0.55 + 0.45 * uIntensity);
    gl_FragColor = vec4(uColor, a);
  }
`;

const PARTICLE_VERT = /* glsl */ `
  uniform float uSize;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = uSize * (30.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`;

const PARTICLE_FRAG = /* glsl */ `
  precision mediump float;
  uniform vec3 uColor;
  uniform float uAlpha;
  void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    if (d > 0.5) discard;
    float core = smoothstep(0.5, 0.0, d);
    gl_FragColor = vec4(uColor, pow(core, 1.5) * uAlpha);
  }
`;

// Loop timing (seconds).
const T_APPROACH_END = 3.2;
const T_HELD_END = 5.9;
const T_VERIFIED_END = 7.5;
const T_CYCLE = 8.6;

const C_CHAIN = new THREE.Color("#57c7ff");
const C_CHAIN_PALE = new THREE.Color("#a9e2ff");
const C_PULSE = new THREE.Color("#eaf7ff");
const C_HELD = new THREE.Color("#e0563f");
const C_VERIFIED = new THREE.Color("#f2b134");
const C_GATE_IDLE = new THREE.Color("#3d6f92");

/** Horizontal offset of the gate plane, clearing the hero copy on the left. */
const GATE_X = 3.2;

const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

function Scene({
  nodeCount,
  parallax,
  onPhase,
}: {
  nodeCount: number;
  parallax: boolean;
  onPhase: (p: GatePhase) => void;
}) {
  const { camera } = useThree();
  const lattice = useMemo(() => buildLattice(nodeCount), [nodeCount]);

  const groupRef = useRef<THREE.Group>(null);
  const particleRef = useRef<THREE.Points>(null);
  const pointer = useRef({ x: 0, y: 0 });
  const lastPhase = useRef<GatePhase | null>(null);

  // Node cloud ------------------------------------------------------------
  const nodeGeo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(lattice.positions, 3));
    g.setAttribute("aScale", new THREE.BufferAttribute(lattice.scales, 1));
    g.setAttribute("aPhase", new THREE.BufferAttribute(lattice.phases, 1));
    g.setAttribute("aTone", new THREE.BufferAttribute(lattice.tones, 1));
    return g;
  }, [lattice]);

  const nodeMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uSize: { value: 2.6 },
          uColorA: { value: C_CHAIN.clone() },
          uColorB: { value: C_CHAIN_PALE.clone() },
        },
        vertexShader: NODE_VERT,
        fragmentShader: NODE_FRAG,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    [],
  );

  // Chain edges -----------------------------------------------------------
  const edgeGeo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(lattice.edgePositions, 3));
    g.setAttribute("aAlong", new THREE.BufferAttribute(lattice.edgeAlong, 1));
    g.setAttribute("aEdgePhase", new THREE.BufferAttribute(lattice.edgePhase, 1));
    return g;
  }, [lattice]);

  const edgeMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uColor: { value: C_CHAIN.clone().multiplyScalar(0.7) },
          uPulse: { value: C_PULSE.clone() },
        },
        vertexShader: EDGE_VERT,
        fragmentShader: EDGE_FRAG,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    [],
  );

  // Gate ------------------------------------------------------------------
  const gateGeo = useMemo(() => new THREE.PlaneGeometry(7.6, 4.7), []);
  const gateMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uColor: { value: C_GATE_IDLE.clone() },
          uIntensity: { value: 0.3 },
        },
        vertexShader: GATE_VERT,
        fragmentShader: GATE_FRAG,
        transparent: true,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    [],
  );

  // Action particle -------------------------------------------------------
  const particleGeo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array([0, 0, 0]), 3));
    return g;
  }, []);
  const particleMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uSize: { value: 30 },
          uColor: { value: C_CHAIN_PALE.clone() },
          uAlpha: { value: 1 },
        },
        vertexShader: PARTICLE_VERT,
        fragmentShader: PARTICLE_FRAG,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    [],
  );

  useEffect(() => {
    return () => {
      nodeGeo.dispose();
      nodeMat.dispose();
      edgeGeo.dispose();
      edgeMat.dispose();
      gateGeo.dispose();
      gateMat.dispose();
      particleGeo.dispose();
      particleMat.dispose();
    };
  }, [nodeGeo, nodeMat, edgeGeo, edgeMat, gateGeo, gateMat, particleGeo, particleMat]);

  useEffect(() => {
    if (!parallax) return;
    const onMove = (e: PointerEvent) => {
      pointer.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      pointer.current.y = -((e.clientY / window.innerHeight) * 2 - 1);
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, [parallax]);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    nodeMat.uniforms.uTime.value = t;
    edgeMat.uniforms.uTime.value = t;
    gateMat.uniforms.uTime.value = t;

    // Slow lattice drift.
    if (groupRef.current) {
      groupRef.current.rotation.y = Math.sin(t * 0.05) * 0.08;
      groupRef.current.rotation.x = Math.cos(t * 0.04) * 0.04;
    }

    // Pointer parallax — capped near 3deg of camera swing at z=14.
    const tx = parallax ? pointer.current.x * 0.7 : 0;
    const ty = parallax ? pointer.current.y * 0.5 : 0;
    camera.position.x += (tx - camera.position.x) * 0.035;
    camera.position.y += (ty - camera.position.y) * 0.035;
    camera.lookAt(0, 0, 0);

    // --- Gate timeline ---------------------------------------------------
    const lt = t % T_CYCLE;
    let phase: GatePhase;
    let z: number;
    let alpha = 1;
    let targetGate: THREE.Color;
    let targetParticle: THREE.Color;
    let intensity: number;

    if (lt < T_APPROACH_END) {
      phase = "approach";
      z = -10 + easeInOut(lt / T_APPROACH_END) * 10;
      targetGate = C_GATE_IDLE;
      targetParticle = C_CHAIN_PALE;
      intensity = 0.3;
    } else if (lt < T_HELD_END) {
      phase = "held";
      const k = (lt - T_APPROACH_END) / (T_HELD_END - T_APPROACH_END);
      // Held right at the gate face, with a tight nervous jitter.
      z = -0.05 + Math.sin(k * Math.PI * 9) * 0.05;
      targetGate = C_HELD;
      targetParticle = C_HELD;
      intensity = 0.65 + 0.35 * Math.sin(k * Math.PI * 6);
    } else if (lt < T_VERIFIED_END) {
      phase = "verified";
      const k = (lt - T_HELD_END) / (T_VERIFIED_END - T_HELD_END);
      z = easeOut(k) * 4.2;
      targetGate = C_VERIFIED;
      targetParticle = C_VERIFIED;
      intensity = 1 - k * 0.5;
    } else {
      phase = "reset";
      const k = (lt - T_VERIFIED_END) / (T_CYCLE - T_VERIFIED_END);
      z = 4.2 + k * 2;
      alpha = 1 - k;
      targetGate = C_GATE_IDLE;
      targetParticle = C_VERIFIED;
      intensity = 0.3;
    }

    if (particleRef.current) {
      particleRef.current.position.z = z;
    }
    particleMat.uniforms.uAlpha.value = alpha;
    (particleMat.uniforms.uColor.value as THREE.Color).lerp(targetParticle, 0.12);
    (gateMat.uniforms.uColor.value as THREE.Color).lerp(targetGate, 0.14);
    gateMat.uniforms.uIntensity.value +=
      (intensity - gateMat.uniforms.uIntensity.value) * 0.1;

    if (phase !== lastPhase.current) {
      lastPhase.current = phase;
      onPhase(phase);
    }
  });

  return (
    <>
      <fog attach="fog" args={["#0a0c10", 14, 34]} />
      <group ref={groupRef}>
        <points geometry={nodeGeo} material={nodeMat} />
        <lineSegments geometry={edgeGeo} material={edgeMat} />
      </group>
      {/* The gate sits right of centre so the hero copy on the left stays on
          clean substrate — the plane is translucent, but a lit rectangle
          directly behind a display-serif headline costs legibility. */}
      <mesh geometry={gateGeo} material={gateMat} position={[GATE_X, 0, 0]} />
      <points
        ref={particleRef}
        geometry={particleGeo}
        material={particleMat}
        position={[GATE_X, 0, 0]}
      />
    </>
  );
}

export default function HeroScene({
  nodeCount,
  parallax,
  frameloop,
  onPhase,
}: {
  nodeCount: number;
  parallax: boolean;
  frameloop: "always" | "never";
  onPhase: (p: GatePhase) => void;
}) {
  return (
    <Canvas
      frameloop={frameloop}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ position: [0, 0, 14], fov: 50 }}
      style={{ pointerEvents: "none" }}
    >
      <Scene nodeCount={nodeCount} parallax={parallax} onPhase={onPhase} />
    </Canvas>
  );
}
