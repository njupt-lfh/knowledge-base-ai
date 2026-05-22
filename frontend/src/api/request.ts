import axios from 'axios'

const request = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 60000,
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export default request
