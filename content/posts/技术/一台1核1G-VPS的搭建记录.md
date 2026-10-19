---
title: "一台 1 核 1G VPS 的搭建记录：代理、订阅与服务监控"
date: 2026-10-19
lastmod: 2026-10-19
slug: "vps-proxy-subscription-monitoring"
draft: false
description: "从 SSH 密钥、防火墙到 Reality、订阅面板和地理数据镜像，记录一台 Debian VPS 的详细搭建步骤、排错过程与后续监控配置。"
categories:
  - 技术
tags:
  - VPS
  - Debian
  - Xray
  - Hysteria2
  - Gatus
isCJKLanguage: true
params:
  author: "Zephyr"
  ShowToc: true
  TocOpen: false
---

最近在一台 1 核 1G 的 VPS 上搭了一些自己常用的服务。最开始是配置代理，后面又加上了订阅、管理面板、流量统计和服务监控。

这篇文章从 SSH 登录开始，记录防火墙、Reality、订阅面板和地理数据镜像的搭建过程，再整理后续加入的 Hysteria 2、流量统计和 Gatus，方便以后查阅和迁移。

<!--more-->

## 前言

我的需求比较简单：日常能用代理，客户端能通过订阅更新配置，再有一个页面查看流量和服务状态。机器配置有限，所以尽量减少后台组件，能用 systemd 管理的服务就直接运行，数据保存在本机。

整个配置分成四部分：

1. 用 Xray 和 Hysteria 2 提供两种代理连接方式。
2. 用 Python 提供节点订阅和管理页面。
3. 采集代理用量，在订阅和面板中显示流量。
4. 用 Gatus 检查本机服务和常用网站。

下面按环境准备、代理、订阅和监控的顺序记录。IP 统一用 `203.0.113.10`，网页域名用 `panel.example.com`，真实 UUID、密钥和随机路径均替换为占位符。

文中的命令分别标注了本地与 VPS 的执行位置。VPS 上的配置操作使用 root 权限，`<UUID>`、`<PRIVATE_KEY>` 等内容需要替换后再使用。最初部署与后续盘点分开记录，运行状态以 2026 年 10 月 19 日的检查为准。

## 一、服务器环境

这台机器是 KVM 虚拟机，配置比较小：

| 项目 | 配置 |
|------|------|
| CPU | 1 核 |
| 内存 | 系统可见约 979MiB |
| 系统盘 | 根分区约 4.9GB |
| Swap | 约 1GB |
| 系统 | Debian 11 |
| Python | 3.9.2 |
| 初次部署的 Xray | 26.3.27 |

2026 年 10 月 19 日盘点时，系统使用内存约 343MiB，可用内存约 500MiB，Swap 使用量为 0。根分区使用率为 59%，还剩约 2GB。

这只是当时的运行情况，没有做压力测试。代理连接数、流量和监控任务变化后，占用也会跟着变化。

考虑到机器配置，我没有引入容器平台。后台服务统一交给 systemd 管理，配置和状态主要用 JSON、SQLite 保存，方便查日志和后续迁移。

## 二、服务架构

先看各个服务之间的关系：

```text
客户端
├─ TCP 443 ───────────→ Xray / VLESS + Reality
├─ UDP 443 ───────────→ Hysteria 2
└─ HTTPS → Cloudflare → VPS TCP 80
                          └─ Python 订阅与管理服务
                              ├─ 节点订阅
                              ├─ /admin/ 管理页面
                              └─ 登录后访问 Gatus
                                   └─ 127.0.0.1:8088

流量采集 → 本机代理统计接口 → JSON
```

代理连接直接到 VPS。Cloudflare 处理的是网页和订阅访问，两部分走不同的链路。

## 三、SSH 登录与密钥配置

### 3.1 首次连接

在本地终端登录 VPS，先接受主机指纹，再输入服务商提供的密码：

```bash
ssh root@203.0.113.10
```

搭建时还遇到过非交互环境不能输入 SSH 密码的情况，最后通过 `SSH_ASKPASS_REQUIRE=force` 配合临时 askpass 程序完成登录。日常在终端里操作，可以直接交互输入密码，不需要这一步。

### 3.2 生成专用密钥

本地生成一把单独用于这台 VPS 的密钥，方便后续管理和吊销：

```bash
ssh-keygen -t ed25519 -f ~/.ssh/vps -C "vps"
```

按提示设置密钥口令，然后把公钥添加到服务器的 `/root/.ssh/authorized_keys`。可在本地执行：

```bash
ssh-copy-id -i ~/.ssh/vps.pub root@203.0.113.10
```

服务器端确认目录和文件权限：

```bash
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
```

保留当前会话，再开一个本地终端验证密钥登录：

```bash
ssh -o IdentitiesOnly=yes -i ~/.ssh/vps root@203.0.113.10 'id -un'
```

返回 `root` 后再关闭服务器密码登录。设置了口令的密钥可以先加载到本地 ssh-agent，再用 `BatchMode=yes` 检查是否仍需要交互认证。

本地 `~/.ssh/config` 加一个别名：

```sshconfig
Host vps
    HostName 203.0.113.10
    User root
    IdentityFile ~/.ssh/vps
    IdentitiesOnly yes
```

之后直接执行 `ssh vps`。`IdentitiesOnly yes` 也能避免 SSH 依次尝试太多默认密钥，触发服务器的认证次数限制。

### 3.3 关闭密码登录

在 VPS 上创建 `/etc/ssh/sshd_config.d/99-hardening.conf`：

```text
PermitRootLogin prohibit-password
PasswordAuthentication no
ChallengeResponseAuthentication no
PermitEmptyPasswords no
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
ClientAliveInterval 300
ClientAliveCountMax 2
```

这台 Debian 11 的 OpenSSH 是 8.4p1。当时使用 `KbdInteractiveAuthentication` 报了不支持的配置项，改用 `ChallengeResponseAuthentication` 后通过校验。

应用前先检查语法，再重载服务：

```bash
sshd -t
systemctl reload ssh
sshd -T | rg 'permitrootlogin|passwordauthentication|challengeresponseauthentication|maxauthtries'
```

如果服务器没有 `rg`，最后一条可改用 `grep -E`。drop-in 是否生效还取决于主配置的 `Include` 位置和其他配置，最终以 `sshd -T` 的结果为准。重载后继续保留原会话，再验证一次新连接。

## 四、Swap、防火墙与 Fail2ban

### 4.1 增加 1GB Swap

机器只有约 1GB 内存，先检查是否已有 Swap：

```bash
swapon --show
free -m
```

初次部署时没有 Swap，于是增加了一个 1GB 文件：

```bash
fallocate -l 1G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
```

在 `/etc/fstab` 中添加一次：

```text
/swapfile none swap sw 0 0
```

再调整 swappiness：

```bash
printf 'vm.swappiness=10\n' > /etc/sysctl.d/99-swappiness.conf
sysctl -p /etc/sysctl.d/99-swappiness.conf
```

已有 `/swapfile` 或 Swap 正在使用时，不重复执行创建和格式化命令。

### 4.2 配置 nftables

这台机器直接使用 nftables。入站和转发默认丢弃，放行 SSH、代理，以及来自 Cloudflare 的网页回源。

先取得 Cloudflare 官方网段：

```bash
curl -fsS https://www.cloudflare.com/ips-v4 -o /tmp/cf-ips-v4
curl -fsS https://www.cloudflare.com/ips-v6 -o /tmp/cf-ips-v6
```

两个文件都应包含有效网段。把它们按逗号连接后，填到下面的 `CF4` 和 `CF6` 集合中：

```bash
paste -sd, /tmp/cf-ips-v4
paste -sd, /tmp/cf-ips-v6
```

`/etc/nftables.conf` 的结构如下。`<CF4_CIDRS>`、`<CF6_CIDRS>` 需要替换为上面的完整输出，不能保留占位符：

```nft
#!/usr/sbin/nft -f

add table inet filter
delete table inet filter

define CF4 = { <CF4_CIDRS> }
define CF6 = { <CF6_CIDRS> }

table inet filter {
    chain input {
        type filter hook input priority filter; policy drop;

        ct state established,related accept
        ct state invalid drop
        iifname "lo" accept
        ip protocol icmp accept
        meta l4proto ipv6-icmp accept

        tcp dport 22 accept
        tcp dport 443 accept
        udp dport 443 accept

        ip saddr $CF4 tcp dport 80 accept
        ip6 saddr $CF6 tcp dport 80 accept
    }

    chain forward {
        type filter hook forward priority filter; policy drop;
    }

    chain output {
        type filter hook output priority filter; policy accept;
    }
}
```

最初 Reality 只需要 TCP 443，加入 Hysteria 2 后补了 UDP 443。这里列的是包含两个协议的规则。

保存修改前保留一份可恢复的旧配置。应用时先校验，校验通过才执行下一条：

```bash
nft -c -f /etc/nftables.conf
# 已运行的服务重载规则
systemctl reload nftables
nft list ruleset
```

首次启用服务时，配置通过校验后执行 `systemctl enable --now nftables`；上面的 `reload` 用于已经运行的服务。

这台机器的 `nftables.service` 在停止时会执行 `nft flush ruleset`。因此修改配置后使用 `reload`，避免 `restart` 先清空规则、再因为新配置语法错误导致加载失败。

配置只重建自己的 `inet filter` 表，没有使用全局 `flush ruleset`，以免顺带删掉 Fail2ban 的封禁表。

### 4.3 配置 Fail2ban

`/etc/fail2ban/jail.local`：

```ini
[DEFAULT]
ignoreip = 127.0.0.1/8 ::1
bantime = 1h
findtime = 10m
maxretry = 5
backend = systemd
banaction = nftables-multiport
banaction_allports = nftables-allports

[sshd]
enabled = true
port = 22
```

固定管理出口可以按需追加到 `ignoreip`。机器没有使用 iptables，因此这里显式指定 nftables 动作。

```bash
fail2ban-client -t
systemctl enable --now fail2ban
fail2ban-client status sshd
```

## 五、双协议代理配置

### 5.1 协议与端口

代理部分用了 Xray 和 Hysteria 2：

| 服务 | 协议 | 监听端口 |
|------|------|------|
| Xray | VLESS / TCP / Reality | TCP 443 |
| Hysteria 2 | Hysteria 2 | UDP 443 |

虽然都用了 443，但 TCP 和 UDP 是不同的传输协议，不会因为端口号相同而冲突。

Reality 作为主要连接方式，Hysteria 2 留作另一种选择。两个协议都跑在同一台机器上，所以这里只是多一种连接方式，机器或机房出问题时，它们还是会一起受影响。

### 5.2 证书与统计接口

Hysteria 2 配置了域名证书，客户端通过 SNI 校验证书，没有关闭证书验证。证书由 Certbot 管理，续期后通过部署钩子更新到 Hysteria 2 使用的位置。

为了后面做流量统计，两个代理都提供了本机统计接口：

- Xray：`127.0.0.1:11111`。
- Hysteria 2：`127.0.0.1:11112`，另外配置了认证。

这些接口只监听回环地址，供本机采集程序和监控使用。

### 5.3 安装 Xray 并生成连接参数

在 VPS 上使用 Xray 官方安装脚本：

```bash
curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh \
    -o /root/install-xray.sh
bash /root/install-xray.sh install
xray version
```

最初搭建记录中的版本为 `26.3.27`，安装脚本下载的版本可能随时间变化。生成 Reality 密钥、客户端 UUID 和 short ID：

```bash
xray x25519
xray uuid
openssl rand -hex 8
```

私钥留在服务器，公钥填到客户端。26.x 的命令输出中，公钥可能显示为 `Password (PublicKey)`，不要把额外的 `Hash32` 当成公钥。

### 5.4 VLESS + Reality 服务端配置

编辑 `/usr/local/etc/xray/config.json`：

```json
{
  "log": { "loglevel": "warning" },
  "inbounds": [{
    "tag": "vless-reality",
    "listen": "0.0.0.0",
    "port": 443,
    "protocol": "vless",
    "settings": {
      "clients": [{
        "id": "<UUID>",
        "flow": "xtls-rprx-vision",
        "email": "vps"
      }],
      "decryption": "none"
    },
    "streamSettings": {
      "network": "tcp",
      "security": "reality",
      "realitySettings": {
        "show": false,
        "dest": "www.apple.com:443",
        "xver": 0,
        "serverNames": ["www.apple.com"],
        "privateKey": "<PRIVATE_KEY>",
        "shortIds": ["<SHORT_ID>"]
      }
    },
    "sniffing": {
      "enabled": true,
      "destOverride": ["http", "tls", "quic"],
      "routeOnly": false
    }
  }],
  "outbounds": [
    { "tag": "direct", "protocol": "freedom" },
    { "tag": "block", "protocol": "blackhole" }
  ],
  "routing": {
    "domainStrategy": "AsIs",
    "rules": [{
      "type": "field",
      "protocol": ["bittorrent"],
      "outboundTag": "block"
    }]
  }
}
```

这是初次部署的配置结构，后面接入流量采集时再合并统计配置。`dest` 是当时版本使用的字段，升级时需要检查对应版本的配置兼容性。

替换占位符后，先校验再启动：

```bash
xray run -test -config /usr/local/etc/xray/config.json
systemctl enable --now xray
systemctl status xray --no-pager
```

已在运行的服务修改配置后，需要在校验通过后执行 `systemctl restart xray`，仅执行 `enable --now` 不会让现有进程重读配置。

### 5.5 导入客户端并验证

客户端使用支持 Reality 的 mihomo 内核。节点部分对应如下：

```yaml
proxies:
  - name: VPS-Reality
    type: vless
    server: 203.0.113.10
    port: 443
    uuid: "<UUID>"
    network: tcp
    tls: true
    udp: true
    flow: xtls-rprx-vision
    servername: www.apple.com
    client-fingerprint: chrome
    reality-opts:
      public-key: "<PUBLIC_KEY>"
      short-id: "<SHORT_ID>"
```

这段放在客户端配置的 `proxies` 下，再将节点加入策略组。UUID、SNI、公钥和 short ID 要与服务端对应。

本地也可以先检查 443 的普通 TLS 响应：

```bash
openssl s_client -connect 203.0.113.10:443 \
    -servername www.apple.com -brief </dev/null
```

当时能看到 Apple 的证书，说明未认证连接按配置转发到了目标站。但这个检查本身不包含 Reality 客户端认证，仍要导入节点后验证代理连接。

客户端的本地 SOCKS 端口为 7890 时，可执行：

```bash
curl --socks5-hostname 127.0.0.1:7890 https://api.ipify.org
```

返回值应与 VPS 的实际出口 IP 一致。`7890` 需要按客户端当前设置调整。

### 5.6 加入 Hysteria 2

后续增加 Hysteria 2，监听 UDP 443，使用 `userpass` 认证。主要配置位于 `/etc/hysteria/config.json`，包含以下几部分：

- `listen`：监听 UDP 443。
- `tls`：域名证书和私钥路径。
- `auth`：用户名与密码。
- `trafficStats`：监听 `127.0.0.1:11112`，并设置统计接口认证。

客户端对应填写 VPS 地址、UDP 端口、认证信息和证书域名。`userpass` 认证需要同时携带用户名和密码，SNI 与证书域名对应，保留证书验证。

证书由 Certbot 管理，HTTP-01 校验文件通过订阅服务的 `/.well-known/acme-challenge/` 路由提供。它对应服务器目录 `/var/www/acme/.well-known/acme-challenge/`。续期后的部署钩子负责更新 Hysteria 2 使用的证书文件。

先查看 systemd 的实际启动参数，确认使用的是这份 JSON 配置：

```bash
systemctl cat hysteria-server
systemctl status hysteria-server --no-pager
ss -lunp | grep ':443'
```

证书校验请求也需要能经过 Cloudflare 到达 HTTP 源站。维护时同时检查校验路由、证书文件权限与续期钩子，避免只更新了 Certbot 目录而代理仍使用旧副本。

## 六、订阅服务与管理面板

### 6.1 订阅入口

节点配置好后，我用一个 Python 服务来提供订阅，同时把常用的管理功能放到同一个页面里。

服务使用 `www-data` 用户运行，监听 TCP 80。公网请求先经过 Cloudflare，再回源到 VPS。

订阅使用随机路径。由于订阅正文包含节点凭据，完整订阅地址也需要像密码一样保管，不能直接贴到博客或公开仓库里。

### 6.2 管理功能

管理入口放在 `/admin/`，登录后可以：

- 查看服务器状态、磁盘空间和代理监听状态。
- 查看本周期流量及剩余额度估算。
- 获取节点分享链接和二维码。
- 修改订阅分流模式。
- 进入 Gatus 监控页面。

二维码在服务器本地生成，不需要把节点链接交给第三方二维码网站。订阅、私有页面和接口也设置了禁止缓存的响应策略。

### 6.3 Cloudflare 回源

Cloudflare 中的配置是：

| 项目 | 设置 |
|------|------|
| DNS | `panel.example.com` 的 A 记录指向 VPS，开启 Proxied |
| SSL/TLS | Flexible |
| Always Use HTTPS | 开启 |

目前客户端到 Cloudflare 使用 HTTPS，Cloudflare 到源站则使用 HTTP 80。源站通过防火墙限制 Cloudflare 来源，但这段回源没有 TLS，后续还可以继续完善。

这里使用 Flexible 是因为当前网页源站只提供 HTTP，而 TCP 443 已经交给 Reality。搭建时尝试 Full，Cloudflare 连接源站 443 后进入了 Reality 的转发流程，最后出现 Apple 边缘节点的 `400 Invalid URL` 页面。后续若给网页源站配置独立的 HTTPS 回源入口，再相应调整 SSL/TLS 模式。

### 6.4 订阅分流规则

当前订阅包含两个节点，策略组分成四个：

| 策略组 | 用途 |
|------|------|
| `PROXY` | 手动选择节点 |
| `AUTO` | 定时测速选择节点 |
| `FALLBACK` | 按优先顺序选择可用节点 |
| 全球直连 | 直连选项 |

默认规则比较简单，没有额外配置 `rule-providers`：

```yaml
rules:
  - GEOSITE,private,DIRECT
  - GEOIP,private,DIRECT,no-resolve
  - GEOSITE,geolocation-!cn,PROXY
  - GEOSITE,cn,DIRECT
  - GEOIP,CN,DIRECT
  - MATCH,PROXY
```

规则按顺序匹配：先让私有地址直连，再处理境外域名、国内域名和 IP，最后走代理兜底。

面板支持 `rule`、`global`、`direct` 三种模式。切换后，后端会在生成订阅时调整 `rules` 内容，客户端需要刷新订阅才能取得更新，不会立即改变客户端正在使用的配置。

我没有单独维护一份 AI 网站规则表。具体请求走哪个节点，还要看客户端加载的规则、地理数据库和策略组选择。服务器虽然配置了每周刷新地理数据的任务，但客户端自己的数据库仍需要单独确认。

### 6.5 部署订阅与面板程序

订阅后端和页面是自写程序，部署文件分别是 `sub-server.py`、`dashboard.html` 和 `set-panel-password.py`。当前后端依赖 PyYAML 和 qrcode，依赖需要安装到 systemd 使用的 Python 环境中。

先在 VPS 上准备目录：

```bash
install -d -o root -g www-data -m 0750 /etc/vps-panel
install -d -o root -g www-data -m 0750 /var/www/sub
install -d -o root -g www-data -m 0750 /var/www/dash
install -d -o root -g www-data -m 0750 /var/www/geo
install -d -o www-data -g www-data -m 0750 /var/lib/vps
```

将程序上传到 VPS 的部署目录后，在该目录中安装文件：

```bash
install -o root -g root -m 0755 sub-server.py /usr/local/bin/sub-server.py
install -o root -g root -m 0755 set-panel-password.py /usr/local/bin/set-panel-password
install -o root -g www-data -m 0640 dashboard.html /var/www/dash/index.html
```

随机订阅文件名用下面的命令生成：

```bash
openssl rand -hex 20
```

将完整客户端配置保存为 `/var/www/sub/<SUB_TOKEN>.yaml`，文件权限设为 `root:www-data`、`640`，再让后端的 `SUB_PATH` 指向同名路径。`SUB_TOKEN` 是随机文件名的一部分，不是节点密码，但拿到完整链接就能取得订阅。

后端路由分工如下：

| 路径 | 用途 | 访问方式 |
|------|------|------|
| `/<SUB_TOKEN>.yaml` | 客户端订阅 | 持有完整链接 |
| `/admin/` | 控制台 | 登录后访问 |
| `/admin/login` | 登录页 | 公开入口 |
| `/admin/api/status` | 状态数据 | 登录后访问 |
| `/admin/api/mode` | 修改分流模式 | 登录后访问 |
| `/geo/<GEO_TOKEN>/…` | 地理数据库 | 持有对应路径 |

下面贴出 `sub-server.py` 的完整实现，包含订阅分流、面板登录、节点分享链接、二维码、状态接口和 Gatus 转发。

保存后修改 `SUB_PATH`、`GEO_PREFIX` 和代码中的 `panel.example.com`，分别对应自己的随机订阅路径、地理数据路径和网页域名。订阅文件与 `dashboard.html` 按前面的路径部署，认证文件由下一节的密码工具生成。


{{< collapse summary="展开 sub-server.py 完整代码" >}}

```python
#!/usr/bin/env python3
"""vps 私人面板 + 订阅服务（带登录认证）

放在 Cloudflare 后面回源（CF 终止 TLS，只放行 CF 的 IP 访问 80）。

路由：
  GET  /<SUB_PATH>                  订阅 YAML            —— 路径保密，不要求登录
  GET  /<DASH_PREFIX>/              控制台（需登录）
  GET  /<DASH_PREFIX>/login         登录页
  POST /<DASH_PREFIX>/login         提交密码
  GET  /<DASH_PREFIX>/logout        退出
  GET  /<DASH_PREFIX>/api/status    状态 JSON（需登录）
  其他                              404

安全设计：
  - 密码以 PBKDF2-HMAC-SHA256 加盐哈希存储，从不保存明文
  - 会话为 HMAC-SHA256 签名令牌（无服务端状态，重启不掉线）
  - 登录失败按真实客户端 IP 限流（读 CF-Connecting-IP）
  - Cookie: HttpOnly + Secure + SameSite=Lax + 限路径
  - 服务以 www-data 运行，仅保留 CAP_NET_BIND_SERVICE
  - 不记访问日志
"""
import base64
import hashlib
import hmac
import http.server
import http.client
import functools
import io
import json
import os
import re
import secrets
import socketserver
import time
import urllib.parse
import yaml

# ── 配置 ────────────────────────────────────────────────────────────────
SUB_DIR = "/var/www/sub"
SUB_SUFFIX = ".yaml"
SUB_PATH = "/<SUB_TOKEN>.yaml"

DASH_FILE = "/var/www/dash/index.html"
DASH_PREFIX = "/admin"          # 注意：这是可猜测路径，安全性完全依赖密码 + 限流
AUTH_FILE = "/etc/vps-panel/auth.json"
TRAFFIC_FILE = "/var/lib/vps-traffic/usage.json"
ACME_DIR = "/var/www/acme/.well-known/acme-challenge"
GATUS_ENABLED = os.environ.get("vps_GATUS_ENABLED") == "1"
GATUS_ADDRESS = ("127.0.0.1", 8088)


# ── 分流模式（/admin/ 面板可切换）────────────────────────────────────
#   rule   = 分流：国内直连 / 境外代理（默认）
#   global = 全局代理
#   direct = 全部直连（相当于暂停代理）
STATE_DIR = "/var/lib/vps"
MODE_FILE = os.path.join(STATE_DIR, "mode")
MODES = ("rule", "global", "direct")

RULES_TEXT = {
    "rule": (
        "  # ① 私有地址直连\n"
        "  - GEOSITE,private,DIRECT\n"
        "  - GEOIP,private,DIRECT,no-resolve\n"
        "\n"
        "  # ② 境外站点走代理（必须排在 cn 之前，避免国内 CDN 解析到海外 IP 被误判）\n"
        "  - GEOSITE,geolocation-!cn,PROXY\n"
        "\n"
        "  # ③ 国内域名与 IP 直连\n"
        "  - GEOSITE,cn,DIRECT\n"
        "  - GEOIP,CN,DIRECT\n"
        "\n"
        "  # ④ 兜底\n"
        "  - MATCH,PROXY\n"
    ),
    "global": (
        "  # 全局代理：除内网地址外全部走代理\n"
        "  - GEOIP,private,DIRECT,no-resolve\n"
        "  - MATCH,PROXY\n"
    ),
    "direct": (
        "  # 全部直连：相当于暂停代理\n"
        "  - MATCH,DIRECT\n"
    ),
}


def read_mode():
    try:
        with open(MODE_FILE) as fh:
            mode = fh.read().strip()
        return mode if mode in MODES else "rule"
    except OSError:
        return "rule"


def write_mode(mode):
    """原子写入，避免并发读到半个文件"""
    if mode not in MODES:
        return False
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = MODE_FILE + ".tmp"
        with open(tmp, "w") as fh:
            fh.write(mode + "\n")
        os.replace(tmp, MODE_FILE)
        return True
    except OSError:
        return False


def traffic_info(fresh=True):
    try:
        with open(TRAFFIC_FILE) as fh:
            d = json.load(fh)
        for key in ("upload", "download", "total", "expire", "updated_at"):
            if type(d[key]) is not int or d[key] < 0:
                return None
        d["stale"] = time.time() - d["updated_at"] > 120 or time.time() >= d["expire"]
        if fresh and d["stale"]:
            return None
        return d
    except (OSError, ValueError, KeyError, TypeError):
        return None


def traffic_headers():
    d = traffic_info()
    if d is None:
        return {}
    return {"Subscription-Userinfo": "; ".join(
        "%s=%d" % (key, d[key]) for key in ("upload", "download", "total", "expire")),
        "Profile-Update-Interval": "1"}

# 地理数据（GEOSITE/GEOIP 用）—— 客户端需免登录拉取，靠路径保密防蹭流量
GEO_DIR = "/var/www/geo"
GEO_PREFIX = "/geo/<GEO_TOKEN>"

SESSION_TTL = 7 * 24 * 3600        # 登录有效期 7 天
MAX_FAILS = 5                      # 15 分钟内允许的失败次数
FAIL_WINDOW = 15 * 60
LOCKOUT = 15 * 60                  # 超限后锁定时长

PORT = 80

# 登录限流状态（内存态，重启即清空 —— 可接受）
_fails = {}   # ip -> [次数, 首次失败时间戳]


# ── 认证 ────────────────────────────────────────────────────────────────
def _load_auth():
    with open(AUTH_FILE) as fh:
        d = json.load(fh)
    return (bytes.fromhex(d["salt"]), bytes.fromhex(d["hash"]),
            int(d["iters"]), bytes.fromhex(d["secret"]))


def check_password(password):
    """恒定时间比较，避免时序侧信道"""
    try:
        salt, want, iters, _ = _load_auth()
    except (OSError, ValueError, KeyError):
        return False
    got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return hmac.compare_digest(got, want)


def make_token(secret, ttl=SESSION_TTL):
    """8 字节过期时间戳 || 32 字节 HMAC —— 定长拼接，避免分隔符歧义"""
    exp = int(time.time()) + ttl
    body = exp.to_bytes(8, "big")
    sig = hmac.new(secret, body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(body + sig).decode().rstrip("=")


def verify_token(token):
    try:
        _, _, _, secret = _load_auth()
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        if len(raw) != 40:
            return False
        body, sig = raw[:8], raw[8:]
        if not hmac.compare_digest(hmac.new(secret, body, hashlib.sha256).digest(), sig):
            return False
        return int.from_bytes(body, "big") > time.time()
    except Exception:
        return False


def rate_limited(ip):
    now = time.time()
    n, first = _fails.get(ip, (0, now))
    if now - first > FAIL_WINDOW:
        _fails.pop(ip, None)
        return False
    return n >= MAX_FAILS and (now - first) < LOCKOUT


def note_fail(ip):
    now = time.time()
    n, first = _fails.get(ip, (0, now))
    if now - first > FAIL_WINDOW:
        n, first = 0, now
    _fails[ip] = (n + 1, first)
    # 顺手清理过期条目，防止内存无限增长
    if len(_fails) > 5000:
        for k in [k for k, (_, f) in _fails.items() if now - f > FAIL_WINDOW]:
            _fails.pop(k, None)


def clear_fails(ip):
    _fails.pop(ip, None)


# ── /proc 读取（不需要任何特权）─────────────────────────────────────────
def _uptime():
    try:
        with open("/proc/uptime") as fh:
            return float(fh.read().split()[0])
    except OSError:
        return 0.0


def _load():
    try:
        with open("/proc/loadavg") as fh:
            return fh.read().split()[:3]
    except OSError:
        return ["0.00", "0.00", "0.00"]


def _mem():
    info = {}
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                key, _, rest = line.partition(":")
                info[key] = int(rest.split()[0])
    except (OSError, ValueError):
        return 0.0, 0.0, 0.0, 0.0
    total = info.get("MemTotal", 0) / 1024
    avail = info.get("MemAvailable", info.get("MemFree", 0)) / 1024
    stotal = info.get("SwapTotal", 0) / 1024
    sfree = info.get("SwapFree", 0) / 1024
    return total, max(total - avail, 0.0), stotal, max(stotal - sfree, 0.0)


def _listening(port, transport="tcp"):
    want = "%04X" % port
    for path in ("/proc/net/" + transport, "/proc/net/" + transport + "6"):
        try:
            with open(path) as fh:
                next(fh, None)
                for line in fh:
                    parts = line.split()
                    if len(parts) > 3 and parts[3] in (("0A",) if transport == "tcp" else ("07", "01")):
                        if parts[1].rsplit(":", 1)[-1].upper() == want:
                            return True
        except OSError:
            continue
    return False


def node_info():
    """Read the same node definitions used by the subscription; auth required by route."""
    with open(os.path.join(SUB_DIR, os.path.basename(SUB_PATH))) as fh:
        config = yaml.safe_load(fh)
    if not isinstance(config, dict) or not isinstance(config.get("proxies"), list):
        raise ValueError("Invalid subscription")
    result = []
    for node in config.get("proxies", []):
        if not isinstance(node, dict):
            raise ValueError("Invalid node")
        kind = node.get("type")
        if kind not in ("vless", "hysteria2"):
            continue
        host = str(node["server"])
        authority = ("[" + host + "]") if ":" in host else host
        authority += ":" + str(int(node["port"]))
        name = str(node["name"])
        sni = node.get("servername", node.get("sni", ""))
        if kind == "vless":
            reality = node.get("reality-opts", {})
            query = dict(encryption="none", flow=node.get("flow", ""), security="reality",
                         sni=sni, fp=node.get("client-fingerprint", "chrome"),
                         pbk=reality.get("public-key", ""), sid=reality.get("short-id", ""),
                         type=node.get("network", "tcp"))
            credential = node["uuid"]
            details = [["UUID", credential], ["公钥", query["pbk"]],
                       ["Short ID", query["sid"]], ["Flow", query["flow"]], ["指纹", query["fp"]]]
        else:
            credential = node["password"]
            query = {"sni": sni}
            if node.get("skip-cert-verify"):
                query["insecure"] = "1"
            if node.get("obfs"):
                query.update(obfs=node["obfs"], **{"obfs-password": node.get("obfs-password", "")})
            details = [["认证", credential], ["证书验证", "已关闭" if node.get("skip-cert-verify") else "已开启"]]
        uri = (kind + "://" + urllib.parse.quote(str(credential), safe="") + "@" + authority
               + "?" + urllib.parse.urlencode(query) + "#" + urllib.parse.quote(name, safe=""))
        result.append(dict(name=name, type=kind, server=host, port=node["port"], sni=sni,
                           transport="TCP" if kind == "vless" else "UDP / QUIC",
                           service="xray" if kind == "vless" else "hysteria",
                           uri=uri, details=details))
    return result


@functools.lru_cache(maxsize=16)
def qr_svg(value):
    import qrcode
    import qrcode.image.svg
    image = qrcode.make(value, image_factory=qrcode.image.svg.SvgPathImage,
                        border=4, box_size=6)
    output = io.BytesIO()
    image.save(output)
    return output.getvalue()


# ── 登录页（与面板同一套深色视觉）───────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="dark">
<title>vps · 登录</title>
<style>
:root{--bg:#0b0d10;--card:#12151b;--line:rgba(255,255,255,.08);--line2:rgba(255,255,255,.14);
--fg:#e7ebf0;--dim:#8b95a5;--dim2:#5d6675;--acc:#3ddc97;--err:#f2555a;
--mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);min-height:100vh;display:grid;place-items:center;padding:22px;
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
background-image:radial-gradient(760px 420px at 20% -10%,rgba(61,220,151,.09),transparent 62%),
radial-gradient(640px 360px at 88% 4%,rgba(90,169,255,.07),transparent 62%);background-attachment:fixed}
.box{width:100%;max-width:372px;background:linear-gradient(180deg,var(--card),#0f1216);
border:1px solid var(--line);border-radius:17px;padding:32px 28px 26px;
box-shadow:0 22px 60px rgba(0,0,0,.55)}
.logo{width:44px;height:44px;border-radius:12px;margin:0 auto 17px;
background:linear-gradient(140deg,var(--acc),#1fa97a);display:grid;place-items:center;
color:#04140d;font-weight:800;font-size:21px;box-shadow:0 6px 22px rgba(61,220,151,.28)}
h1{font-size:16.5px;font-weight:650;text-align:center;letter-spacing:.2px}
p.s{font-size:12.5px;color:var(--dim2);text-align:center;margin:5px 0 24px}
label{display:block;font-size:12px;color:var(--dim2);margin-bottom:7px;letter-spacing:.03em}
input{width:100%;padding:12px 14px;border-radius:10px;background:#0a0c0f;
border:1px solid var(--line2);color:var(--fg);font:15px var(--mono);outline:none;transition:.15s}
input:focus{border-color:rgba(61,220,151,.55);box-shadow:0 0 0 3px rgba(61,220,151,.1)}
button{width:100%;margin-top:16px;padding:12px;border:none;border-radius:10px;cursor:pointer;
background:linear-gradient(140deg,var(--acc),#22b881);color:#04140d;font-size:14.5px;font-weight:700;
transition:.15s;font-family:inherit}
button:hover{filter:brightness(1.08)} button:active{transform:translateY(1px)}
.msg{margin-top:15px;padding:10px 13px;border-radius:9px;font-size:12.8px;line-height:1.6;
background:rgba(242,85,90,.1);border:1px solid rgba(242,85,90,.28);color:#f79a9d}
.foot{margin-top:22px;padding-top:16px;border-top:1px solid var(--line);font-size:11.5px;
color:var(--dim2);text-align:center}
</style></head><body>
<form class="box" method="POST" action="login" autocomplete="off">
  <div class="logo">A</div>
  <h1>vps 私人控制台</h1>
  <p class="s">请输入访问密码</p>
  <label for="pw">密码</label>
  <input id="pw" name="password" type="password" autofocus required
         autocomplete="current-password" spellcheck="false">
  <button type="submit">进入</button>
  __MSG__
  <div class="foot">此页面为私人用途 · 请勿分享地址</div>
</form>
</body></html>
"""


# ── HTTP ───────────────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "vps/1.1"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # ---------- 工具 ----------
    def _client_ip(self):
        """CF 是唯一能到达 80 的来源（nftables 已限流），因此该头可信"""
        ip = self.headers.get("CF-Connecting-IP")
        return ip.strip() if ip else self.client_address[0]

    def _cookie(self, name):
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
        return None

    def _authed(self):
        return (verify_token(self._cookie("vps_sess") or "") or
                verify_token(self._cookie("vps_monitor") or ""))

    def _send(self, code, body, ctype, head_only=False, extra=None, cache="no-store"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _redirect(self, location, cookie=None, status=302):
        """status 默认 302（临时）。

        注意：登录相关跳转绝不能用 301 —— 301 是永久重定向，浏览器会长期缓存，
        一旦缓存了「面板 → /login」，登录成功后也会被直接弹回登录页。
        只有「补尾斜杠」这种真正永久的规范化才用 301。
        """
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        for value in (cookie if isinstance(cookie, list) else [cookie] if cookie else []):
            self.send_header("Set-Cookie", value)
        self.end_headers()

    def _monitor_cookie(self):
        _, _, _, secret = _load_auth()
        return ("vps_monitor=%s; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=%d"
                % (make_token(secret), SESSION_TTL))

    def _proxy_gatus(self, head_only):
        if not self._authed():
            if self.path.startswith("/api/"):
                return self._send(401, '{"ok":false,"error":"unauthorized"}',
                                  "application/json", head_only)
            return self._redirect(DASH_PREFIX + "/login?next=monitor")
        if self.command not in ("GET", "HEAD"):
            return self._send(405, "Read only\n", "text/plain", head_only)
        connection = http.client.HTTPConnection(*GATUS_ADDRESS, timeout=8)
        try:
            # Fixed upstream only. Never forward panel cookies or authentication headers.
            connection.request(self.command, self.path, headers={
                "Accept": self.headers.get("Accept", "*/*"), "Accept-Encoding": "identity"})
            response = connection.getresponse()
            body = response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise ValueError("Upstream response too large")
            # HEAD must preserve the GET representation length.
            self.send_response(response.status)
            self.send_header("Content-Type", response.getheader("Content-Type", "application/octet-stream"))
            self.send_header("Content-Length", response.getheader("Content-Length", str(len(body))) if head_only else str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
        except (OSError, ValueError, http.client.HTTPException):
            return self._send(502, "Monitoring temporarily unavailable\n", "text/plain", head_only)
        finally:
            connection.close()

    def _not_found(self, head_only=False):
        self._send(404, "Not Found\n", "text/plain; charset=utf-8", head_only)

    def _login_page(self, head_only, msg=""):
        html = LOGIN_HTML.replace("__MSG__", msg)
        if GATUS_ENABLED and urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("next") == ["monitor"]:
            html = html.replace('action="login"', 'action="login?next=monitor"')
        return self._send(200, html, "text/html; charset=utf-8", head_only,
                          {"X-Frame-Options": "DENY"})

    # ---------- 路由 ----------
    def _route(self, head_only=False, post_body=None):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        norm = path.rstrip("/") or "/"
        destination = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("next")

        if GATUS_ENABLED and path == "/_internal/monitor-health":
            # Trust the socket peer, never X-Forwarded-For / CF-Connecting-IP.
            if self.client_address[0] not in ("127.0.0.1", "::1") or post_body is not None:
                return self._not_found(head_only)
            disk = os.statvfs("/")
            payload = {"ok": True, "traffic_fresh": traffic_info() is not None,
                       "xray_listening": _listening(443),
                       "hysteria_listening": _listening(443, "udp"),
                       "disk_available_bytes": disk.f_bavail * disk.f_frsize}
            return self._send(200, json.dumps(payload), "application/json", head_only)

        # ACME HTTP-01: only a single URL-safe token, never directory traversal.
        prefix = "/.well-known/acme-challenge/"
        if path.startswith(prefix):
            token = path[len(prefix):]
            if post_body is not None or not re.fullmatch(r"[A-Za-z0-9_-]{20,200}", token):
                return self._not_found(head_only)
            try:
                with open(os.path.join(ACME_DIR, token), "rb") as fh:
                    body = fh.read(4096)
            except OSError:
                return self._not_found(head_only)
            return self._send(200, body, "text/plain", head_only)

        # 0) 地理数据（客户端免登录拉取）
        #    .dat 是二进制，gzip 后只剩 21%~30%，所以优先发预压缩版本。
        #    Go 的 HTTP 客户端（mihomo 用的）默认带 Accept-Encoding: gzip 并透明解压。
        if path in (GEO_PREFIX + "/geoip.dat", GEO_PREFIX + "/geosite.dat"):
            name = os.path.basename(path)
            full = os.path.join(GEO_DIR, name)
            gz = full + ".gz"
            want_gz = "gzip" in (self.headers.get("Accept-Encoding") or "").lower()
            use_gz = want_gz and os.path.isfile(gz)
            target = gz if use_gz else full
            if not os.path.isfile(target):
                return self._not_found(head_only)
            try:
                with open(target, "rb") as fh:
                    blob = fh.read()
            except OSError:
                return self._send(500, "Internal Error\n", "text/plain; charset=utf-8", head_only)
            extra = {"Vary": "Accept-Encoding"}
            if use_gz:
                extra["Content-Encoding"] = "gzip"
            return self._send(200, blob, "application/octet-stream", head_only,
                              extra=extra, cache="public, max-age=86400")

        # 1) 订阅：精确匹配，不要求登录（客户端无法交互登录）
        if path == SUB_PATH:
            name = os.path.basename(path)
            full = os.path.join(SUB_DIR, name)
            if not name.endswith(SUB_SUFFIX) or not os.path.isfile(full):
                return self._not_found(head_only)
            try:
                with open(full, "rb") as fh:
                    raw = fh.read().decode("utf-8", "replace")
            except OSError:
                return self._send(500, "Internal Error\n", "text/plain; charset=utf-8", head_only)
            # rules: 是 YAML 的最后一个顶层键，按当前模式整体替换它之后的内容
            head, sep, _ = raw.partition("\nrules:")
            if sep:
                raw = head + "\nrules:\n" + RULES_TEXT[read_mode()]
            data = raw.encode("utf-8")
            return self._send(200, data, "text/yaml; charset=utf-8", head_only,
                              extra=traffic_headers())

        # 2) 登录
        if norm == DASH_PREFIX + "/login":
            if post_body is None:
                return self._login_page(head_only)
            ip = self._client_ip()
            if rate_limited(ip):
                return self._login_page(head_only, "尝试次数过多，请 15 分钟后再试。")
            pw = urllib.parse.parse_qs(post_body.decode("utf-8", "replace")).get("password", [""])[0]
            if check_password(pw):
                clear_fails(ip)
                _, _, _, secret = _load_auth()
                cookie = ("vps_sess=%s; Path=%s/; HttpOnly; Secure; SameSite=Lax; Max-Age=%d"
                          % (make_token(secret), DASH_PREFIX, SESSION_TTL))
                if GATUS_ENABLED and destination == ["monitor"]:
                    return self._redirect("/", [cookie, self._monitor_cookie()], status=303)
                return self._redirect(DASH_PREFIX + "/", cookie, status=303)
            note_fail(ip)
            left = max(MAX_FAILS - _fails.get(ip, (0, 0))[0], 0)
            hint = "密码错误。" + ("剩余 %d 次尝试机会。" % left if left <= 2 and left > 0 else "")
            return self._login_page(head_only, hint)

        # 3) 退出
        if norm == DASH_PREFIX + "/logout":
            return self._redirect(DASH_PREFIX + "/login",
                                  ["vps_sess=; Path=%s/; HttpOnly; Secure; SameSite=Lax; Max-Age=0"
                                   % DASH_PREFIX,
                                   "vps_monitor=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0"], status=303)

        if GATUS_ENABLED and norm == DASH_PREFIX + "/monitor":
            if not self._authed():
                return self._redirect(DASH_PREFIX + "/login?next=monitor")
            return self._redirect("/", self._monitor_cookie())

        # 4) 以下全部要求已登录
        if norm in (DASH_PREFIX, DASH_PREFIX + "/api/status", DASH_PREFIX + "/api/mode",
                    DASH_PREFIX + "/api/nodes", DASH_PREFIX + "/api/qr"):
            if not self._authed():
                if norm.startswith(DASH_PREFIX + "/api/"):
                    return self._send(401, '{"ok":false,"error":"unauthorized"}',
                                      "application/json; charset=utf-8", head_only)
                return self._redirect(DASH_PREFIX + "/login")

        if norm == DASH_PREFIX + "/api/nodes":
            try:
                payload = {"ok": True, "subscription": "https://panel.example.com" + SUB_PATH,
                           "nodes": node_info()}
                return self._send(200, json.dumps(payload, ensure_ascii=False),
                                  "application/json; charset=utf-8", head_only)
            except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError):
                return self._send(503, '{"ok":false,"error":"nodes_unavailable"}',
                                  "application/json", head_only)

        if norm == DASH_PREFIX + "/api/qr":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                if query.get("kind") == ["sub"]:
                    value = "https://panel.example.com" + SUB_PATH
                elif query.get("kind") == ["node"]:
                    name = query.get("name", [""])[0]
                    value = next(n["uri"] for n in node_info() if n["name"] == name)
                else:
                    return self._not_found(head_only)
                return self._send(200, qr_svg(value), "image/svg+xml", head_only,
                                  {"X-Content-Type-Options": "nosniff"})
            except StopIteration:
                return self._not_found(head_only)
            except (OSError, ValueError, TypeError, KeyError, ImportError, yaml.YAMLError):
                return self._send(503, "QR unavailable", "text/plain", head_only)

        # 5) 面板首页
        if norm == DASH_PREFIX:
            if path != DASH_PREFIX + "/":
                return self._redirect(DASH_PREFIX + "/", status=301)
            try:
                with open(DASH_FILE, "rb") as fh:
                    html = fh.read()
            except OSError:
                return self._send(500, "Dashboard missing\n", "text/plain; charset=utf-8", head_only)
            return self._send(200, html, "text/html; charset=utf-8", head_only,
                              {"X-Frame-Options": "DENY"})

        # 6) 状态 API
        if norm == DASH_PREFIX + "/api/status":
            mt, mu, st, su = _mem()
            disk = os.statvfs("/")
            payload = {
                "ok": True,
                "mode": read_mode(),
                "traffic": traffic_info(fresh=False),
                "ts": int(time.time()),
                "xray": {"listening": _listening(443)},
                "services": {
                    "xray": {"listening": _listening(443)},
                    "hysteria": {"listening": _listening(443, "udp")},
                },
                "server": {
                    "uptime": _uptime(),
                    "load": _load(),
                    "mem_total": round(mt, 1),
                    "mem_used": round(mu, 1),
                    "swap_total": round(st, 1),
                    "swap_used": round(su, 1),
                    "cpu_count": os.cpu_count() or 1,
                    "disk_total": disk.f_blocks * disk.f_frsize,
                    "disk_available": disk.f_bavail * disk.f_frsize,
                },
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            return self._send(200, body, "application/json; charset=utf-8", head_only)

        # 7) 切换分流模式（需登录）
        if norm == DASH_PREFIX + "/api/mode":
            if post_body is None:
                body = json.dumps({"ok": True, "mode": read_mode()},
                                  ensure_ascii=False).encode("utf-8")
                return self._send(200, body, "application/json; charset=utf-8", head_only)
            want = (urllib.parse.parse_qs(post_body.decode("utf-8", "replace"))
                    .get("mode", [""])[0] or "").strip()
            if not write_mode(want):
                return self._send(400, '{"ok":false,"error":"invalid mode"}',
                                  "application/json; charset=utf-8", head_only)
            body = json.dumps({"ok": True, "mode": want},
                              ensure_ascii=False).encode("utf-8")
            return self._send(200, body, "application/json; charset=utf-8", head_only)

        if GATUS_ENABLED and not (norm == DASH_PREFIX or norm.startswith(DASH_PREFIX + "/")):
            return self._proxy_gatus(head_only)
        return self._not_found(head_only)

    # ---------- 入口 ----------
    def do_GET(self):
        self._route(False)

    def do_HEAD(self):
        self._route(True)

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n > 8192:                      # 正常表单远小于此，防滥用
            return self._send(413, "Too Large\n", "text/plain; charset=utf-8")
        body = self.rfile.read(n) if n else b""
        self._route(False, post_body=body)

    def log_message(self, *args):
        pass  # 不记访问日志


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    Server(("0.0.0.0", PORT), Handler).serve_forever()
```

{{< /collapse >}}

### 6.6 systemd 与登录认证

`/etc/systemd/system/sub-server.service`：

```ini
[Unit]
Description=Private subscription and dashboard
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/sub-server.py 80
Restart=always
RestartSec=3
User=www-data
Group=www-data
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadOnlyPaths=/var/www/sub /var/www/dash /var/www/geo
ReadWritePaths=/var/lib/vps

[Install]
WantedBy=multi-user.target
```

先设置管理密码，再启动服务：

```bash
/usr/local/bin/set-panel-password
systemctl daemon-reload
systemctl enable --now sub-server
systemctl status sub-server --no-pager
```

密码使用 PBKDF2-HMAC-SHA256，加 16 字节随机盐，迭代 260000 次。`auth.json` 保存哈希及会话签名材料，权限为 `root:www-data 640`。

会话使用 HMAC-SHA256 签名，Cookie 设置 `HttpOnly`、`Secure` 和 `SameSite=Lax`。同一 IP 在 15 分钟内连续失败 5 次，会限制登录 15 分钟。识别来源时使用 `CF-Connecting-IP`，前提是公网回源入口确实只接受 Cloudflare 来源。

更改密码后执行 `systemctl restart sub-server`。工具会保留会话签名密钥，因此已登录设备不会立即退出；需要撤销所有现有会话时，应轮换签名密钥并重启服务。

登录测试通过真实公网 HTTPS 地址进行。只在本机 HTTP 地址测试带 `Secure` 的 Cookie，容易把客户端拒绝发送 Cookie 误判成服务端认证失败。

密码设置工具保存为 `set-panel-password.py`，按前面的安装命令部署成 `/usr/local/bin/set-panel-password`。它负责交互输入、密码哈希、会话签名密钥和文件权限设置。


{{< collapse summary="展开 set-panel-password.py 完整代码" >}}

```python
#!/usr/bin/env python3
"""设置 / 更换 vps 面板密码

用法：
    set-panel-password              # 交互式输入（推荐）
    set-panel-password --random     # 生成一个随机强密码并打印
    set-panel-password '新密码'      # 直接指定（会进 shell 历史，不推荐）

密码以 PBKDF2-HMAC-SHA256（260000 次迭代 + 16 字节随机盐）存储，
auth.json 里从不保存明文。

改密码时保留原有的会话签名密钥，因此已登录的浏览器不会被踢下线。
若要强制所有设备重新登录，需轮换 auth.json 的会话签名密钥并重启服务。
"""
import getpass
import hashlib
import json
import os
import secrets
import sys

AUTH = "/etc/vps-panel/auth.json"
ITERS = 260000
MIN_LEN = 8


def main():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return

    if args and args[0] == "--random":
        pw = secrets.token_urlsafe(15)
    elif args:
        pw = args[0]
    else:
        pw = getpass.getpass("新密码: ")
        if pw != getpass.getpass("再输一次: "):
            print("✗ 两次输入不一致", file=sys.stderr)
            sys.exit(1)

    if len(pw) < MIN_LEN:
        print("✗ 密码至少 %d 位" % MIN_LEN, file=sys.stderr)
        sys.exit(1)

    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, ITERS)

    # 保留原有 secret，避免已有会话全部失效
    secret = os.urandom(32)
    try:
        with open(AUTH) as fh:
            secret = bytes.fromhex(json.load(fh)["secret"])
    except Exception:
        pass

    os.makedirs(os.path.dirname(AUTH), exist_ok=True)
    with open(AUTH, "w") as fh:
        json.dump({"salt": salt.hex(), "hash": dk.hex(),
                   "iters": ITERS, "secret": secret.hex()}, fh)

    # 服务以 www-data 运行，需要能读到；只给组读权限
    try:
        import grp
        gid = grp.getgrnam("www-data").gr_gid
        os.chown(AUTH, 0, gid)
        os.chmod(AUTH, 0o640)
        os.chown(os.path.dirname(AUTH), 0, gid)
        os.chmod(os.path.dirname(AUTH), 0o750)
    except Exception as exc:
        print("⚠️  权限设置失败（需以 root 运行）: %s" % exc, file=sys.stderr)

    print("✅ 面板密码已更新")
    if args and args[0] == "--random":
        print()
        print("   新密码: %s" % pw)
        print()
        print("   请立即保存到密码管理器。此密码不会再次显示。")
    print("   重启服务生效: systemctl restart sub-server")


if __name__ == "__main__":
    main()
```

{{< /collapse >}}

### 6.7 二维码和状态采集

初版页面用 segno 生成静态 SVG，后续加入双节点后，改为由后端使用 qrcode 按订阅或节点链接生成 SVG，对应上面代码中的 `qr_svg()`。两种方式都在本机处理，不需要向第三方二维码服务发送订阅或节点链接。

服务器在线时间、负载和内存主要读取 `/proc/uptime`、`/proc/loadavg`、`/proc/meminfo`。TCP 监听状态读取 `/proc/net/tcp` 与 `/proc/net/tcp6`，不用给网页进程额外的管理权限。

面板轮询最初设为 10 秒，实际经过 Cloudflare 后，部分请求耗时较长，于是调整到 30 秒，并加入 12 秒超时和请求进行中标记。上一个请求没结束时跳过下一次，避免慢请求堆积。

### 6.8 地理数据镜像与自动刷新

客户端直接从 GitHub Release 下载地理数据库时比较慢，于是在 VPS 上准备了一份镜像：

```bash
BASE="https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest"
curl -fsSL -o /var/www/geo/geoip.dat "$BASE/geoip.dat"
curl -fsSL -o /var/www/geo/geosite.dat "$BASE/geosite.dat"
gzip -kf /var/www/geo/geoip.dat
gzip -kf /var/www/geo/geosite.dat
```

上面是首次下载。定期更新时先下载到临时位置，两个文件都成功且体积检查通过后才替换，避免下载中断破坏正在提供的文件。

客户端中指定镜像地址：

```yaml
geodata-mode: true
geox-url:
  geoip: "https://panel.example.com/geo/<GEO_TOKEN>/geoip.dat"
  geosite: "https://panel.example.com/geo/<GEO_TOKEN>/geosite.dat"
```

服务端根据 `Accept-Encoding` 判断是否返回预压缩的 `.gz`，同时发送 `Content-Encoding: gzip` 与 `Vary: Accept-Encoding`，原始文件仍然保留。

当时一次对比测试中，两个文件总下载时间从约 53 秒降到 7.7 秒，解压后的内容与原文件一致。这是当时的链路测试结果，实际速度仍取决于网络和缓存情况。

`geo-refresh.service` 调用 `/usr/local/bin/geo-refresh`。刷新程序下载两个文件、检查体积并重新生成压缩文件，再替换正式版本。对应定时器为：

```ini
[Unit]
Description=Weekly geodata refresh

[Timer]
OnCalendar=weekly
Persistent=true
RandomizedDelaySec=3600
Unit=geo-refresh.service

[Install]
WantedBy=timers.target
```

程序和 service 文件部署好后启用：

```bash
systemctl daemon-reload
systemctl enable --now geo-refresh.timer
systemctl list-timers geo-refresh.timer
```

分流模式保存在 `/var/lib/vps/mode`，写入时先写临时文件，再用 `os.replace` 替换。订阅模板将 `rules:` 放在最后一个顶层键，后端只替换规则部分，保留节点、策略组、DNS 和地理数据设置。

## 七、流量统计

### 7.1 采集与显示

为了在客户端里直接看到用量，我加了一个独立的流量采集服务，每 15 秒读取一次两个代理的统计数据，把上传和下载累计后保存下来。

客户端刷新订阅时，服务通过 `Subscription-Userinfo` 响应头返回用量、额度和下一次重置时间。

| 项目 | 当前设置 |
|------|------|
| 周期额度 | 十进制 1000GB，即 1,000,000,000,000 字节 |
| 重置时间 | 每月 24 日 00:00 |
| 时区 | Asia/Shanghai |
| 统计范围 | 两个代理的有效载荷上传与下载之和 |
| 采样间隔 | 15 秒 |

统计服务正常重启不会清零。读取不到新鲜数据时，订阅会省略用量头，避免把统计异常显示成零用量。

### 7.2 统计范围与误差

这里显示的是本机代理用量估算。协议开销、SSH、系统更新等流量没有全部计入，商家的计费方向、单位和结算时刻也没有逐项核实。正式启用统计前的历史用量没有补录，所以第一个周期显示的剩余额度可能偏高。

另外，如果代理在两次采样之间异常重启，也可能遗漏少量计数。目前只做显示，达到额度不会自动断网。

### 7.3 接入本机统计接口

Xray 配置中合并以下顶层字段，启用入站统计和本机 metrics：

```json
{
  "stats": {},
  "policy": {
    "system": {
      "statsInboundUplink": true,
      "statsInboundDownlink": true
    }
  },
  "metrics": {
    "tag": "metrics",
    "listen": "127.0.0.1:11111"
  }
}
```

这里的字段合并到已有配置，不能用这段直接覆盖包含入站和出站的完整文件。校验并重启 Xray 后，可在 VPS 本机检查：

```bash
curl --noproxy '*' -fsS http://127.0.0.1:11111/debug/vars
```

采集器从 `stats.inbound` 中读取指定 tag 的累计上下行数据。Hysteria 2 则读取本机 `/traffic` 接口，并携带统计认证信息。

`/etc/vps-panel/traffic.json` 对应的配置字段为：

```json
{
  "total_bytes": 1000000000000,
  "reset_day": 24,
  "timezone": "Asia/Shanghai",
  "sources": ["xray", "hysteria"],
  "xray_tags": ["vless-reality"],
  "hysteria_stats_secret": "<HYSTERIA_STATS_SECRET>"
}
```

`xray_tags` 必须与入站 tag 一致，统计密钥要与 Hysteria 2 的设置对应。配置文件中包含认证信息，应限制访问权限。

### 7.4 部署采集服务

在包含采集程序和单元文件的部署目录中执行：

```bash
install -o root -g root -m 0755 traffic-collector.py /usr/local/bin/vps-traffic.py
install -o root -g root -m 0644 vps-traffic.service /etc/systemd/system/vps-traffic.service
systemctl daemon-reload
systemctl enable --now vps-traffic
journalctl -u vps-traffic -n 30 --no-pager
```

采集服务每 15 秒采样，以代理服务的 systemd `InvocationID` 区分进程重启，使用差值累加流量。状态写入 `/var/lib/vps-traffic/state.json`，提供给面板和订阅的结果保存在 `usage.json`，文件采用原子替换。

订阅服务只使用两分钟内的新鲜结果，并返回类似下面的响应头：

```http
Subscription-Userinfo: upload=1024; download=2048; total=1000000000000; expire=1792857600
Profile-Update-Interval: 1
```

其中用量单位为字节，`expire` 为周期结束时间的 Unix 时间戳，实际值由程序计算。客户端是否自动更新以及具体间隔，仍取决于客户端实现。

完整采集器如下，保存为 `traffic-collector.py`。它只使用 Python 标准库；运行前需要准备好前面的 `traffic.json`、两个代理的统计接口，以及对应的 systemd 单元。


{{< collapse summary="展开 traffic-collector.py 完整代码" >}}

```python
#!/usr/bin/env python3
"""Persist proxy payload usage; billing is an estimate, not the VPS ledger.

Counter snapshots are non-destructive. At most one sampling interval can be
lost on an unexpected proxy restart. Files are replaced atomically.
"""
import calendar
import datetime as dt
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from zoneinfo import ZoneInfo

STATE_DIR = Path('/var/lib/vps-traffic')
CONFIG_FILE = Path('/etc/vps-panel/traffic.json')
STOP = threading.Event()


def cycle_bounds(now, day=24, timezone='Asia/Shanghai'):
    local = dt.datetime.fromtimestamp(now, ZoneInfo(timezone))
    def boundary(year, month):
        return dt.datetime(year, month, min(day, calendar.monthrange(year, month)[1]),
                           tzinfo=local.tzinfo)
    start = boundary(local.year, local.month)
    if local < start:
        year, month = (local.year - 1, 12) if local.month == 1 else (local.year, local.month - 1)
        start = boundary(year, month)
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    return int(start.timestamp()), int(boundary(year, month).timestamp())


def accumulate(state, name, identity, upload, download):
    if not identity or any(type(x) is not int or x < 0 for x in (upload, download)):
        raise ValueError('Invalid source counters')
    previous = state.setdefault('sources', {}).get(name, {})
    for key, value in (('upload', upload), ('download', download)):
        old = previous.get(key, 0) if previous.get('identity') == identity else 0
        state[key] = state.get(key, 0) + (value - old if value >= old else value)
    state['sources'][name] = dict(identity=identity, upload=upload, download=download)


def atomic_json(path, data):
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w') as fh:
        os.fchmod(fh.fileno(), 0o640)
        json.dump(data, fh, sort_keys=True)
        fh.write('\n')
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def invocation(service):
    return subprocess.check_output(['systemctl', 'show', service, '--property=InvocationID',
                                    '--value', '--no-pager'], timeout=4, text=True).strip()


def http_json(url, secret=None):
    req = urllib.request.Request(url, headers={'Authorization': secret} if secret else {})
    # Metrics are loopback only; never inherit an HTTP proxy.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=3) as r:
        return json.load(r)


def sample(config, source):
    service = 'xray.service' if source == 'xray' else 'hysteria-server.service'
    before = invocation(service)
    if not before:
        raise ValueError('No service invocation')
    if source == 'xray':
        data = http_json('http://127.0.0.1:11111/debug/vars')['stats']['inbound']
        counters = [data[tag] for tag in config['xray_tags']]
        upload = sum(int(x['uplink']) for x in counters)
        download = sum(int(x['downlink']) for x in counters)
    else:
        data = http_json('http://127.0.0.1:11112/traffic', config['hysteria_stats_secret'])
        upload = sum(int(x['rx']) for x in data.values())
        download = sum(int(x['tx']) for x in data.values())
    if before != invocation(service):
        raise ValueError('Service restarted during sample')
    return before, upload, download


def run_once(config, state):
    now = int(time.time())
    start, end = cycle_bounds(now, config['reset_day'], config['timezone'])
    if state.get('cycle_start') != start:
        if state.get('cycle_start'):
            atomic_json(STATE_DIR / ('cycle-%s.json' % state['cycle_start']), state)
        state.update(cycle_start=start, upload=0, download=0)
    errors = {}
    for source in config['sources']:
        try:
            accumulate(state, source, *sample(config, source))
        except Exception as exc:
            errors[source] = str(exc)
            print('%s: %s' % (source, exc), file=sys.stderr, flush=True)
    state.setdefault('started_at', now)
    state['updated_at'] = now
    state['errors'] = errors
    atomic_json(STATE_DIR / 'state.json', state)
    usage = dict(upload=state['upload'], download=state['download'],
                 total=int(config['total_bytes']), expire=end,
                 cycle_start=start, started_at=state['started_at'],
                 updated_at=now, errors=errors, scope='proxy-payload',
                 partial_cycle=state['started_at'] > start)
    # Keep last good header on source failure; the web service expires it after 2 min.
    if not errors:
        atomic_json(STATE_DIR / 'usage.json', usage)


def main():
    os.umask(0o027)
    STATE_DIR.mkdir(exist_ok=True, mode=0o750)
    path = STATE_DIR / 'state.json'
    # Malformed persistent state must fail loudly, never silently erase usage.
    state = json.loads(path.read_text()) if path.exists() else {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: STOP.set())
    while True:
        config = json.loads(CONFIG_FILE.read_text())
        run_once(config, state)
        if '--once' in sys.argv or STOP.wait(15):
            break
    if '--once' not in sys.argv:
        run_once(config, state)


if __name__ == '__main__':
    main()
```

{{< /collapse >}}

## 八、Gatus 服务监控

### 8.1 监控入口与检查项

服务多了以后，逐个检查比较麻烦，于是又加了 Gatus。

Gatus 只监听 `127.0.0.1:8088`，通过现有管理页面登录后转发访问，没有另外开放公网端口。

目前一共配置了 57 项检查：

- 9 项本机和业务检查，大约每 60 秒执行一次。
- 24 个网站，每个网站分两项检查，共 48 项，大约每 5 分钟执行一次。

本机检查主要看网页入口、证书、订阅、代理端口、统计接口、流量数据是否新鲜，以及 SSH 和磁盘剩余空间。

外部网站包括 ChatGPT、Claude、Gemini、DeepSeek、Kimi 等 AI 平台，以及 Google、YouTube、GitHub 等常用网站。

### 8.2 区分连接状态和网页响应

这里使用 HEAD 请求，把检查分成两项：

| 检查项 | 通过条件 |
|------|------|
| HTTPS 可达 | 完成 HTTPS 通信并收到 2xx～5xx 响应 |
| 网页响应 | 返回 2xx 或 3xx |

这样可以区分“能收到网站响应”和“请求返回成功或重定向”。比如 403 可能是访问限制，429 可能是限流，405 可能是不支持 HEAD，不能看到红灯就认定整个平台宕机。

这些探测都从 VPS 发出，也没有登录账号或调用模型 API。因此，绿灯只能说明对应检查通过，不能说明账号、地区权益或模型调用都可用，也不能代表客户端到 VPS 的实际体验。

Gatus 本身和代理在同一台机器上，VPS 离线时状态页也会一起离线。目前没有配置外部告警渠道。

### 8.3 历史记录与资源限制

历史记录使用 SQLite 保存，重启后保留。每项检查最多保留 1440 条详细结果和 100 个事件。

Gatus 设置了 192MiB 内存上限、25% CPU 配额，Go 内存目标为 128MiB。盘点时 systemd 统计的占用约为 25MiB，实际占用和配置上限是两回事。

### 8.4 配置 Gatus

Gatus 二进制安装到 `/usr/local/bin/gatus`，使用独立的 `gatus` 用户。配置文件为 `/etc/gatus/config.yaml`，监听和存储部分如下：

```yaml
web:
  address: 127.0.0.1
  port: 8088
storage:
  type: sqlite
  path: /var/lib/gatus/gatus.db
  caching: false
  maximum-number-of-results: 1440
  maximum-number-of-events: 100
concurrency: 2
endpoints:
  - name: Reality TCP 端口
    group: 代理服务
    url: tcp://127.0.0.1:443
    interval: 60s
    client:
      timeout: 5s
    conditions:
      - "[CONNECTED] == true"
```

私有订阅地址和 Hysteria 2 统计认证信息通过 `/etc/gatus/monitor.env` 提供，再由 systemd 的 `EnvironmentFile` 注入。配置中引用 `${vps_SUBSCRIPTION_URL}`、`${vps_HYSTERIA_STATS_SECRET}`，不把真实值写入公开示例。

服务单元中设置的主要参数是：

```ini
[Service]
User=gatus
Group=gatus
ExecStart=/usr/local/bin/gatus
Environment=GATUS_CONFIG_PATH=/etc/gatus/config.yaml
Environment=GOMEMLIMIT=128MiB
Environment=GOGC=50
EnvironmentFile=/etc/gatus/monitor.env
WorkingDirectory=/var/lib/gatus
StateDirectory=gatus
StateDirectoryMode=0750
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/gatus
MemoryHigh=128M
MemoryMax=192M
CPUQuota=25%
```

这部分合并在完整的 `gatus.service` 中，文件还包含网络依赖和开机启用设置。安装后执行：

```bash
systemctl daemon-reload
systemctl enable --now gatus
curl --noproxy '*' -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8088/
```

随后在订阅服务中启用 Gatus 转发，通过 `vps_GATUS_ENABLED=1` 控制。登录后由现有页面和会话机制访问监控，Gatus 的网页及 API 都需要经过认证检查，不能只保护首页。

## 九、安全配置与日常维护

最后把入口、配置和常用检查方式整理一下，方便以后维护。

### 9.1 端口与访问控制

| 端口 | 用途 |
|------|------|
| TCP 22 | SSH |
| TCP 443 | Reality |
| UDP 443 | Hysteria 2 |
| TCP 80 | 网页与订阅回源，限制 Cloudflare 来源 |

当前 nftables 的入站和转发默认丢弃，出站允许。这次检查的是运行中的规则，没有逐行比对持久化配置。

SSH 开启公钥认证，关闭密码和交互式认证，root 允许使用密钥登录。Fail2ban 启用了 `sshd` jail。

网页、Hysteria 2 和 Gatus 分别使用对应的服务用户。

目前 Xray 使用 `nobody`，流量采集以 root 运行，代理和网页服务也没有配置与监控相同的资源限制，这些地方后续可以继续调整。

### 9.2 配置文件与状态数据

| 路径 | 内容 |
|------|------|
| `/usr/local/etc/xray/config.json` | Xray 配置 |
| `/etc/hysteria/config.json` | Hysteria 2 配置 |
| `/usr/local/bin/sub-server.py` | 订阅与管理服务 |
| `/etc/vps-panel/` | 面板认证和流量配置 |
| `/var/lib/vps-traffic/` | 流量累计与周期状态 |
| `/etc/gatus/config.yaml` | Gatus 检查项 |
| `/var/lib/gatus/gatus.db` | 监控历史 |
| `/etc/systemd/system/` | 自定义服务和定时器 |

迁移时除了程序和配置，也要带走流量统计和监控历史等状态文件。证书和认证文件需要单独保管。

原始订阅 YAML、节点分享链接和随机订阅路径都包含连接信息，不适合直接作为文章附件。自写的面板、采集器和刷新程序按各自部署文件安装，迁移时需要把这些程序一并保存。

### 9.3 常用检查命令

```bash
# 查看失败的服务
systemctl --failed

# 查看主要业务服务
systemctl status xray hysteria-server sub-server gatus

# 查看 Gatus 最近的日志
journalctl -u gatus -n 50 --no-pager

# 查看磁盘和内存
df -h /
free -m
```

定时任务包括证书续期、地理数据库刷新、日志轮转和磁盘维护。服务器本地日志时区与流量结算时区不同，排查时要先确认时间口径。

## 十、搭建时遇到的问题

### 10.1 端口通了，Reality 仍然 EOF

最初使用 `www.microsoft.com` 作为目标站时，客户端一直报 `connect error: EOF`。普通 TLS 探测能取到证书，服务端日志里的认证信息也匹配，但握手没有完成。

排查时做了两件事：一是在服务器本机回环连接，绕开客户端到 VPS 的链路；二是保持其余设置不变，替换目标站。回环测试同样失败，改成 `www.apple.com` 后连接通过。

这次问题与当时版本、配置和目标站的 TLS 行为有关，不能据此认定某个站点在所有时间和版本下都不可用。排查时先做本地回环，再比较目标站，比反复改客户端参数更容易缩小范围。

### 10.2 防火墙规则的分隔符和重载方式

Cloudflare 网段最初被写成空格分隔，而 nftables 集合需要逗号，导致配置校验失败。随后执行 `restart`，服务先清空规则，再加载失败，一度没有防火墙规则。

之后固定为先执行 `nft -c -f`，通过后再 `reload`。同时去掉全局 `flush ruleset`，保留 Fail2ban 自己管理的表。

### 10.3 Nginx 安装时返回 404

当时 apt 的软件索引引用了仓库中已不存在的 Nginx 包版本，安装一直返回 404。最后没有继续为静态订阅服务增加 Nginx，改为 Python 提供文件和路由，后续面板也在这个服务上扩展。

软件源与系统升级仍需要单独维护，Python 服务只是解决了当时的网页入口需求。

### 10.4 登录成功后仍跳回登录页

最初未登录时返回 `301`，浏览器把登录跳转缓存了。即使登录成功，也可能继续跳回登录页。

登录相关跳转改成临时的 `302` 或 `303`，私有页面与接口使用 `Cache-Control: no-store`，再通过真实 HTTPS 入口验证。

### 10.5 地理数据每次都回源

当时 `.dat` 文件的响应显示 `cf-cache-status: DYNAMIC`，没有命中 Cloudflare 缓存。预压缩后下载时间已经明显缩短，就先保留这个方案。若后续增加缓存规则，只对地理数据路径配置，订阅和管理接口继续禁止缓存。

### 10.6 GitHub Release 下载拿到空文件

GitHub Release 的地址会重定向，下载时漏掉 `-L`，拿到的不是最终文件。后面统一使用 `curl -fsSL`，再检查下载结果和文件体积。

## 十一、待完善事项

上面包含初次搭建过程与后续配置。初次搭建记录中验证过 Reality 连接，但 10 月 19 日的盘点主要检查运行配置，没有重启服务或重新做双协议连接、吞吐测试。后续还有几项工作需要补：

- **连接测试**：重新验证两个协议的客户端连接、吞吐和日常使用情况。
- **回源配置**：目前 Cloudflare 到源站使用 HTTP，后续可以继续完善源站 TLS，并核对 Cloudflare 账户中的相关设置。
- **系统维护**：排查 `cloud-init` 和 `cloud-final` 的失败状态，整理 Debian 11 的软件源和升级安排。
- **权限与资源限制**：评估 Xray 专用用户、流量采集权限，以及代理和网页服务的资源限制。
- **备份恢复**：除了保存配置，也要做一次完整恢复演练，确认状态数据和认证材料能一起迁移。

商家流量账单的计费口径还没有逐项核实，面板显示的剩余额度仍按前面的本机统计方式理解。

## 总结

这次从代理开始，陆续加上订阅面板、流量统计和 Gatus，一台小 VPS 也承担了不少日常功能。

过程中比较有用的一点，是把每个服务负责的事情弄清楚：流量统计用来观察用量，Gatus 用来查看探测结果。知道它们能检查什么、还有哪些没有验证，后面排查问题就容易一些。

目前这套配置已经跑起来了，接下来主要是补齐验证和维护工作。先把已有服务用稳，再按需要慢慢增加功能。
