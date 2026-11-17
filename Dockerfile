# Deliberately INSECURE Dockerfile for the lab. Issues to find and fix:
#  - large, end-of-life, unpinned base image (many OS CVEs)
#  - runs as root
#  - no HEALTHCHECK
#  - secret passed as build arg / env
FROM python:3.15-slim

ARG API_KEY=changeme
ENV API_KEY=${API_KEY}

WORKDIR /app
COPY app/ /app/
RUN pip install -r requirements.txt

EXPOSE 5000
CMD ["python", "app.py"]
