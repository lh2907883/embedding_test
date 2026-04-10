<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { searchApi, type SearchResultItem } from '@/api'
import { ElMessage } from 'element-plus'

const props = defineProps<{ tenantId: string }>()
const router = useRouter()
const query = ref('')
const topK = ref(5)
const results = ref<SearchResultItem[]>([])
const loading = ref(false)
const searched = ref(false)

async function doSearch() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入搜索关键词')
    return
  }
  loading.value = true
  searched.value = true
  try {
    const { data } = await searchApi.search(props.tenantId, {
      query: query.value,
      top_k: topK.value,
    })
    results.value = data
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '搜索失败')
  } finally {
    loading.value = false
  }
}

function scoreColor(score: number) {
  if (score >= 0.85) return '#67c23a'
  if (score >= 0.7) return '#e6a23c'
  return '#f56c6c'
}
</script>

<template>
  <div>
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px">
      <el-button @click="router.push(`/tenant/${tenantId}`)" :icon="'Back'" circle size="small" />
      <h2 style="margin: 0">搜索 - 租户: {{ tenantId }}</h2>
    </div>

    <div style="display: flex; gap: 10px; margin-bottom: 20px">
      <el-input
        v-model="query"
        placeholder="输入搜索关键词..."
        size="large"
        clearable
        @keyup.enter="doSearch"
        style="flex: 1"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select v-model="topK" size="large" style="width: 120px">
        <el-option :value="3" label="Top 3" />
        <el-option :value="5" label="Top 5" />
        <el-option :value="10" label="Top 10" />
        <el-option :value="20" label="Top 20" />
      </el-select>
      <el-button type="primary" size="large" @click="doSearch" :loading="loading">搜索</el-button>
    </div>

    <el-alert v-if="searched && !loading && results.length === 0" title="没有找到相关结果" type="info" show-icon :closable="false" />

    <div v-for="(r, i) in results" :key="r.chunk_id" style="margin-bottom: 16px">
      <el-card>
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span>
              <el-tag size="small" style="margin-right: 8px">#{{ i + 1 }}</el-tag>
              <span style="color: #666">{{ r.metadata.source || r.doc_id }} / {{ r.chunk_id }}</span>
            </span>
            <el-tag :color="scoreColor(r.score)" effect="dark" size="small" style="border: none">
              {{ (r.score * 100).toFixed(1) }}%
            </el-tag>
          </div>
        </template>
        <p style="white-space: pre-wrap; line-height: 1.8; margin: 0">{{ r.text }}</p>
      </el-card>
    </div>
  </div>
</template>
