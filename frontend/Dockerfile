FROM node:20-alpine

WORKDIR /myapp

# Install dependencies first so the layer is cached across code changes.
COPY package*.json ./
RUN npm install --force

COPY . .

EXPOSE 3000

CMD ["npm", "start"]
