# 离线接口文档静态资源（Swagger UI / ReDoc）

本目录为 `/docs`（Swagger UI）与 `/redoc` 的离线静态资源，由后端挂载在
`/swagger-assets/` 下（见 `core/initializations/app_initialization.py`），
全程无外网请求（ReDoc 模板的 Google Fonts 外链已在后端以
`with_google_fonts=False` 关闭）。

## 旧浏览器兼容处理（Chrome/Edge 90 目标）

`swagger-ui-bundle.js` 与 `redoc.standalone.js` 使用了三个 Chrome 90 缺失的
API，缺失时运行期抛 TypeError 导致文档页不可用：

| API | 最低支持版本 |
|---|---|
| `Object.hasOwn` | Chrome 93 |
| `Array.prototype.findLast / findLastIndex` | Chrome 97 |
| `Array / String.prototype.at` | Chrome 92 |

已将 `legacy-compat-polyfills.js`（特性检测式垫片，现代浏览器上零副作用）
**前置合并**进上述两个 JS 文件头部（带 `__LEGACY_COMPAT_POLYFILLS_APPLIED__`
幂等标记）。`swagger-ui.css` 未做改动：其中仅 3 条 `:has()` 装饰性布局规则
（Chrome 105+）在更低版本上不生效，属轻微布局差异，不影响功能。

另已**剥离文件尾部的 `sourceMappingURL` 注释**（`swagger-ui.css` 与
`redoc.standalone.js` 各一条）：离线部署不携带 `.map` 文件，悬空注释会使
DevTools 请求 `swagger-ui.css.map` / `redoc.standalone.js.map` 报 404
控制台错误。剥离后浏览器不再请求，功能不受影响。

注意：StaticFiles 默认不带 Cache-Control，浏览器会按启发式缓存长期使用旧
副本——vendor 更新后客户端可能仍加载旧文件（表现为"改过还报旧错"）。后端
已在 `app_initialization.register_middlewares` 为 `/swagger-assets/` 响应补
`Cache-Control: no-cache`（每次再验证, ETag 未变即 304）；vendor 更新后若
仍见旧行为，先重启后端并让客户端强制刷新一次（Ctrl+Shift+R）。

## 升级 swagger-ui / redoc 时必做

1. 用上游新版文件**整体替换** `swagger-ui-bundle.js` / `redoc.standalone.js`；
2. 重新前置垫片（在本目录执行）：

```bash
node -e '
const fs = require("fs");
const poly = fs.readFileSync("legacy-compat-polyfills.js", "utf-8");
for (const f of ["swagger-ui-bundle.js", "redoc.standalone.js"]) {
  const orig = fs.readFileSync(f, "utf-8");
  if (orig.includes("__LEGACY_COMPAT_POLYFILLS_APPLIED__")) { console.log("skip", f); continue; }
  fs.writeFileSync(f, poly.replace("(function () {",
    "/* __LEGACY_COMPAT_POLYFILLS_APPLIED__ */\n(function () {") + "\n" + orig);
  console.log("patched", f);
}'
```

3. 复扫新版本是否引入了其他 Chrome 90+ API（`structuredClone`、
   `AbortSignal.timeout`、`Object.groupBy`、`toSorted` 等），如有则扩展
   `legacy-compat-polyfills.js` 后重复合并；
4. 重新剥离文件尾部的 `sourceMappingURL` 注释（上游包自带、但 `.map`
   不入库），避免 DevTools 404 报错：

```bash
node -e '
const fs = require("fs");
for (const [file, re] of [
  ["swagger-ui.css", /\n*\/\*#\s*sourceMappingURL=[^*]*\*\/\s*$/],
  ["swagger-ui-bundle.js", /\n*\/\/#\s*sourceMappingURL=.*\s*$/],
  ["redoc.standalone.js", /\n*\/\/#\s*sourceMappingURL=.*\s*$/],
]) {
  const s = fs.readFileSync(file, "utf-8");
  const next = s.replace(re, "\n");
  if (next !== s) { fs.writeFileSync(file, next); console.log("stripped", file); }
}'
```

5. 用 `npx esbuild <file> --target=chrome90 --outfile=/dev/null` 验证语法。
