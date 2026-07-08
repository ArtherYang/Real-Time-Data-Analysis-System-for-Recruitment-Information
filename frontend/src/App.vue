<!--
  应用根组件
  ==========
  包含顶部导航栏、侧边栏和主内容区域。
  - 顶部栏：用户信息、角色菜单（管理员可见导出/管理）、退出登录
  - 侧边栏：导航菜单
  - 主体区：router-view

  AI生成，待人工审查。
-->
<template>
  <div id="app">
    <el-container class="app-container">
      <!-- 顶部导航 -->
      <el-header class="app-header">
        <div class="header-left">
          <Logo :size="36" show-text :text-width="140" />
        </div>

        <div class="header-right">
          <!-- 未登录：版本号 -->
          <template v-if="!authStore.isLoggedIn">
            <el-tag type="info" size="small">v0.1.0</el-tag>
          </template>

          <!-- 已登录：用户菜单 -->
          <template v-else>
            <el-dropdown trigger="click" @command="handleUserCommand">
              <span class="user-dropdown-trigger">
                <el-icon><UserFilled /></el-icon>
                <span class="user-nickname">{{ authStore.user?.nickname || '用户' }}</span>
                <el-tag
                  v-if="authStore.isAdmin"
                  type="danger"
                  size="small"
                  style="margin-left: 6px"
                >管理员</el-tag>
                <el-tag
                  v-else-if="authStore.isHR"
                  type="warning"
                  size="small"
                  style="margin-left: 6px"
                >企业HR</el-tag>
                <el-icon class="dropdown-arrow"><ArrowDown /></el-icon>
              </span>

              <template #dropdown>
                <el-dropdown-menu>
                  <!-- 管理员专属：数据导出 -->
                  <el-dropdown-item
                    v-if="authStore.isAdmin"
                    command="export"
                  >
                    <el-icon><Download /></el-icon>
                    数据导出
                  </el-dropdown-item>

                  <!-- 管理员专属：系统管理 -->
                  <el-dropdown-item
                    v-if="authStore.isAdmin"
                    command="admin"
                    divided
                  >
                    <el-icon><Setting /></el-icon>
                    系统管理
                  </el-dropdown-item>

                  <!-- 分隔线 -->
                  <el-dropdown-item
                    v-if="authStore.isAdmin"
                    divided
                    command="profile"
                  >
                    <el-icon><User /></el-icon>
                    个人设置
                  </el-dropdown-item>

                  <el-dropdown-item
                    v-if="!authStore.isAdmin"
                    command="profile"
                  >
                    <el-icon><User /></el-icon>
                    个人设置
                  </el-dropdown-item>

                  <!-- 退出登录 -->
                  <el-dropdown-item command="logout" divided>
                    <el-icon><SwitchButton /></el-icon>
                    <span style="color: #f56c6c">退出登录</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </div>
      </el-header>

      <!-- 侧边栏 + 主体 -->
      <el-container class="app-body">
        <el-aside width="200px" class="app-sidebar">
          <el-menu
            :default-active="activeMenu"
            router
            background-color="#304156"
            text-color="#bfcbd9"
            active-text-color="#409EFF"
          >
            <el-menu-item index="/">
              <span class="menu-icon">📊</span>
              <span>仪表盘</span>
            </el-menu-item>
            <el-menu-item index="/analysis/salary">
              <span class="menu-icon">💰</span>
              <span>薪资分析</span>
            </el-menu-item>
            <el-menu-item index="/analysis/skills">
              <span class="menu-icon">💡</span>
              <span>技能需求</span>
            </el-menu-item>
            <el-menu-item index="/analysis/cities">
              <span class="menu-icon">🗺️</span>
              <span>城市分布</span>
            </el-menu-item>
            <el-menu-item index="/dashboard/fullscreen">
              <span class="menu-icon">🖥️</span>
              <span>数据大屏</span>
            </el-menu-item>
            <el-menu-item index="/jobs">
              <span class="menu-icon">📋</span>
              <span>岗位浏览</span>
            </el-menu-item>

            <!-- 管理员专属菜单 -->
            <template v-if="authStore.isAdmin">
              <el-menu-item index="/admin/data-export">
                <span class="menu-icon">📥</span>
                <span>数据导出</span>
              </el-menu-item>
              <el-menu-item index="/admin/management">
                <span class="menu-icon">⚙️</span>
                <span>系统管理</span>
              </el-menu-item>
            </template>
          </el-menu>
        </el-aside>

        <el-main class="app-main">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  UserFilled,
  ArrowDown,
  Download,
  Setting,
  User,
  SwitchButton,
  Monitor,
  List,
} from "@element-plus/icons-vue";
import { useAuthStore } from "./stores/auth";
import Logo from "./components/Logo.vue";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const activeMenu = computed(() => route.path);

function handleUserCommand(command) {
  switch (command) {
    case "logout":
      authStore.logout();
      router.push("/login");
      break;
    case "export":
      // 滚动到仪表盘页面的导出面板
      router.push("/");
      break;
    case "admin":
      router.push("/admin/management");
      break;
    case "profile":
      // 个人设置 — 待实现，先提示
      router.push("/");
      break;
  }
}
</script>

<style scoped>
.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 60px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-dropdown-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #ffffff;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s;
  user-select: none;
}

.user-dropdown-trigger:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.user-nickname {
  font-size: 14px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dropdown-arrow {
  font-size: 12px;
  margin-left: 2px;
}

.app-body {
  flex: 1;
  overflow: hidden;
}

.app-sidebar {
  background-color: #304156;
  overflow-y: auto;
}

.app-sidebar .el-menu {
  border-right: none;
}

.menu-icon {
  font-size: 18px;
  margin-right: 4px;
  display: inline-flex;
  align-items: center;
}

.app-main {
  background-color: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}
</style>
