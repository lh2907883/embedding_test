<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { tenantApi, type Tenant } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const tenants = ref<Tenant[]>([])
const loading = ref(false)
const showDialog = ref(false)
const form = ref({ tenant_id: '', name: '' })

async function loadTenants() {
  loading.value = true
  try {
    const { data } = await tenantApi.list()
    tenants.value = data
  } finally {
    loading.value = false
  }
}

async function createTenant() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入租户名称')
    return
  }
  try {
    const payload: any = { name: form.value.name }
    if (form.value.tenant_id.trim()) payload.tenant_id = form.value.tenant_id.trim()
    await tenantApi.create(payload)
    ElMessage.success('租户创建成功')
    showDialog.value = false
    form.value = { tenant_id: '', name: '' }
    await loadTenants()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  }
}

async function deleteTenant(tenant: Tenant) {
  await ElMessageBox.confirm(`确定删除租户「${tenant.name}」及其所有数据？`, '确认删除', { type: 'warning' })
  try {
    await tenantApi.delete(tenant.tenant_id)
    ElMessage.success('已删除')
    await loadTenants()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(loadTenants)
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px">
      <h2 style="margin: 0">租户管理</h2>
      <el-button type="primary" @click="showDialog = true">
        <el-icon><Plus /></el-icon>新建租户
      </el-button>
    </div>

    <el-table :data="tenants" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="tenant_id" label="租户ID" width="200" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="created_at" label="创建时间" width="200">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="router.push(`/tenant/${row.tenant_id}`)">
            文档管理
          </el-button>
          <el-button size="small" @click="router.push(`/tenant/${row.tenant_id}/search`)">
            搜索
          </el-button>
          <el-button size="small" type="danger" @click="deleteTenant(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDialog" title="新建租户" width="400px">
      <el-form label-width="80px">
        <el-form-item label="租户ID">
          <el-input v-model="form.tenant_id" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="请输入租户名称" @keyup.enter="createTenant" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="createTenant">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>
