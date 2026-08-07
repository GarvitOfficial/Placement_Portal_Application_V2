<script setup>
import axios from 'axios'
import { onMounted, ref } from 'vue'

const props = defineProps({ user: { type: Object, required: true } })
const emit = defineEmits(['logout'])
const API = 'http://127.0.0.1:8000'

const company = ref({})
const drives = ref([])
const applications = ref([])
const message = ref('')
const error = ref('')
const departmentOptions = ref([])
const driveForm = ref({
  company_id: props.user.company_id,
  job_title: '',
  description: '',
  cgpa_required: '',
  branch_required: [],
  years: [],
  deadline: '',
})
const scheduleById = ref({})

async function loadDepartments() {
  try {
    const response = await axios.get(`${API}/departments`)
    departmentOptions.value = response.data
  } catch (err) {
    departmentOptions.value = ['CSE', 'ECE', 'EEE', 'IT', 'Mechanical', 'Civil', 'Chemical', 'Biotechnology']
  }
}

function toggleBranch(dept) {
  const index = driveForm.value.branch_required.indexOf(dept)
  if (index === -1) {
    driveForm.value.branch_required.push(dept)
  } else {
    driveForm.value.branch_required.splice(index, 1)
  }
}

function toggleYear(year) {
  const index = driveForm.value.years.indexOf(year)
  if (index === -1) {
    driveForm.value.years.push(year)
  } else {
    driveForm.value.years.splice(index, 1)
  }
}

async function loadData() {
  error.value = ''
  try {
    const [companies, driveList, appList] = await Promise.all([
      axios.get(`${API}/companies`),
      axios.get(`${API}/drives?company_id=${props.user.company_id}`),
      axios.get(`${API}/applications?company_id=${props.user.company_id}`),
    ])
    company.value = companies.data.find((item) => item.id === props.user.company_id) || {}
    if (!driveForm.value.branch_required.length && company.value.departments && company.value.departments.length) {
      driveForm.value.branch_required = [...company.value.departments]
    }
    drives.value = driveList.data.map((drive) => ({
      ...drive,
      applicants_count: appList.data.filter((app) => app.drive_id === drive.id).length,
    }))
    applications.value = appList.data
  } catch (err) {
    error.value = err.response?.data?.message || 'Unable to load company dashboard'
  }
}

async function createDrive() {
  message.value = ''
  error.value = ''
  try {
    const response = await axios.post(`${API}/drive/create`, driveForm.value)
    message.value = response.data.message
    driveForm.value = {
      company_id: props.user.company_id,
      job_title: '',
      description: '',
      cgpa_required: '',
      branch_required: company.value.departments ? [...company.value.departments] : [],
      years: [],
      deadline: '',
    }
    await loadData()
  } catch (err) {
    error.value = err.response?.data?.message || 'Drive creation failed'
  }
}

async function updateStatus(applicationId, status) {
  try {
    const response = await axios.put(`${API}/application/update/${applicationId}`, {
      status,
      company_id: props.user.company_id,
    })
    message.value = response.data.message
    await loadData()
  } catch (err) {
    error.value = err.response?.data?.message || 'Status update failed'
  }
}

async function schedule(applicationId) {
  if (!scheduleById.value[applicationId]) {
    error.value = 'Interview schedule is required'
    return
  }
  try {
    const response = await axios.put(`${API}/application/schedule/${applicationId}`, {
      interview_schedule: scheduleById.value[applicationId],
      company_id: props.user.company_id,
    })
    message.value = response.data.message
    await loadData()
  } catch (err) {
    error.value = err.response?.data?.message || 'Interview schedule failed'
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
      <span class="navbar-brand mb-0 h1">Company Dashboard</span>
      <button class="btn btn-outline-secondary" type="button" @click="emit('logout')">Logout</button>
    </nav>

    <div v-if="message" class="alert alert-success">{{ message }}</div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <div class="card card-body mb-4">
      <h4>Company Details</h4>
      <p class="mb-1"><strong>Name:</strong> {{ company.company_name }}</p>
      <p class="mb-1"><strong>Website:</strong> {{ company.website }}</p>
      <p class="mb-1"><strong>HR Contact:</strong> {{ company.hr_contact || 'Not provided' }}</p>
      <p class="mb-1"><strong>Departments:</strong> {{ company.departments && company.departments.length ? company.departments.join(', ') : 'Not specified' }}</p>
      <p class="mb-0"><strong>Status:</strong> {{ company.approved ? 'Approved' : 'Pending/Rejected' }}</p>
    </div>

    <div class="card card-body mb-4">
      <h4>Create Placement Drive</h4>
      <form @submit.prevent="createDrive">
        <div class="row">
          <div class="col-md-4 mb-2">
            <label class="form-label">Job Title</label>
            <input v-model="driveForm.job_title" class="form-control" required />
          </div>
          <div class="col-md-4 mb-2">
            <label class="form-label">CGPA Required</label>
            <input v-model="driveForm.cgpa_required" class="form-control" type="number" min="0" max="10" step="0.01" required />
          </div>
          <div class="col-md-4 mb-2">
            <label class="form-label">Deadline</label>
            <input v-model="driveForm.deadline" class="form-control" type="date" required />
          </div>
          <div class="col-md-4 mb-2">
            <label class="form-label">Eligible Years</label>
            <div class="d-flex flex-wrap gap-2">
              <div v-for="year in [2, 3, 4]" :key="year" class="form-check">
                <input
                  :id="`drive-year-${year}`"
                  class="form-check-input"
                  type="checkbox"
                  :value="year"
                  :checked="driveForm.years.includes(year)"
                  @change="toggleYear(year)"
                />
                <label class="form-check-label" :for="`drive-year-${year}`">Year {{ year }}</label>
              </div>
            </div>
            <small class="text-muted">Select all eligible years.</small>
          </div>
          <div class="col-md-12 mb-2">
            <label class="form-label">Eligible Departments</label>
            <div class="d-flex flex-wrap gap-2">
              <div v-for="dept in departmentOptions" :key="dept" class="form-check">
                <input
                  :id="`drive-dept-${dept}`"
                  class="form-check-input"
                  type="checkbox"
                  :value="dept"
                  :checked="driveForm.branch_required.includes(dept)"
                  @change="toggleBranch(dept)"
                />
                <label class="form-check-label" :for="`drive-dept-${dept}`">{{ dept }}</label>
              </div>
            </div>
            <small class="text-muted">Students from any selected department can apply.</small>
          </div>
          <div class="col-md-12 mb-2">
            <label class="form-label">Description</label>
            <textarea v-model="driveForm.description" class="form-control" required></textarea>
          </div>
        </div>
        <button class="btn btn-primary" type="submit">Create Drive</button>
      </form>
    </div>

    <div class="card card-body mb-4">
      <h4>Created Drives</h4>
      <table class="table table-bordered table-sm">
        <thead>
          <tr>
            <th>Title</th>
            <th>Departments</th>
            <th>Years</th>
            <th>Status</th>
            <th>Deadline</th>
            <th>Applicants Count</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="drive in drives" :key="drive.id">
            <td>{{ drive.job_title }}</td>
            <td>{{ drive.branches && drive.branches.length ? drive.branches.join(', ') : drive.branch_required }}</td>
            <td>{{ drive.years && drive.years.length ? drive.years.join(', ') : (drive.year_required || 'N/A') }}</td>
            <td>{{ drive.status }}</td>
            <td>{{ drive.deadline }}</td>
            <td>{{ drive.applicants_count }}</td>
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
            <th>Drive</th>
            <th>Status</th>
            <th>Interview Schedule</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="app in applications" :key="app.application_id">
            <td>{{ app.student_name }}</td>
            <td>{{ app.job_title }}</td>
            <td>{{ app.status }}</td>
            <td>
              <input v-model="scheduleById[app.application_id]" class="form-control form-control-sm mb-1" type="datetime-local" />
              <div>{{ app.interview_schedule }}</div>
            </td>
            <td>
              <button class="btn btn-outline-primary btn-sm me-1 mb-1" type="button" @click="updateStatus(app.application_id, 'Shortlisted')">Shortlist</button>
              <button class="btn btn-outline-danger btn-sm me-1 mb-1" type="button" @click="updateStatus(app.application_id, 'Rejected')">Reject</button>
              <button class="btn btn-outline-success btn-sm me-1 mb-1" type="button" @click="updateStatus(app.application_id, 'Selected')">Selected</button>
              <button class="btn btn-outline-secondary btn-sm mb-1" type="button" @click="schedule(app.application_id)">Schedule</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
