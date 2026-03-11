import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'

/* 导入设计系统样式 */
import './assets/styles/variables.css'
import './assets/styles/reset.css'
import './assets/styles/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
