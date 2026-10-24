# 运行与部署

推荐 Python 3.11+。演示仅用标准库；真实采集与测试依赖通过 requirements 文件安装。

## 模式

```bash
python refresh.py --mode demo
python refresh.py --mode live
python refresh.py --mode live --allow-fallback
python refresh.py --mode cached
```

live 需要 FREETRADE_REPORT_PERIOD、FREETRADE_ANNUAL_YEAR。外部访问失败默认报错。fallback 仅使用之前真实采集成功的快照，不能拿合成 demo 冒充市场缓存。

可通过 --output、--cache 指定目录。扫描 CSV 默认写到 var/outputs；FREETRADE_DATA_DIR 可改数据根目录。不要让多个任务同时写相同缓存与输出。

## 静态部署

任意静态托管服务都可以发布 dist/index.html。下面是可选 SSH 工作流：

```bash
export PYTHON="$PWD/.venv/bin/python"
export FREETRADE_DEPLOY=1
export FREETRADE_REMOTE=deploy@example.com
export FREETRADE_REMOTE_DIR=/srv/www/freetrade
export FREETRADE_PUBLIC_URL=https://example.com
export FREETRADE_SSH_KEY=/path/to/deploy-key
bash scripts/run_refresh_and_deploy.sh --mode live --allow-fallback
```

需要预先创建目录并确认服务器指纹已写入 known_hosts。脚本不跳过主机验证。每次运行在 var/render-TIMESTAMP 输出，将 index.html 上传为临时文件后远端原子替换；随后核对 HTTPS 200、必需链接和文件完全一致。

部署包装器使用它自己的逐次输出目录覆盖 --output，避免发布其他运行的旧文件。日志为私人运行产物，不应直接提交。不要把 .env 或 SSH Key 放进 Git。

## 定时任务示例

根据机器实际时区设置调度；必须明确 Asia/Shanghai。参考工作日 12:00 运行。这里不安装或修改任何用户已有自动任务。

```cron
# 确保 cron 环境与 PATH、Python、环境变量均已配置。
0 12 * * 1-5 /path/to/freetrade/scripts/local-scheduled-wrapper.sh
```

local-scheduled-wrapper.sh 由部署方创建，负责配置环境、进入项目并调用部署脚本。建议使用平台调度器的并发锁，避免重叠运行。

## 核验

```bash
python scripts/verify_site.py https://example.com --expected dist/index.html
```

使用 SSH 包装器时，把 expected 指向它输出的 var/render-TIMESTAMP/index.html。单独 200 只能证明连通，不能证明部署内容或数据日期。
