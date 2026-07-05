/**
 * 用户认证 Store (Pinia)
 * ======================
 * 管理用户登录状态、JWT Token 和用户信息。
 *
 * 功能：
 * - 登录 / 注册 / 退出
 * - Token 持久化（localStorage）
 * - 自动恢复登录状态
 * - 角色判断
 *
 * AI生成，待人工审查。
 */

import { defineStore } from "pinia";
import api from "../api";

// Token 存储键名
const ACCESS_TOKEN_KEY = "rdas_access_token";
const REFRESH_TOKEN_KEY = "rdas_refresh_token";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    /** 当前登录用户信息（null 表示未登录） */
    user: null,
    /** JWT 访问令牌 */
    accessToken: localStorage.getItem(ACCESS_TOKEN_KEY) || null,
    /** JWT 刷新令牌 */
    refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY) || null,
    /** 是否正在登录中 */
    loading: false,
  }),

  getters: {
    /** 是否已登录 */
    isLoggedIn(state) {
      return !!state.accessToken && !!state.user;
    },

    /** 当前用户角色 */
    userRole(state) {
      return state.user?.role || "";
    },

    /** 是否为管理员 */
    isAdmin() {
      return this.userRole === "管理员";
    },

    /** 是否为企业HR */
    isHR() {
      return this.userRole === "企业HR";
    },

    /** 是否为普通用户 */
    isRegularUser() {
      return this.userRole === "普通用户";
    },
  },

  actions: {
    // ============================================================
    // Token 持久化
    // ============================================================

    _saveTokens(accessToken, refreshToken) {
      this.accessToken = accessToken;
      this.refreshToken = refreshToken;
      if (accessToken) {
        localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
      } else {
        localStorage.removeItem(ACCESS_TOKEN_KEY);
      }
      if (refreshToken) {
        localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
      } else {
        localStorage.removeItem(REFRESH_TOKEN_KEY);
      }
    },

    _clearTokens() {
      this.accessToken = null;
      this.refreshToken = null;
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    },

    // ============================================================
    // 获取当前用户信息
    // ============================================================

    async fetchUserInfo() {
      if (!this.accessToken) return;
      try {
        const data = await api.get("/auth/me");
        this.user = data.user || data;
      } catch (e) {
        console.error("获取用户信息失败:", e);
        // Token 无效，清除登录状态
        if (e.response?.status === 401) {
          this._clearTokens();
          this.user = null;
        }
      }
    },

    // ============================================================
    // 登录
    // ============================================================

    async login(account, password) {
      this.loading = true;
      try {
        const data = await api.post("/auth/login", { account, password });
        // 后端返回格式: { user: {...}, access_token: "...", refresh_token: "..." }
        const { user, access_token, refresh_token } = data;
        this._saveTokens(access_token, refresh_token);
        this.user = user;
        return { success: true };
      } catch (e) {
        const msg =
          e.response?.data?.message || "登录失败，请检查网络连接";
        return { success: false, message: msg };
      } finally {
        this.loading = false;
      }
    },

    // ============================================================
    // 注册
    // ============================================================

    async register({ email, phone, password, nickname }) {
      this.loading = true;
      try {
        const data = await api.post("/auth/register", {
          email: email || undefined,
          phone: phone || undefined,
          password,
          nickname,
        });
        // 注册成功自动登录
        const { user, access_token, refresh_token } = data;
        this._saveTokens(access_token, refresh_token);
        this.user = user;
        return { success: true };
      } catch (e) {
        const msg =
          e.response?.data?.message || "注册失败，请检查网络连接";
        return { success: false, message: msg };
      } finally {
        this.loading = false;
      }
    },

    // ============================================================
    // 刷新令牌
    // ============================================================

    async refreshAccessToken() {
      if (!this.refreshToken) return false;
      try {
        // 刷新时不走拦截器（避免循环），使用原始 axios
        const axios = (await import("axios")).default;
        const res = await axios.post("/api/v1/auth/refresh", {
          refresh_token: this.refreshToken,
        });
        if (res.data?.code >= 200 && res.data?.code < 300) {
          const access_token = res.data.data?.access_token;
          if (access_token) {
            this._saveTokens(access_token, this.refreshToken);
            return true;
          }
        }
        return false;
      } catch (e) {
        console.error("刷新令牌失败:", e);
        this._clearTokens();
        this.user = null;
        return false;
      }
    },

    // ============================================================
    // 退出
    // ============================================================

    logout() {
      this._clearTokens();
      this.user = null;
    },

    // ============================================================
    // 更新个人资料
    // ============================================================

    async updateProfile({ nickname, avatar_url }) {
      try {
        const data = await api.put("/auth/me", {
          nickname: nickname || undefined,
          avatar_url: avatar_url || undefined,
        });
        this.user = data.user || data;
        return { success: true };
      } catch (e) {
        const msg =
          e.response?.data?.message || "更新失败";
        return { success: false, message: msg };
      }
    },
  },
});
