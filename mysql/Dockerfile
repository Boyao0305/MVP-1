# 使用官方 MySQL 镜像作为基础镜像
FROM mysql:8.0

# 将自定义的 my.cnf 配置文件复制到容器中的 /etc/mysql 目录
COPY my.cnf /etc/mysql/my.cnf

# 设置默认数据库和用户（可以在 `docker-compose.yml` 中配置）
# 这些值会被自动传递给容器的环境变量
ENV MYSQL_ROOT_PASSWORD=root_password
ENV MYSQL_DATABASE=mydatabase
ENV MYSQL_USER=user
ENV MYSQL_PASSWORD=password

# 在 MySQL 容器启动时运行 mysqld 进程
CMD ["mysqld"]
