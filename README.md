# 兑了么 DD RedeeMe · 游戏兑换码桌面挂件「大肥鱼」

> Windows 桌面常驻小挂件：监控《原神》《崩坏：星穹铁道》《鸣潮》《绝区零》的前瞻兑换码，新码弹窗提醒、一键复制、本地标记。
> 数据来自姊妹仓库 [Ecila01/game-codes-repo](https://github.com/Ecila01/game-codes-repo)（数据与展示分离架构，raw 直链读取，无需任何服务端）。
>
> **当前状态：v0.1.0 已发布**，变更详情见 [CHANGELOG](CHANGELOG.md)。

![挂件示意图占位](assets/fish.png)

## 功能清单

- 🫧 **挂件形态**：无边框半透明置顶小挂件（大肥鱼贴纸 + 自带气泡框显示最新码摘要），拖拽移动、四边贴边吸附、双击展开/收起完整列表（按游戏分组）
- 📋 **一键复制**：每个码旁复制按钮；右键条目可本地标记"已兑换 / 已过期"（只写本地，不回写仓库）
- 🔔 **提醒**：轮询拉取（默认 30 分钟）发现新码 → Windows 原生通知；每日固定时间（默认 12:00）或当日首次启动检查
- 🌐 **多数据源回退**：raw 直链 → jsDelivr 镜像按序尝试，全部失败自动沿用本地缓存并提示"数据暂时无法更新"
- 🧩 **配置化**：数据源 URL / 轮询间隔 / 每日时间 / 通知开关 / 吸附阈值等全部在 `config.json`，改完即生效，无需改代码
- 🚀 **托盘与自启**：系统托盘图标 + 右键菜单（刷新/设置/退出）、关窗进托盘、注册表开机自启动

## 快速开始

```bash
# 1) 环境：Python 3.10+
pip install -r requirements.txt

# 2) 配置数据源（可选，默认已指向 Ecila01/game-codes-repo）
#    编辑仓库根目录 config.json → data_sources[0].url 换成你的 codes.json raw 地址
#    大陆网络建议把 jsdelivr-mirror 的 enabled 保持 true 作为回退

# 3) 运行
cd src
python -m code_widget.main
```

## 配置说明（config.json）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `data_sources` | raw + jsDelivr | **有序**数据源列表，运行时按序回退；`type` 预留扩展（如 `rest_api`） |
| `fetch.interval_minutes` | 30 | 轮询间隔 |
| `fetch.daily_check_time` | "12:00" | 每日检查时刻 |
| `fetch.check_on_startup` | true | 当日首次启动即检查 |
| `notify.*` | — | 通知总开关 / 新码 / 错误提示 |
| `ui.*` | — | 透明度、缩放、置顶、吸附阈值 |
| `general.autostart` | true | 开机自启动（托盘菜单可同步切换） |
| `general.repo_url` | game-codes-repo 地址 | 托盘"打开数据仓库"的目标 |

> 首次运行若 `config.json` 缺失或损坏会自动用默认值重建（旧文件转 `.bak`）。

## 目录结构

```
dd-redeeme/
├── config.json            # 用户配置（可编辑，与代码默认值自动合并）
├── assets/fish.png        # 大肥鱼素材
├── src/code_widget/
│   ├── main.py            # 入口（AppUserModelID / 日志 / 装配）
│   ├── service.py         # CodeService：业务编排，UI 与逻辑唯一桥梁
│   ├── core/              # models / config / fetcher / parser / cache / notifier / scheduler
│   └── ui/                # widget / tray（挂件与托盘界面）
└── tests/                 # parser / cache-diff 单元测试
```

## 开发与测试

```bash
pip install -r requirements-dev.txt
pytest                    # 单元测试（parser / cache diff / 每日时刻计算）
```

## 打包

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean DDRedeeMe.spec   # 便携版单文件（入口 run.py）
# 一键构建 便携版 + 安装包：tools\build_release.bat
```

> 打包常见坑位：`AppUserModelID`（Toast 通知归属，安装版快捷方式需携带）、`sys._MEIPASS`（onefile 运行时资源路径）、windowed 模式下的日志重定向。

## License

[MIT](LICENSE)。本工具与米哈游/库洛游戏官方无关；游戏名称与兑换码仅作信息聚合展示。
