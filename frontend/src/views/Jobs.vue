<template>
  <div class="jobs-page">
    <h2>📋 岗位浏览</h2>

    <!-- 搜索 + 筛选 -->
    <div class="jobs-toolbar">
      <el-input v-model="keyword" placeholder="搜索岗位、公司..." clearable
        style="width:240px" @keyup.enter="search" />
      <el-select v-model="filterCity" placeholder="城市" clearable style="width:130px">
        <el-option v-for="c in store.filterOptions.cities" :key="c" :label="c" :value="c" />
      </el-select>
      <el-select v-model="filterCategory" placeholder="岗位类型" clearable style="width:140px">
        <el-option v-for="c in store.filterOptions.job_categories" :key="c" :label="c" :value="c" />
      </el-select>
      <el-select v-model="filterExp" placeholder="经验" clearable style="width:120px">
        <el-option v-for="e in store.filterOptions.experiences" :key="e" :label="e" :value="e" />
      </el-select>
      <el-select v-model="filterEdu" placeholder="学历" clearable style="width:110px">
        <el-option v-for="e in store.filterOptions.educations" :key="e" :label="e" :value="e" />
      </el-select>
      <el-button type="primary" @click="search">搜索</el-button>
    </div>

    <!-- 结果统计 -->
    <div class="jobs-count">共 {{ total }} 条结果</div>

    <!-- 卡片列表 -->
    <div v-loading="loading" class="jobs-list">
      <div v-if="jobs.length === 0 && !loading" class="empty">暂无匹配岗位</div>
      <div v-for="job in jobs" :key="job.job_id" class="job-card" @click="openDetail(job)">
        <div class="jc-top">
          <h3>{{ job.title }}</h3>
          <span class="jc-salary" v-if="job.salary_min">¥{{ (job.salary_min/1000).toFixed(0) }}K-{{ (job.salary_max/1000).toFixed(0) }}K</span>
          <span class="jc-salary" v-else>薪资面议</span>
        </div>
        <div class="jc-company">{{ job.company }}
          <el-tag size="small" style="margin-left:6px">{{ job.company_type || '' }}</el-tag>
        </div>
        <div class="jc-tags">
          <el-tag size="small" type="info">{{ job.city }}</el-tag>
          <el-tag size="small" type="info">{{ job.experience }}</el-tag>
          <el-tag size="small" type="info">{{ job.education }}</el-tag>
          <el-tag size="small" type="info">{{ job.platform }}</el-tag>
        </div>
        <div class="jc-skills" v-if="job.skills">
          <el-tag v-for="s in job.skills.split(',').slice(0,6)" :key="s" size="small" type="success" effect="plain" style="margin:2px">{{ s.trim() }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div class="jobs-pager" v-if="total > 20">
      <el-pagination background layout="prev, pager, next" :total="total"
        :page-size="20" v-model:current-page="page" @current-change="loadJobs" />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" :title="detailJob?.title" width="620px">
      <template v-if="detailJob">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="公司">{{ detailJob.company }}</el-descriptions-item>
          <el-descriptions-item label="城市">{{ detailJob.city }}</el-descriptions-item>
          <el-descriptions-item label="薪资">
            <span v-if="detailJob.salary_min">¥{{ detailJob.salary_min }}-{{ detailJob.salary_max }}</span>
            <span v-else>面议</span>
          </el-descriptions-item>
          <el-descriptions-item label="经验">{{ detailJob.experience }}</el-descriptions-item>
          <el-descriptions-item label="学历">{{ detailJob.education }}</el-descriptions-item>
          <el-descriptions-item label="平台">{{ detailJob.platform }}</el-descriptions-item>
          <el-descriptions-item label="岗位类型">{{ detailJob.job_category }}</el-descriptions-item>
          <el-descriptions-item label="行业">{{ detailJob.industry }}</el-descriptions-item>
          <el-descriptions-item label="公司规模">{{ detailJob.company_size }}</el-descriptions-item>
          <el-descriptions-item label="公司类型">{{ detailJob.company_type }}</el-descriptions-item>
          <el-descriptions-item label="福利" :span="2">{{ detailJob.welfare }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="detailJob.skills" style="margin-top:12px">
          <el-tag v-for="s in detailJob.skills.split(',')" :key="s" style="margin:2px">{{ s.trim() }}</el-tag>
        </div>
        <div v-if="detailJob.description" style="margin-top:12px; white-space:pre-wrap; color:#666; font-size:13px; line-height:1.6">
          {{ detailJob.description }}
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useAnalysisStore } from "../stores/analysis";
import api from "../api";

const store = useAnalysisStore();
const keyword = ref("");
const filterCity = ref("");
const filterCategory = ref("");
const filterExp = ref("");
const filterEdu = ref("");
const jobs = ref([]);
const total = ref(0);
const page = ref(1);
const loading = ref(false);
const detailVisible = ref(false);
const detailJob = ref(null);

onMounted(async () => {
  await store.fetchFilterOptions();
  await loadJobs();
});

async function loadJobs() {
  loading.value = true;
  try {
    const params = { page: page.value, per_page: 20 };
    if (keyword.value) params.keyword = keyword.value;
    if (filterCity.value) params.city = filterCity.value;
    if (filterCategory.value) params.job_category = filterCategory.value;
    if (filterExp.value) params.experience = filterExp.value;
    if (filterEdu.value) params.education = filterEdu.value;

    // Raw axios to get pagination (interceptor strips it)
    const axios = (await import("axios")).default;
    const res = await axios.get("/api/v1/jobs", { params });
    if (res.data?.code >= 200 && res.data?.code < 300) {
      jobs.value = res.data.data || [];
      total.value = res.data.pagination?.total || jobs.value.length;
    }
  } catch (e) {
    console.error("loadJobs:", e);
  } finally {
    loading.value = false;
  }
}

function search() { page.value = 1; loadJobs(); }

function openDetail(job) {
  detailJob.value = job;
  detailVisible.value = true;
}
</script>

<style scoped>
.jobs-page { padding: 4px 0; }
.jobs-page h2 { margin-bottom: 12px; color: #303133; }

.jobs-toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
  background: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.jobs-count { color: #909399; font-size: 13px; margin-bottom: 8px; }

.jobs-list { display: flex; flex-direction: column; gap: 8px; }
.empty { text-align: center; color: #c0c4cc; padding: 40px; }

.job-card {
  background: #fff; border-radius: 8px; padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06); cursor: pointer;
  transition: box-shadow 0.15s; border-left: 3px solid transparent;
}
.job-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-left-color: #409eff; }
.jc-top { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
.jc-top h3 { margin: 0; font-size: 15px; color: #303133; }
.jc-salary { color: #f56c6c; font-weight: 600; font-size: 14px; }
.jc-company { color: #606266; font-size: 13px; margin-bottom: 6px; }
.jc-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 4px; }
.jc-skills { display: flex; flex-wrap: wrap; gap: 2px; }

.jobs-pager { display: flex; justify-content: center; margin-top: 16px; }
</style>
