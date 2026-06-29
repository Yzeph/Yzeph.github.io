---
title: "macOS 环境恢复指南"
date: 2026-06-29  
draft: false
tags:
  - MacBook Air
---

## 目录

1. [系统基础设置](#1-系统基础设置)
2. [终端 & Shell](#2-终端--shell)
3. [Homebrew 包管理](#3-homebrew-包管理)
4. [开发语言运行时](#4-开发语言运行时)
5. [数据库 & 服务](#5-数据库--服务)
6. [开发工具](#6-开发工具)
7. [Claude Code 配置](#7-claude-code-配置)
8. [Android 开发环境](#8-android-开发环境)
9. [其他常用工具](#9-其他常用工具)
10. [恢复核对清单](#10-恢复核对清单)

---

## 1. 系统基础设置

### 1.1 系统偏好设置

```
- 触控 ID: 添加指纹
- Apple ID: 登录 iCloud
- 触控板: 开启轻点来点按
- 访达: 显示路径栏、状态栏
- Dock: 偏好设置（图标大小、自动隐藏等）
```

### 1.2 Xcode Command Line Tools

```bash
xcode-select --install
```

这是许多工具编译的前置条件。

---

## 2. 终端 & Shell

### 2.1 终端模拟器 — kitty

Kitty 是一个 GPU 加速的终端模拟器。

```bash
# 安装
brew install --cask kitty
```

配置文件在 `~/.config/kitty/kitty.conf`，备份在恢复文档同级目录下。

### 2.2 Oh My Zsh

```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
```

### 2.3 Powerlevel10k 主题

```bash
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git \
  ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k
```

配置在 `~/.p10k.zsh`（由 `p10k configure` 命令生成或恢复备份）。

### 2.4 Oh My Zsh 插件

```bash
# 命令自动建议
git clone https://github.com/zsh-users/zsh-autosuggestions \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions

# 语法高亮
git clone https://github.com/zsh-users/zsh-syntax-highlighting \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting
```

### 2.5 `.zshrc` 配置

`~/.zshrc` 文件需按原始配置恢复。核心要点：

| 配置项 | 说明 |
|--------|------|
| **主题** | ZSH_THEME="powerlevel10k/powerlevel10k" |
| **插件** | git, zsh-autosuggestions, zsh-syntax-highlighting, extract, web-search |
| **Homebrew 镜像** | 中科大源 (USTC) — 请参见 `.zprofile` 中的镜像配置 |
| **NVM** | 通过 `source /opt/homebrew/opt/nvm/nvm.sh` 加载 |
| **Conda** | 通过 `conda init zsh` 自动生成 |
| **Android SDK** | `ANDROID_HOME` + `PATH` 追加 platform-tools |
| **Python 3.10** | `/opt/homebrew/opt/python@3.10/libexec/bin` 加入 PATH |

**`.zprofile`** — 放置 Homebrew 镜像配置：

```bash
eval $(/opt/homebrew/bin/brew shellenv)
export HOMEBREW_API_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles/api
export HOMEBREW_BOTTLE_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles/bottles
export HOMEBREW_PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
```

---

## 3. Homebrew 包管理

### 3.1 Homebrew 本体

```bash
# 使用中科大镜像安装（推荐国内网络）
/bin/bash -c "$(curl -fsSL https://gitee.com/ineo6/homebrew-install/raw/master/install.sh)"
```

### 3.2 配置镜像源（国内网络加速）

在 `~/.zprofile` 中设置（见 2.5 节），然后执行：

```bash
brew update
```

### 3.3 批量安装 Formula

```bash
# ===== 基础工具 =====
brew install wget
brew install gh           # GitHub CLI
brew install git
brew install bat          # 带语法高亮的 cat
brew install btop         # 系统资源监控
brew install fastfetch    # 系统信息展示
brew install lazygit      # Git TUI
brew install cloc         # 代码行数统计
brew install htop

# ===== 压缩/图片库（依赖链） =====
brew install jpeg-turbo libpng libtiff webp
brew install giflib little-cms2
brew install aom dav1d libavif
brew install cairo pango gdk-pixbuf
brew install harfbuzz freetype fontconfig
brew install librsvg
brew install graphviz

# ===== 开发语言运行时 =====
brew install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
brew install python@3.10
brew install openjdk        # Java 21 LTS
brew install maven
brew install tomcat@8
brew install tomcat@9

# ===== 数据库/缓存 =====
brew install mysql
brew install redis

# ===== 工具链 =====
brew install protobuf
brew install openssl@3
brew install readline sqlite

# ===== 文档/笔记 =====
brew install pandoc

# ===== 文件同步 =====
brew install syncthing

# ===== 网络安全 =====
brew install trivy         # 容器安全扫描
brew install mole          # SSH 隧道管理

# ===== 静态站点 =====
brew install hugo

# ===== 内部库 =====
brew install lz4 lzo zstd zlib-ng-compat
brew install pcre2
brew install oniguruma
brew install icu4c@78
brew install libidn2 libunistring
brew install libssh2 libgit2
brew install libx11 libxcb libxau libxdmcp
brew install libxext libxrender
brew install libthai libdatrie
brew install libdeflate
brew install libvmaf
brew install highway
brew install imath openexr openjph jpeg-xl
brew install gts
brew install netpbm
brew install xxhash yyjson
brew install lua          # 被 graphviz 依赖
brew install m4           # 被 autotools 依赖
brew install mpdecimal
brew install libtool
```

### 3.4 批量安装 Cask（GUI 应用）

```bash
brew install --cask kitty           # 终端模拟器
brew install --cask maczip          # 解压工具
brew install --cask sublime-text    # 文本编辑器
brew install --cask miniconda       # Python 环境管理
brew install --cask claude-code     # Claude Code CLI
brew install --cask copilot-cli     # GitHub Copilot CLI
brew install --cask cc-switch       # Nintendo Switch 模拟器
brew install --cask swift-shift     # 窗口管理
```

---

## 4. 开发语言运行时

### 4.1 Node.js（通过 nvm）

```bash
# nvm 已通过 brew 安装，然后在 .zshrc 中 source
# 安装并使用 Node v22 LTS
nvm install 22
nvm alias default 22
nvm use default
```

**全局 npm 包：**（当前很少）

```bash
npm install -g corepack
```

如果需要 **pnpm**：`npm install -g pnpm`

### 4.2 Python（通过 Homebrew + pip）

Python 3.10 通过 Homebrew 安装。pip 已安装的包可通过下述命令批量恢复（建议按项目使用 virtualenv/conda，不强制全局安装）：

```bash
# pip 安装（按需恢复）
pip3 install \
  torch transformers sentence-transformers \
  scikit-learn scipy numpy networkx \
  requests httpx huggingface_hub \
  rich pygments \
  pyyaml pycodestyle \
  jinja2 markdown-it-py \
  typer click shellingham \
  safetensors tokenizers \
  joblib threadpoolctl \
  tqdm
```

> 大部分 pip 包是 codebase-memory 的依赖，运行 `pip install -r requirements.txt` 会更轻松。

### 4.3 Java

```bash
# OpenJDK 21 LTS（Microsoft 构建版 — 已通过 brew 安装）
brew install openjdk

# 检查
java --version
# openjdk 21.0.8 2025-07-15 LTS
```

### 4.4 Maven

```bash
brew install maven
mvn --version
# Apache Maven 3.9.16
```

### 4.5 Apache Tomcat

```bash
brew install tomcat@8
brew install tomcat@9
```

- Tomcat 8: `/opt/homebrew/opt/tomcat@8/`
- Tomcat 9: `/opt/homebrew/opt/tomcat@9/`

---

## 5. 数据库 & 服务

### 5.1 MySQL

```bash
brew install mysql
brew services start mysql
```

- 默认端口: `3306`
- 默认 socket: `/tmp/mysql.sock`

首次安装后运行安全配置：
```bash
mysql_secure_installation
```

### 5.2 Redis

```bash
brew install redis
brew services start redis
```

- 默认端口: `6379`

### 5.3 Syncthing（文件同步）

```bash
brew install syncthing
brew services start syncthing
```

- Web UI: http://127.0.0.1:8384
- 同步端口: `22000` (TCP)

---

## 6. 开发工具

### 6.1 Git

```bash
# 已包含在 CLT 中
git --version
# git version 2.50.1 (Apple Git-155)

# 基本配置
git config --global user.name "YanRui06"
git config --global user.email "yanrui060127@outlook.com"
git config --global credential.helper osxkeychain
```

### 6.2 GitHub CLI

```bash
brew install gh
gh auth login
```

### 6.3 JetBrains IDE（手动安装）

当前 `devecostudio`（DevEco Studio）正在使用 63342 端口。

### 6.4 Android SDK

```bash
# 安装位置
export ANDROID_HOME=/Users/Zephyr/Library/Android/sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools

# platform-tools 包含:
#   adb, fastboot, etc1tool, hprof-conv
```

需手动从 Android Studio 下载 SDK Platform-Tools，或通过 `sdkmanager` 安装。

### 6.5 其他 CLI 工具

```bash
# bat — 带语法高亮的 cat
alias cat=bat  # 可选

# btop — 系统资源监控
btop

# fastfetch — 系统信息
fastfetch

# lazygit — Git 终端 UI
lazygit

# cloc — 代码行数统计
cloc .

# trivy — 安全扫描
trivy image <image-name>

# hugo — 静态站点生成器
hugo version  # v0.163.3+extended

# pandoc — 文档格式转换
pandoc --version  # 3.10
```

---

## 7. Claude Code 配置

### 7.1 安装

```bash
brew install --cask claude-code
# 或通过 npm: npm install -g @anthropic-ai/claude-code
```

### 7.2 Settings 配置

配置文件: `~/.claude/settings.json`

**关键配置说明：**

```json
{
    // 模型 — 使用 DeepSeek 作为后端（通过兼容 API）
    "model": "haiku",
    "env": {
        "ANTHROPIC_AUTH_TOKEN": "sk-<your-token>",
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-pro",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-flash",
        "ANTHROPIC_MODEL": "deepseek-v4-flash"
    },
    "enabledPlugins": {
        "frontend-design@claude-plugins-official": true
    },
    "extraKnownMarketplaces": {
        "claude-plugins-official": {
            "source": { "source": "git", "url": "https://github.com/anthropics/claude-plugins-official.git" }
        },
        "ponytail": {
            "source": { "source": "github", "repo": "DietrichGebert/ponytail" }
        }
    },
    "hooks": {
        "PreToolUse": [
            { "matcher": "Grep|Glob", "hooks": [
                { "type": "command", "command": "~/.claude/hooks/cbm-code-discovery-gate", "timeout": 5 }
            ]}
        ],
        "SessionStart": [
            { "matcher": "startup", "hooks": [
                { "type": "command", "command": "~/.claude/hooks/cbm-session-reminder" }
            ]},
            { "matcher": "resume", "hooks": [
                { "type": "command", "command": "~/.claude/hooks/cbm-session-reminder" }
            ]},
            { "matcher": "clear", "hooks": [
                { "type": "command", "command": "~/.claude/hooks/cbm-session-reminder" }
            ]},
            { "matcher": "compact", "hooks": [
                { "type": "command", "command": "~/.claude/hooks/cbm-session-reminder" }
            ]}
        ]
    }
}
```

> **注意**: `ANTHROPIC_AUTH_TOKEN` 包含敏感 API Key，恢复时需要从安全密码管理器获取新 token。

### 7.3 Codebase Memory MCP

通过 `~/.claude/.mcp.json` 或 `~/.claude/settings.json` 中的 MCP 配置连接。

```bash
# 安装 codebase-memory-mcp
# 请参考 https://github.com/<repo>/codebase-memory-mcp 的安装说明
```

#### 钩子脚本

| 路径 | 用途 |
|------|------|
| `~/.claude/hooks/cbm-code-discovery-gate` | PreToolUse 钩子，拦截 Grep/Glob |
| `~/.claude/hooks/cbm-session-reminder` | SessionStart 钩子，注入上下文提醒 |

---

## 8. Android 开发环境

### 8.1 ADB / Fastboot

从 [Android Developer](https://developer.android.com/studio/releases/platform-tools) 下载 SDK Platform-Tools，解压到：

```
/Users/Zephyr/Library/Android/sdk/platform-tools/
```

### 8.2 HDC（HarmonyOS 设备连接）

```bash
# 端口 8710 — HarmonyOS 调试桥
# 随 DevEco Studio 自动安装
# 路径通常在 DevEco Studio 安装目录的 Sdk/toolchains/ 下
```

---

## 9. 其他常用工具

### 9.1 Clash Verge（代理工具）

代理端口: `127.0.0.1:33331`  
需手动安装，可从 [GitHub Releases](https://github.com/clash-verge-rev/clash-verge-rev/releases) 下载。

### 9.2 Apifox（API 调试工具）

本地端口: `127.0.0.1:42950`  
需手动安装，从 [Apifox 官网](https://app.apifox.com/download) 下载。

### 9.3 MacZip

```bash
brew install --cask maczip
```

### 9.4 CC Switch（Nintendo Switch 模拟器）

```bash
brew install --cask cc-switch
```

---

## 10. 恢复核对清单

### 一键安装脚本流程

```bash
#!/bin/bash
set -e

echo "===== 1. Xcode Command Line Tools ====="
xcode-select --install

echo "===== 2. Homebrew ====="
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval $(/opt/homebrew/bin/brew shellenv)' >> ~/.zprofile

echo "===== 3. Oh My Zsh ====="
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

echo "===== 4. Powerlevel10k ====="
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git \
  ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k

echo "===== 5. Zsh 插件 ====="
git clone https://github.com/zsh-users/zsh-autosuggestions \
  ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
git clone https://github.com/zsh-users/zsh-syntax-highlighting \
  ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting

echo "===== 6. Homebrew Formula 清单 ====="
# (从下方 brew-bundle 方式恢复)

echo "===== 7. 配置 .zshrc / .zprofile ====="
# 从备份恢复 ~/.zshrc 和 ~/.zprofile
```

### Brew Bundle 方式（推荐）

```bash
# 导出当前环境的 Brewfile
brew bundle dump --file=~/Brewfile-backup

# 在新机器上恢复
brew bundle --file=~/Brewfile-backup
```

### 手动核对清单

| # | 项目 | 状态 |
|---|------|------|
| ☐ | **系统**: Xcode CLT 安装 | |
| ☐ | **系统**: 网络配置 (Clash Verge / 代理) | |
| ☐ | **终端**: kitty 安装 & 配置恢复 | |
| ☐ | **Shell**: Oh My Zsh + Powerlevel10k | |
| ☐ | **Shell**: zsh 插件 (autosuggestions, syntax-highlighting) | |
| ☐ | **Shell**: `.zshrc` + `.zprofile` 恢复 | |
| ☐ | **包管理**: Homebrew 安装 & 镜像源配置 | |
| ☐ | **包管理**: brew formula 恢复 | |
| ☐ | **包管理**: brew cask 恢复 (kitty, sublime, miniconda 等) | |
| ☐ | **Node**: nvm + Node 22 LTS 安装 | |
| ☐ | **Node**: npm 全局包 | |
| ☐ | **Python**: Python 3.10 + pip 包 | |
| ☐ | **Java**: OpenJDK 21 + Maven | |
| ☐ | **Java**: Tomcat 8/9 | |
| ☐ | **数据库**: MySQL 安装 & 启动 | |
| ☐ | **数据库**: Redis 安装 & 启动 | |
| ☐ | **同步**: Syncthing 配置恢复 | |
| ☐ | **Git**: 全局配置 (name, email) | |
| ☐ | **Git**: SSH 密钥恢复 | |
| ☐ | **GitHub**: gh auth login | |
| ☐ | **Claude Code**: 安装 & settings.json 恢复 | |
| ☐ | **Claude Code**: API Key 配置 | |
| ☐ | **Claude Code**: MCP 配置 & 钩子脚本恢复 | |
| ☐ | **Android**: SDK platform-tools (adb) | |
| ☐ | **编辑器**: Sublime Text / JetBrains 恢复 | |
| ☐ | **工具**: Apifox, MacZip, CC Switch 等 | |
| ☐ | **代理**: Clash Verge 安装 & 配置恢复 | |

---

## 附录: 重要目录/文件备份清单

恢复时从旧机器备份以下文件/目录：

| 路径 | 重要性 | 说明 |
|------|--------|------|
| `~/.zshrc` | ⭐⭐⭐ | Shell 配置核心 |
| `~/.zprofile` | ⭐⭐⭐ | Homebrew 镜像初始化 |
| `~/.p10k.zsh` | ⭐⭐ | Powerlevel10k 主题配置 |
| `~/.ssh/` | ⭐⭐⭐ | SSH 密钥 |
| `~/.gitconfig` | ⭐⭐ | Git 全局配置 |
| `~/.claude/settings.json` | ⭐⭐⭐ | Claude Code 配置（注意 token 需要新申请） |
| `~/.claude/hooks/` | ⭐⭐⭐ | Claude Code 钩子脚本 |
| `~/.config/kitty/kitty.conf` | ⭐⭐ | Kitty 终端配置 |
| `~/.config/syncthing/` | ⭐⭐⭐ | Syncthing 配置文件 |
| `~/.nvm/` | ⭐⭐ | Node.js 版本缓存（可重新安装） |
| `~/Library/Android/sdk/` | ⭐⭐ | Android SDK（可重新下载） |
| `~/.oh-my-zsh/custom/` | ⭐⭐ | 自定义主题/插件（可重新 clone） |

---

> **提示**: 可以将此文档中所有 brew install 命令合并为一个 `Brewfile`，用 `brew bundle dump` 生成，恢复时只需 `brew bundle` 一行命令。
