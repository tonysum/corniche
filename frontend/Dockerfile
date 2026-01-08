# 前端服务 Dockerfile
FROM node:20-alpine AS builder

# 设置工作目录
WORKDIR /app

# 复制package文件
COPY package*.json ./

# 安装依赖（使用 npm install 而不是 npm ci，更兼容）
RUN npm install

# 复制源代码
COPY . .

# 构建应用
RUN npm run build

# 生产环境镜像
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV production

# 复制 package.json 用于安装生产依赖
COPY --from=builder /app/package*.json ./

# 只安装生产依赖
RUN npm ci --only=production

# 复制构建产物和必要文件
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules

# 暴露端口
EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

# 启动命令
CMD ["npm", "start"]

