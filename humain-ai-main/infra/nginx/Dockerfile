# Use the official Nginx alpine image
FROM nginx:alpine

# Remove default configuration
RUN rm /etc/nginx/conf.d/default.conf || true

# Copy our custom configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Expose port 80
EXPOSE 80
