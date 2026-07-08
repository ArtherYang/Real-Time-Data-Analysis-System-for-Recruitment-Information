<!--
  登录 / 注册页面
  ==============
  支持邮箱+密码登录、手机号注册。
  登录成功后自动跳转到首页。

  AI生成，待人工审查。
-->
<template>
  <div class="login-container">
    <div class="login-card">
      <!-- 标题 -->
      <div class="login-header">
        <Logo :size="48" show-text :text-width="140" />
        <p class="login-subtitle">{{ isRegister ? "创建新账号" : "欢迎回来，请登录" }}</p>
      </div>

      <!-- 表单 -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="0"
        size="large"
        @submit.prevent="handleSubmit"
      >
        <!-- 注册时显示昵称 -->
        <el-form-item v-if="isRegister" prop="nickname">
          <el-input
            v-model="form.nickname"
            placeholder="昵称"
            :prefix-icon="User"
          />
        </el-form-item>

        <!-- 邮箱（登录/注册通用） -->
        <el-form-item prop="email">
          <el-input
            v-model="form.email"
            placeholder="邮箱地址（登录用）"
            :prefix-icon="Message"
          />
        </el-form-item>

        <!-- 手机号（注册时可选） -->
        <el-form-item v-if="isRegister" prop="phone">
          <el-input
            v-model="form.phone"
            placeholder="手机号（选填）"
            :prefix-icon="Phone"
          />
        </el-form-item>

        <!-- 密码 -->
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="密码"
            :prefix-icon="Lock"
          />
        </el-form-item>

        <!-- 错误提示 -->
        <el-alert
          v-if="errorMsg"
          :title="errorMsg"
          type="error"
          show-icon
          :closable="true"
          @close="errorMsg = ''"
          style="margin-bottom: 16px"
        />

        <!-- 提交按钮 -->
        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="authStore.loading"
            style="width: 100%"
          >
            {{ isRegister ? "注 册" : "登 录" }}
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 切换登录/注册 -->
      <div class="login-footer">
        <span v-if="!isRegister">
          还没有账号？
          <el-link type="primary" @click="toggleMode">立即注册</el-link>
        </span>
        <span v-else>
          已有账号？
          <el-link type="primary" @click="toggleMode">去登录</el-link>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from "vue";
import { useRouter, useRoute } from "vue-router";
import { Message, Lock, Phone, User } from "@element-plus/icons-vue";
import { useAuthStore } from "../stores/auth";
import Logo from "../components/Logo.vue";

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const formRef = ref(null);
const isRegister = ref(false);
const errorMsg = ref("");

const form = reactive({
  nickname: "",
  email: "",
  phone: "",
  password: "",
});

// 登录模式的校验规则
const loginRules = {
  email: [
    { required: true, message: "请输入邮箱", trigger: "blur" },
    { type: "email", message: "邮箱格式不正确", trigger: "blur" },
  ],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
  ],
};

// 注册模式的校验规则
const registerRules = {
  nickname: [
    { required: true, message: "请输入昵称", trigger: "blur" },
  ],
  email: [
    { required: true, message: "请输入邮箱", trigger: "blur" },
    { type: "email", message: "邮箱格式不正确", trigger: "blur" },
  ],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 8, message: "密码至少8位", trigger: "blur" },
    { max: 20, message: "密码最多20位", trigger: "blur" },
    {
      pattern: /^(?=.*[a-zA-Z])(?=.*\d)/,
      message: "密码需包含字母和数字",
      trigger: "blur",
    },
  ],
};

const formRules = ref(loginRules);

function toggleMode() {
  isRegister.value = !isRegister.value;
  errorMsg.value = "";
  form.nickname = "";
  form.phone = "";
  form.password = "";
  formRules.value = isRegister.value ? registerRules : loginRules;
  // 重置表单校验状态
  formRef.value?.resetFields();
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  errorMsg.value = "";

  if (isRegister.value) {
    // 注册
    const result = await authStore.register({
      email: form.email,
      phone: form.phone || undefined,
      password: form.password,
      nickname: form.nickname,
    });
    if (result.success) {
      navigateAfterLogin();
    } else {
      errorMsg.value = result.message;
    }
  } else {
    // 登录
    const result = await authStore.login(form.email, form.password);
    if (result.success) {
      navigateAfterLogin();
    } else {
      errorMsg.value = result.message;
    }
  }
}

function navigateAfterLogin() {
  const redirect = route.query.redirect || "/";
  router.push(redirect);
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}

.login-card {
  width: 420px;
  padding: 40px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h2 {
  margin: 12px 0 4px;
  font-size: 20px;
  color: #303133;
}

.login-subtitle {
  margin: 0;
  font-size: 14px;
  color: #909399;
}

.login-footer {
  text-align: center;
  font-size: 14px;
  color: #909399;
}
</style>
