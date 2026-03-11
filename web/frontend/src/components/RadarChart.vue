<script setup>
/**
 * RadarChart — 双轨雷达图组件
 * 同时展示 proportion（精力占比）和 depth（投入深度）
 */
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

const props = defineProps({
  profileData: { type: Object, default: () => ({}) },
})

const canvasRef = ref(null)
let chartInstance = null

const DIMENSION_NAMES = {
  system_platform: '系统平台',
  driver_development: '底层驱动',
  application_software: '上层应用',
  wireless_communication: '无线通信',
  sqa_quality: 'SQA质量',
}

function buildChart() {
  if (!canvasRef.value) return

  // 销毁旧实例
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }

  const radarOuter = props.profileData?.radar_outer
  if (!radarOuter) return

  const labels = []
  const proportions = []
  const depths = []

  for (const [dim, data] of Object.entries(radarOuter)) {
    labels.push(DIMENSION_NAMES[dim] || dim)
    const p = data.proportion || 0
    proportions.push(p <= 1 ? Math.round(p * 100) : p)
    depths.push(data.depth || 0)
  }

  // depth(0~5) 映射到 0~100
  const depthMapped = depths.map((d) => Math.round((d / 5) * 100))

  chartInstance = new Chart(canvasRef.value, {
    type: 'radar',
    data: {
      labels: labels.length > 0 ? labels : ['系统', '驱动', '应用', '无线', 'SQA'],
      datasets: [
        {
          label: '精力占比',
          data: proportions,
          backgroundColor: 'rgba(194, 65, 12, 0.08)',
          borderColor: 'rgba(194, 65, 12, 0.8)',
          pointBackgroundColor: 'rgba(194, 65, 12, 1)',
          pointBorderColor: '#fff',
          borderWidth: 2,
          pointRadius: 4,
        },
        {
          label: '投入深度',
          data: depthMapped,
          backgroundColor: 'rgba(217, 119, 6, 0.06)',
          borderColor: 'rgba(217, 119, 6, 0.7)',
          pointBackgroundColor: 'rgba(217, 119, 6, 1)',
          pointBorderColor: '#fff',
          borderWidth: 2,
          borderDash: [4, 4],
          pointRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          angleLines: { color: 'rgba(0, 0, 0, 0.06)' },
          grid: { color: 'rgba(0, 0, 0, 0.04)', circular: true },
          pointLabels: {
            font: {
              family: "'Inter', 'PingFang SC', sans-serif",
              size: 13,
              weight: '500',
            },
            color: '#78716C',
            padding: 16,
          },
          ticks: { display: false, min: 0, max: 100 },
        },
      },
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            font: { family: "'Inter', sans-serif", size: 12 },
            color: '#78716C',
            usePointStyle: true,
            pointStyle: 'circle',
            padding: 20,
          },
        },
        tooltip: {
          backgroundColor: 'rgba(28, 25, 23, 0.92)',
          titleFont: { family: "'Inter', sans-serif", size: 13 },
          bodyFont: { family: "'Inter', sans-serif", size: 12 },
          padding: 12,
          cornerRadius: 8,
          callbacks: {
            afterLabel(context) {
              if (context.datasetIndex === 0) {
                const depth = depths[context.dataIndex]
                return depth ? `投入深度: ${depth}/5` : ''
              }
              return ''
            },
          },
        },
      },
    },
  })
}

onMounted(buildChart)
onBeforeUnmount(() => chartInstance?.destroy())
watch(() => props.profileData, buildChart, { deep: true })
</script>

<template>
  <div class="radar-chart">
    <canvas ref="canvasRef"></canvas>
  </div>
</template>

<style scoped>
.radar-chart {
  position: relative;
  width: 100%;
  height: 320px;
}
</style>
