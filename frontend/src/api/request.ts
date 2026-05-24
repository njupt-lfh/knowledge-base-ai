import axios from 'axios'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8082',
  timeout: 60000,
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  },
)

export default request
