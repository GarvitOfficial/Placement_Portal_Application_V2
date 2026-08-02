<script setup>
import axios from 'axios'
import { onMounted, ref } from 'vue'

const emit = defineEmits(['registered'])
const API = 'http://127.0.0.1:8000'
const error = ref('')
const departmentOptions = ref([])
const form = ref({
  username: '',
  email: '',
  password: '',
  full_name: '',
  cgpa: '',
  branch: '',
  year: '',
})

async function loadDepartments() {
  try {
    const response = await axios.get(`${API}/departments`)
    departmentOptions.value = response.data
  } catch (err) {
    departmentOptions.value = ['CSE', 'ECE', 'EEE', 'IT', 'Mechanical', 'Civil', 'Chemical', 'Biotechnology']
  }
}

async function register() {
  error.value = ''
  try {
    const response = await axios.post(`${API}/student/register`, form.value)
    emit('registered', response.data.message)
  } catch (err) {
    error.value = err.response?.data?.message || 'Student registration failed'
  }
}

onMounted(loadDepartments)
</script>

<template>
  <form class="card card-body" @submit.prevent="register">
    <h4 class="mb-3">Student Registration</h4>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div class="mb-2">
      <label class="form-label">Username</label>
      <input v-model="form.username" class="form-control" required />
    </div>
    <div class="mb-2">
      <label class="form-label">Email</label>
      <input v-model="form.email" class="form-control" type="email" required />
    </div>
    <div class="mb-2">
      <label class="form-label">Password</label>
      <input v-model="form.password" class="form-control" type="password" required />
    </div>
    <div class="mb-2">
      <label class="form-label">Full Name</label>
      <input v-model="form.full_name" class="form-control" required />
    </div>
    <div class="row">
      <div class="col-md-4 mb-2">
        <label class="form-label">CGPA</label>
        <input v-model="form.cgpa" class="form-control" type="number" min="0" max="10" step="0.01" required />
      </div>
      <div class="col-md-4 mb-2">
        <label class="form-label">Branch</label>
        <select v-model="form.branch" class="form-select" required>
          <option value="" disabled>Select branch</option>
          <option v-for="dept in departmentOptions" :key="dept" :value="dept">{{ dept }}</option>
        </select>
      </div>
      <div class="col-md-4 mb-2">
        <label class="form-label">Year</label>
        <input v-model="form.year" class="form-control" type="number" min="1" max="5" required />
      </div>
    </div>
    <button class="btn btn-success mt-2" type="submit">Register Student</button>
  </form>
</template>
