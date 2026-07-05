/**
 * 路由配置
 * ========
 * Vue Router 路由表 + 导航守卫（认证检查）。
 *
 * 守卫逻辑：
 * 1. 访问需要认证的页面时，检查 localStorage 中的 token
 * 2. 无 token → 重定向到 /login?redirect=<原路径>
 * 3. 有 token 但 Store 中无用户 → 自动拉取用户信息
 * 4. 已登录访问 /login → 重定向到首页
 *
 * AI生成，待人工审查。
 */

import { createRouter, createWebHistory } from "vue-router";
import Dashboard from "../views/Dashboard.vue";

const routes = [
  {
    path: "/",
    name: "Dashboard",
    component: Dashboard,
    meta: { requiresAuth: true },
  },
  {
    path: "/analysis/salary",
    name: "SalaryAnalysis",
    component: () => import("../views/SalaryAnalysis.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/analysis/skills",
    name: "SkillAnalysis",
    component: () => import("../views/SkillAnalysis.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/analysis/cities",
    name: "CityAnalysis",
    component: () => import("../views/CityAnalysis.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/dashboard/fullscreen",
    name: "FullscreenDashboard",
    component: () => import("../views/FullscreenDashboard.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/jobs",
    name: "Jobs",
    component: () => import("../views/Jobs.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/login",
    name: "Login",
    component: () => import("../views/Login.vue"),
    meta: { guest: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// ---- 导航守卫 ----
router.beforeEach(async (to, from, next) => {
  // 在守卫函数内部 import store，确保 Pinia 已安装
  const { useAuthStore } = await import("../stores/auth");
  const authStore = useAuthStore();

  const accessToken = localStorage.getItem("rdas_access_token");

  // 已登录用户访问登录页 → 重定向到首页
  if (to.meta.guest && accessToken) {
    return next("/");
  }

  // 需要认证的页面
  if (to.meta.requiresAuth) {
    if (!accessToken) {
      // 无 token → 跳转登录
      return next({ path: "/login", query: { redirect: to.fullPath } });
    }

    // 有 token 但用户信息未加载 → 拉取
    if (!authStore.user) {
      try {
        await authStore.fetchUserInfo();
      } catch (e) {
        // 拉取失败（token 无效）
      }
    }

    // 拉取后仍未获取到用户 → token 已失效
    if (!authStore.user) {
      return next({ path: "/login", query: { redirect: to.fullPath } });
    }
  }

  next();
});

export default router;
