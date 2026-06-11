---
title: "使用 Hugo 搭建个人博客"
date: 2025-05-16
draft: false
tags: ["Hugo", "博客", "教程"]
categories: ["技术"]
---

## Hugo 博客搭建教程

在这篇文章中，我将分享如何使用 Hugo 搭建一个个人技术博客。

### 为什么选择 Hugo？

1. 快速：Hugo 是世界上最快的静态网站生成器之一
2. 简单：配置简单，容易上手  
3. 灵活：支持多种主题和自定义功能

### 环境准备

1. 安装 Git
2. 安装 Homebrew (MacOS)
3. 安装 Hugo

### 详细搭建步骤

#### 1. 安装 Hugo (MacOS)

```bash
brew install hugo
hugo version  # 验证安装
```

#### 2. 创建新站点

```bash
hugo new site myblog
cd myblog
```

#### 3. 添加主题 (以PaperMod为例)

```bash
git submodule add https://github.com/adityatelange/hugo-PaperMod themes/PaperMod
```

#### 4. 基础配置

编辑`config.toml`：

```toml
baseURL = "https://yourusername.github.io/"
title = "我的技术博客"
theme = "PaperMod"
```

#### 5. 创建第一篇文章

```bash
hugo new posts/first-post.md
```

#### 6. 本地测试

```bash
hugo server -D
```
访问 http://localhost:1313 预览

#### 7. 部署到GitHub Pages

1. 创建GitHub仓库 `yourusername.github.io`
2. 初始化Git并提交代码：

```bash
git init
git add .
git commit -m "初始化Hugo博客"
git remote add origin https://github.com/yourusername/yourusername.github.io.git
git push -u origin main
```

### 进阶配置

1. 自定义域名
2. 添加评论系统
3. 配置SEO优化
4. 集成Google Analytics

### 常见问题

1. 主题不显示？检查config.toml中的theme设置
2. 本地预览看不到草稿？使用`-D`参数
3. 部署后样式丢失？检查baseURL设置

### 总结

Hugo是一个强大而高效的静态网站生成器，适合技术博客和个人网站。通过本教程，您已经学会了从零开始搭建并部署一个Hugo博客。

-- Zephyr