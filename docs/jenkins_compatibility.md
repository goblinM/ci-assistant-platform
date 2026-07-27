# Jenkins MVP 兼容矩阵

| 维度 | MVP 支持 | 说明 |
| --- | --- | --- |
| Jenkins 版本 | 2.4xx LTS 及更新 LTS | 通过 Remote Access API `/api/json` |
| Freestyle Job | 支持 | Build、Console、Changeset |
| Pipeline Job | 基础支持 | Build 与聚合 Console；Stage View/WFAPI 非必需 |
| Multibranch Pipeline | 支持嵌套 Job 路径 | `folder/job` 映射为 `/job/folder/job/job` |
| 认证 | 用户名 + API Token | 不支持密码登录 |
| 事件 | Generic Webhook/通知插件 JSON | 入口要求共享 Token |
| Changeset | Git 常用字段 | 多 SCM 插件的私有字段不保证映射 |
| Console | 支持并限制长度 | 默认保留末尾 200,000 字符 |

不在 MVP 保证范围：Blue Ocean 私有 API、Stage View 强依赖、Matrix 子任务逐格诊断、
自定义插件专有构建类型和需要浏览器 Cookie 的认证方式。

