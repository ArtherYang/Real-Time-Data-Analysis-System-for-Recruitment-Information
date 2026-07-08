import { defineStore } from "pinia";
import api from "../api";

export const useAnalysisStore = defineStore("analysis", {
  state: () => ({
    // 筛选条件
    filters: {
      city: "",
      job_category: "",
      platform: "",
      experience: "",
      education: "",
      salary_min: null,
      salary_max: null,
      date_from: "",
      date_to: "",
    },

    // 筛选器选项
    filterOptions: {
      cities: [],
      job_categories: [],
      platforms: [],
      experiences: [],
      educations: [],
      salary_range: { min: 0, max: 50000 },
    },

    // 仪表盘概览
    summary: {
      total_jobs: 0,
      new_this_week: 0,
      city_count: 0,
      avg_salary: 0,
      daily_trend: [],
    },

    // 各分析维度数据
    hotJobs: [],
    salaryDist: [],
    cityDist: [],
    experienceEdu: { experience: [], education: [] },
    skillRanking: [],
    salaryTrend: [],
    cityMetadata: [],

    // 加载状态
    loading: {
      summary: false,
      hotJobs: false,
      salaryDist: false,
      cityDist: false,
      experienceEdu: false,
      skillRanking: false,
      salaryTrend: false,
    },
  }),

  getters: {
    activeFilters(state) {
      const params = {};
      for (const [key, val] of Object.entries(state.filters)) {
        if (val !== "" && val !== null) {
          params[key] = val;
        }
      }
      return params;
    },
  },

  actions: {
    setFilter(key, value) {
      this.filters[key] = value;
    },

    setFilters(filterObj) {
      Object.assign(this.filters, filterObj);
    },

    resetFilters() {
      this.filters = {
        city: "", job_category: "", platform: "",
        experience: "", education: "",
        salary_min: null, salary_max: null,
        date_from: "", date_to: "",
      };
    },

    _buildQuery(extra = {}) {
      const params = new URLSearchParams();
      // 先放筛选条件
      for (const [key, val] of Object.entries(this.filters)) {
        if (val !== "" && val !== null) {
          params.append(key, val);
        }
      }
      // 再放额外参数（如 top, group_by 等）
      for (const [key, val] of Object.entries(extra)) {
        if (val !== undefined && val !== null) {
          params.append(key, val);
        }
      }
      const qs = params.toString();
      return qs ? `?${qs}` : "";
    },

    // ---- 筛选器选项 ----
    async fetchFilterOptions() {
      try {
        const data = await api.get("/filters/options");
        this.filterOptions = {
          cities: data.cities || [],
          job_categories: data.job_categories || [],
          platforms: data.platforms || [],
          experiences: data.experiences || [],
          educations: data.educations || [],
          salary_range: data.salary_range || { min: 0, max: 50000 },
        };
      } catch (e) {
        console.error("fetchFilterOptions:", e);
      }
    },

    // ---- 仪表盘概览（来自 /jobs/stats/overview） ----
    async fetchSummary() {
      this.loading.summary = true;
      try {
        const data = await api.get(`/jobs/stats/overview${this._buildQuery()}`);
        this.summary = {
          total_jobs: data.total || 0,
          new_this_week: data.this_week_new || 0,
          city_count: data.city_distribution ? data.city_distribution.length : 0,
          avg_salary: data.avg_salary_min && data.avg_salary_max
            ? Math.round((data.avg_salary_min + data.avg_salary_max) / 2)
            : 0,
          daily_trend: [],
        };
        // 同时填充经验/学历分布
        this.experienceEdu = {
          experience: (data.experience_distribution || []).map((e) => ({
            name: e.experience || e.name || "",
            count: e.count || 0,
          })),
          education: (data.education_distribution || []).map((e) => ({
            name: e.education || e.name || "",
            count: e.count || 0,
          })),
        };
      } catch (e) {
        console.error("fetchSummary:", e);
      } finally {
        this.loading.summary = false;
      }
    },

    // ---- 岗位热度（/analysis/hot-jobs） ----
    async fetchHotJobs(limit = 15, groupBy = "category") {
      this.loading.hotJobs = true;
      try {
        const data = await api.get(
          `/analysis/hot-jobs${this._buildQuery({ top: limit, group_by: groupBy })}`
        );
        // data is [{category, count, percentage}, ...]
        this.hotJobs = (data || []).map((item) => ({
          name: item.category,
          count: item.count,
          percentage: item.percentage,
        }));
      } catch (e) {
        console.error("fetchHotJobs:", e);
      } finally {
        this.loading.hotJobs = false;
      }
    },

    // ---- 薪资分布（/analysis/salary-distribution） ----
    async fetchSalaryDist(groupBy = "job_category") {
      this.loading.salaryDist = true;
      try {
        const data = await api.get(
          `/analysis/salary-distribution${this._buildQuery({ group_by: groupBy, top: 20 })}`
        );
        // data: {group_by, items: [{group_key, sample_count, stats: {mean, median, p25, p75, min, max, count}}]}
        this.salaryDist = (data.items || []).map((item) => ({
          group: item.group_key,
          count: item.sample_count,
          avg: item.stats?.mean || 0,
          median: item.stats?.median || 0,
          p25: item.stats?.p25 || 0,
          p75: item.stats?.p75 || 0,
          min: item.stats?.min || 0,
          max: item.stats?.max || 0,
        }));
      } catch (e) {
        console.error("fetchSalaryDist:", e);
      } finally {
        this.loading.salaryDist = false;
      }
    },

    // ---- 城市分布（/analysis/city-distribution） ----
    async fetchCityDist(limit = 50) {
      this.loading.cityDist = true;
      try {
        const data = await api.get(`/analysis/city-distribution${this._buildQuery({ top: limit })}`);
        // data: {total, cr5, cities: [{city, count, percentage, ...}], ...}
        this.cityDist = (data.cities || []).map((item) => ({
          city: item.city,
          count: item.count,
          percentage: item.percentage,
        }));
      } catch (e) {
        console.error("fetchCityDist:", e);
      } finally {
        this.loading.cityDist = false;
      }
    },

    // ---- 经验/学历分布（已从 overview 获取，可单独刷新） ----
    async fetchExperienceEdu() {
      // 复用 overview 接口
      await this.fetchSummary();
    },

    // ---- 技能排行（/analysis/skills-frequency） ----
    async fetchSkillRanking(limit = 20) {
      this.loading.skillRanking = true;
      try {
        const data = await api.get(`/analysis/skills-frequency${this._buildQuery({ top: limit })}`);
        // data: {total_skill_occurrences, unique_skills, skills: [{skill, count, frequency_pct}]}
        this.skillRanking = (data.skills || []).map((item) => ({
          name: item.skill,
          count: item.count,
          frequency_pct: item.frequency_pct,
        }));
      } catch (e) {
        console.error("fetchSkillRanking:", e);
      } finally {
        this.loading.skillRanking = false;
      }
    },

    // ---- 趋势（/analysis/trend） ----
    async fetchSalaryTrend(granularity = "weekly") {
      this.loading.salaryTrend = true;
      try {
        const data = await api.get(
          `/analysis/trend${this._buildQuery({ granularity })}`
        );
        // data: {granularity, category, data_points: [{period, count, growth_rate}]}
        this.salaryTrend = (data.data_points || []).map((point) => {
          // Format "2026-22" → "第22周" for readability
          let label = point.period;
          const m = point.period.match(/^\d{4}-(\d+)$/);
          if (m) label = `第${m[1]}周`;
          return {
            date: label,
            job_count: point.count,
            growth_rate: point.growth_rate != null ? Math.round(point.growth_rate * 10) / 10 : null,
          };
        });
      } catch (e) {
        console.error("fetchSalaryTrend:", e);
      } finally {
        this.loading.salaryTrend = false;
      }
    },

    // ---- 城市元数据（/cities/metadata） ----
    async fetchCityMetadata() {
      try {
        const data = await api.get("/cities/metadata");
        this.cityMetadata = data.cities || [];
      } catch (e) {
        console.error("fetchCityMetadata:", e);
      }
    },

    // ---- 一键刷新所有（hotJobs 由各页面自行调用以选择 groupBy） ----
    async refreshAll() {
      await Promise.all([
        this.fetchSummary(),
        this.fetchSalaryDist(),
        this.fetchCityDist(),
        this.fetchSkillRanking(),
        this.fetchSalaryTrend(),
      ]);
    },
  },
});
