<script setup>
/**
 * AbilityChart3D — 统一能力图谱 3D 可视化（仿真水晶柱 + 浮岛版）
 *
 * 水晶柱造型：参照真实天然水晶 — 修长六棱柱体 + 顶部短斜切锥面
 * 色调：暖琥珀/铜橙色系，与 UI 主色 #C2410C 统一
 */
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

const props = defineProps({
  outerData: { type: Object, required: true },
  innerData: { type: Object, required: true },
})

const DIM_LABELS = {
  system_platform: '系统平台',
  driver_development: '底层驱动',
  application_software: '上层应用',
  wireless_communication: '无线通信',
  sqa_quality: 'SQA质量',
}

// 暖色系浮岛配色（铜→橙→金递进）
const INNER_LAYERS = [
  { key: 'truth_seeking', label: '求真', color: 0xBF360C, emissive: 0x8B1A00, desc: '基石 · 溯源行为' },
  { key: 'pragmatic', label: '务实', color: 0xE65100, emissive: 0xBF360C, desc: '框架 · 交付行为' },
  { key: 'rigorous', label: '严谨', color: 0xF57C00, emissive: 0xE65100, desc: '附着 · 质量行为' },
]

const canvasRef = ref(null)
const tooltipData = ref(null)
const tooltipPos = ref({ x: 0, y: 0 })

let scene, camera, renderer, controls
let sceneObjects = []
let animFrameId = null
let raycaster, mouse
let interactables = []
let islandMeshes = []
let particles = null

const CRYSTAL_MAX_HEIGHT = 5.0
const CRYSTAL_BASE_RADIUS = 0.55
const CRYSTAL_MIN_RADIUS = 0.12
const RING_DIST = 5.0
const ISLAND_GAP = 1.5

onMounted(() => { nextTick(() => { initScene(); buildChart(); animate() }) })

onBeforeUnmount(() => {
  if (animFrameId) cancelAnimationFrame(animFrameId)
  if (controls) controls.dispose()
  if (renderer) { renderer.dispose(); renderer.forceContextLoss() }
  window.removeEventListener('resize', onResize)
})

watch(() => [props.outerData, props.innerData], () => { clearChart(); buildChart() }, { deep: true })

function initScene() {
  const container = canvasRef.value
  const w = container.clientWidth
  const h = container.clientHeight

  scene = new THREE.Scene()
  scene.background = new THREE.Color('#0D0907') // 暖黑色
  scene.fog = new THREE.FogExp2(0x0D0907, 0.018)

  camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 200)
  camera.position.set(8, 6, 10)
  camera.lookAt(0, 1.5, 0)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(w, h)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.1
  container.appendChild(renderer.domElement)

  // 暖色灯光系统
  scene.add(new THREE.AmbientLight(0x2D1B0E, 0.5))

  const mainLight = new THREE.DirectionalLight(0xFFE0B2, 0.9)
  mainLight.position.set(8, 10, 6)
  scene.add(mainLight)

  const rimLight = new THREE.DirectionalLight(0xFFAB40, 0.3)
  rimLight.position.set(-6, 6, -8)
  scene.add(rimLight)

  // 中心暖色点光
  const coreLight = new THREE.PointLight(0xFF6D00, 1.2, 12)
  coreLight.position.set(0, 2, 0)
  scene.add(coreLight)
  sceneObjects.push(coreLight)

  buildGroundGrid()
  buildParticles()

  // OrbitControls
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.06
  controls.autoRotate = true
  controls.autoRotateSpeed = 0.5
  controls.maxPolarAngle = Math.PI * 0.55
  controls.minPolarAngle = Math.PI * 0.15
  controls.minDistance = 6
  controls.maxDistance = 22

  raycaster = new THREE.Raycaster()
  mouse = new THREE.Vector2()
  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('pointerleave', () => { tooltipData.value = null })
  window.addEventListener('resize', onResize)
}

function buildGroundGrid() {
  // 暖色同心圆
  for (let r = 2; r <= 10; r += 2) {
    const geo = new THREE.RingGeometry(r - 0.015, r + 0.015, 64)
    const mat = new THREE.MeshBasicMaterial({
      color: 0x5D4037, transparent: true, opacity: 0.12, side: THREE.DoubleSide
    })
    const mesh = new THREE.Mesh(geo, mat)
    mesh.rotation.x = -Math.PI / 2
    mesh.position.y = -0.5
    scene.add(mesh)
    sceneObjects.push(mesh)
  }
  // 放射线
  for (let i = 0; i < 10; i++) {
    const angle = (i / 10) * Math.PI * 2
    const pts = [
      new THREE.Vector3(0, -0.5, 0),
      new THREE.Vector3(Math.cos(angle) * 10, -0.5, Math.sin(angle) * 10),
    ]
    const geo = new THREE.BufferGeometry().setFromPoints(pts)
    const mat = new THREE.LineBasicMaterial({ color: 0x4E342E, transparent: true, opacity: 0.08 })
    scene.add(new THREE.Line(geo, mat))
  }
}

function buildParticles() {
  const count = 200
  const pos = new Float32Array(count * 3)
  for (let i = 0; i < count; i++) {
    pos[i * 3] = (Math.random() - 0.5) * 28
    pos[i * 3 + 1] = Math.random() * 12 - 2
    pos[i * 3 + 2] = (Math.random() - 0.5) * 28
  }
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  const mat = new THREE.PointsMaterial({
    color: 0xFFAB40, size: 0.04, transparent: true, opacity: 0.35, sizeAttenuation: true,
  })
  particles = new THREE.Points(geo, mat)
  scene.add(particles)
  sceneObjects.push(particles)
}

/**
 * 仿真水晶柱几何体
 *
 * 参照天然石英水晶：
 * - 柱身占总高度 ~80%：六棱柱等宽直筒
 * - 顶冠占 ~20%：六面斜切收尖（锥角约 30°）
 * - 底部微微外扩
 */
function createCrystalGeometry(radius, height) {
  const bodyRatio = 0.82 // 柱身占比
  const bodyH = height * bodyRatio
  const capH = height * (1 - bodyRatio)
  const sides = 6

  // 用 LatheGeometry 的轮廓点阵描述剖面
  const profile = []
  const bottomR = radius * 1.06 // 底部微扩
  const bodyR = radius
  const tipR = radius * 0.08 // 尖端极细

  // 从底部向上构建轮廓
  profile.push(new THREE.Vector2(0, 0))           // 底面中心
  profile.push(new THREE.Vector2(bottomR, 0))      // 底面外缘
  profile.push(new THREE.Vector2(bottomR, 0.05))   // 底面微倒角
  profile.push(new THREE.Vector2(bodyR, 0.15))     // 过渡到柱身

  // 柱身直筒段（多个中间点保持笔直）
  const bodySteps = 4
  for (let i = 0; i <= bodySteps; i++) {
    const t = i / bodySteps
    const y = 0.15 + t * (bodyH - 0.15)
    // 柱身非常轻微的内收（真实水晶特征）
    const r = bodyR * (1 - t * 0.02)
    profile.push(new THREE.Vector2(r, y))
  }

  // 顶冠斜切收尖段
  const capSteps = 3
  for (let i = 1; i <= capSteps; i++) {
    const t = i / capSteps
    const y = bodyH + t * capH
    const r = bodyR * (1 - 0.02) * (1 - t * 0.92) // 从柱身宽度线性收窄
    profile.push(new THREE.Vector2(Math.max(r, tipR), y))
  }

  // 尖端
  profile.push(new THREE.Vector2(0, height * 1.01))

  return new THREE.LatheGeometry(profile, sides)
}

function buildChart() {
  const outer = props.outerData || {}
  const inner = props.innerData || {}
  const dims = Object.keys(DIM_LABELS)
  const n = dims.length

  // ===== 五根水晶柱 =====
  dims.forEach((dimKey, i) => {
    const angle = (i / n) * Math.PI * 2 - Math.PI / 2
    const val = outer[dimKey] || { proportion: 0, depth: 0 }
    const proportion = val.proportion || 0
    const depth = val.depth || 0

    const radius = CRYSTAL_MIN_RADIUS + proportion * (CRYSTAL_BASE_RADIUS - CRYSTAL_MIN_RADIUS) * n
    const height = Math.max(0.8, (depth / 5) * CRYSTAL_MAX_HEIGHT)

    const geo = createCrystalGeometry(radius, height)

    // 暖色水晶材质 — 琥珀色系
    const depthNorm = depth / 5
    const hue = 0.06 + i * 0.012 // 色相在暖橙系微变
    const color = new THREE.Color().setHSL(hue, 0.75, 0.40 + depthNorm * 0.12)
    const emissive = new THREE.Color().setHSL(hue, 0.9, 0.12 + depthNorm * 0.15)

    const mat = new THREE.MeshPhysicalMaterial({
      color,
      emissive,
      emissiveIntensity: 0.3 + depthNorm * 0.5,
      transparent: true,
      opacity: 0.78,
      roughness: 0.12,
      metalness: 0.0,
      clearcoat: 1.0,
      clearcoatRoughness: 0.05,
      transmission: 0.15,
      thickness: 2.0,
      ior: 1.55,
      flatShading: true, // 六棱面平整分明，棱角感更强
      side: THREE.DoubleSide,
    })

    const mesh = new THREE.Mesh(geo, mat)
    mesh.position.set(Math.cos(angle) * RING_DIST, -0.5, Math.sin(angle) * RING_DIST)
    mesh.rotation.y = angle + Math.random() * 0.15 // 微旋转增自然感
    mesh.userData = { type: 'pillar', dimKey, label: DIM_LABELS[dimKey], proportion, depth }

    scene.add(mesh)
    sceneObjects.push(mesh)
    interactables.push(mesh)

    // 底部暖光圈
    const glowGeo = new THREE.RingGeometry(0, radius * 2.0, 32)
    const glowMat = new THREE.MeshBasicMaterial({
      color: 0xBF360C, transparent: true, opacity: 0.10 + depthNorm * 0.08, side: THREE.DoubleSide,
    })
    const glow = new THREE.Mesh(glowGeo, glowMat)
    glow.rotation.x = -Math.PI / 2
    glow.position.set(Math.cos(angle) * RING_DIST, -0.48, Math.sin(angle) * RING_DIST)
    scene.add(glow)
    sceneObjects.push(glow)

    // 连接光束
    const beamPts = [
      new THREE.Vector3(0, -0.3, 0),
      new THREE.Vector3(Math.cos(angle) * RING_DIST, -0.3, Math.sin(angle) * RING_DIST),
    ]
    const beamGeo = new THREE.BufferGeometry().setFromPoints(beamPts)
    const beamMat = new THREE.LineBasicMaterial({ color: 0x5D4037, transparent: true, opacity: 0.15 })
    scene.add(new THREE.Line(beamGeo, beamMat))

    // 维度标签
    const labelSp = createTextSprite(DIM_LABELS[dimKey], { fontSize: 26, color: '#BCAAA4' })
    labelSp.position.set(
      Math.cos(angle) * (RING_DIST + 1.2),
      height + 0.5,
      Math.sin(angle) * (RING_DIST + 1.2),
    )
    labelSp.scale.set(1.6, 0.6, 1)
    scene.add(labelSp)
    sceneObjects.push(labelSp)

    // 数值标签
    const valSp = createTextSprite(`${(proportion * 100).toFixed(0)}% · D${depth}`, { fontSize: 18, color: '#FFAB40' })
    valSp.position.set(Math.cos(angle) * RING_DIST, height * 0.55, Math.sin(angle) * RING_DIST)
    valSp.scale.set(1.1, 0.38, 1)
    scene.add(valSp)
    sceneObjects.push(valSp)
  })

  // ===== 三层基石浮岛 =====
  INNER_LAYERS.forEach((layer, i) => {
    const val = inner[layer.key] || { level: 0 }
    const level = val.level || 0
    const y = i * ISLAND_GAP

    const maxR = 1.8
    const minR = 0.5
    const radius = minR + (level / 5) * (maxR - minR)

    // 浮岛主体 — 略厚的扁圆盘
    const islandGeo = new THREE.CylinderGeometry(radius, radius * 1.08, 0.22, 32)
    const islandMat = new THREE.MeshPhysicalMaterial({
      color: layer.color,
      emissive: layer.emissive,
      emissiveIntensity: 0.5,
      transparent: true,
      opacity: 0.82,
      roughness: 0.2,
      metalness: 0.08,
      clearcoat: 0.6,
    })
    const island = new THREE.Mesh(islandGeo, islandMat)
    island.position.y = y
    island.userData = { type: 'foundation', layerKey: layer.key, label: layer.label, desc: layer.desc, level }
    scene.add(island)
    sceneObjects.push(island)
    interactables.push(island)
    islandMeshes.push(island)

    // 浮岛发光外环
    const haloGeo = new THREE.TorusGeometry(radius * 0.95, 0.03, 8, 48)
    const haloMat = new THREE.MeshBasicMaterial({ color: layer.color, transparent: true, opacity: 0.35 })
    const halo = new THREE.Mesh(haloGeo, haloMat)
    halo.rotation.x = Math.PI / 2
    halo.position.y = y
    scene.add(halo)
    sceneObjects.push(halo)

    // 发光底光
    const underGeo = new THREE.RingGeometry(radius * 0.2, radius * 1.2, 48)
    const underMat = new THREE.MeshBasicMaterial({ color: layer.emissive, transparent: true, opacity: 0.08, side: THREE.DoubleSide })
    const under = new THREE.Mesh(underGeo, underMat)
    under.rotation.x = -Math.PI / 2
    under.position.y = y - 0.25
    scene.add(under)
    sceneObjects.push(under)

    // 层间能量光柱
    if (i > 0) {
      const pGeo = new THREE.CylinderGeometry(0.04, 0.04, ISLAND_GAP - 0.3, 6)
      const pMat = new THREE.MeshBasicMaterial({ color: layer.emissive, transparent: true, opacity: 0.15 })
      const p = new THREE.Mesh(pGeo, pMat)
      p.position.y = y - ISLAND_GAP / 2
      scene.add(p)
      sceneObjects.push(p)
    }

    // 层级标签
    const lvSp = createTextSprite(`${layer.label} Lv.${level}`, {
      fontSize: 22,
      color: '#FFFFFF',
      bgColor: `#${layer.emissive.toString(16).padStart(6, '0')}`,
    })
    lvSp.position.set(radius + 0.6, y + 0.15, 0)
    lvSp.scale.set(1.3, 0.48, 1)
    scene.add(lvSp)
    sceneObjects.push(lvSp)
  })

  // 中心轴线
  const axH = INNER_LAYERS.length * ISLAND_GAP
  const axGeo = new THREE.CylinderGeometry(0.015, 0.015, axH + 0.5, 6)
  const axMat = new THREE.MeshBasicMaterial({ color: 0x5D4037, transparent: true, opacity: 0.12 })
  const ax = new THREE.Mesh(axGeo, axMat)
  ax.position.y = axH / 2 - 0.3
  scene.add(ax)
  sceneObjects.push(ax)
}

function clearChart() {
  sceneObjects.forEach((obj) => {
    scene.remove(obj)
    if (obj.geometry) obj.geometry.dispose()
    if (obj.material) { if (obj.material.map) obj.material.map.dispose(); obj.material.dispose() }
  })
  sceneObjects = []; interactables = []; islandMeshes = []; particles = null
  buildGroundGrid(); buildParticles()
}

function animate() {
  animFrameId = requestAnimationFrame(animate)
  if (controls) controls.update()
  const t = performance.now() * 0.001

  // 浮岛呼吸浮动
  islandMeshes.forEach((mesh, idx) => {
    mesh.position.y = idx * ISLAND_GAP + Math.sin(t * 0.4 + idx * 1.0) * 0.06
  })

  if (particles) particles.rotation.y = t * 0.015
  if (renderer && scene && camera) renderer.render(scene, camera)
}

function onResize() {
  const c = canvasRef.value; if (!c) return
  const w = c.clientWidth, h = c.clientHeight
  camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h)
}

function onPointerMove(e) {
  const rect = renderer.domElement.getBoundingClientRect()
  mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(mouse, camera)
  const hits = raycaster.intersectObjects(interactables)

  interactables.forEach((m) => {
    if (m.material?.emissiveIntensity !== undefined) {
      if (m.userData?.type === 'pillar') {
        const d = m.userData.depth || 0
        m.material.emissiveIntensity = 0.3 + (d / 5) * 0.5
      } else { m.material.emissiveIntensity = 0.5 }
    }
  })

  if (hits.length > 0) {
    const obj = hits[0].object
    if (obj.material?.emissiveIntensity !== undefined) obj.material.emissiveIntensity = 1.8
    tooltipData.value = obj.userData
    tooltipPos.value = {
      x: e.clientX - canvasRef.value.getBoundingClientRect().left + 14,
      y: e.clientY - canvasRef.value.getBoundingClientRect().top - 10,
    }
    controls.autoRotate = false
  } else { tooltipData.value = null; controls.autoRotate = true }
}

function createTextSprite(text, opts = {}) {
  const { fontSize = 24, color = '#BCAAA4', bgColor = null,
    fontFamily = 'Inter, "PingFang SC", "Microsoft YaHei", sans-serif' } = opts
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  const dpr = 2, pad = 14
  ctx.font = `bold ${fontSize * dpr}px ${fontFamily}`
  const m = ctx.measureText(text)
  const tw = m.width + pad * 2 * dpr
  const th = fontSize * dpr * 1.8 + pad * dpr
  canvas.width = tw; canvas.height = th
  ctx.font = `bold ${fontSize * dpr}px ${fontFamily}`
  if (bgColor) {
    ctx.fillStyle = bgColor
    ctx.beginPath(); ctx.roundRect(0, 0, tw, th, 8 * dpr); ctx.fill()
    ctx.strokeStyle = 'rgba(255,171,64,0.4)'; ctx.lineWidth = dpr; ctx.stroke()
    ctx.fillStyle = '#FFF'
  } else { ctx.fillStyle = color }
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
  ctx.fillText(text, tw / 2, th / 2)
  const texture = new THREE.CanvasTexture(canvas)
  texture.minFilter = THREE.LinearFilter
  return new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false }))
}
</script>

<template>
  <div class="ability-chart-3d" ref="canvasRef">
    <div v-if="tooltipData" class="ability-chart-3d__tooltip"
      :style="{ left: tooltipPos.x + 'px', top: tooltipPos.y + 'px' }">
      <template v-if="tooltipData.type === 'pillar'">
        <strong>{{ tooltipData.label }}</strong>
        <div class="ability-chart-3d__tooltip-row">
          <span>精力占比</span>
          <span class="ability-chart-3d__tooltip-val">{{ (tooltipData.proportion * 100).toFixed(1) }}%</span>
        </div>
        <div class="ability-chart-3d__tooltip-row">
          <span>投入深度</span>
          <span class="ability-chart-3d__tooltip-val">{{ tooltipData.depth }} / 5</span>
        </div>
      </template>
      <template v-else-if="tooltipData.type === 'foundation'">
        <strong>{{ tooltipData.label }} Lv.{{ tooltipData.level }}</strong>
        <div class="ability-chart-3d__tooltip-desc">{{ tooltipData.desc }}</div>
      </template>
    </div>
    <div class="ability-chart-3d__hint">拖拽旋转 · 滚轮缩放 · 悬停查看数值</div>
  </div>
</template>

<style scoped>
.ability-chart-3d {
  position: relative;
  width: 100%;
  height: 500px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: #0D0907;
}
.ability-chart-3d__tooltip {
  position: absolute; pointer-events: none; z-index: 20;
  background: rgba(20, 12, 8, 0.94); color: #E0D5CC;
  padding: 10px 16px; border-radius: 10px; font-size: 13px; line-height: 1.7;
  min-width: 130px; border: 1px solid rgba(191, 54, 12, 0.35);
  box-shadow: 0 0 18px rgba(191, 54, 12, 0.12), 0 4px 14px rgba(0,0,0,0.5);
  backdrop-filter: blur(12px);
}
.ability-chart-3d__tooltip strong { display: block; font-size: 14px; margin-bottom: 4px; color: #FFAB40; }
.ability-chart-3d__tooltip-row { display: flex; justify-content: space-between; gap: 20px; }
.ability-chart-3d__tooltip-val { font-weight: 600; font-family: var(--font-mono); color: #FFE0B2; }
.ability-chart-3d__tooltip-desc { font-size: 12px; color: #8D6E63; margin-top: 2px; }
.ability-chart-3d__hint {
  position: absolute; bottom: 12px; left: 50%; transform: translateX(-50%);
  font-size: 11px; color: rgba(188, 170, 164, 0.35); letter-spacing: 2px; pointer-events: none;
}
</style>
