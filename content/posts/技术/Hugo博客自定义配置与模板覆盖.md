---
title: "Hugo博客自定义配置与模板覆盖"
date: 2026-06-17
draft: false
tags:
  - Hugo
  - PaperMod
  - 博客
---

最近对博客做了一些整理和自定义配置，记录一下过程。

<!--more-->

## 清理无用文件

项目早期遗留了一些自定义模板文件，但 Hugo 有严格的模板查找规则，命名不对就不会被加载。

### 删除 `_default01/` 目录

`layouts/_default01/` 下有两个文件（`index.html` 和 `archives.html`），但 Hugo 只识别 `_default/` 目录，`_default01` 永远不会被用到，直接删除。

### 删除无用的 `extend_footer.html`

PaperMod 提供了 `extend_footer.html` 钩子用来扩展页脚，但它只会在 `config.yaml` 中配置了 `customFooterHTML` 参数时才有输出。我的配置中没有这个参数，所以这是个空钩子，删除后 PaperMod 会回退到内置实现，效果完全一样。

### 更新文件架构文档

同步更新了 `文件架构` 文档，使其反映项目的真实结构，包括新加的 GitHub Actions 工作流、归档页面、星标项目页面等。

## 自定义页脚

PaperMod 的页脚包含版权信息、自定义文字和 "Powered by Hugo & PaperMod"。

要修改页脚，把主题中的模板复制到项目目录覆盖即可：

```bash
cp themes/PaperMod/layouts/partials/footer.html layouts/partials/footer.html
```

之后编辑 `layouts/partials/footer.html` 就能完全控制页脚内容。

## 配置分享按钮

PaperMod 支持多种分享平台：X (Twitter)、Facebook、LinkedIn、Reddit、WhatsApp、Telegram 等。

默认开启所有按钮，可以通过 `ShareButtons` 参数精确控制，也可以直接关闭：

```yaml
params:
  ShowShareButtons: false  # 完全关闭分享按钮
```

或者只保留特定平台：

```yaml
params:
  ShareButtons:
    - x
    - facebook
```

## 修改导航按钮为外部链接

首页 **profileMode** 和顶部导航栏的按钮可以指向外部链接。我把"项目"按钮改为指向 GitHub 仓库列表：

```yaml
- name: 项目
  url: https://github.com/Yzeph?tab=repositories
```

## 去除外链图标

当导航或按钮的 URL 是外部链接时，PaperMod 会自动在文字后面加一个小箭头图标。我不需要这个图标，通过覆盖模板移除了它。

### 导航栏

复制 `themes/PaperMod/layouts/partials/header.html` 到 `layouts/partials/header.html`，删除以下代码段：

```html
{{- if (findRE "://" .URL) }}&nbsp;
<svg ...>...</svg>
{{- end }}
```

### 首页 profileMode 按钮

同样，复制 `index_profile.html` 并删除相同的 SVG 图标代码。

## 总结

Hugo 的模板覆盖机制很灵活——把主题中的文件复制到项目同名路径下即可覆盖。通过这些调整，博客变得更干净，也更符合个人需求。
