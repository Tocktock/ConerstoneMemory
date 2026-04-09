FROM node:24-alpine

WORKDIR /app

COPY package.json package-lock.json /app/
COPY apps/web/package.json /app/apps/web/package.json
RUN npm ci

COPY apps/web /app/apps/web

WORKDIR /app/apps/web
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]

