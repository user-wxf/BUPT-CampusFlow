import axios from 'axios'
const api = axios.create({ baseURL: '/api', timeout: 30000 })
api.interceptors.request.use((config) => { const token = localStorage.getItem('campusflow_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })
export async function request(config) { try { const response = await api(config); if (response.data?.code !== 0) throw new Error(response.data?.message || '请求失败'); return response.data.data } catch (error) { throw new Error(error.response?.data?.message || error.message || '无法连接后端服务') } }
export default api
