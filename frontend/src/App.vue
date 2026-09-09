<script setup>
import { ref } from 'vue'

const status = ref('未连接')
const isConnecting = ref(false)

async function testBackendConnection() {
  isConnecting.value = true
  status.value = '正在连接…'

  try {
    const response = await fetch('/api/health')
    const data = await response.json()

    if (!response.ok || data.code !== 0) {
      throw new Error(data.message || '后端返回异常')
    }

    status.value = data.data?.status === 'ok'
      ? '✅ 邮智办后端运行正常'
      : `✅ ${data.message || '后端连接成功'}`
  } catch (error) {
    status.value = `连接失败：${error.message || '请确认 FastAPI 服务已启动'}`
  } finally {
    isConnecting.value = false
  }
}
</script>

<template>
  <main class="page">
    <h1>邮智办</h1>
    <p>北邮校园事务智能办理助手</p>

    <button type="button" :disabled="isConnecting" @click="testBackendConnection">
      {{ isConnecting ? '连接中…' : '测试后端连接' }}
    </button>

    <p class="status">后端状态：{{ status }}</p>
  </main>
</template>

<style scoped>
.page {
  max-width: 520px;
  margin: 80px auto;
  padding: 32px;
  text-align: center;
  font-family: "Microsoft YaHei", sans-serif;
}

button {
  padding: 10px 18px;
  border: 0;
  border-radius: 6px;
  background: #1f5fbf;
  color: #fff;
  cursor: pointer;
}

button:disabled {
  cursor: wait;
  opacity: 0.7;
}

.status {
  margin-top: 24px;
}
</style>
