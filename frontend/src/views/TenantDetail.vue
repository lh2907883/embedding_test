<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { documentApi, type Document } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps<{ tenantId: string }>()
const router = useRouter()
const documents = ref<Document[]>([])
const loading = ref(false)

// 文件上传
const uploading = ref(false)

// 文本输入
const showTextDialog = ref(false)
const textForm = ref({ text: '', source: '' })

async function loadDocuments() {
  loading.value = true
  try {
    const { data } = await documentApi.list(props.tenantId)
    documents.value = data
  } finally {
    loading.value = false
  }
}

async function handleUpload(options: any) {
  uploading.value = true
  try {
    await documentApi.upload(props.tenantId, options.file)
    ElMessage.success(`文件「${options.file.name}」上传成功`)
    await loadDocuments()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function addText() {
  if (!textForm.value.text.trim()) {
    ElMessage.warning('请输入文本内容')
    return
  }
  try {
    const payload: any = { text: textForm.value.text }
    if (textForm.value.source.trim()) payload.source = textForm.value.source.trim()
    await documentApi.addText(props.tenantId, payload)
    ElMessage.success('文本添加成功')
    showTextDialog.value = false
    textForm.value = { text: '', source: '' }
    await loadDocuments()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '添加失败')
  }
}

async function deleteDoc(doc: Document) {
  await ElMessageBox.confirm(`确定删除文档「${doc.filename || doc.doc_id}」？`, '确认删除', { type: 'warning' })
  try {
    await documentApi.delete(props.tenantId, doc.doc_id)
    ElMessage.success('已删除')
    await loadDocuments()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

function formatSize(bytes: number | null) {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

onMounted(loadDocuments)
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px">
      <div style="display: flex; align-items: center; gap: 12px">
        <el-button @click="router.push('/')" :icon="'Back'" circle size="small" />
        <h2 style="margin: 0">租户: {{ tenantId }}</h2>
      </div>
      <div style="display: flex; gap: 10px">
        <el-button @click="router.push(`/tenant/${tenantId}/search`)">
          <el-icon><Search /></el-icon>搜索
        </el-button>
        <el-button type="primary" @click="showTextDialog = true">
          <el-icon><EditPen /></el-icon>添加文本
        </el-button>
        <el-upload
          :http-request="handleUpload"
          :show-file-list="false"
          accept=".pdf,.docx,.xlsx,.txt"
        >
          <el-button type="success" :loading="uploading">
            <el-icon><Upload /></el-icon>上传文件
          </el-button>
        </el-upload>
      </div>
    </div>

    <el-alert v-if="!loading && documents.length === 0" title="暂无文档" type="info" show-icon :closable="false"
      description="点击「上传文件」或「添加文本」开始添加文档" style="margin-bottom: 20px" />

    <el-table :data="documents" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="doc_id" label="文档ID" width="120" />
      <el-table-column prop="filename" label="文件名">
        <template #default="{ row }">
          {{ row.filename || '(文本输入)' }}
        </template>
      </el-table-column>
      <el-table-column prop="file_type" label="类型" width="80" />
      <el-table-column label="大小" width="100">
        <template #default="{ row }">
          {{ formatSize(row.file_size) }}
        </template>
      </el-table-column>
      <el-table-column prop="chunk_count" label="分块数" width="80" />
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button size="small" type="danger" @click="deleteDoc(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showTextDialog" title="添加文本" width="600px">
      <el-form label-width="80px">
        <el-form-item label="来源">
          <el-input v-model="textForm.source" placeholder="可选，如：笔记、会议记录" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="textForm.text" type="textarea" :rows="10" placeholder="请输入文本内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTextDialog = false">取消</el-button>
        <el-button type="primary" @click="addText">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>
