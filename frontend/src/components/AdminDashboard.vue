<script setup>
import axios from 'axios'
import { onMounted, ref } from 'vue'

defineProps({ user: { type: Object, required: true } })
const emit = defineEmits(['logout'])
const API = 'http://127.0.0.1:8000'

const dashboard = ref({})
const stats = ref(null)
const studentQuery = ref('')
const companyQuery = ref('')
const students = ref([])
const companies = ref([])
const drives = ref([])
const applications = ref([])
const message = ref('')
const error = ref('')

// Advanced student search filters
const studentBranch = ref('')
const studentYear = ref('')
const studentMinCgpa = ref('')
const studentMaxCgpa = ref('')

// Export controls
const exportType = ref('students')
const exportEmail = ref('')
const exportFile = ref('')
const exportEmailed = ref(false)
const exporting = ref(false)

async function loadData() {
  error.value = ''
  try {
    const [dash, statsRes, studentList, companyList, driveList, appList] = await Promise.all([
      axios.get(`${API}/admin/dashboard`),
      axios.get(`${API}/admin/stats`),
      axios.get(`${API}/admin/search/students`),
      axios.get(`${API}/admin/search/companies`),
      axios.get(`${API}/drives`),
      axios.get(`${API}/applications`),
    ])
    dashboard.value = dash.data
    stats.value = statsRes.data
    students.value = studentList.data
    companies.value = companyList.data
    drives.value = driveList.data
    applications.value = appList.data
  } catch (err) {
    error.value = err.response?.data?.message || 'Unable to load admin dashboard'
  }
}

function statusBadge(status) {
  const map = {
    Applied: 'text-bg-info',
    Shortlisted: 'text-bg-warning',
    Selected: 'text-bg-success',
    Rejected: 'text-bg-danger',
    Pending: 'text-bg-secondary',
    Approved: 'text-bg-success',
    Closed: 'text-bg-dark',
  }
  return map[status] || 'text-bg-secondary'
}

async function searchStudents() {
  const params = new URLSearchParams()
  if (studentQuery.value) params.append('q', studentQuery.value)
  if (studentBranch.value) params.append('branch', studentBranch.value)
  if (studentYear.value) params.append('year', studentYear.value)
  if (studentMinCgpa.value) params.append('min_cgpa', studentMinCgpa.value)
  if (studentMaxCgpa.value) params.append('max_cgpa', studentMaxCgpa.value)
  const response = await axios.get(`${API}/admin/search/students?${params.toString()}`)
  students.value = response.data
}

async function searchCompanies() {
  const response = await axios.get(`${API}/admin/search/companies?q=${encodeURIComponent(companyQuery.value)}`)
  companies.value = response.data
}

async function exportData() {
  message.value = ''
  error.value = ''
  exportFile.value = ''
  exportEmailed.value = false
  exporting.value = true
  try {
    const response = await axios.post(`${API}/admin/export`, {
      type: exportType.value,
      email: exportEmail.value,
    })
    exportFile.value = response.data.filename
    exportEmailed.value = response.data.emailed
    message.value = response.data.emailed
      ? `Export ready and emailed to ${response.data.email_to}`
      : exportEmail.value
        ? `Export ready, but email could not be sent (set SMTP_USER / SMTP_PASSWORD env vars)`
        : 'Export ready'
  } catch (err) {
    error.value = err.response?.data?.message || 'Export failed'
  } finally {
    exporting.value = false
  }
}

async function action(url) {
  message.value = ''
  error.value = ''
  try {
    const response = await axios.put(`${API}${url}`)
    message.value = response.data.message
    await loadData()
  } catch (err) {
    error.value = err.response?.data?.message || 'Action failed'
  }
}

onMounted(loadData)
</script>

<template>
  <div>
    <nav class="navbar navbar-light bg-light mb-4 px-3">
      <span class="navbar-brand mb-0 h1">Admin Dashboard</span>
      <button class="btn btn-outline-secondary" type="button" @click="emit('logout')">Logout</button>
    </nav>

    <div v-if="message" class="alert alert-success">{{ message }}</div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <div class="row mb-4">
      <div class="col-md-3 mb-2">
        <div class="card card-body"><strong>Students</strong><span>{{ dashboard.students }}</span></div>
      </div>
      <div class="col-md-3 mb-2">
        <div class="card card-body"><strong>Companies</strong><span>{{ dashboard.companies }}</span></div>
      </div>
      <div class="col-md-3 mb-2">
        <div class="card card-body"><strong>Drives</strong><span>{{ dashboard.drives }}</span></div>
      </div>
      <div class="col-md-3 mb-2">
        <div class="card card-body"><strong>Applications</strong><span>{{ dashboard.applications }}</span></div>
      </div>
    </div>

    <div v-if="stats" class="card card-body mb-4">
      <h4>Placement Statistics</h4>
      <div class="row text-center mb-3">
        <div class="col-md-2 col-4 mb-2">
          <div class="border rounded p-2"><strong>{{ stats.drives_conducted }}</strong><br /><small class="text-muted">Drives Conducted</small></div>
        </div>
        <div class="col-md-2 col-4 mb-2">
          <div class="border rounded p-2"><strong>{{ stats.drives_pending }}</strong><br /><small class="text-muted">Drives Pending</small></div>
        </div>
        <div class="col-md-2 col-4 mb-2">
          <div class="border rounded p-2"><strong>{{ stats.students_applied }}</strong><br /><small class="text-muted">Students Applied</small></div>
        </div>
        <div class="col-md-2 col-4 mb-2">
          <div class="border rounded p-2"><strong>{{ stats.students_shortlisted }}</strong><br /><small class="text-muted">Shortlisted</small></div>
        </div>
        <div class="col-md-2 col-4 mb-2">
          <div class="border rounded p-2"><strong>{{ stats.students_selected }}</strong><br /><small class="text-muted">Selected</small></div>
        </div>
        <div class="col-md-2 col-4 mb-2">
          <div class="border rounded p-2"><strong>{{ stats.selection_rate }}%</strong><br /><small class="text-muted">Selection Rate</small></div>
        </div>
      </div>
      <h6>Company-wise Placements</h6>
      <table class="table table-bordered table-sm">
        <thead>
          <tr><th>Company</th><th>Applications</th><th>Shortlisted</th><th>Selected</th></tr>
        </thead>
        <tbody>
          <tr v-if="!Object.keys(stats.per_company).length">
            <td colspan="4" class="text-center text-muted">No applications yet.</td>
          </tr>
          <tr v-for="(counts, name) in stats.per_company" :key="name">
            <td>{{ name }}</td>
            <td>{{ counts.applications }}</td>
            <td>{{ counts.shortlisted }}</td>
            <td>{{ counts.selected }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card card-body mb-4">
      <h4>Export Data</h4>
      <form class="row g-2 align-items-end" @submit.prevent="exportData">
        <div class="col-md-3">
          <label class="form-label">Export Type</label>
          <select v-model="exportType" class="form-select">
            <option value="students">Students</option>
            <option value="companies">Companies</option>
            <option value="applications">Applications</option>
          </select>
        </div>
        <div class="col-md-4">
          <label class="form-label">Email Export To (optional)</label>
          <input v-model="exportEmail" class="form-control" type="email" placeholder="recipient@example.com" />
        </div>
        <div class="col-md-3">
          <button class="btn btn-primary w-100" type="submit" :disabled="exporting">
            {{ exporting ? 'Exporting...' : 'Export CSV' }}
          </button>
        </div>
        <div class="col-md-2">
          <a v-if="exportFile" :href="`${API}/exports/${exportFile}`" class="btn btn-success w-100" download>Download</a>
        </div>
      </form>
      <p v-if="exportFile" class="mt-2 mb-0 text-muted">
        File: {{ exportFile }}
        <span v-if="exportEmail"> — {{ exportEmailed ? `emailed to ${exportEmail}` : 'email not sent (SMTP not configured)' }}</span>
      </p>
    </div>

    <div class="card card-body mb-4">
      <h4>Search Students</h4>
      <form class="row g-2 mb-3" @submit.prevent="searchStudents">
        <div class="col-md-4">
          <input v-model="studentQuery" class="form-control" placeholder="Name, email, or username" />
        </div>
        <div class="col-md-2">
          <input v-model="studentBranch" class="form-control" placeholder="Branch (e.g. CSE)" />
        </div>
        <div class="col-md-2">
          <input v-model="studentYear" class="form-control" type="number" min="1" max="5" placeholder="Year" />
        </div>
        <div class="col-md-2">
          <input v-model="studentMinCgpa" class="form-control" type="number" step="0.01" min="0" max="10" placeholder="Min CGPA" />
        </div>
        <div class="col-md-2">
          <input v-model="studentMaxCgpa" class="form-control" type="number" step="0.01" min="0" max="10" placeholder="Max CGPA" />
        </div>
        <div class="col-md-12">
          <button class="btn btn-primary" type="submit">Search</button>
        </div>
      </form>
      <table class="table table-bordered table-sm">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>CGPA</th>
            <th>Branch</th>
            <th>Year</th>
            <th>Blacklisted</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="student in students" :key="student.id">
            <td>{{ student.full_name }}</td>
            <td>{{ student.email }}</td>
            <td>{{ student.cgpa }}</td>
            <td>{{ student.branch }}</td>
            <td>{{ student.year }}</td>
            <td>{{ student.blacklisted ? 'Yes' : 'No' }}</td>
            <td>
              <button class="btn btn-outline-danger btn-sm" type="button" @click="action(`/admin/student/blacklist/${student.id}`)">
                Blacklist Student
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card card-body mb-4">
      <h4>Search Companies</h4>
      <form class="row mb-3" @submit.prevent="searchCompanies">
        <div class="col-md-10">
          <input v-model="companyQuery" class="form-control" placeholder="Company name" />
        </div>
        <div class="col-md-2">
          <button class="btn btn-primary w-100" type="submit">Search</button>
        </div>
      </form>
      <table class="table table-bordered table-sm">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Website</th>
            <th>Approved</th>
            <th>Blacklisted</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="company in companies" :key="company.id">
            <td>{{ company.company_name }}</td>
            <td>{{ company.email }}</td>
            <td>{{ company.website }}</td>
            <td>{{ company.approved ? 'Yes' : 'No' }}</td>
            <td>{{ company.blacklisted ? 'Yes' : 'No' }}</td>
            <td>
              <button class="btn btn-outline-success btn-sm me-1 mb-1" type="button" @click="action(`/admin/company/approve/${company.id}`)">Approve Company</button>
              <button class="btn btn-outline-warning btn-sm me-1 mb-1" type="button" @click="action(`/admin/company/reject/${company.id}`)">Reject Company</button>
              <button class="btn btn-outline-danger btn-sm mb-1" type="button" @click="action(`/admin/company/blacklist/${company.id}`)">Blacklist Company</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card card-body mb-4">
      <h4>Placement Drives</h4>
      <table class="table table-bordered table-sm">
        <thead>
          <tr>
            <th>Company</th>
            <th>Title</th>
            <th>Deadline</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="drive in drives" :key="drive.id">
            <td>{{ drive.company_name }}</td>
            <td>{{ drive.job_title }}</td>
            <td>{{ drive.deadline }}</td>
            <td><span class="badge" :class="statusBadge(drive.status)">{{ drive.status }}</span></td>
            <td>
              <button class="btn btn-outline-success btn-sm me-1" type="button" @click="action(`/admin/drive/approve/${drive.id}`)">Approve Drive</button>
              <button class="btn btn-outline-warning btn-sm" type="button" @click="action(`/admin/drive/reject/${drive.id}`)">Reject Drive</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card card-body">
      <h4>Applications</h4>
      <table class="table table-bordered table-sm">
        <thead>
          <tr>
            <th>Student</th>
            <th>Company</th>
            <th>Drive</th>
            <th>Status</th>
            <th>Applied On</th>
            <th>Interview</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="app in applications" :key="app.application_id">
            <td>{{ app.student_name }}</td>
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
