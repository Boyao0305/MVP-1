# 使用官方 Nginx 镜像作为基础镜像
FROM nginx:latest

# 复制自定义的 Nginx 配置文件到容器中
COPY nginx.conf /etc/nginx/nginx.conf

# 暴露 Nginx 默认的 HTTP 端口
EXPOSE 80
# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]