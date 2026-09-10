<script setup>
import { computed, onMounted, ref } from 'vue'
import { request } from './api/client'

const navItems = [
  { key: 'query', label: '智能办理' },
  { key: 'profile', label: '我的画像' },
  { key: 'todos', label: '我的待办' },
  { key: 'history', label: '查询历史' },
]
const quickQuestions = ['缓考申请', '请假', '奖学金', '成绩问题']

const page = ref('login')
const busy = ref(false)
const notice = ref('')
const bad = ref(false)
const user = ref(null)
const health = ref('服务连接中')
const result = ref(null)
const todos = ref([])
const history = ref([])
const mode = ref('login')
const auth = ref({ username: '', password: '' })
const profile = ref({ college: '', grade: '', education_level: '本科', campus: '' })
const question = ref('我想申请缓考')
const todo = ref({ title: '', notes: '' })

const say = (x, e = false) => {
  notice.value = x
  bad.value = e
}
const fail = e => say(e.message || '请求失败', true)
const list = value => (Array.isArray(value) ? value : [])
const activePage = computed(() => (page.value === 'result' ? 'query' : page.value))
const profileSummary = computed(() => {
  const parts = [
    profile.value.grade ? `${profile.value.grade}级` : '',
    profile.value.education_level || '',
    profile.value.campus ? `${profile.value.campus}校区` : '',
  ].filter(Boolean)
  return parts.length ? parts.join(' / ') : '完善画像后获得更贴合的办理建议'
})
const completedCount = computed(() => todos.value.filter(item => item.completed).length)

function setFavicon() {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="28" fill="#5f6875"/><path d="M18 31a14 14 0 0 1 23.7-10.1" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round"/><path d="M46 33a14 14 0 0 1-23.7 10.1" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round"/><path d="M42 13v12H30" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><path d="M22 51V39h12" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/></svg>`
  let link = document.querySelector('link[rel="icon"]')
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.type = 'image/svg+xml'
  link.href = `data:image/svg+xml,${encodeURIComponent(svg)}`
}

function fillQuestion(text) {
  question.value = text
}

function formatTime(value) {
  if (!value) return '时间未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function viewHistory(item) {
  if (typeof item.result === 'string') {
    try {
      result.value = JSON.parse(item.result)
    } catch {
      result.value = { answer: item.result, plans: [], materials: [], steps: [], sources: [], warnings: [] }
    }
  } else {
    result.value = item.result
  }
  page.value = 'result'
}

async function healthCheck() {
  health.value = '服务连接中'
  try {
    const d = await request({ url: '/health' })
    health.value = d?.status === 'ok' ? '服务正常' : '服务已连接'
  } catch (e) {
    health.value = `服务暂不可用：${e.message}`
  }
}

async function load() {
  const [p, t, h] = await Promise.all([
    request({ url: '/profile' }),
    request({ url: '/todos' }),
    request({ url: '/history' }),
  ])
  profile.value = p || profile.value
  todos.value = t || []
  history.value = h || []
}

async function submitAuth() {
  busy.value = true
  notice.value = ''
  try {
    if (mode.value === 'register') {
      await request({ method: 'post', url: '/auth/register', data: auth.value })
      mode.value = 'login'
      say('注册成功，请登录。')
    } else {
      const d = await request({ method: 'post', url: '/auth/login', data: auth.value })
      localStorage.setItem('campusflow_token', d.access_token)
      user.value = d.user
      await load()
      page.value = 'query'
      say('登录成功。')
    }
  } catch (e) {
    fail(e)
  } finally {
    busy.value = false
  }
}

function logout() {
  localStorage.removeItem('campusflow_token')
  user.value = null
  page.value = 'login'
}

async function saveProfile() {
  try {
    profile.value = await request({ method: 'put', url: '/profile', data: profile.value })
    say('画像已保存。')
  } catch (e) {
    fail(e)
  }
}

async function query() {
  busy.value = true
  try {
    result.value = await request({ method: 'post', url: '/query', data: { question: question.value } })
    history.value = await request({ url: '/history' })
    page.value = 'result'
  } catch (e) {
    fail(e)
  } finally {
    busy.value = false
  }
}

async function reloadTodos() {
  todos.value = await request({ url: '/todos' })
}

async function addTodo() {
  try {
    await request({ method: 'post', url: '/todos', data: { ...todo.value, completed: false, due_at: null } })
    todo.value = { title: '', notes: '' }
    await reloadTodos()
  } catch (e) {
    fail(e)
  }
}

async function toggle(t) {
  try {
    await request({
      method: 'put',
      url: `/todos/${t.id}`,
      data: { title: t.title, notes: t.notes || '', completed: !t.completed, due_at: t.due_at || null },
    })
    await reloadTodos()
  } catch (e) {
    fail(e)
  }
}

async function removeTodo(id) {
  try {
    await request({ method: 'delete', url: `/todos/${id}` })
    await reloadTodos()
  } catch (e) {
    fail(e)
  }
}

async function addSteps(plan) {
  try {
    await Promise.all(
      (plan.steps || []).map(title =>
        request({
          method: 'post',
          url: '/todos',
          data: { title, notes: `来自：${plan.title}`, completed: false, due_at: null },
        }),
      ),
    )
    await reloadTodos()
    page.value = 'todos'
    say('办理步骤已加入待办。')
  } catch (e) {
    fail(e)
  }
}

async function removeHistory(id) {
  try {
    await request({ method: 'delete', url: `/history/${id}` })
    history.value = await request({ url: '/history' })
  } catch (e) {
    fail(e)
  }
}

onMounted(async () => {
  setFavicon()
  healthCheck()
  if (!localStorage.getItem('campusflow_token')) return
  try {
    user.value = await request({ url: '/auth/me' })
    await load()
    page.value = 'query'
  } catch {
    logout()
  }
})
</script>

<template>
  <div v-if="!user" class="auth-shell">
    <section class="auth-hero">
      <div class="brand-mark">邮</div>
      <p class="eyebrow">北邮校园事务智能办理助手</p>
      <h1>邮智办</h1>
      <p class="hero-copy">校园事务，一问即办。</p>
      <div class="service-pill" :class="{ offline: health.includes('暂不可用') }">
        <span></span>{{ health }}
      </div>
    </section>

    <main class="auth-panel">
      <p v-if="notice" :class="['notice', { bad }]">{{ notice }}</p>
      <section class="card auth-card">
        <p class="section-kicker">{{ mode === 'login' ? '欢迎回来' : '创建账号' }}</p>
        <h2>{{ mode === 'login' ? '登录邮智办' : '注册学生账号' }}</h2>
        <p class="muted">账号仅限字母、数字、下划线；密码至少 8 位。</p>
        <form class="form" @submit.prevent="submitAuth">
          <label>
            <span>账号</span>
            <input v-model.trim="auth.username" placeholder="请输入账号" minlength="3" required>
          </label>
          <label>
            <span>密码</span>
            <input v-model="auth.password" type="password" placeholder="请输入密码" minlength="8" required>
          </label>
          <button class="primary full" :disabled="busy">
            {{ busy ? '处理中...' : mode === 'login' ? '登录' : '注册' }}
          </button>
        </form>
        <div class="auth-actions">
          <button class="text-button" type="button" @click="mode = mode === 'login' ? 'register' : 'login'">
            {{ mode === 'login' ? '没有账号？注册' : '已有账号？登录' }}
          </button>
          <button class="ghost" type="button" @click="healthCheck">重新检测服务</button>
        </div>
      </section>
    </main>
  </div>

  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-mark small">邮</div>
        <div>
          <strong>邮智办</strong>
          <span>北邮校园事务智能办理助手</span>
        </div>
      </div>

      <div class="service-status" :class="{ offline: health.includes('暂不可用') }">
        <span></span>{{ health }}
      </div>

      <nav class="side-nav">
        <button
          v-for="item in navItems"
          :key="item.key"
          :class="{ active: activePage === item.key }"
          type="button"
          @click="page = item.key"
        >
          {{ item.label }}
        </button>
      </nav>

      <div class="user-box">
        <span>{{ user.username }}</span>
        <button class="text-button" type="button" @click="logout">退出登录</button>
      </div>
    </aside>

    <main class="content">
      <p v-if="notice" :class="['notice', { bad }]">{{ notice }}</p>

      <section v-if="page === 'query'" class="assistant-page">
        <div class="page-heading">
          <p class="section-kicker">AI 办理入口</p>
          <h1>你好，我是邮智办</h1>
          <p>告诉我你遇到的校园事务问题，我会结合你的学生画像和知识库信息整理办理建议。</p>
        </div>

        <section class="query-card card">
          <form class="query-form" @submit.prevent="query">
            <label>
              <span>校园事务问题</span>
              <textarea
                v-model.trim="question"
                rows="7"
                maxlength="2000"
                placeholder="例如：我最近生病了，想了解缓考申请需要准备什么材料。"
                required
              ></textarea>
            </label>
            <div class="quick-row">
              <button v-for="item in quickQuestions" :key="item" class="chip" type="button" @click="fillQuestion(item)">
                {{ item }}
              </button>
            </div>
            <button class="primary query-submit" :disabled="busy">
              {{ busy ? '生成中...' : '获取办理方案' }}
            </button>
          </form>
        </section>
      </section>

      <section v-if="page === 'profile'" class="stack">
        <div class="page-heading compact">
          <p class="section-kicker">我的画像</p>
          <h1>让办理建议更贴近你</h1>
          <p>学生画像会用于个性化事务匹配，保存后再次查询会带入你的学院、年级、培养层次和校区。</p>
        </div>

        <section class="profile-overview">
          <div class="overview-main">
            <span>当前画像</span>
            <strong>{{ profileSummary }}</strong>
          </div>
          <div class="overview-meta">{{ profile.college || '学院待完善' }}</div>
        </section>

        <section class="card">
          <form class="profile-form" @submit.prevent="saveProfile">
            <label>
              <span>学院</span>
              <input v-model.trim="profile.college" placeholder="例如：计算机学院">
            </label>
            <label>
              <span>年级</span>
              <input v-model.trim="profile.grade" placeholder="例如：2024">
            </label>
            <label>
              <span>培养层次</span>
              <select v-model="profile.education_level">
                <option>本科</option>
                <option>硕士</option>
                <option>博士</option>
              </select>
            </label>
            <label>
              <span>校区</span>
              <input v-model.trim="profile.campus" placeholder="例如：海南">
            </label>
            <button class="primary form-submit">保存 Profile</button>
          </form>
        </section>
      </section>

      <section v-if="page === 'result'" class="stack">
        <div class="page-heading compact">
          <p class="section-kicker">办理结果</p>
          <h1>AI 办理建议</h1>
          <p>以下内容来自本次查询结果，可按需将办理步骤加入待办。</p>
        </div>

        <template v-if="result">
          <section class="answer-card card">
            <div class="result-card-title">
              <span>AI 办理建议</span>
              <small v-if="result.mode">生成模式：{{ result.mode }}</small>
            </div>
            <p>{{ result.answer || '本次查询暂未返回文字建议。' }}</p>
          </section>

          <section class="result-section">
            <h2>办理方案</h2>
            <article v-for="plan in list(result.plans)" :key="plan.affair_id || plan.title" class="plan-card card">
              <div class="plan-head">
                <div>
                  <span class="plan-label">方案</span>
                  <h3>{{ plan.title || '未命名办理方案' }}</h3>
                </div>
                <button class="ghost" type="button" :disabled="!list(plan.steps).length" @click="addSteps(plan)">
                  将办理步骤加入 Todo
                </button>
              </div>

              <div class="plan-grid">
                <div class="info-block">
                  <h4>所需材料</h4>
                  <ul v-if="list(plan.materials).length" class="plain-list">
                    <li v-for="x in list(plan.materials)" :key="x">{{ x }}</li>
                  </ul>
                  <p v-else class="empty-inline">暂无材料信息</p>
                </div>

                <div class="info-block">
                  <h4>办理地点 / 联系信息</h4>
                  <p><b>地点：</b>{{ plan.location || '暂无' }} {{ plan.room || '' }}</p>
                  <p><b>联系人：</b>{{ plan.contact || '暂无' }}</p>
                  <p><b>办公时间：</b>{{ plan.office_hours || '暂无' }}</p>
                </div>
              </div>

              <div class="steps-block">
                <h4>办理步骤</h4>
                <ol v-if="list(plan.steps).length" class="steps-list">
                  <li v-for="x in list(plan.steps)" :key="x">
                    <span>{{ x }}</span>
                  </li>
                </ol>
                <p v-else class="empty-inline">暂无步骤信息</p>
              </div>
            </article>
            <div v-if="!list(result.plans).length" class="empty-card">
              暂未获取到结构化办理方案
            </div>
          </section>

          <section class="result-section">
            <h2>信息来源</h2>
            <div v-if="list(result.sources).length" class="source-grid">
              <article v-for="s in list(result.sources)" :key="`${s.title || ''}-${s.reference || ''}`" class="source-card">
                <strong>{{ s.title || '来源资料' }}</strong>
                <span>{{ s.reference || '暂无引用信息' }}</span>
              </article>
            </div>
            <div v-else class="empty-card slim">暂无来源信息</div>
          </section>

          <section v-if="list(result.warnings).length" class="result-section">
            <h2>注意事项</h2>
            <div class="warning-list">
              <p v-for="w in list(result.warnings)" :key="w" class="warning">注意：{{ w }}</p>
            </div>
          </section>
        </template>
        <section v-else class="empty-card">请先提交查询。</section>
      </section>

      <section v-if="page === 'todos'" class="stack">
        <div class="page-heading compact">
          <p class="section-kicker">我的待办</p>
          <h1>办理任务</h1>
          <p>{{ completedCount }} / {{ todos.length }} 项已完成</p>
        </div>

        <section class="card">
          <form class="todo-form" @submit.prevent="addTodo">
            <input v-model.trim="todo.title" placeholder="待办标题" required>
            <input v-model.trim="todo.notes" placeholder="备注（可选）">
            <button class="primary">添加</button>
          </form>
        </section>

        <div v-if="!todos.length" class="empty-card">暂无待办。</div>
        <article v-for="t in todos" :key="t.id" class="todo-card">
          <label class="check-wrap">
            <input :checked="t.completed" type="checkbox" @change="toggle(t)">
            <span></span>
          </label>
          <div class="todo-body" :class="{ done: t.completed }">
            <strong>{{ t.title }}</strong>
            <p v-if="t.notes">{{ t.notes }}</p>
          </div>
          <button class="text-button danger" type="button" @click="removeTodo(t.id)">删除</button>
        </article>
      </section>

      <section v-if="page === 'history'" class="stack">
        <div class="page-heading compact">
          <p class="section-kicker">查询历史</p>
          <h1>最近的办理咨询</h1>
          <p>回看历史查询结果，或清理不再需要的记录。</p>
        </div>

        <div v-if="!history.length" class="empty-card">暂无历史记录。</div>
        <article v-for="h in history" :key="h.id" class="history-card">
          <div>
            <span>{{ formatTime(h.created_at) }}</span>
            <strong>{{ h.question }}</strong>
          </div>
          <div class="history-actions">
            <button class="ghost" type="button" @click="viewHistory(h)">查看结果</button>
            <button class="text-button danger" type="button" @click="removeHistory(h.id)">删除</button>
          </div>
        </article>
      </section>
    </main>
  </div>
</template>

<style>
:root {
  color: #172033;
  background: #eef4fb;
  font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
  font-synthesis: none;
  line-height: 1.5;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

button,
input,
textarea,
select {
  font: inherit;
}

button {
  border: 0;
}

button:disabled {
  cursor: not-allowed;
  opacity: .58;
}

.auth-shell {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(380px, 520px);
  min-height: 100vh;
  background: #f4f8ff;
}

.auth-hero {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 72px clamp(32px, 7vw, 112px);
}

.brand-mark {
  display: grid;
  width: 64px;
  height: 64px;
  margin-bottom: 28px;
  place-items: center;
  border-radius: 16px;
  color: #fff;
  background: #1c5fc4;
  box-shadow: 0 14px 32px rgba(24, 78, 164, .22);
  font-size: 28px;
  font-weight: 800;
}

.brand-mark.small {
  flex: 0 0 auto;
  width: 42px;
  height: 42px;
  margin: 0;
  border-radius: 12px;
  font-size: 20px;
}

.eyebrow,
.section-kicker,
.plan-label {
  margin: 0 0 8px;
  color: #2967bc;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
}

.auth-hero h1 {
  margin: 0;
  font-size: clamp(44px, 6vw, 80px);
  line-height: 1.05;
  letter-spacing: 0;
}

.hero-copy {
  max-width: 520px;
  margin: 22px 0 28px;
  color: #40516d;
  font-size: 22px;
}

.service-pill,
.service-status {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid #c7e4d4;
  border-radius: 999px;
  color: #17633f;
  background: #f0fbf5;
  font-size: 13px;
  font-weight: 700;
}

.service-pill span,
.service-status span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #18a058;
}

.service-pill.offline,
.service-status.offline {
  border-color: #f4c7c7;
  color: #9f1d28;
  background: #fff3f3;
}

.service-pill.offline span,
.service-status.offline span {
  background: #d9293e;
}

.auth-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 32px;
}

.card,
.empty-card,
.todo-card,
.history-card {
  border: 1px solid #dbe6f5;
  border-radius: 8px;
  background: rgba(255, 255, 255, .94);
  box-shadow: 0 18px 45px rgba(35, 64, 112, .08);
}

.auth-card,
.card {
  padding: 28px;
}

.auth-card h2,
.page-heading h1 {
  margin: 0;
  color: #111a2d;
  font-size: 30px;
  line-height: 1.18;
  letter-spacing: 0;
}

.muted,
.page-heading p,
.info-block p,
.todo-body p {
  color: #64748b;
}

.form,
.query-form,
.profile-form {
  display: grid;
  gap: 16px;
}

label span {
  display: block;
  margin-bottom: 7px;
  color: #35445f;
  font-size: 14px;
  font-weight: 700;
}

input,
textarea,
select {
  width: 100%;
  border: 1px solid #cbd8ea;
  border-radius: 7px;
  outline: none;
  background: #fff;
  color: #172033;
  transition: border-color .18s ease, box-shadow .18s ease;
}

input,
select {
  height: 44px;
  padding: 0 13px;
}

textarea {
  min-height: 180px;
  resize: vertical;
  padding: 13px;
}

input:focus,
textarea:focus,
select:focus {
  border-color: #2f72d8;
  box-shadow: 0 0 0 3px rgba(47, 114, 216, .13);
}

.primary,
.ghost,
.text-button,
.chip {
  min-height: 40px;
  border-radius: 7px;
  cursor: pointer;
}

.primary {
  padding: 0 18px;
  color: #fff;
  background: #1f62c9;
  font-weight: 700;
  box-shadow: 0 10px 20px rgba(31, 98, 201, .18);
}

.primary:hover {
  background: #1858b8;
}

.full {
  width: 100%;
}

.ghost,
.chip {
  padding: 0 14px;
  border: 1px solid #cbd8ea;
  color: #225aab;
  background: #f6f9fe;
  font-weight: 700;
}

.text-button {
  padding: 0;
  color: #225aab;
  background: transparent;
  font-weight: 700;
}

.danger {
  color: #b42332;
}

.auth-actions,
.quick-row,
.history-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.auth-actions {
  justify-content: space-between;
  margin-top: 18px;
}

.notice {
  margin: 0 0 18px;
  padding: 12px 14px;
  border: 1px solid #bfe6cf;
  border-radius: 8px;
  color: #17633f;
  background: #effbf5;
  font-weight: 700;
}

.notice.bad {
  border-color: #fac8ce;
  color: #9f1d28;
  background: #fff2f4;
}

.app-shell {
  display: grid;
  grid-template-columns: 272px minmax(0, 1fr);
  min-height: 100vh;
  background: #eef4fb;
}

.sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 22px;
  border-right: 1px solid #d7e3f3;
  background: #fff;
}

.sidebar-brand {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 22px;
}

.sidebar-brand strong,
.user-box span {
  display: block;
  color: #111a2d;
  font-size: 18px;
}

.sidebar-brand span {
  display: block;
  margin-top: 2px;
  color: #718096;
  font-size: 12px;
}

.service-status {
  margin-bottom: 24px;
}

.side-nav {
  display: grid;
  gap: 8px;
}

.side-nav button {
  width: 100%;
  min-height: 44px;
  padding: 0 14px;
  border-radius: 8px;
  color: #334155;
  background: transparent;
  text-align: left;
  cursor: pointer;
  font-weight: 700;
}

.side-nav button:hover {
  background: #f0f5fc;
}

.side-nav button.active {
  color: #fff;
  background: #1f62c9;
  box-shadow: 0 10px 24px rgba(31, 98, 201, .18);
}

.user-box {
  margin-top: auto;
  padding-top: 18px;
  border-top: 1px solid #e5edf7;
}

.user-box .text-button {
  margin-top: 8px;
}

.content {
  width: min(1120px, 100%);
  margin: 0 auto;
  padding: 44px clamp(20px, 4vw, 54px);
}

.assistant-page,
.stack {
  display: grid;
  gap: 20px;
}

.page-heading {
  max-width: 780px;
}

.page-heading.compact {
  max-width: 860px;
}

.page-heading p {
  margin: 12px 0 0;
  font-size: 16px;
}

.query-card {
  max-width: 900px;
}

.query-submit {
  justify-self: end;
  min-width: 156px;
}

.profile-overview {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 24px 28px;
  border: 1px solid #cfdff3;
  border-radius: 8px;
  color: #fff;
  background: #1f4f99;
}

.overview-main span,
.overview-meta {
  color: #cfe0fb;
}

.overview-main strong {
  display: block;
  margin-top: 6px;
  font-size: 26px;
  letter-spacing: 0;
}

.overview-meta {
  align-self: center;
  font-weight: 700;
}

.profile-form {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.form-submit {
  justify-self: start;
  min-width: 140px;
}

.answer-card p {
  margin: 18px 0 0;
  color: #273449;
  font-size: 17px;
  white-space: pre-wrap;
}

.result-card-title,
.plan-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.result-card-title span,
.result-section h2 {
  color: #111a2d;
  font-size: 20px;
  font-weight: 800;
}

.result-card-title small {
  color: #718096;
}

.result-section {
  display: grid;
  gap: 14px;
}

.result-section h2 {
  margin: 6px 0 0;
}

.plan-card {
  padding: 24px;
}

.plan-card h3 {
  margin: 0;
  color: #111a2d;
  font-size: 22px;
}

.plan-card h4 {
  margin: 0 0 10px;
  color: #263750;
  font-size: 15px;
}

.plan-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, .8fr);
  gap: 18px;
  margin-top: 20px;
}

.info-block,
.steps-block {
  padding: 16px;
  border: 1px solid #e1eaf6;
  border-radius: 8px;
  background: #f8fbff;
}

.plain-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 20px;
}

.steps-block {
  margin-top: 18px;
}

.steps-list {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: step;
}

.steps-list li {
  display: grid;
  grid-template-columns: 30px 1fr;
  gap: 12px;
  align-items: start;
  counter-increment: step;
}

.steps-list li::before {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 999px;
  color: #fff;
  background: #2f72d8;
  content: counter(step);
  font-size: 13px;
  font-weight: 800;
}

.empty-card {
  padding: 22px;
  color: #64748b;
  text-align: center;
}

.empty-card.slim {
  padding: 16px;
  text-align: left;
}

.empty-inline {
  margin: 0;
  color: #718096;
}

.source-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.source-card {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px solid #dfe8f5;
  border-radius: 8px;
  background: #fff;
}

.source-card strong {
  color: #263750;
}

.source-card span {
  color: #64748b;
  font-size: 14px;
}

.warning-list {
  display: grid;
  gap: 10px;
}

.warning {
  margin: 0;
  padding: 13px 14px;
  border: 1px solid #f0d59c;
  border-radius: 8px;
  color: #7a4c05;
  background: #fff9e8;
}

.todo-form {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) auto;
  gap: 12px;
}

.todo-card,
.history-card {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 18px;
}

.check-wrap {
  display: block;
  position: relative;
  width: 22px;
  height: 22px;
  margin: 0;
}

.check-wrap input {
  position: absolute;
  width: 22px;
  height: 22px;
  margin: 0;
  opacity: 0;
  cursor: pointer;
}

.check-wrap span {
  display: block;
  width: 22px;
  height: 22px;
  border: 2px solid #a9b9cf;
  border-radius: 6px;
  background: #fff;
}

.check-wrap input:checked + span {
  border-color: #18a058;
  background: #18a058;
}

.check-wrap input:checked + span::after {
  display: block;
  width: 6px;
  height: 11px;
  margin: 2px 0 0 6px;
  border: solid #fff;
  border-width: 0 2px 2px 0;
  content: "";
  transform: rotate(45deg);
}

.todo-body {
  flex: 1;
  min-width: 0;
}

.todo-body strong,
.history-card strong {
  display: block;
  color: #172033;
  overflow-wrap: anywhere;
}

.todo-body p {
  margin: 4px 0 0;
}

.todo-body.done strong,
.todo-body.done p {
  color: #94a3b8;
  text-decoration: line-through;
}

.history-card {
  justify-content: space-between;
}

.history-card span {
  display: block;
  margin-bottom: 6px;
  color: #718096;
  font-size: 13px;
}

@media (max-width: 900px) {
  .auth-shell,
  .app-shell {
    grid-template-columns: 1fr;
  }

  .auth-hero {
    padding: 40px 24px 20px;
  }

  .auth-panel {
    padding: 20px;
  }

  .sidebar {
    position: static;
    height: auto;
    padding: 16px;
  }

  .side-nav {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .side-nav button {
    text-align: center;
  }

  .user-box {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-top: 16px;
  }

  .content {
    padding-top: 28px;
  }

  .plan-grid,
  .profile-form,
  .todo-form {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .auth-hero h1,
  .page-heading h1 {
    font-size: 34px;
  }

  .side-nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .profile-overview,
  .plan-head,
  .result-card-title,
  .todo-card,
  .history-card {
    align-items: stretch;
    flex-direction: column;
  }

  .history-actions {
    width: 100%;
  }

  .history-actions .ghost {
    flex: 1;
  }
}
</style>
