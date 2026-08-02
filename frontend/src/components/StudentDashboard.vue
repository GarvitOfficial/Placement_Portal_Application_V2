<script setup>
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'

const props = defineProps({ user: { type: Object, required: true } })
const emit = defineEmits(['logout'])
const API = 'http://127.0.0.1:8000'

const student = ref({})
const drives = ref([])
const applications = ref([])
const resume = ref(null)
const message = ref('')
const error = ref('')
const exportTaskId = ref('')
const exportFile = ref('')
const exporting = ref(false)
const departmentOptions = ref([])

// Drive filters (client-side over the approved drive list)
const driveSearch = ref('')
const driveBranch = ref('')
const driveMaxCgpa = ref('')
const driveDeadline = ref('')

const filteredDrives = computed(() => {
  return drives.value.filter((drive) => {
    if (driveSearch.value) {
      const q = driveSearch.value.toLowerCase()
      const haystack = `${drive.job_title} ${drive.company_name}`.toLowerCase()
      if (!haystack.includes(q)) return false
    }
    if (driveBranch.value) {
      const branches = drive.branches && drive.branches.length ? drive.branches : [drive.branch_required]
      if (!branches.some((b) => String(b).toLowerCase().includes(driveBranch.value.toLowerCase()))) return false
    }
    if (driveMaxCgpa.value !== '' && !Number.isNaN(Number(driveMaxCgpa.value))) {
      if (drive.cgpa_required > Number(driveMaxCgpa.value)) return false
    }
    if (driveDeadline.value && drive.deadline > driveDeadline.value) return false
    return true
  })
})

function clearDriveFilters() {
  driveSearch.value = ''
  driveBranch.value = ''
  driveMaxCgpa.value = ''
  driveDeadline.value = ''
}

function statusBadge(status) {
  const map = {
    Applied: 'text-bg-info',
    Shortlisted: 'text-bg-warning',
    Selected: 'text-bg-success',
    Rejected: 'text-bg-danger',
  }
  return map[status] || 'text-bg-secondary'
}

async function loadDepartments() {
  try {
    const response = await axios.get(`${API}/departments`)
    departmentOptions.value = response.data
  } catch (err) {
    departmentOptions.value = ['CSE', 'ECE', 'EEE', 'IT', 'Mechanical', 'Civil', 'Chemical', 'Biotechnology']
  }
}

async function loadData() {
  error.value = ''
  try {
    const studentId = props.user.student_id
    const [profile, driveList, history] = await Promise.all([
      axios.get(`${API}/student/profile/${studentId}`),
      axios.get(`${API}/drives?approved_only=true`),
      axios.get(`${API}/student/history/${studentId}`),
    ])
    student.value = profile.data
    drives.value = driveList.data
    applications.value = history.data
  } catch (err) {
    error.value = err.response?.data?.message || 'Unable to load dashboard'
  }
}

async function updateProfile() {
  message.value = ''
  error.value = ''
  try {
    const response = await axios.put(`${API}/student/profile/${student.value.id}`, student.value)
    student.value = response.data.student
    message.value = response.data.message
  } catch (err) {
    error.value = err.response?.data?.message || 'Profile update failed'
  }
}

async function uploadResume() {
  if (!resume.value) {
    error.value = 'Select a resume file'
    return
  }
  const data = new FormData()
  data.append('resume', resume.value)
  try {
    const response = await axios.post(`${API}/student/resume/${student.value.id}`, data)
    student.value.resume = response.data.filename
    message.value = response.data.message
  } catch (err) {
    error.value = err.response?.data?.message || 'Resume upload failed'
  }
}

async function apply(driveId) {
  message.value = ''
  error.value = ''
  try {
    const response = await axios.post(`${API}/apply`, {
      student_id: student.value.id,
      drive_id: driveId,
    })
    message.value = response.data.message
    await loadData()
  } catch (err) {
    error.value = err.response?.data?.message || 'Apply failed'
  }
}

async function exportCsv() {
  message.value = ''
  error.value = ''
  exportFile.value = ''
  exporting.value = true
  try {
    const response = await axios.post(`${API}/export/applications/${student.value.id}`)
    if (response.data.mode === 'sync') {
      exportFile.value = response.data.filename
      message.value = `Export Completed: ${response.data.filename}`
      exporting.value = false
    } else {
      exportTaskId.value = response.data.task_id
      pollExport(0)
    }
  } catch (err) {
    exporting.value = false
    error.value = err.response?.data?.message || 'Export failed'
  }
}

async function pollExport(attempts) {
  try {
    const response = await axios.get(`${API}/export/status/${exportTaskId.value}`)
    if (response.data.status === 'Export Completed') {
      exportFile.value = response.data.filename
      message.value = `Export Completed: ${response.data.filename}`
      exporting.value = false
      return
    }
    if (response.data.status === 'Failed') {
      error.value = response.data.message || 'Export failed'
      exporting.value = false
      return
    }
    if (attempts >= 20) {
      error.value = 'Export is taking too long. Please try again.'
      exporting.value = false
      return
    }
    setTimeout(() => pollExport(attempts + 1), 1500)
  } catch (err) {
    exporting.value = false
    error.value = err.response?.data?.message || 'Export status check failed'
  }
}

onMounted(() => {
  loadDepartments()
  loadData()
})
</script>

<template>
  <div>
    <nav class="navbar navbar-light bg-light mb-4 px-3">
      <span class="navbar-brand mb-0 h1">Student Dashboard</span>
      <button class="btn btn-outline-secondary" type="button" @click="emit('logout')">Logout</button>
    </nav>

    <div v-if="message" class="alert alert-success">{{ message }}</div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <div class="card card-body mb-4">
      <h4>Student Information</h4>
      <p class="mb-1"><strong>Name:</strong> {{ student.full_name }}</p>
      <p class="mb-1"><strong>Email:</strong> {{ student.email }}</p>
      <p class="mb-1"><strong>CGPA:</strong> {{ student.cgpa }}</p>
      <p class="mb-1"><strong>Branch:</strong> {{ student.branch }}</p>
      <p class="mb-0"><strong>Year:</strong> {{ student.year }}</p>
    </div>

    <div class="card card-body mb-4">
      <h4>Profile Update</h4>
      <form @submit.prevent="updateProfile">
        <div class="row">
          <div class="col-md-3 mb-2">
            <label class="form-label">Full Name</label>
            <input v-model="student.full_name" class="form-control" required />
          </div>
          <div class="col-md-3 mb-2">
            <label class="form-label">CGPA</label>
            <input v-model="student.cgpa" class="form-control" type="number" min="0" max="10" step="0.01" required />
          </div>
          <div class="col-md-3 mb-2">
            <label class="form-label">Branch</label>
            <select v-model="student.branch" class="form-select" required>
              <option v-if="student.branch && !departmentOptions.includes(student.branch)" :value="student.branch">{{ student.branch }}</option>
              <option v-for="dept in departmentOptions" :key="dept" :value="dept">{{ dept }}</option>
            </select>
          </div>
          <div class="col-md-3 mb-2">
            <label class="form-label">Year</label>
            <input v-model="student.year" class="form-control" type="number" min="1" max="5" required />
          </div>
        </div>
        <button class="btn btn-primary mt-2" type="submit">Update Profile</button>
      </form>
    </div>

    <div class="card card-body mb-4">
      <h4>Resume Upload</h4>
      <p v-if="student.resume" class="mb-2">Current resume: {{ student.resume }}</p>
      <input class="form-control mb-2" type="file" @change="resume = $event.target.files[0]" />
      <button class="btn btn-primary" type="button" @click="uploadResume">Upload Resume</button>
    </div>

    <div class="card card-body mb-4">
      <h4>Approved Drives</h4>
      <div class="row g-2 mb-3">
        <div class="col-md-3">
          <input v-model="driveSearch" class="form-control form-control-sm" placeholder="Search job title or company" />
        </div>
        <div class="col-md-2">
          <select v-model="driveBranch" class="form-select form-select-sm">
            <option value="">All Branches</option>
            <option v-for="dept in departmentOptions" :key="dept" :value="dept">{{ dept }}</option>
          </select>
        </div>
        <div class="col-md-2">
          <input v-model="driveMaxCgpa" class="form-control form-control-sm" type="number" step="0.1" min="0" max="10" placeholder="Max CGPA cutoff" />
        </div>
        <div class="col-md-3">
          <input v-model="driveDeadline" class="form-control form-control-sm" type="date" title="Deadline on or before" />
        </div>
        <div class="col-md-2">
          <button class="btn btn-outline-secondary btn-sm w-100" type="button" @click="clearDriveFilters">Clear Filters</button>
        </div>
      </div>
      <table class="table table-bordered table-sm">
        <thead>
          <tr>
            <th>Company</th>
            <th>Title</th>
            <th>CGPA</th>
            <th>Branch</th>
            <th>Year</th>
            <th>Deadline</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!filteredDrives.length">
            <td colspan="7" class="text-center text-muted">No drives match the selected filters.</td>
          </tr>
          <tr v-for="drive in filteredDrives" :key="drive.id">
            <td>{{ drive.company_name }}</td>
            <td>{{ drive.job_title }}</td>
            <td>{{ drive.cgpa_required }}</td>
            <td>{{ drive.branches && drive.branches.length ? drive.branches.join(', ') : drive.branch_required }}</td>
            <td>{{ drive.year_required }}</td>
            <td>{{ drive.deadline }}</td>
            <td><button class="btn btn-success btn-sm" type="button" @click="apply(drive.id)">Apply</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card card-body">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <h4 class="mb-0">My Applications</h4>
        <div>
          <button class="btn btn-outline-primary btn-sm" type="button" :disabled="exporting" @click="exportCsv">
            {{ exporting ? 'Exporting...' : 'Export CSV' }}
          </button>
          <a v-if="exportFile" :href="`${API}/exports/${exportFile}`" class="btn btn-success btn-sm ms-2" download>Download CSV</a>
        </div>
      </div>
      <table class="table table-bordered table-sm">
        <thead>
          <tr>
            <th>Company</th>
            <th>Drive</th>
            <th>Status</th>
            <th>Applied On</th>
            <th>Interview</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="app in applications" :key="app.application_id">
            <td>{{ app.company_name }}</td>
            <td>{{ app.job_title }}</td>
            <td><span class="badge" :class="statusBadge(app.status)">{{ app.status }}</span></td>
            <td>{{ app.application_date }}</td>
            <td>{{ app.interview_schedule }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
