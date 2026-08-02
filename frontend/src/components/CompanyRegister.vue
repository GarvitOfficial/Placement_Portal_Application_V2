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
  company_name: '',
  hr_contact: '',
  website: '',
  departments: [],
})

async function loadDepartments() {
  try {
    const response = await axios.get(`${API}/departments`)
    departmentOptions.value = response.data
  } catch (err) {
    departmentOptions.value = ['CSE', 'ECE', 'EEE', 'IT', 'Mechanical', 'Civil', 'Chemical', 'Biotechnology']
  }
}

function toggleDepartment(dept) {
  const index = form.value.departments.indexOf(dept)
  if (index === -1) {
    form.value.departments.push(dept)
  } else {
    form.value.departments.splice(index, 1)
  }
}

async function register() {
  error.value = ''
  try {
    const response = await axios.post(`${API}/company/register`, form.value)
    emit('registered', response.data.message)
  } catch (err) {
    error.value = err.response?.data?.message || 'Company registration failed'
  }
}

onMounted(loadDepartments)
</script>

<template>
  <form class="card card-body" @submit.prevent="register">
    <h4 class="mb-3">Company Registration</h4>
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
    <div class="mb-2">
      <label class="form-label">Departments You Hire From</label>
      <div class="d-flex flex-wrap gap-2">
        <div v-for="dept in departmentOptions" :key="dept" class="form-check">
          <input
            :id="`reg-dept-${dept}`"
            class="form-check-input"
            type="checkbox"
            :value="dept"
            :checked="form.departments.includes(dept)"
            @change="toggleDepartment(dept)"
          />
          <label class="form-check-label" :for="`reg-dept-${dept}`">{{ dept }}</label>
        </div>
      </div>
      <small class="text-muted">Select the departments eligible for your placement drives.</small>
    </div>
    <button class="btn btn-success mt-2" type="submit">Register Company</button>
  </form>
</template>
