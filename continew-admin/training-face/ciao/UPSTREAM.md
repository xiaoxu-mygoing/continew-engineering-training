# 组员人脸服务来源

- 仓库：https://github.com/CiaoAmore16/continew-admin-backend
- 固定提交：d07842571e9afc9c630049bcd1b07b4043fd9a5f
- 来源目录：face-poc/face_auth、face-poc/service
- 原始模块保留，用于 InsightFace 特征、随机姿态挑战和连续帧身份确认。
- 项目适配代码位于上级目录，不将原始 JSON 示例库用于正式租户数据。
- MiniFASNet 模型不在上游 AuthSession 登录流程中调用，不能仅凭模型文件宣称已启用被动防伪。
