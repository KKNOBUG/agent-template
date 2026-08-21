/*!
 * 旧浏览器兼容垫片（Chrome/Edge 90 目标, 离线接口文档专用）。
 *
 * swagger-ui-bundle.js / redoc.standalone.js 使用了三个 Chrome 90 缺失的 API:
 *   - Object.hasOwn                 （Chrome 93+）
 *   - Array.prototype.findLast/…Index（Chrome 97+）
 *   - Array/String.prototype.at      （Chrome 92+）
 * 缺失时会在运行期抛 TypeError 导致文档页不可用, 故在此按特性检测补齐。
 *
 * 本文件已前置合并进 swagger-ui-bundle.js 与 redoc.standalone.js 两个离线包
 * （保证先于业务代码执行, 后端无需改动）。若日后升级 swagger-ui / redoc,
 * 需重新执行合并（见本目录 README.md）。
 */
(function () {
  'use strict';

  // ---- Object.hasOwn (Chrome 93+) ----
  if (!Object.hasOwn) {
    Object.defineProperty(Object, 'hasOwn', {
      value: function (obj, prop) {
        return Object.prototype.hasOwnProperty.call(obj, prop);
      },
      writable: true,
      configurable: true,
      enumerable: false,
    });
  }

  // ---- Array.prototype.at / String.prototype.at (Chrome 92+) ----
  function toRelativeIndex(len, idx) {
    var n = Math.trunc(idx) || 0;
    if (n < 0) n += len;
    return n < 0 || n >= len ? undefined : n;
  }
  if (!Array.prototype.at) {
    Object.defineProperty(Array.prototype, 'at', {
      value: function (idx) {
        var i = toRelativeIndex(this.length, idx);
        return i === undefined ? undefined : this[i];
      },
      writable: true,
      configurable: true,
      enumerable: false,
    });
  }
  if (!String.prototype.at) {
    Object.defineProperty(String.prototype, 'at', {
      value: function (idx) {
        var i = toRelativeIndex(this.length, idx);
        return i === undefined ? undefined : this.charAt(i);
      },
      writable: true,
      configurable: true,
      enumerable: false,
    });
  }

  // ---- Array.prototype.findLast / findLastIndex (Chrome 97+) ----
  if (!Array.prototype.findLast) {
    Object.defineProperty(Array.prototype, 'findLast', {
      value: function (cb, thisArg) {
        for (var i = this.length - 1; i >= 0; i--) {
          if (i in this && cb.call(thisArg, this[i], i, this)) return this[i];
        }
        return undefined;
      },
      writable: true,
      configurable: true,
      enumerable: false,
    });
  }
  if (!Array.prototype.findLastIndex) {
    Object.defineProperty(Array.prototype, 'findLastIndex', {
      value: function (cb, thisArg) {
        for (var i = this.length - 1; i >= 0; i--) {
          if (i in this && cb.call(thisArg, this[i], i, this)) return i;
        }
        return -1;
      },
      writable: true,
      configurable: true,
      enumerable: false,
    });
  }
})();
