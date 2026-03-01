# Stage 1: Dependencies (dev target — no build, just deps)
FROM node:20-alpine AS dev

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts || npm install

COPY . .

# Stage 2: Production build
FROM dev AS build

ARG VITE_APP_URL=http://localhost:3000
ENV VITE_APP_URL=$VITE_APP_URL

RUN npm run build

# Stage 3: Serve with nginx (production)
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
