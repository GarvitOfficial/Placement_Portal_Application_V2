<script setup>
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'
import LoginView from './components/LoginView.vue'
import StudentDashboard from './components/StudentDashboard.vue'
import CompanyDashboard from './components/CompanyDashboard.vue'
import AdminDashboard from './components/AdminDashboard.vue'

const user = ref(JSON.parse(localStorage.getItem('placement_user') || 'null'))

function applyAuthHeader(currentUser) {
  if (currentUser && currentUser.token) {
    axios.defaults.headers.common['Authorization'] = `Bearer ${currentUser.token}`
  } else {
    delete axios.defaults.headers.common['Authorization']
  }
}

const activeComponent = computed(() => {
  if (!user.value) return LoginView
  if (user.value.role === 'student') return StudentDashboard
  if (user.value.role === 'company') return CompanyDashboard
  if (user.value.role === 'admin') return AdminDashboard
  return LoginView
})

function setUser(nextUser) {
  user.value = nextUser
  localStorage.setItem('placement_user', JSON.stringify(nextUser))
  applyAuthHeader(nextUser)
}

function logout() {
  user.value = null
  localStorage.removeItem('placement_user')
  applyAuthHeader(null)
}

// On 401 (expired/invalid token) send the user back to the login screen.
axios.interceptors.response.use(
  (response) => response,
  (err) => {
    if (err.response && err.response.status === 401 && user.value) {
      logout()
    }
    return Promise.reject(err)
  }
)

onMounted(() => applyAuthHeader(user.value))
</script>

<template>
  <main class="container py-4">
    <component :is="activeComponent" :user="user" @login="setUser" @logout="logout" />
  </main>
</template>
