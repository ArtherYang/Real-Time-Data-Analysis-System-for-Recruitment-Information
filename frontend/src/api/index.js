/**
 * API 请求层 (Axios)
 * ==================
 * 统一的 HTTP 客户端，封装了：
 * - 请求拦截：自动附加 JWT Authorization 头
 * - 响应拦截：统一提取 data 字段 / 401 自动刷新令牌
 *
 * AI生成，待人工审查。
 */

import axios from "axios";

const ACCESS_TOKEN_KEY = "rdas_access_token";
const REFRESH_TOKEN_KEY = "rdas_refresh_token";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 10000,
});

// ---- 请求拦截器：自动带 Authorization ----
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (err) => Promise.reject(err)
);

// ---- 是否正在刷新令牌（避免并发刷新） ----
let isRefreshing = false;
let refreshQueue = [];

function processRefreshQueue(newToken) {
  refreshQueue.forEach(([resolve, reject]) => {
    if (newToken) {
      resolve(newToken);
    } else {
      reject(new Error("refresh_failed"));
    }
  });
  refreshQueue = [];
}

// ---- 响应拦截器 ----
api.interceptors.response.use(
  (res) => {
    // 统一提取 data（新格式: {code, message, data}）
    if (res.data && res.data.code >= 200 && res.data.code < 300) {
      return res.data.data;
    }
    return res.data;
  },
  async (err) => {
    const originalRequest = err.config;
    const status = err.response?.status;

    // 401 + 不是刷新令牌请求 + 未重试过 → 尝试刷新令牌
    if (
      status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/refresh") &&
      !originalRequest.url?.includes("/auth/login")
    ) {
      if (isRefreshing) {
        // 正在刷新中，排队等待
        return new Promise((resolve, reject) => {
          refreshQueue.push([resolve, reject]);
        }).then((newToken) => {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          originalRequest._retry = true;
          return api(originalRequest);
        });
      }

      isRefreshing = true;
      originalRequest._retry = true;

      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (refreshToken) {
        try {
          const res = await axios.post("/api/v1/auth/refresh", {
            refresh_token: refreshToken,
          });
          if (res.data?.code >= 200 && res.data?.code < 300) {
            const newAccessToken = res.data.data?.access_token;
            if (newAccessToken) {
              localStorage.setItem(ACCESS_TOKEN_KEY, newAccessToken);
              originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
              processRefreshQueue(newAccessToken);
              isRefreshing = false;
              return api(originalRequest);
            }
          }
        } catch (refreshErr) {
          // 刷新失败，清除 token
          console.error("令牌刷新失败，请重新登录");
        }
      }

      // 刷新失败：清除本地存储的令牌
      processRefreshQueue(null);
      isRefreshing = false;
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }

    console.error("API Error:", err.response?.status, err.response?.data);
    return Promise.reject(err);
  }
);

export default api;
