# 📱 Streamlit Cloud 部署指南

本文档说明如何将Bittensor成熟子网模拟器部署到Streamlit Cloud，创建在线体验网站。

## 🚀 快速部署步骤

### 1. 注册Streamlit Cloud账号
1. 访问 [share.streamlit.io](https://share.streamlit.io)
2. 点击 "Sign up" 使用GitHub账号登录
3. 授权Streamlit访问您的GitHub仓库

### 2. 部署应用
1. 登录后点击 "New app"
2. 填写部署信息：
   - **Repository**: `MrHardcandy/bittensor-mature-subnet-simulator`
   - **Branch**: `main`
   - **Main file path**: `app.py`
3. 点击 "Deploy" 开始部署

### 3. 等待部署完成
- 首次部署通常需要3-5分钟
- 部署完成后会自动打开应用
- 您将获得一个永久URL，格式如：`https://[app-name].streamlit.app`

## 📋 部署配置说明

### 已包含的配置文件

1. **requirements.txt** - Python依赖包
   ```
   streamlit>=1.28.0
   pandas>=1.5.0
   plotly>=5.15.0
   numpy>=1.24.0
   ```

2. **.streamlit/config.toml** - Streamlit配置
   - 自定义主题颜色
   - 服务器设置
   - 性能优化

3. **Procfile** - 应用启动配置（已包含）

## 🔧 高级配置

### 自定义域名
1. 在Streamlit Cloud设置中可以配置自定义域名
2. 需要在您的DNS提供商处添加CNAME记录

### 环境变量
如需添加环境变量：
1. 在Streamlit Cloud应用设置中
2. 点击 "Advanced settings"
3. 添加所需的环境变量

### 资源限制
免费版Streamlit Cloud限制：
- 1GB内存
- 1个CPU核心
- 公开仓库免费使用

## 🎯 部署后访问

部署成功后，您可以：
1. 分享应用URL给其他用户
2. 在README中添加在线演示链接
3. 监控应用使用情况和日志

## 📊 监控和维护

### 查看日志
1. 在Streamlit Cloud控制台
2. 点击您的应用
3. 选择 "Logs" 查看运行日志

### 更新应用
- 推送代码到GitHub后会自动更新
- 通常1-2分钟内生效

## 🆘 常见问题

### 部署失败
- 检查requirements.txt是否完整
- 确保app.py在仓库根目录
- 查看部署日志定位问题

### 应用运行缓慢
- 优化数据处理逻辑
- 使用st.cache_data装饰器
- 减少大型数据集操作

### 依赖包冲突
- 使用精确版本号
- 测试本地环境兼容性
- 查看Streamlit Cloud支持的包版本

## 🔗 相关链接

- [Streamlit Cloud文档](https://docs.streamlit.io/streamlit-cloud)
- [应用性能优化](https://docs.streamlit.io/library/advanced-features/performance)
- [部署最佳实践](https://docs.streamlit.io/streamlit-cloud/get-started/deploy-an-app)