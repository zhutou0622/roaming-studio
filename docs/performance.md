# 大文件性能优化记录（CDVGBCCUSAK405097_20240320_135240_POST）

## English summary

The reference file is a 1.08 MB TAP3.12 batch with **168,605 ASN.1 nodes / 3,883 call records**.
It was unusable in the first implementation; the optimisations below brought it back to interactive
speed:

| Operation | Before | After |
| --- | --- | --- |
| Open file (decode + annotate) | 2.0 s | **1.2 s** |
| Header calculation (`/api/state`, `/api/nav`, save) | 4.3 s per call | **< 1 ms** |
| Open `callEventDetails` | 65.6 MB JSON, UI freeze | **0.34 s / 3,884 rows** |
| Node details for the root | 70.7 MB JSON | **0.7 KB** |
| Navigation tree (3,883 rows) | one-shot DOM | **400-row chunks + scroll loading** |
| Save untouched file | 1 byte larger | **byte-identical** |

Root causes and fixes: full-table regex scans in `header()`, deep subtree serialisation for node
details, unbounded tree depth for large lists, double schema annotation on open, re-encoding of
indefinite-length elements, and one-shot DOM construction. Detailed Chinese notes follow below.

---

样本：`E:\Deepseek工作目录\Romaing Stadio\CDVGBCCUSAK405097_20240320_135240_POST`
大小 1.08 MB，TAP3.12，**168,605 个 ASN.1 节点 / 3,883 条话单**（原报告“很卡”即此文件）。

## 优化前后（同一台机器，同一文件）

| 操作 | 优化前 | 优化后 |
| --- | --- | --- |
| 打开文件（解码+标注） | 2.03 s | **1.2 s** |
| `GET /api/state`、`/api/nav`、保存响应里的 header 计算 | **4.3 s/次**（被重复调用 3–5 次） | **< 1 ms**（索引 + 缓存） |
| 打开 `callEventDetails`（左树点击） | **65.6 MB JSON / 1.03 s 后端 + 浏览器渲染卡死** | 0.34 s / 3,884 行（按需展开） |
| 选中根节点 / 批次组（`/api/node/{id}`） | **70.7 MB JSON**（深拷贝整棵树） | 0.7 KB / < 1 ms |
| 打开单个 CED（45 节点） | 正常 | 8 ms |
| 左树 CED 列表（3,883 行） | 一次性 3,883 行 DOM | 首屏 400 行 + 滚动自动加载 |
| 选中节点 + 右侧词条 | — | 3–6 ms |
| 校验整文件 | — | 0.27 s（2 error / 92 warning） |
| 未修改文件另存 | 重编码后 1,082,084 B（比原文件多 1 B） | **1,082,083 B，字节级一致**，0.23 s |

界面启动：Electron 打开大文件到树渲染完成 **约 0.25 s**（不含后端 1.2 s 打开），总耗时 < 1 s 量级。

## 根因与修复

1. **`header()` 每次全表正则扫描**
   `first(r"\.?name$")` 对 168k 个节点做 8 次正则/路径匹配 → 单次 4.3 s，而 `/api/state`、`/api/nav`、`/api/save` 各调一次。
   → `_reindex()` 建 `name → node` 索引；`header()` 查索引并缓存基线（只动态更新 `dirty`）。**4.3 s → 0 ms**。

2. **节点检查器序列化整棵子树**
   `/api/node/{id}` 用 `to_dict(shallow=False)` 递归整棵树：点根节点 = 70.7 MB JSON。
   → 新增 `Tap3Document.node_detail()`：只返回自身字段 + 子节点 id 列表 + 原始字节片段；`deep=1` 才递归。**70.7 MB → 0.7 KB**。

3. **`/api/tree` 深度 7 无条件展开**
   左树点 `callEventDetails` 时把 3,883 条话单全展开 = 65.6 MB / 23k+ 行。
   → 前端按节点类型选择深度（事件 = 7，其它 = 1）；后端加 20,000 节点预算与 `truncated` 标记，超出部分按需懒加载。**1.03 s/65 MB → 0.34 s/3,884 行**。

4. **ASN.1 标注跑两遍 Schema**
   为挑选 TAP0309/TAP0311 模块，对整棵树标注两次再选优。
   → 先用原始 TLV 快速嗅探 `releaseVersionNumber`（APPLICATION 189），按版本选模块，只标注一次；仅在 mismatch 偏高时才回退另一模块。**2.03 s → 1.2 s**。

5. **重复路径计算**
   `_walk_ids()` 在每个节点上调用 `path()` 递归拼父链（168k × 深度）。
   → 遍历时把 `parent_path` 直接传给子节点，`path()` 变 O(1)；`markNav()` 从全表扫描改为 O(1) 行定位。

6. **另存后文件变大 1 字节**
   该文件的 `callEventDetails` 使用 BER 不定长（`0x80 … 00 00`），解码器重编码成定长后长度字段多 1 字节。
   → `ber.encode_element()` 保留 `indefinite` 标记，未修改文件另存**字节级一致**；同时保留定长文件的最小长度编码。

7. **左树 3,883 行一次性建 DOM**
   → 分块渲染（每块 400 行）+ `IntersectionObserver` 滚到底自动续载；同时保留“Show next 400 of 3883…”提示行。

## 复现测量

```bat
cd TapStudio\desktop
npx electron perf.js "E:\Deepseek工作目录\Romaing Stadio\CDVGBCCUSAK405097_20240320_135240_POST"
python -m unittest tests.test_performance -v      :: 大文件回归（不存在样本时自动跳过）
```

`perf.js` 输出示例：

```
open (server)      : 1385 ms  events=3883
UI boot to tree    : 246 ms
nav rows           : 408
open event list    : 339 ms  (rows=3884)
open DataInterChange: 8 ms   (rows=6)
open CED #1        : 8 ms    (rows=45)
select leaf + dict : 6 ms
validate (api)     : 314 ms  errors=2 warnings=92
```

## 仍可继续优化

- 解码 168k 节点仍是 Python 对象构建（约 0.9 s）：如需 < 0.5 s，可把 BER 解码换成 `__slots__`/数组式存储或 C 扩展。
- 打开事件列表时 3,884 行仍是同步渲染（0.34 s）：可改为虚拟滚动（只渲染视口 ±1 屏）。
- 校验 0.27 s 可接受；若要批量跑目录，建议走 CLI 并行而非 UI。

## 界面交互修复（右键菜单 / Find 窗口无法关闭）

**现象**：选中记录后右键菜单点不掉；接着打开 Find 窗口后按钮全部无响应。

**根因**：
1. `#ctxLayer` 是 `position:fixed; inset:0` 的全屏层，且没有 `pointer-events:none`。菜单打开后整块屏幕都被它盖住，点击任何位置都命中该层；关闭逻辑又写成“点击不在 `#ctxLayer` 内才关闭”，于是永远不会关闭。
2. `#ctxLayer` 与 `#modalLayer` 同为 `z-index:80`，且 `#ctxLayer` 在 DOM 中更靠后 → 右键菜单打开时，Find 对话框虽然显示出来，但全屏 ctx 层压在它上面，拦截了 Close/Find 的点击。

**修复**：
- `#ctxLayer { pointer-events:none }`，仅 `#ctxLayer .dropdown { pointer-events:auto }`；外部点击用 `closest('#ctxLayer .dropdown')` 判定。
- 模态层提到 `z-index:90`；`dialog()` 打开前先 `closeMenus(); closeCtx()`。
- 右键菜单项点击后同时 `closeCtx()`；新增 Esc、滚动、窗口 resize/blur 自动关闭；菜单弹出位置做视口边界收拢。

**回归**：`npx electron uitest-large.js` 新增 22 项断言，覆盖
右键菜单打开/外部点击关闭/Esc 关闭、菜单项打开 Find 且 ctx 已关闭、
Find 结果跳转、Find/校验/Hex/Preferences 的关闭按钮、编辑保存重开、
渲染进程零报错；全部通过。

截图：`docs/ui-ctx-menu.png`（菜单可正常弹出、背景不被遮挡）、`docs/ui-find-dialog.png`（关闭按钮可用）。
