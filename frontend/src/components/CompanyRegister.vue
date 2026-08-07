<script setup>
import axios from 'axios'
import { ref } from 'vue'

const emit = defineEmits(['registered'])
const API = 'http://127.0.0.1:8000'
const error = ref('')
const form = ref({
  email: '',
  password: '',
  company_name: '',
  hr_contact: '',
  website: '',
})

async function register() {
  error.value = ''
  try {
    const response = await axios.post(`${API}/company/register`, form.value)
    emit('registered', response.data.message)
  } catch (err) {
    error.value = err.response?.data?.message || 'Company registration failed'
  }
}
</script>

<template>
  <form class="card card-body" @submit.prevent="register">
    <h4 class="mb-3">Company Registration</h4>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div class="mb-2">
      <label class="form-label">Email</label>
      <input v-model="form.email" class="form-control" type="email" required />
    </div>
    <div class="mb-2">
      <label class="form-label">Password</label>
      <input v-model="form.password" class="form-control" type="password" required />
    </div>
    <div class="mb-2">
      <label class="form-label">Company Name</label>
      <input v-model="form.company_name" class="form-control" required />
    </div>
    <div class="mb-2">
      <label class="form-label">HR Contact (email or phone)</label>
      <input v-model="form.hr_contact" class="form-control" placeholder="hr@company.com / +91 98765 43210" />
    </div>
    <div class="mb-2">
      <label class="form-label">Website</label>
      <input v-model="form.website" class="form-control" required />
    </div>
    <button class="btn btn-success mt-2" type="submit">Register Company</button>
  </form>
</template>
