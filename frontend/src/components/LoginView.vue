<script setup>
import axios from 'axios'
import { ref } from 'vue'
import StudentRegister from './StudentRegister.vue'
import CompanyRegister from './CompanyRegister.vue'

const emit = defineEmits(['login'])
const API = 'http://127.0.0.1:8000'

const email = ref('')
const password = ref('')
const error = ref('')
const message = ref('')
const mode = ref('login')

async function login() {
  error.value = ''
  message.value = ''
  if (!email.value || !password.value) {
    error.value = 'Email and password are required'
    return
  }
  try {
    const response = await axios.post(`${API}/login`, {
      email: email.value,
      password: password.value,
    })
    emit('login', response.data)
  } catch (err) {
    error.value = err.response?.data?.message || 'Login failed'
  }
}

function registered(text) {
  message.value = text
  mode.value = 'login'
}
</script>

<template>
  <div class="row justify-content-center">
    <div class="col-lg-6">
      <h2 class="mb-3">Placement Portal Login</h2>

      <div class="mb-3">
        <button class="btn btn-primary me-2" type="button" @click="mode = 'login'">Login</button>
        <button class="btn btn-outline-primary me-2" type="button" @click="mode = 'student'">
          Student Registration
        </button>
        <button class="btn btn-outline-primary" type="button" @click="mode = 'company'">
          Company Registration
        </button>
      </div>

      <div v-if="message" class="alert alert-success">{{ message }}</div>
      <div v-if="error" class="alert alert-danger">{{ error }}</div>

      <form v-if="mode === 'login'" class="card card-body" @submit.prevent="login">
        <div class="mb-3">
          <label class="form-label">Email</label>
          <input v-model="email" class="form-control" type="email" required />
        </div>
        <div class="mb-3">
          <label class="form-label">Password</label>
          <input v-model="password" class="form-control" type="password" required />
        </div>
        <button class="btn btn-success" type="submit">Login</button>
      </form>

      <StudentRegister v-if="mode === 'student'" @registered="registered" />
      <CompanyRegister v-if="mode === 'company'" @registered="registered" />
    </div>
  </div>
</template>
