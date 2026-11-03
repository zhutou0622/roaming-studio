# 贡献指南

[English](CONTRIBUTING.md) | **简体中文**

感谢参与 Roaming Studio（TAP3 Studio）。以下是最小开发闭环。

## 环境

- Python **3.9+**（推荐 3.11）
- Node.js **20+**（仅桌面壳与前端测试需要）
- Windows 10/11 用于打包桌面版；Web/CLI 跨平台

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt

cd desktop && npm install && cd ..
```

## 目录速览

| 路径 | 内容 |
| --- | --- |
| `tap3studio/` | 解析、编辑、校验、字典、REST 服务、CLI |
| `web/` | 经典 Win32 风格前端（无构建步骤） |
| `desktop/` | Electron 外壳、PyInstaller 后端打包、UI 回归脚本 |
| `tests/` | 单元与性能回归（大文件样本缺失时自动跳过） |
| `docs/` | 截图、性能与修复记录 |

## 开发运行

```bash
python run.py --open samples/demo.tap3
cd desktop && npm start            # 先关闭 ELECTRON_RUN_AS_NODE
```

## 提交前必跑

```bash
python -m unittest discover -s tests -v
node --check web/app.js

cd desktop
npx electron uitest.js
# 有真实大文件时：
npx electron uitest-large.js "<file>"
npx electron uitest-sections.js "<file>"
```

## 代码约定

- Python：标准库优先；新解析/校验逻辑必须有单元测试；不要在主流程里做全表扫描（参考 `docs/performance.md`）。
- 前端：无框架、无构建步骤；DOM 行数要有上限或分块；所有弹层关闭逻辑需覆盖点击外部 / `Esc` / 滚动。
- 修改 schema 或字典文本时，注明来源（TD.57 章节），不要引入非公开文档内容。
- 不提交任何客户 TAP 数据、`dist/`、`release/`、`node_modules/`。

## PR 检查清单

- [ ] 新增/修改行为有测试（Python 或 `desktop/uitest*.js`）
- [ ] `python -m unittest discover -s tests` 全绿
- [ ] 前端 `node --check` 通过，无控制台报错
- [ ] 更新了相关文档（README / docs / desktop/README）
- [ ] 不含凭证、客户数据或大文件

提交信息建议 `type(scope): summary`（如 `fix(ui): keep call view after edit`）。
