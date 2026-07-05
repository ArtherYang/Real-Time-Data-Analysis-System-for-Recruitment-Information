-- ============================================================
-- 招聘信息实时数据分析系统 (RDAS) — 数据库初始化脚本
-- ============================================================
-- 版本: v1.0
-- 日期: 2026-07-02
-- 作者: 杨昱晨 (AI生成，待人工审查)
-- 数据库: MySQL 8.0+
-- ============================================================

CREATE DATABASE IF NOT EXISTS rdas
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE rdas;

-- ============================================================
-- 1. 岗位信息表 (jobs)
-- ============================================================
CREATE TABLE IF NOT EXISTS jobs (
    job_id          VARCHAR(32)     NOT NULL PRIMARY KEY COMMENT '岗位唯一标识 (UUID去连字符)',
    title           VARCHAR(200)    NOT NULL COMMENT '岗位名称（标准化后）',
    title_raw       VARCHAR(200)    DEFAULT NULL COMMENT '岗位名称（原始）',
    company         VARCHAR(200)    NOT NULL COMMENT '公司名称',

    -- 薪资 (月薪, 单位: 元)
    salary_min      INT             DEFAULT NULL COMMENT '最低月薪（元）',
    salary_max      INT             DEFAULT NULL COMMENT '最高月薪（元）',
    salary_type     ENUM('月薪','年薪','面议','时薪')
                                    NOT NULL DEFAULT '月薪' COMMENT '薪资类型',

    -- 地域
    city            VARCHAR(50)     NOT NULL COMMENT '工作城市（标准化，地级市）',
    district        VARCHAR(100)    DEFAULT NULL COMMENT '区/县',

    -- 要求
    experience      ENUM('应届生','1-3年','3-5年','5-10年','10年以上','不限')
                                    NOT NULL DEFAULT '不限' COMMENT '经验要求',
    education       ENUM('不限','大专','本科','硕士','博士')
                                    NOT NULL DEFAULT '不限' COMMENT '学历要求',

    -- 内容
    description     TEXT            DEFAULT NULL COMMENT '岗位描述原文',
    skills          VARCHAR(500)    DEFAULT NULL COMMENT '技能标签（逗号分隔）',
    job_type        VARCHAR(50)     DEFAULT NULL COMMENT '工作类型（全职/兼职/实习）',
    recruit_number  VARCHAR(20)     DEFAULT NULL COMMENT '招聘人数',

    -- 分类维度
    industry        VARCHAR(100)    DEFAULT NULL COMMENT '所属行业',
    job_category    VARCHAR(100)    DEFAULT NULL COMMENT '岗位大类（技术/产品/运营/市场/职能）',

    -- 公司信息
    company_size    VARCHAR(50)     DEFAULT NULL COMMENT '公司规模',
    company_type    VARCHAR(50)     DEFAULT NULL COMMENT '公司类型（民营/国企/外企/上市公司）',
    welfare         VARCHAR(500)    DEFAULT NULL COMMENT '福利标签',

    -- 来源与溯源
    platform        ENUM('BOSS直聘','智联招聘','前程无忧','猎聘','其他')
                                    NOT NULL COMMENT '数据来源平台',
    platform_job_id VARCHAR(100)    DEFAULT NULL COMMENT '平台原始职位ID',
    source_url      VARCHAR(500)    DEFAULT NULL COMMENT '职位详情页原始URL',

    -- 时间
    published_at    DATE            DEFAULT NULL COMMENT '岗位发布日期（来自平台）',
    crawled_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '系统采集时间',

    -- 状态
    status          ENUM('有效','已过期','已删除')
                                    NOT NULL DEFAULT '有效' COMMENT '数据状态',

    -- 索引
    INDEX idx_title (title),
    INDEX idx_company (company),
    INDEX idx_city (city),
    INDEX idx_experience (experience),
    INDEX idx_education (education),
    INDEX idx_platform (platform),
    INDEX idx_published_at (published_at),
    INDEX idx_salary (salary_min, salary_max),
    INDEX idx_platform_job (platform, platform_job_id),
    INDEX idx_status (status),
    INDEX idx_job_category (job_category),
    INDEX idx_city_salary (city, salary_min, salary_max),
    INDEX idx_title_city (title, city),

    -- 全文索引（MySQL 5.7.6+ ngram 分词，支持中文模糊搜索）
    FULLTEXT INDEX ft_title_desc (title, description) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='岗位信息表 — 核心业务表，存储各平台采集的招聘岗位数据';


-- ============================================================
-- 2. 用户表 (users)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id         VARCHAR(32)     NOT NULL PRIMARY KEY COMMENT '用户唯一标识',
    email           VARCHAR(100)    DEFAULT NULL COMMENT '邮箱地址',
    phone           VARCHAR(20)     DEFAULT NULL COMMENT '手机号',
    password_hash   VARCHAR(255)    NOT NULL COMMENT 'bcrypt密码哈希',
    nickname        VARCHAR(50)     NOT NULL COMMENT '用户昵称',
    role            ENUM('普通用户','企业HR','管理员')
                                    NOT NULL DEFAULT '普通用户' COMMENT '用户角色',
    avatar_url      VARCHAR(500)    DEFAULT NULL COMMENT '头像URL',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    last_login      DATETIME        DEFAULT NULL COMMENT '最后登录时间',
    is_active       TINYINT(1)      NOT NULL DEFAULT 1 COMMENT '账号是否启用',

    -- 登录安全
    login_attempts  TINYINT         NOT NULL DEFAULT 0 COMMENT '连续登录失败次数',
    locked_until    DATETIME        DEFAULT NULL COMMENT '账号锁定截止时间',

    UNIQUE INDEX idx_email (email),
    UNIQUE INDEX idx_phone (phone),
    INDEX idx_role (role),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户表 — 系统用户账号与角色管理';


-- ============================================================
-- 3. 分析结果缓存表 (analysis_cache)
-- ============================================================
CREATE TABLE IF NOT EXISTS analysis_cache (
    cache_id        VARCHAR(32)     NOT NULL PRIMARY KEY COMMENT '缓存唯一标识',
    cache_type      VARCHAR(50)     NOT NULL COMMENT '缓存类型: hot_jobs/salary_dist/city_dist/skill_analysis',
    params_hash     VARCHAR(64)     NOT NULL COMMENT '查询参数 SHA-256 哈希值',
    result_data     JSON            NOT NULL COMMENT '分析结果数据 (JSON格式)',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '缓存创建时间',
    expires_at      DATETIME        NOT NULL COMMENT '缓存过期时间',

    INDEX idx_cache_type (cache_type),
    INDEX idx_params_hash (params_hash),
    INDEX idx_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='分析结果缓存表 — 缓存高频分析查询结果，减少实时计算压力';


-- ============================================================
-- 4. 采集日志表 (crawl_logs)
-- ============================================================
CREATE TABLE IF NOT EXISTS crawl_logs (
    log_id          VARCHAR(32)     NOT NULL PRIMARY KEY COMMENT '日志唯一标识',
    platform        VARCHAR(50)     NOT NULL COMMENT '采集平台',
    task_type       ENUM('全量采集','增量更新','手动触发')
                                    NOT NULL DEFAULT '全量采集' COMMENT '任务类型',
    status          ENUM('排队中','执行中','已完成','失败','已取消')
                                    NOT NULL DEFAULT '排队中' COMMENT '任务状态',
    keyword         VARCHAR(100)    DEFAULT NULL COMMENT '搜索关键词',
    total_count     INT             NOT NULL DEFAULT 0 COMMENT '目标采集总数',
    success_count   INT             NOT NULL DEFAULT 0 COMMENT '成功采集数',
    fail_count      INT             NOT NULL DEFAULT 0 COMMENT '失败数',
    started_at      DATETIME        DEFAULT NULL COMMENT '任务开始时间',
    finished_at     DATETIME        DEFAULT NULL COMMENT '任务结束时间',
    error_msg       TEXT            DEFAULT NULL COMMENT '错误信息（失败时记录）',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',

    INDEX idx_platform (platform),
    INDEX idx_status (status),
    INDEX idx_started_at (started_at),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='采集日志表 — 记录每次数据采集任务的执行情况';


-- ============================================================
-- 5. 用户收藏表 (user_favorites)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_favorites (
    favorite_id     VARCHAR(32)     NOT NULL PRIMARY KEY COMMENT '收藏唯一标识',
    user_id         VARCHAR(32)     NOT NULL COMMENT '用户ID',
    job_id          VARCHAR(32)     DEFAULT NULL COMMENT '收藏的岗位ID',
    filter_condition JSON          DEFAULT NULL COMMENT '收藏的筛选条件组合 (JSON)',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '收藏时间',

    INDEX idx_user_id (user_id),
    INDEX idx_job_id (job_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户收藏表 — 用户收藏的岗位或筛选条件';


-- ============================================================
-- 6. 用户扩展信息 (user_profiles)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_profiles (
    profile_id      INT             AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    user_id         VARCHAR(32)     NOT NULL UNIQUE COMMENT '用户ID（关联users表）',
    real_name       VARCHAR(50)     DEFAULT NULL COMMENT '真实姓名',
    age             INT             DEFAULT NULL COMMENT '年龄',
    university      VARCHAR(100)    DEFAULT NULL COMMENT '毕业院校',
    major           VARCHAR(100)    DEFAULT NULL COMMENT '专业',
    city            VARCHAR(50)     DEFAULT NULL COMMENT '所在城市',
    phone           VARCHAR(20)     DEFAULT NULL COMMENT '手机号',
    avatar_url      VARCHAR(500)    DEFAULT NULL COMMENT '头像URL',
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户扩展信息 — 1:1 关联 users 表';


-- ============================================================
-- 7. 用户求职意向 (user_preferences)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_preferences (
    pref_id             INT             AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    user_id             VARCHAR(32)     NOT NULL UNIQUE COMMENT '用户ID（关联users表）',
    desired_position    VARCHAR(100)    DEFAULT NULL COMMENT '意向岗位',
    desired_city        VARCHAR(50)     DEFAULT NULL COMMENT '意向城市',
    desired_salary_min  INT             DEFAULT NULL COMMENT '期望最低薪资',
    desired_salary_max  INT             DEFAULT NULL COMMENT '期望最高薪资',
    industry_pref       VARCHAR(50)     DEFAULT NULL COMMENT '偏好行业',
    job_type_pref       VARCHAR(20)     DEFAULT NULL COMMENT '偏好工作类型（全职/实习/不限）',
    created_at          DATETIME        DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at          DATETIME        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户求职意向 — 1:1 关联 users 表';


-- ============================================================
-- 8. 简历模板 (resume_templates)
-- ============================================================
CREATE TABLE IF NOT EXISTS resume_templates (
    template_id     INT             AUTO_INCREMENT PRIMARY KEY COMMENT '模板ID',
    name            VARCHAR(50)     NOT NULL COMMENT '模板名称（简洁/专业/创意）',
    preview_url     VARCHAR(500)    DEFAULT NULL COMMENT '预览图URL',
    css_styles      TEXT            DEFAULT NULL COMMENT 'CSS样式定义（JSON）',
    is_active       TINYINT(1)      DEFAULT 1 COMMENT '是否启用',
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='简历模板 — 预置3套模板';

-- 预置 3 套模板
INSERT INTO resume_templates (name, preview_url, css_styles, is_active) VALUES
('简洁模板', NULL, '{"primary_color":"#2c3e50","font":"微软雅黑","layout":"single_column"}', 1),
('专业模板', NULL, '{"primary_color":"#1a5276","font":"宋体","layout":"two_column"}', 1),
('创意模板', NULL, '{"primary_color":"#e74c3c","font":"思源黑体","layout":"timeline"}', 1);


-- ============================================================
-- 9. 用户简历 (resumes)
-- ============================================================
CREATE TABLE IF NOT EXISTS resumes (
    resume_id           INT             AUTO_INCREMENT PRIMARY KEY COMMENT '简历ID',
    user_id             VARCHAR(32)     NOT NULL COMMENT '用户ID（关联users表）',
    template_id         INT             NOT NULL DEFAULT 1 COMMENT '使用的模板ID',
    full_name           VARCHAR(50)     NOT NULL COMMENT '姓名',
    email               VARCHAR(100)    DEFAULT NULL COMMENT '联系邮箱',
    phone               VARCHAR(20)     DEFAULT NULL COMMENT '联系电话',
    university          VARCHAR(100)    DEFAULT NULL COMMENT '毕业院校',
    major               VARCHAR(100)    DEFAULT NULL COMMENT '专业',
    degree              VARCHAR(20)     DEFAULT NULL COMMENT '学历（本科/硕士/博士）',
    graduation_year     INT             DEFAULT NULL COMMENT '毕业年份',
    skills_text         TEXT            DEFAULT NULL COMMENT '技能描述',
    work_experience     TEXT            DEFAULT NULL COMMENT '工作经历（JSON格式）',
    project_experience  TEXT            DEFAULT NULL COMMENT '项目经历（JSON格式）',
    self_intro          TEXT            DEFAULT NULL COMMENT '自我评价',
    status              VARCHAR(20)     DEFAULT 'draft' COMMENT '状态（draft/published）',
    created_at          DATETIME        DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at          DATETIME        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_user_id (user_id),
    INDEX idx_template_id (template_id),
    INDEX idx_status (status),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (template_id) REFERENCES resume_templates(template_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户简历 — 关联 users 和 resume_templates';
