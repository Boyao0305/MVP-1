##################  Stage 1 — build with Vite  ##################
FROM node:18-bullseye AS builder
WORKDIR /app

# 1  Copy manifest files
COPY package*.json ./

# 2  Install *all* deps (dev + prod) — ignore NODE_ENV
#    This works even if the base image sets NODE_ENV=production
RUN npm install                         # NOT npm ci

# ⬆  npm install always installs devDependencies,
#    regardless of the NODE_ENV inherited from the base image.
#    (If you want the speed of 'npm ci', add `--include=dev`
#     **and** put an explicit 'npm install -g npm@9' to guarantee npm 9+.)

# 3  Copy the rest of your source
COPY . .

# 4  Build — call Vite *via npx* so it works even if $PATH is odd
RUN chmod -R +x node_modules/.bin
RUN npx vite build                      # outputs to /app/dist

##################  Stage 2 — runtime  ##########################
FROM nginx:1.25-alpine
COPY --from=builder /app/dist /output/
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
