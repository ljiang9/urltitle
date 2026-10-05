# urltitle

批量抓取网页标题的小工具：URL 进，标题出。

做研究时经常攒下一堆链接，先看一眼标题再决定读哪个；
`--md` 直接输出 Markdown 链接列表，粘进笔记就能用。

## 快速开始

```bash
python -m urltitle examples/urls.txt
python -m urltitle https://example.com https://www.python.org/
cat urls.txt | python -m urltitle --stdin
python -m urltitle urls.txt --md >> 笔记.md
python -m urltitle urls.txt --json
```

## 参数

| 参数 | 说明 |
|---|---|
| `sources` | URL 列表文件，或直接写 URL（可多个；`#` 开头行和空行忽略；不是文件的参数当 URL） |
| `--stdin` | 从标准输入读 URL |
| `--jobs N` | 并发数（默认 8） |
| `--timeout S` | 单个请求超时秒数（默认 10） |
| `--json` | JSON 输出 |
| `--md` | 输出 Markdown 链接列表 `[标题](url)` |
| `--version` | 版本号 |

## 标题从哪来

1. **优先 `og:title`**——通常是作者想对外展示的标题，比 `<title>` 干净（少了" - 站名"后缀）；
2. 没有 `og:title` 再退回 `<title>`；
3. 都没有 → 状态记"未找到标题"，不报错中断。

编码按 `Content-Type` 头 → `<meta charset>` → 默认 utf-8 的顺序猜。

## 设计取舍

- 只下载每个页面前 64KB：标题都在 `<head>` 里，没必要下整页。
- 自动解压 gzip / deflate（很多站点默认返回压缩内容）。
- 非 HTML（如 PDF、图片）直接跳过并标注类型，不硬解析。
- 拿不到标题的链接照常列出，状态里写原因（404、超时、非 HTML…）。

## 诚实局限

- **纯静态解析**：JS 渲染的页面（SPA）在静态 HTML 里没有标题，拿不到——这是架构局限，不是 bug。
- 有些站会按 User-Agent 屏蔽爬虫，可能返回 403/验证码页。
- 并发 + 超时是礼貌抓取，不是压力测试，请别拿它扫站。

## 许可证

MIT，Copyright (c) 2026 ljiang9。
